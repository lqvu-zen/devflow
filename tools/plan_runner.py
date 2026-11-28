from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import Callable, NamedTuple, Sequence

PLUGIN = Path(__file__).resolve().parents[1]
HOOKS_DIR = PLUGIN / "hooks"
TOOLS_DIR = PLUGIN / "tools"
AGENTS_DIR = PLUGIN / "agents"
SESSION_START = HOOKS_DIR / "session_start.py"
BRANCH = "develop"
PROMPT = "/devflow:next-step"
COMMIT_FLAG = "--commit-without-asking"
WAIVED_FLAG = "--waived"
WAIVED_TEXT = "waived"
DECIDE_FLAG = "--decide-without-asking"
DECIDING_FLAG = "--deciding"
DECIDING_TEXT = "deciding"
DECIDED = re.compile(r"decided without asking:\s*(.+)", re.I)
DECISION_SPLIT = re.compile(r";\s*(?=\(\d+\)\s)")
SEE_TRIED = re.compile(r"[;,.]?\s*see Tried\W*$", re.I)
WAIVER_ENV = "DEVFLOW_COMMIT_WITHOUT_ASKING"
WAIVER_DIR = "devflow-runner"
TOKEN = re.compile(r"[0-9a-f]{32}")
MODES = ("default", "acceptEdits")
DEFAULT_MODE = "acceptEdits"
DENIAL_TEXT = 100
DENIAL_KEYS = ("command", "file_path", "notebook_path", "path", "pattern")
WAITING = "waiting for the maintainer's yes"
CUT_OFF = "cut off by the usage limit"
RESUME_ONLY_ADVICE = ("; after the reset, resume the cut-off session with the `claude --resume` line below "
                      "and finish the step there")
RESUME_ADVICE = RESUME_ONLY_ADVICE + " (the next run would refuse this tree)"
NO_SESSION_ADVICE = ("; no session id was read to resume it: after the reset, deal with those changes by hand, "
                     "then run the plan again")
RERUN_ADVICE = "; after the reset, run the plan again, which retakes the step"
START_FORMAT = "%Y-%m-%d %H:%M:%S %z"
BOM = b"\xef\xbb\xbf"
USAGE_LIMIT = re.compile(r"hit your [\w -]*?limit|usage limit reached", re.I)
LIMIT_TEXT = 120
COST_NOT_READ = "cost not read"
GIT_SECONDS = 30
CI_SECONDS = 60
SESSION_SECONDS = 4 * 3600
KILL_SECONDS = 30
CRASH_TEXT = LIMIT_TEXT
CRASH_LINE = re.compile(r"error|exception|fatal", re.I)


def _load(name: str, path: Path):
    loaded = sys.modules.get(name)
    if loaded is not None:
        return loaded
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _session_start():
    return _load("devflow_session_start", SESSION_START)


def _model_check():
    if str(TOOLS_DIR) not in sys.path:
        sys.path.insert(0, str(TOOLS_DIR))
    return _load("model_check", TOOLS_DIR / "model_check.py")


class NextStep(NamedTuple):
    plan: str | None
    number: int | None
    title: str
    run: str | None
    stop: str | None
    lines: list[str]
    code: int
    budget: str | None = None


class SessionResult(NamedTuple):
    cost: float | None
    session_id: str | None
    denials: list[str]
    is_error: bool
    raw_ok: bool
    subtype: str | None = None
    limit: str | None = None
    timed_out: float | None = None
    crash: str | None = None


class StepRow(NamedTuple):
    plan: str
    number: int
    title: str
    outcome: str
    why: str | None
    commits: list[str]
    cost: float | None
    session: str | None = None
    decisions: tuple[str, ...] = ()
    refused: tuple[str, ...] = ()


