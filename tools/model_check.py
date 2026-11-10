from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

from eval_cost import agent_name, read_jsonl
from session_extract import recent_sessions, sessions_folder

MODELS = ("haiku", "sonnet", "opus")
EFFORTS = ("low", "medium", "high", "xhigh", "max")
MAY_MOVE_DOWN = {"designer", "implementer", "tester"}
AGENT_TOOLS = ("Agent", "Task")
PINS_DIR = Path(__file__).resolve().parents[1] / "agents"
HOOKS_DIR = Path(__file__).resolve().parents[1] / "hooks"
META_TAIL = ".meta.json"
SYNTHETIC = "<synthetic>"
LINE_PREFIX = re.compile(r"^\s*\*\*Model:\*\*\s*", re.IGNORECASE)
LINE_SHAPE = re.compile(r"^([A-Za-z][A-Za-z-]*)\s*:\s*([A-Za-z]+)\s*,\s*([A-Za-z]+)\s*(?:;.*)?$")
FRONT_FIELD = re.compile(r"^(model|effort)\s*:\s*(\S+)\s*$")
CLOSING = "effort is the effort each reply recorded; the role of a general-purpose call is not known"
BOARD_KEY = "models"
DEFAULT_WORD = "default"
BOARD_VALUE = re.compile(r"^\s*([A-Za-z]+)\s*(?:,\s*([A-Za-z]+)\s*)?$")
BOARD_KEYS = ("orchestrator", "locator", "designer", "designer.diagnosis", "implementer",
              "implementer.escalate", "reviewer", "planner", "tester", "manage-project.readers")
STEP_HEADING = re.compile(r"^###\s+(\d{1,3})(?!\d)")
SESSION_PASS = "session model, set with /model"


class Expect(NamedTuple):
    model: str
    effort: str | None
    source: str


PHASES = {"designer.diagnosis": ("designer", Expect("opus", "high", "default")),
          "implementer.escalate": ("implementer", Expect("opus", "medium", "default"))}
GENERAL = {"orchestrator": Expect("sonnet", None, "default"),
           "manage-project.readers": Expect("sonnet", None, "default")}
DIAGNOSIS_FLOOR = Expect("opus", "high", "floor")


class Row(NamedTuple):
    key: str
    agent: str | None
    expect: Expect | None
    passes: str

    @property
    def source(self) -> str:
        return self.expect.source if self.expect else "no pin"


@dataclass
class Call:
    role: str
    tool_use_id: str
    passed_model: str | None = None
    passed_effort: str | None = None
    models: Counter = field(default_factory=Counter)
    efforts: set = field(default_factory=set)
    transcript: bool = False
    finished: bool = False


def family(model_id: str) -> str:
    lowered = str(model_id).lower()
    for run in re.findall(r"[a-z]+", lowered):
        if run in MODELS:
            return run
    return lowered


def load_pins(agents_dir: Path) -> dict[str, Expect]:
    pins: dict[str, Expect] = {}
    for path in sorted(Path(agents_dir).glob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0].strip() != "---":
            continue
        fields: dict[str, str] = {}
        for line in lines[1:]:
            if line.strip() == "---":
                break
            match = FRONT_FIELD.match(line)
            if match:
                fields[match.group(1)] = match.group(2).lower()
        if "model" in fields:
            pins[path.stem] = Expect(family(fields["model"]), fields.get("effort"), "pin")
    return pins


def parse_model_line(text: str) -> tuple[str, Expect]:
    body = LINE_PREFIX.sub("", text.strip(), count=1).strip()
    match = LINE_SHAPE.match(body)
    if not match:
        raise ValueError(f"not a Model line: {text!r}; expected '<role>: <Model>, <effort>; <why>'")
    role, model, effort = (part.lower() for part in match.groups())
    if model not in MODELS:
        raise ValueError(f"unknown model {model!r} in {text!r}; expected one of {', '.join(MODELS)}")
    if effort not in EFFORTS:
        raise ValueError(f"unknown effort {effort!r} in {text!r}; expected one of {', '.join(EFFORTS)}")
    return role, Expect(model, effort, "Model line")


