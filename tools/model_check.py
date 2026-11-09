from __future__ import annotations

import argparse
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
META_TAIL = ".meta.json"
SYNTHETIC = "<synthetic>"
LINE_PREFIX = re.compile(r"^\s*\*\*Model:\*\*\s*", re.IGNORECASE)
LINE_SHAPE = re.compile(r"^([A-Za-z][A-Za-z-]*)\s*:\s*([A-Za-z]+)\s*,\s*([A-Za-z]+)\s*(?:;.*)?$")
FRONT_FIELD = re.compile(r"^(model|effort)\s*:\s*(\S+)\s*$")
CLOSING = "effort is the effort each reply recorded; the role of a general-purpose call is not known"


class Expect(NamedTuple):
    model: str
    effort: str | None
    source: str


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
    shown = f"{expect.model}, {expect.effort}" if expect.effort else expect.model
    return f"{shown} ({expect.source})"


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report the model each agent call in a session ran on.")
    parser.add_argument("source", nargs="?", default=".", help="a session .jsonl, an eval workspace, or the project path")
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
    expectations = dict(pins)
    moved: set[str] = set()
    for text in args.model:
        try:
            role, expect = parse_model_line(text)
        except ValueError as error:
            print(f"model_check: {error}")
            return 2
        reason = refusal(role, expect, pins)
        if not reason and role in moved:
            reason = f"a second --model line for {role}; give one line per role"
        if reason:
            print(f"model_check: refused {text!r}: {reason}")
            return 2
        moved.add(role)
        expectations[role] = expect
    parts: list[Expect] = []
    for text in args.part:
        try:
            role, expect = parse_model_line(text)
        except ValueError as error:
            print(f"model_check: {error}")
            return 2
        if role != "implementer":
            reason = "a part is an implementer line"
        elif "implementer" in moved:
            reason = "--part takes the place of an implementer --model line; give one or the other"
        else:
            reason = refusal(role, expect, pins)
        if reason:
            print(f"model_check: refused {text!r}: {reason}")
            return 2
        parts.append(expect)
    numbered = tuple(Expect(part.model, part.effort, f"part {number} of {len(parts)}")
                     for number, part in enumerate(parts, 1))
    root = Path(args.projects_root) if args.projects_root else default_projects_root()
    sessions = sessions_of(args.source, root, args.count, args.exclude)
    if isinstance(sessions, str):
        print(f"model_check: {sessions}")
        return 2
    total = 0
    for index, path in enumerate(sessions):
        if index:
            print()
        lines, mismatches = format_session(path, agent_calls(path), expectations, numbered)
        total += mismatches
        for line in lines:
            print(line)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