def _git(project: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(["git", *args], cwd=str(project), capture_output=True, text=True,
                                encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
                                timeout=GIT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def ask_next_step(project: Path) -> NextStep:
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project)
    try:
        result = subprocess.run([sys.executable, str(SESSION_START), "--next-step"], cwd=str(project),
                                capture_output=True, text=True, encoding="utf-8", errors="replace",
                                stdin=subprocess.DEVNULL, env=env, timeout=120)
    except (OSError, subprocess.SubprocessError) as error:
        return NextStep(None, None, "", None, f"session_start.py --next-step failed: {error}", [], 1)
    lines = [line.rstrip() for line in result.stdout.splitlines() if line.strip()]
    if result.returncode != 0:
        said = " ".join(lines + [line.strip() for line in result.stderr.splitlines() if line.strip()])
        return NextStep(None, None, "", None,
                        f"session_start.py --next-step exited {result.returncode}: {said or 'no output'}",
                        lines, result.returncode)
    plan = number = run = stop = budget = None
    title = ""
    for line in lines:
        if line.startswith("Plan: "):
            plan = line[len("Plan: "):].strip()
            if plan.endswith(" (the next plan)"):
                plan = plan[:-len(" (the next plan)")].strip()
        elif line.startswith("Step: "):
            head, _, rest = line[len("Step: "):].partition(" ")
            if head.isdigit():
                number, title = int(head), rest.strip()
        elif line.startswith("Run: "):
            run = line[len("Run: "):].strip()
        elif line.startswith("Stop: "):
            stop = line[len("Stop: "):].strip()
        elif line.startswith("Budget: "):
            budget = line[len("Budget: "):].strip()
    if run is None and stop is None:
        stop = "session_start.py --next-step printed neither Run nor Stop: " + (" ".join(lines) or "no output")
        return NextStep(plan, number, title, None, stop, lines, 1)
    if run is not None and (plan is None or number is None):
        return NextStep(plan, number, title, None,
                        "session_start.py --next-step named a skill but no plan or step", lines, 1)
    return NextStep(plan, number, title, run, stop, lines, 0, budget)


def foreign_changes(project: Path, layout) -> list[str] | None:
    session_start = _session_start()
    out = _git(project, "status", "--porcelain", "--untracked-files=all")
    if out is None:
        return None
    paths = [session_start._path_of(line) for line in out.splitlines() if line.strip()]
    return [path for path in paths if not layout.is_managed_path(path)]


def current_branch(project: Path) -> str:
    return (_git(project, "rev-parse", "--abbrev-ref", "HEAD") or "").strip()


def head_of(project: Path) -> str:
    return (_git(project, "rev-parse", "HEAD") or "").strip()


def preflight(project: Path, layout, claude: object) -> str | None:
    branch = current_branch(project)
    if branch != BRANCH:
        return f"the branch is {branch or 'unknown'}, not {BRANCH}; the runner works on {BRANCH} only"
    foreign = foreign_changes(project, layout)
    if foreign is None:
        return "git status failed"
    if foreign:
        return "the tree has changes beyond the status and plan files: " + ", ".join(foreign)
    if not claude:
        return "claude was not found; pass --claude PATH"
    return None


def orchestrator_model(config: object) -> str | None:
    model_check = _model_check()
    raw, _where, _read = model_check.read_user_defaults(os.environ, model_check.default_user_settings())
    rows, _notes = model_check.board_rows(config, model_check.load_pins(AGENTS_DIR),
                                          user=model_check.parse_user_defaults(raw))
    for row in rows:
        if row.key == "orchestrator" and row.expect is not None:
            return row.expect.model
    return None


def _money(value: float) -> str:
    return f"{value:.2f}"


def claude_argv(claude: object, model: str | None, budget: float | None, mode: str | None) -> list[str]:
    head = [claude] if isinstance(claude, (str, os.PathLike)) else list(claude)
    argv = [str(part) for part in head] + ["-p", PROMPT, "--output-format", "json"]
    if model:
        argv += ["--model", model]
    if budget is not None:
        argv += ["--max-budget-usd", _money(budget)]
    if mode:
        argv += ["--permission-mode", mode]
    return argv


def _last_object(text: str) -> dict | None:
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if isinstance(data, dict):
        return data
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if isinstance(data, dict):
            return data
    return None


def denial_text(denial: object) -> str:
    if not isinstance(denial, dict):
        return "unknown tool"
    name = denial.get("tool_name")
    name = name if isinstance(name, str) and name else "unknown tool"
    given = denial.get("tool_input")
    if not isinstance(given, dict):
        return name
    for key in DENIAL_KEYS:
        value = given.get(key)
        if isinstance(value, str) and value.strip():
            first = " ".join(value.split())
            if len(first) > DENIAL_TEXT:
                first = first[:DENIAL_TEXT - 3] + "..."
            return f"{name} `{first}`"
    return name


def limit_message(text: object) -> str | None:
    if not isinstance(text, str):
        return None
    for line in text.splitlines():
        if USAGE_LIMIT.search(line):
            line = " ".join(line.split())
            if len(line) > LIMIT_TEXT:
                line = line[:LIMIT_TEXT - 3] + "..."
            return line
    return None


def crash_text(returncode: int, errors: str) -> str | None:
    if returncode == 0:
        return None
    text = f"exit {returncode}"
    lines = [" ".join(line.split()) for line in (errors or "").splitlines() if line.strip()]
    if not lines:
        return text
    line = next((line for line in lines if CRASH_LINE.search(line)), lines[-1])
    if len(line) > CRASH_TEXT:
        line = line[:CRASH_TEXT - 3] + "..."
    return f"{text}: {line}"


def read_result(text: str, returncode: int, errors: str = "") -> SessionResult:
    data = _last_object(text)
    if data is None:
        found = limit_message(errors) if returncode != 0 else None
        return SessionResult(None, None, [], True, False, None, found, None, crash_text(returncode, errors))
    cost = data.get("total_cost_usd")
    if isinstance(cost, bool) or not isinstance(cost, (int, float)):
        cost = None
    names: list[str] = []
    denials = data.get("permission_denials")
    if isinstance(denials, list):
        for denial in denials:
            name = denial_text(denial)
            if name not in names:
                names.append(name)
    session_id = data.get("session_id")
    subtype = data.get("subtype")
    failed = bool(data.get("is_error")) or returncode != 0
    found = None
    if failed:
        found = limit_message(data.get("result")) or limit_message(errors)
    return SessionResult(float(cost) if cost is not None else None,
                         session_id if isinstance(session_id, str) else None,
                         names, failed, True,
                         subtype if isinstance(subtype, str) and subtype else None, found)


def kill_tree(process) -> None:
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True,
                           stdin=subprocess.DEVNULL, timeout=GIT_SECONDS)
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
    try:
        process.kill()
    except OSError:
        pass