def refusal(role: str, expect: Expect, pins: dict[str, Expect]) -> str | None:
    pin = pins.get(role)
    if pin is None:
        return f"unknown role {role!r}; the roles are {', '.join(sorted(pins))}"
    if role in MAY_MOVE_DOWN:
        return None
    if pin.model in MODELS and MODELS.index(expect.model) < MODELS.index(pin.model):
        return f"{role} may not move below its pin's model ({pin.model})"
    if pin.effort in EFFORTS and expect.effort in EFFORTS:
        if EFFORTS.index(expect.effort) < EFFORTS.index(pin.effort):
            return f"{role} may not move below its pin's effort ({pin.effort})"
    return None


def _below(expect: Expect, floor: Expect) -> bool:
    if MODELS.index(expect.model) < MODELS.index(floor.model):
        return True
    if floor.effort in EFFORTS and expect.effort in EFFORTS:
        return EFFORTS.index(expect.effort) < EFFORTS.index(floor.effort)
    return False


def shown(expect: Expect | None) -> str:
    if expect is None:
        return "-"
    return f"{expect.model}, {expect.effort}" if expect.effort else expect.model


def agent_of(key: str) -> str | None:
    if key in PHASES:
        return PHASES[key][0]
    if key in GENERAL:
        return None
    return key


def board_defaults(pins: dict[str, Expect]) -> dict[str, Expect | None]:
    found: dict[str, Expect | None] = {}
    for key in BOARD_KEYS:
        if key in GENERAL:
            found[key] = GENERAL[key]
        elif key in PHASES:
            found[key] = PHASES[key][1]
        else:
            found[key] = pins.get(key)
    return found


def parse_board_value(text: object, fallback: Expect | None) -> Expect:
    if not isinstance(text, str):
        raise ValueError(f"not a string ({type(text).__name__}); write \"<Model>, <effort>\", \"<Model>\" "
                         f"or \"{DEFAULT_WORD}\"")
    match = BOARD_VALUE.match(text)
    if not match:
        raise ValueError(f"{text!r} is not \"<Model>, <effort>\" or \"<Model>\"; name the model as "
                         f"{', '.join(MODELS)}, not by its full id")
    model = match.group(1).lower()
    effort = match.group(2).lower() if match.group(2) else None
    if model not in MODELS:
        raise ValueError(f"unknown model {model!r}; expected one of {', '.join(MODELS)}")
    if effort is not None and effort not in EFFORTS:
        raise ValueError(f"unknown effort {effort!r}; expected one of {', '.join(EFFORTS)}")
    if effort is None and fallback is not None:
        effort = fallback.effort
    return Expect(model, effort, "board")


def read_board(config: object) -> tuple[dict[str, object], list[str]]:
    if not isinstance(config, dict) or BOARD_KEY not in config:
        return {}, []
    board = config[BOARD_KEY]
    if not isinstance(board, dict):
        return {}, [f"{BOARD_KEY}: not an object ({type(board).__name__}); every role stays on its default"]
    entries: dict[str, object] = {}
    ignored: list[str] = []
    for key, value in board.items():
        if key not in BOARD_KEYS:
            ignored.append(f"{key}: unknown key; the keys are {', '.join(BOARD_KEYS)}")
        elif isinstance(value, str) and value.strip().lower() == DEFAULT_WORD:
            continue
        elif key == "orchestrator" and isinstance(value, str) and "," in value:
            ignored.append(f"{key}: {value!r}: the orchestrator takes a model only, and runs on the "
                           f"session model set with /model")
        else:
            entries[key] = value
    return entries, ignored