def run_session(argv: list[str], project: Path, env: dict, seconds: float = SESSION_SECONDS) -> SessionResult:
    options = {} if os.name == "nt" else {"start_new_session": True}
    try:
        process = subprocess.Popen(argv, cwd=str(project), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                   env=env, **options)
    except OSError as error:
        return SessionResult(None, None, [], True, False, crash=f"could not start: {error}")
    try:
        output, errors = process.communicate(timeout=seconds)
    except subprocess.TimeoutExpired:
        kill_tree(process)
        try:
            process.communicate(timeout=KILL_SECONDS)
        except (subprocess.SubprocessError, OSError, ValueError):
            pass
        return SessionResult(None, None, [], True, False, timed_out=seconds)
    except KeyboardInterrupt:
        kill_tree(process)
        raise
    errors = errors or ""
    if errors:
        sys.stderr.write(errors)
        sys.stderr.flush()
    return read_result(output or "", process.returncode, errors)


def row_state(root: Path, plan: str, number: int) -> str | None:
    session_start = _session_start()
    try:
        md = (Path(root) / plan).read_text(encoding="utf-8-sig")
    except (OSError, ValueError):
        return None
    found = session_start.step_states(md).get(number)
    return found[1] if found else None


def mark_for_retake(root: Path, plan: str, number: int, claimed: str, stamp: str) -> bool:
    session_start = _session_start()
    path = Path(root) / plan
    try:
        raw = path.read_bytes()
        bom = raw.startswith(BOM)
        text = raw[3:].decode("utf-8") if bom else raw.decode("utf-8")
    except (OSError, ValueError):
        return False
    lines = re.split(r"(?<=\n)", text)
    inside = False
    hits = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## "):
            inside = stripped[3:].strip().lower() == "status"
            continue
        if not inside:
            continue
        match = session_start._STATUS_ROW.match(stripped)
        if match and int(match.group(1)) == number and match.group(3) == claimed:
            hits.append(index)
    if len(hits) != 1:
        return False
    index = hits[0]
    cell = re.match(r"^(\s*\|\s*\d+\s+[^|]*?\s*\|\s*)([^|]*?)(\s*\|.*)$", lines[index], re.S)
    if cell is None or cell.group(2) != claimed:
        return False
    lines[index] = f"{cell.group(1)}stopped ({stamp}): {CUT_OFF}; retake it{cell.group(3)}"
    data = "".join(lines).encode("utf-8")
    try:
        path.write_bytes((BOM if bom else b"") + data)
    except OSError:
        return False
    return True