def _floor_of(key: str, expect: Expect, pins: dict[str, Expect]) -> Expect | None:
    if key == "designer.diagnosis":
        return DIAGNOSIS_FLOOR if _below(expect, DIAGNOSIS_FLOOR) else None
    if key in pins and key not in MAY_MOVE_DOWN and refusal(key, expect, pins):
        return pins[key]
    return None


def _model_line_keys(role: str, keys: tuple[str, ...]) -> list[str]:
    return [key for key in keys if agent_of(key) == role]


def board_rows(config: object, pins: dict[str, Expect], lines=(), parts=()) -> tuple[list[Row], list[tuple[str, str]]]:
    defaults = board_defaults(pins)
    current = dict(defaults)
    extra = tuple(role for role in sorted(pins) if role not in BOARD_KEYS)
    keys = BOARD_KEYS + extra
    for role in extra:
        current[role] = pins[role]
    entries, ignored = read_board(config)
    notes: list[tuple[str, str]] = [("ignored", text) for text in ignored]
    for key, value in entries.items():
        try:
            expect = parse_board_value(value, defaults[key])
        except ValueError as error:
            notes.append(("ignored", f"{key}: {error}"))
            continue
        floor = _floor_of(key, expect, pins)
        if floor is not None:
            current[key] = Expect(floor.model, floor.effort, f"floor (board said {shown(expect)})")
        else:
            current[key] = expect
    moved: set[str] = set()
    for text in lines:
        try:
            role, expect = parse_model_line(text)
        except ValueError as error:
            notes.append(("not followed", str(error)))
            continue
        reason = refusal(role, expect, pins)
        if not reason and role in moved:
            reason = f"a second --model line for {role}; give one line per role"
        if reason:
            notes.append(("not followed", f"{text!r}: {reason}"))
            continue
        moved.add(role)
        for key in _model_line_keys(role, keys):
            if key == "designer.diagnosis" and _below(expect, DIAGNOSIS_FLOOR):
                notes.append(("not followed", f"{text!r} for designer.diagnosis: fix-bug's diagnosis may not "
                                              f"move below opus, high"))
                continue
            current[key] = expect
    rows = [Row(key, agent_of(key), current[key], "") for key in keys]
    accepted: list[Expect] = []
    for text in parts:
        try:
            role, expect = parse_model_line(text)
        except ValueError as error:
            notes.append(("not followed", str(error)))
            continue
        if role != "implementer":
            reason = "a part is an implementer line"
        elif "implementer" in moved:
            reason = "--part takes the place of an implementer --model line; give one or the other"
        else:
            reason = refusal(role, expect, pins)
        if reason:
            notes.append(("not followed", f"{text!r}: {reason}"))
            continue
        accepted.append(expect)
    for number, part in enumerate(accepted, 1):
        label = f"part {number} of {len(accepted)}"
        rows.append(Row(f"implementer {label}", "implementer", Expect(part.model, part.effort, label), ""))
    return [row._replace(passes=pass_text(row, pins)) for row in rows], notes


def _pass_value(expect: Expect) -> str:
    if expect.effort:
        return f'model: "{expect.model}", effort: "{expect.effort}"'
    return f'model: "{expect.model}"'


def pass_text(row: Row, pins: dict[str, Expect]) -> str:
    if row.key == "orchestrator":
        return SESSION_PASS
    if row.expect is None:
        return "nothing"
    pin = pins.get(row.agent) if row.agent else None
    if pin is not None and (row.expect.model, row.expect.effort) == (pin.model, pin.effort):
        return "nothing"
    return _pass_value(row.expect)


def step_model_lines(plan_md: str) -> dict[int, list[str]]:
    found: dict[int, list[str]] = {}
    number = None
    for line in plan_md.splitlines():
        heading = STEP_HEADING.match(line)
        if heading:
            number = int(heading.group(1))
            continue
        if line.startswith("## ") or line.startswith("### "):
            number = None
            continue
        if number is not None and LINE_PREFIX.match(line):
            found.setdefault(number, []).append(LINE_PREFIX.sub("", line.strip(), count=1).strip())
    return found