def ci_conclusion(project: Path, head: str) -> str:
    session_start = _session_start()

    def run(argv: list) -> str | None:
        return session_start.run(argv, timeout=CI_SECONDS, cwd=str(project))

    runs = session_start._runs_for(run, head)
    if runs is None:
        return "unread (gh unavailable)"
    if not runs:
        return "missing (no run)"
    latest = runs[0]
    if latest.get("status") == "completed" and latest.get("conclusion") == "success":
        return "success"
    return session_start._describe(runs)


def session_trouble(result: SessionResult) -> str:
    if not result.raw_ok:
        return "; the session's result could not be read" + (f" ({result.crash})" if result.crash else "")
    if result.is_error:
        ended = result.subtype if result.subtype and result.subtype != "success" else "an error"
        return f"; the session ended with {ended}"
    return ""


def _foreign_clause(foreign: list[str] | None) -> str:
    if foreign:
        return ("; it left changes beyond the status and plan files: " + ", ".join(foreign)
                + " (the next run refuses until they are dealt with)")
    return ""


def _duration(seconds: float) -> str:
    total = int(round(seconds))
    if total >= 3600 and total % 3600 == 0:
        count, unit = total // 3600, "hour"
    elif total >= 60 and total % 60 == 0:
        count, unit = total // 60, "minute"
    else:
        count, unit = total, "second"
    return f"{count} {unit}" + ("" if count == 1 else "s")


def timeout_stop(project: Path, layout, number: int, seconds: float) -> str:
    return (f"step {number}'s session ran past the session timeout ({_duration(seconds)}) and was ended; "
            "its row was left as it was" + _foreign_clause(foreign_changes(project, layout)))


def limit_advice(foreign: list[str] | None, retakes: bool, session: str | None) -> str:
    if foreign:
        return RESUME_ADVICE if session else NO_SESSION_ADVICE
    if foreign is not None and retakes:
        return RERUN_ADVICE
    return RESUME_ONLY_ADVICE if session else ""


def limit_stop(project: Path, root: Path, layout, plan: str, number: int, message: str,
               session: str | None) -> str:
    session_start = _session_start()
    head = f"the usage limit cut off step {number}'s session ({message})"
    state = row_state(root, plan, number)
    waiting = state is not None and WAITING in state.lower().replace("’", "'")
    retakes = state is not None and not waiting and session_start.is_open(state)
    if state is not None and not waiting and session_start.is_claimed(state):
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        if mark_for_retake(root, plan, number, state, stamp):
            why = (f"{head}; its row now reads `stopped ({stamp}): {CUT_OFF}; retake it`, "
                   "so the next run takes it again")
        else:
            why = f"{head}; its row could not be marked: set it to stopped by hand"
    else:
        why = f"{head}; its row was left as it was"
    foreign = foreign_changes(project, layout)
    return why + _foreign_clause(foreign) + limit_advice(foreign, retakes, session)


def denial_clause(result: SessionResult) -> str:
    if not result.denials:
        return ""
    return "; the session met permission asks it could not answer: " + ", ".join(result.denials)


def step_outcome(project: Path, root: Path, layout, plan: str, number: int, result: SessionResult,
                 ci: Callable[[Path, str], str]) -> tuple[str, str | None]:
    session_start = _session_start()
    if result.limit:
        return "stopped", limit_stop(project, root, layout, plan, number, result.limit, result.session_id)
    if result.timed_out is not None:
        return "stopped", timeout_stop(project, layout, number, result.timed_out)
    refusals = denial_clause(result)
    state = row_state(root, plan, number)
    if state is None:
        return "stopped", f"step {number}'s Status row is missing from {plan}" + refusals
    if WAITING in state.lower().replace("’", "'"):
        return "stopped", f"step {number}'s code commit waits for the maintainer's yes" + refusals
    if session_start.is_open(state):
        why = f"step {number} ended `{state.strip()}`, not done"
        return "stopped", why + session_trouble(result) + refusals
    foreign = foreign_changes(project, layout)
    if foreign is None:
        return "stopped", "git status failed after the session" + refusals
    if foreign:
        left = "the session left changes beyond the status and plan files: " + ", ".join(foreign)
        return "stopped", left + refusals
    branch = current_branch(project)
    if branch != BRANCH:
        return "stopped", f"the branch is now {branch or 'unknown'}, not {BRANCH}" + refusals
    head = head_of(project)
    conclusion = ci(project, head)
    if conclusion != "success":
        return "stopped", f"CI on HEAD {head[:7] or 'unknown'} is {conclusion}, not green" + refusals
    return "done", None


def decisions_in(state: str | None) -> tuple[str, ...]:
    found = DECIDED.search(state or "")
    if not found:
        return ()
    text = SEE_TRIED.sub("", found.group(1).strip()).strip()
    return tuple(part.strip() for part in DECISION_SPLIT.split(text) if part.strip())


def decision_lines(row: StepRow) -> list[str]:
    return [f"  - decided {decision}" for decision in row.decisions]


def refusal_lines(row: StepRow) -> list[str]:
    return [f"  - refused {text}" for text in row.refused]


def commits_since(project: Path, before: str) -> list[str]:
    if not before:
        return []
    out = _git(project, "log", "--reverse", "--format=%h", f"{before}..HEAD")
    return [line.strip() for line in (out or "").splitlines() if line.strip()]


def session_env(project: Path, token: str | None) -> dict:
    env = dict(os.environ)
    env.pop(WAIVER_ENV, None)
    env.pop("CLAUDECODE", None)
    env["CLAUDE_PROJECT_DIR"] = str(project)
    if token:
        env[WAIVER_ENV] = token
    return env


def spent_of(rows: Sequence[StepRow]) -> float:
    return sum(row.cost for row in rows if row.cost is not None)


def row_line(row: StepRow) -> str:
    outcome = row.outcome if row.why is None else f"{row.outcome} ({row.why})"
    commits = " ".join(row.commits) if row.commits else "none"
    cost = f"${_money(row.cost)}" if row.cost is not None else COST_NOT_READ
    return f"- {row.number} {row.title}: {outcome}; commits {commits}; {cost}"


def say_now(line: str) -> None:
    print(line, flush=True)


def started_stamp() -> str:
    return datetime.datetime.now().astimezone().strftime(START_FORMAT)