def _session_start():
    loaded = sys.modules.get("devflow_session_start")
    if loaded is not None:
        return loaded
    spec = importlib.util.spec_from_file_location("devflow_session_start", HOOKS_DIR / "session_start.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["devflow_session_start"] = module
    spec.loader.exec_module(module)
    return module


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, ValueError):
        return None


def open_step_lines(project: Path, config: object) -> list[tuple[int, str, list[str]]]:
    hooks = _session_start()
    layout = hooks.Layout(config if isinstance(config, dict) else {})
    status_md = _read_text(Path(project) / layout.status_file)
    plan = hooks.current_plan(status_md, layout) if status_md else None
    plan_md = _read_text(Path(project) / plan) if plan else None
    if not plan_md:
        return []
    states = hooks.step_states(plan_md)
    found = []
    for number, lines in step_model_lines(plan_md).items():
        state = states.get(number, ("", ""))[1]
        if number in states and not hooks.is_open(state):
            continue
        found.append((number, "claimed" if hooks.is_claimed(state) else "open", lines))
    return found


def session_model(project: Path, projects_root: Path) -> str | None:
    try:
        folder = sessions_folder(str(Path(project).resolve()), Path(projects_root))
        newest = recent_sessions(folder, 1) if folder is not None else []
        model = None
        for entry in read_jsonl(newest[0]) if newest else ():
            message = entry.get("message")
            if entry.get("type") != "assistant" or entry.get("isSidechain") or not isinstance(message, dict):
                continue
            if isinstance(message.get("model"), str) and message["model"] != SYNTHETIC:
                model = message["model"]
    except OSError:
        return None
    return family(model) if model else None


def _orchestrator_pass(row: Row, session: str | None) -> str:
    if session is None:
        return f"{SESSION_PASS}; this session's model was not read"
    if row.expect is not None and session != row.expect.model:
        return f"{SESSION_PASS}; this session ran on {session}, not {row.expect.model}"
    return f"{SESSION_PASS}; this session ran on {session}"


def format_board(label: str, rows: list[Row], notes: list[tuple[str, str]],
                 open_steps: list[tuple[int, str, list[str]]], session: str | None) -> list[str]:
    lines = [f"model board: {label}", "key | model | effort | from | pass"]
    for row in rows:
        model = row.expect.model if row.expect else "-"
        effort = (row.expect.effort if row.expect else None) or "-"
        passes = _orchestrator_pass(row, session) if row.key == "orchestrator" else row.passes
        lines.append(f"{row.key} | {model} | {effort} | {row.source} | {passes}")
    if open_steps:
        lines.append("open steps with a Model line:")
        for number, state, step_lines in open_steps:
            lines += [f"  step {number} ({state}): {text}" for text in step_lines]
    else:
        lines.append("open steps with a Model line: none")
    lines += [f"not followed: {text}" for kind, text in notes if kind == "not followed"]
    ignored = [text for kind, text in notes if kind == "ignored"]
    lines += [f"ignored: {text}" for text in ignored] or ["ignored: nothing"]
    return lines


def board_summary(config: object, pins: dict[str, Expect], step: int | None, step_lines: list[str],
                  view_path: str) -> str:
    tail = f"Full view: python {view_path} --board"
    rows, notes = board_rows(config, pins)
    defaults = board_defaults(pins)
    has_board = isinstance(config, dict) and BOARD_KEY in config
    said: list[str] = []
    moves = [f"{row.key} to {shown(row.expect)}" for row in rows
             if row.source == "board" and shown(row.expect) != shown(defaults.get(row.key))]
    if moves:
        said.append("board moves " + " and ".join(moves))
    said += [f"{row.key} kept on {shown(row.expect)} (floor)" for row in rows if row.source.startswith("floor")]
    if step is not None and step_lines:
        roles: list[str] = []
        refused: list[str] = []
        for text in step_lines:
            try:
                role, expect = parse_model_line(text)
            except ValueError:
                role, reason = "an unreadable role", "unreadable"
            else:
                reason = refusal(role, expect, pins) or ("second line" if role in roles else None)
            found = refused if reason else roles
            if role not in found:
                found.append(role)
        if roles:
            said.append(f"step {step}'s Model line moves {' and '.join(roles)}")
        if refused:
            said.append(f"step {step}'s Model line for {' and '.join(refused)} is not followed")
    ignored = sum(1 for kind, _text in notes if kind == "ignored")
    if ignored:
        said.append(f"{ignored} {'entry' if ignored == 1 else 'entries'} ignored")
    if not has_board:
        head = "the plugin's pins (no board in .claude/devflow.json)"
        return f"Models: {'; '.join([head] + said)}. {tail}"
    if not said:
        return f"Models: board, every role on its default. {tail}"
    return f"Models: {'; '.join(said)}. {tail}"


def expectations_from(rows: list[Row], escalated: bool = False, diagnosis: bool = False) -> dict[str, Expect]:
    by_key = {row.key: row.expect for row in rows}
    chosen = {row.key: row.key for row in rows if row.agent == row.key}
    if escalated:
        chosen["implementer"] = "implementer.escalate"
    if diagnosis:
        chosen["designer"] = "designer.diagnosis"
    return {role: by_key[key] for role, key in chosen.items() if by_key.get(key) is not None}