def run_plan(project: Path, steps: int | None, dollars: float | None, commit_flag: bool, model: str | None,
             mode: str | None, claude: object, ci: Callable[[Path, str], str] = ci_conclusion,
             token: str | None = None, rows: list | None = None,
             say: Callable[[str], None] = None,
             session_seconds: float = SESSION_SECONDS) -> tuple[list[StepRow], str, int]:
    session_start = _session_start()
    say = say or say_now
    rows = [] if rows is None else rows
    found = session_start.devflow_store.find(project)
    if found is None:
        return rows, f"no .claude/devflow.json in {project}", 1
    layout = session_start.Layout(found.config)
    taken: set[tuple[str, int]] = set()
    while True:
        step = ask_next_step(project)
        if step.stop is not None:
            return rows, step.stop, step.code
        if (step.plan, step.number) in taken:
            return rows, f"step {step.number} offered again; not retried", 1
        if steps is not None and len(rows) >= steps:
            return rows, f"the step limit ({steps}) is reached", 0
        if step.budget is not None:
            return rows, (f"step {step.number} has a Budget of its own ({step.budget}): its spend is outside "
                          "--dollars and its runs outlive a headless turn; take it with /devflow:next-step "
                          "in a session"), 0
        budget = None
        if dollars is not None:
            if any(row.cost is None for row in rows):
                return rows, "a session's cost was not read, so the dollar limit can't be kept", 1
            spent = spent_of(rows)
            left = dollars - spent
            if spent >= dollars or _money(left) == "0.00":
                return rows, f"the dollar limit (${_money(dollars)}) is reached: ${_money(spent)} spent", 0
            budget = left
        before = head_of(project)
        say(f"Running step {step.number} {step.title} ({step.plan}) with {step.run}... "
            f"(started {started_stamp()})")
        argv = claude_argv(claude, model, budget, mode)
        result = run_session(argv, project, session_env(project, token if commit_flag else None),
                             session_seconds)
        outcome, why = step_outcome(project, found.root, layout, step.plan, step.number, result, ci)
        row = StepRow(step.plan, step.number, step.title, outcome, why, commits_since(project, before),
                      result.cost, result.session_id,
                      decisions_in(row_state(found.root, step.plan, step.number)),
                      tuple(result.denials) if outcome == "done" else ())
        rows.append(row)
        say(row_line(row))
        for line in decision_lines(row) + refusal_lines(row):
            say(line)
        taken.add((step.plan, step.number))
        if why is not None:
            return rows, why, 1


def summary(rows: Sequence[StepRow], reason: str, flag: bool, spent: float | None,
            decide: bool = False) -> list[str]:
    count = f"{len(rows)} step" + ("" if len(rows) == 1 else "s")
    unread = any(row.cost is None for row in rows)
    money = COST_NOT_READ if spent is None else f"${_money(spent)} spent"
    if spent is not None and unread:
        money += f" ({COST_NOT_READ} for some steps)"
    flags = f"{COMMIT_FLAG} {'on' if flag else 'off'}"
    if decide:
        flags += f"; {DECIDE_FLAG} on"
    lines = [f"Plan runner: {flags}; {count}; {money}"]
    for row in rows:
        lines.append(row_line(row))
        lines += decision_lines(row)
        lines += refusal_lines(row)
    lines.append(f"Stopped: {reason.rstrip('.')}.")
    if rows and rows[-1].outcome != "done" and rows[-1].session:
        lines.append(f"To answer step {rows[-1].number}'s session: claude --resume {rows[-1].session}")
    return lines


def waiver_folder(common: Path) -> Path:
    return Path(common) / WAIVER_DIR


def make_waiver(common: Path, decide: bool = False) -> tuple[str, Path]:
    token = secrets.token_hex(16)
    folder = waiver_folder(common)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / token
    started = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    path.write_text(json.dumps({"pid": os.getpid(), "started": started, "decide": decide}), encoding="utf-8")
    return token, path


def drop_waiver(path: Path | None) -> None:
    if path is None:
        return
    try:
        Path(path).unlink()
    except FileNotFoundError:
        pass
    try:
        Path(path).parent.rmdir()
    except OSError:
        pass


def waived(project: Path, env) -> bool:
    token = env.get(WAIVER_ENV) or ""
    if not TOKEN.fullmatch(token):
        return False
    session_start = _session_start()
    try:
        common = session_start.devflow_store.common_dir(Path(project))
        return (waiver_folder(common) / token).is_file()
    except (OSError, ValueError):
        return False