def _meta(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _role(kind: object) -> str:
    if not isinstance(kind, str) or not kind:
        return "general-purpose"
    return kind.split(":")[-1] or "general-purpose"


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _read_replies(path: Path, call: Call) -> None:
    seen: set[str] = set()
    for entry in read_jsonl(path):
        if entry.get("type") != "assistant":
            continue
        message = entry.get("message") or {}
        if not isinstance(message, dict):
            continue
        effort = entry.get("effort")
        if isinstance(effort, str) and effort:
            call.efforts.add(effort.lower())
        model = message.get("model")
        key = message.get("id") or entry.get("uuid")
        if not isinstance(model, str) or model == SYNTHETIC or key in seen:
            continue
        seen.add(key)
        call.models[model] += 1


def agent_calls(session_jsonl: Path) -> list[Call]:
    session_jsonl = Path(session_jsonl)
    calls: list[Call] = []
    by_id: dict[str, Call] = {}
    for entry in read_jsonl(session_jsonl):
        if entry.get("type") != "assistant":
            continue
        message = entry.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            if block.get("name") not in AGENT_TOOLS or block.get("id") in by_id:
                continue
            params = block.get("input")
            if not isinstance(params, dict):
                continue
            call = Call(
                role=_role(params.get("subagent_type")),
                tool_use_id=str(block.get("id") or ""),
                passed_model=_text(params.get("model")),
                passed_effort=_text(params.get("effort")),
            )
            calls.append(call)
            by_id[call.tool_use_id] = call
    folder = session_jsonl.with_suffix("") / "subagents"
    for path in sorted(folder.glob("agent-*.jsonl")):
        meta_path = path.with_name(path.stem + META_TAIL)
        meta = _meta(meta_path)
        call = by_id.get(str(meta.get("toolUseId") or ""))
        if call is None:
            call = Call(role=agent_name(meta_path), tool_use_id=str(meta.get("toolUseId") or path.stem))
            calls.append(call)
        call.passed_model = call.passed_model or _text(meta.get("model"))
        call.passed_effort = call.passed_effort or _text(meta.get("effort"))
        call.transcript = True
        call.finished = meta.get("finished") is True
        _read_replies(path, call)
    return calls


def judge(call: Call, expect: Expect | None) -> tuple[str, list[str]]:
    notes: list[str] = []
    if not call.transcript:
        notes.append("no transcript")
    else:
        if not call.models:
            notes.append("no replies")
        if not call.efforts:
            notes.append("effort not recorded")
        if not call.finished:
            notes.append("not finished")
    if expect is None:
        return "no pin", notes
    if not call.models:
        return "not read", notes
    wrong_model = any(family(model) != expect.model for model in call.models)
    wrong_effort = bool(expect.effort) and any(effort != expect.effort for effort in call.efforts)
    return ("MISMATCH" if wrong_model or wrong_effort else "ok"), notes


def _passed(call: Call) -> str:
    parts = []
    if call.passed_model:
        parts.append(f"model {call.passed_model}")
    if call.passed_effort:
        parts.append(f"effort {call.passed_effort}")
    return ", ".join(parts) or "nothing"


def _expected(expect: Expect | None) -> str:
    if expect is None:
        return "no pin"
    return f"{shown(expect)} ({expect.source})"


def _expect_for(call: Call, expectations: dict[str, Expect], parts: tuple[Expect, ...], index: int) -> Expect | None:
    expect = expectations.get(call.role)
    if not parts or call.role != "implementer":
        return expect
    if index < len(parts):
        return parts[index]
    if expect is None:
        return None
    return Expect(expect.model, expect.effort, f"{expect.source}, beyond the {len(parts)} parts")


def format_session(path: Path, calls: list[Call], expectations: dict[str, Expect],
                   parts: tuple[Expect, ...] = ()) -> tuple[list[str], int]:
    parts = tuple(parts)
    lines = [f"session {Path(path).stem} ({path})"]
    lines.append("role | passed | ran on | effort | expected | verdict")
    mismatches = 0
    not_read: list[str] = []
    implementer_calls = 0
    for number, call in enumerate(calls, 1):
        expect = _expect_for(call, expectations, parts, implementer_calls)
        if call.role == "implementer":
            implementer_calls += 1
        verdict, notes = judge(call, expect)
        if verdict == "MISMATCH":
            mismatches += 1
        ran = ", ".join(f"{model} ({count})" for model, count in sorted(call.models.items())) or "-"
        effort = ", ".join(sorted(call.efforts)) or "not recorded"
        lines.append(f"{call.role} | {_passed(call)} | {ran} | {effort} | {_expected(expect)} | {verdict}")
        if notes:
            not_read.append(f"{call.role} (call {number}): {', '.join(notes)}")
        if call.role == "general-purpose":
            not_read.append(f"{call.role} (call {number}): role not known")
    for part in parts[implementer_calls:]:
        not_read.append(f"{part.source} ({part.model}, {part.effort}): no implementer call")
    if not calls:
        not_read.append("no agent calls in this session")
    lines.append(f"mismatches: {mismatches}")
    lines.append("not read: " + ("; ".join(not_read) if not_read else "nothing"))
    lines.append(CLOSING)
    return lines, mismatches


def sessions_of(source: str, projects_root: Path, count: int, exclude: str) -> list[Path] | str:
    path = Path(source)
    if path.is_file() and path.suffix.lower() == ".jsonl":
        return [path]
    workspace = path / "config" / "projects"
    if workspace.is_dir():
        found = sorted(workspace.glob("*/*.jsonl"))
        return found or f"no session files under {workspace}"
    folder = sessions_folder(str(path.resolve()), Path(projects_root))
    if folder is None:
        return f"no sessions folder for {source} under {projects_root}"
    found = recent_sessions(folder, count, exclude)
    return found or f"no sessions in {folder}"


def default_projects_root() -> Path:
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    if config:
        return Path(config) / "projects"
    return Path.home() / ".claude" / "projects"


def config_path(source: str, given: str | None) -> Path:
    if given:
        return Path(given)
    candidate = Path(source) / ".claude" / "devflow.json"
    if Path(source).is_dir() and candidate.is_file():
        return candidate
    return Path(".claude") / "devflow.json"


def load_board_config(path: Path) -> tuple[object, str]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return {}, f"{path} (no file; the plugin's pins)"
    except ValueError as error:
        return {}, f"{path} (not UTF-8: {error}; the plugin's pins)"
    try:
        config = json.loads(text)
    except ValueError as error:
        return {}, f"{path} (not JSON: {error}; the plugin's pins)"
    if not isinstance(config, dict) or BOARD_KEY not in config:
        return config, f'{path} (no "{BOARD_KEY}"; the plugin\'s pins)'
    return config, f'{path} "{BOARD_KEY}"'


def _validated(args: argparse.Namespace, pins: dict[str, Expect]) -> str | None:
    moved: set[str] = set()
    for text in args.model:
        try:
            role, expect = parse_model_line(text)
        except ValueError as error:
            return str(error)
        reason = refusal(role, expect, pins)
        if not reason and role in moved:
            reason = f"a second --model line for {role}; give one line per role"
        if reason:
            return f"refused {text!r}: {reason}"
        moved.add(role)
    for text in args.part:
        try:
            role, expect = parse_model_line(text)
        except ValueError as error:
            return str(error)
        if role != "implementer":
            reason = "a part is an implementer line"
        elif "implementer" in moved:
            reason = "--part takes the place of an implementer --model line; give one or the other"
        else:
            reason = refusal(role, expect, pins)
        if reason:
            return f"refused {text!r}: {reason}"
    return None


def _check(source: str, root: Path, args: argparse.Namespace, expectations: dict[str, Expect],
           parts: tuple[Expect, ...]) -> int:
    sessions = sessions_of(source, root, args.count, args.exclude)
    if isinstance(sessions, str):
        print(f"model_check: {sessions}")
        return 2
    total = 0
    for index, path in enumerate(sessions):
        if index:
            print()
        lines, mismatches = format_session(path, agent_calls(path), expectations, parts)
        total += mismatches
        for line in lines:
            print(line)
    return 1 if total else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show the model board, or report the model each agent call in a "
                                                 "session ran on against it.")
    parser.add_argument("source", nargs="?", default=".",
                        help="a session .jsonl, an eval workspace, or the project path (with --board, the project)")
    parser.add_argument("--board", action="store_true", help="print each role's model, effort, source and pass")
    parser.add_argument("--run", default=None, help="with --board, also check this session source")
    parser.add_argument("--config", default=None, help="the devflow.json holding the board")
    parser.add_argument("--escalated", action="store_true", help="judge the implementer by implementer.escalate")
    parser.add_argument("--diagnosis", action="store_true", help="judge the designer by designer.diagnosis")
    parser.add_argument("--model", action="append", default=[], help="'<role>: <Model>, <effort>; <why>'")
    parser.add_argument("--part", action="append", default=[], help="'implementer: <Model>, <effort>; <what>', one per part, in order")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--exclude", default="", help="session id to leave out")
    parser.add_argument("--projects-root", default=None)
    parser.add_argument("--agents", default=str(PINS_DIR))
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    pins = load_pins(Path(args.agents))
    path = config_path(args.source, args.config).resolve()
    config, label = load_board_config(path)
    root = Path(args.projects_root) if args.projects_root else default_projects_root()
    if not args.board:
        problem = _validated(args, pins)
        if problem:
            print(f"model_check: {problem}")
            return 2
    rows, notes = board_rows(config, pins, args.model, args.part)
    expectations = expectations_from(rows, args.escalated, args.diagnosis)
    parts = tuple(row.expect for row in rows if row.key.startswith("implementer part "))
    if not args.board:
        print(f"model_check: board: {label}")
        for kind, text in notes:
            print(f"model_check: {kind}: {text}")
        return _check(args.source, root, args, expectations, parts)
    project = Path(args.source) if Path(args.source).is_dir() else path.parent.parent
    for line in format_board(label, rows, notes, open_step_lines(project, config), session_model(project, root)):
        print(line)
    if args.run is None:
        return 0
    print()
    return _check(args.run, root, args, expectations, parts)


if __name__ == "__main__":
    sys.exit(main())