def deciding(project: Path, env) -> bool:
    token = env.get(WAIVER_ENV) or ""
    if not TOKEN.fullmatch(token):
        return False
    session_start = _session_start()
    try:
        common = session_start.devflow_store.common_dir(Path(project))
        data = json.loads((waiver_folder(common) / token).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get("decide") is True


def _project() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())


def parser() -> argparse.ArgumentParser:
    made = argparse.ArgumentParser(prog="plan_runner.py",
                                   description="Run the plan's next steps, one fresh headless session each.")
    made.add_argument("--steps", type=int, default=None)
    made.add_argument("--dollars", type=float)
    made.add_argument(COMMIT_FLAG, dest="commit", action="store_true")
    made.add_argument(DECIDE_FLAG, dest="decide", action="store_true")
    made.add_argument("--model")
    made.add_argument("--permission-mode", dest="mode", choices=MODES, default=DEFAULT_MODE)
    made.add_argument("--claude", default="claude")
    return made


def main(argv: list[str] | None = None, claude: object = None,
         ci: Callable[[Path, str], str] = ci_conclusion) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if WAIVED_FLAG in args:
        if args != [WAIVED_FLAG]:
            print(f"usage: plan_runner.py {WAIVED_FLAG} (alone)", file=sys.stderr)
            return 2
        ok = waived(_project(), os.environ)
        print(WAIVED_TEXT if ok else f"not {WAIVED_TEXT}")
        return 0 if ok else 1
    if DECIDING_FLAG in args:
        if args != [DECIDING_FLAG]:
            print(f"usage: plan_runner.py {DECIDING_FLAG} (alone)", file=sys.stderr)
            return 2
        ok = deciding(_project(), os.environ)
        print(DECIDING_TEXT if ok else f"not {DECIDING_TEXT}")
        return 0 if ok else 1
    made = parser()
    if "--permission-mode" in args or any(a.startswith("--permission-mode=") for a in args):
        if "bypassPermissions" in args or "--permission-mode=bypassPermissions" in args:
            print("plan_runner.py: --permission-mode bypassPermissions is refused; "
                  "use default or acceptEdits", file=sys.stderr)
            return 2
    try:
        options = made.parse_args(args)
    except SystemExit as error:
        return 2 if error.code else 0
    if options.steps is not None and options.steps < 1:
        print("plan_runner.py: --steps must be at least 1", file=sys.stderr)
        return 2
    if options.dollars is not None and not options.dollars > 0:
        print("plan_runner.py: --dollars must be more than 0", file=sys.stderr)
        return 2
    options.commit = options.commit or options.decide
    session_start = _session_start()
    project = _project()
    try:
        found = session_start.devflow_store.find(project)
    except (session_start.devflow_store.StoreError, ValueError) as error:
        print(f"Plan runner refused: {error}.")
        return 1
    if found is None:
        print(f"Plan runner refused: no .claude/devflow.json in {project}; run /devflow:setup first.")
        return 1
    layout = session_start.Layout(found.config)
    command = claude if claude is not None else shutil.which(options.claude)
    refusal = preflight(project, layout, command)
    if refusal:
        print(f"Plan runner refused: {refusal}.")
        return 1
    model = options.model or orchestrator_model(found.config)
    rows: list[StepRow] = []
    waiver = None
    token = None
    try:
        if options.commit:
            token, waiver = make_waiver(session_start.devflow_store.common_dir(project), decide=options.decide)
        try:
            rows, reason, code = run_plan(project, options.steps, options.dollars, options.commit, model,
                                          options.mode, command, ci, token, rows)
        except KeyboardInterrupt:
            reason, code = "interrupted", 1
    finally:
        drop_waiver(waiver)
    spent = None if rows and all(row.cost is None for row in rows) else spent_of(rows)
    for line in summary(rows, reason, options.commit, spent, options.decide):
        print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
