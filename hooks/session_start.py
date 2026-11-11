from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping, NamedTuple, Optional

Runner = Callable[[list], Optional[str]]

MAX_CHANGES = 15
DEADLINE_SECONDS = 15.0


class Layout:
    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        config = config or {}
        status = config.get("status_file")
        plans = config.get("plans_dir")
        name = config.get("name")
        self.status_file = (status if isinstance(status, str) and status else "docs/STATUS.md")
        self.plans_dir = (plans if isinstance(plans, str) and plans else "docs/plans")
        self.status_file = self.status_file.replace("\\", "/").strip("/")
        self.plans_dir = self.plans_dir.replace("\\", "/").strip("/")
        self.name = name if isinstance(name, str) and name else "devflow"
        self.plan_pattern = re.compile(re.escape(self.plans_dir) + r"/[\w.\-]+\.md")
        self.models = config.get("models")
        self.has_board = "models" in config

    def is_managed_path(self, path: str) -> bool:
        form = path.replace("\\", "/")
        return (form == self.status_file or form.startswith(self.plans_dir + "/")
                or form == self.plans_dir)


DEFAULT_LAYOUT = Layout()


def run(argv: list, timeout: float = 5, cwd: str | None = None) -> str | None:
    try:
        result = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=timeout, cwd=cwd)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.rstrip()


def runner_until(deadline: float, cwd: str | None = None,
                 clock: Callable[[], float] = time.monotonic) -> Runner:
    def bounded(argv: list) -> str | None:
        left = deadline - clock()
        if left <= 0:
            return None
        return run(argv, timeout=min(5.0, left), cwd=cwd)
    return bounded


def upstream_state(run: Runner) -> tuple[str, str, int, int, str]:
    branch = (run(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "").strip()
    head = (run(["git", "rev-parse", "HEAD"]) or "").strip()
    upstream = (run(["git", "rev-parse", "--abbrev-ref", "@{u}"]) or "").strip()
    behind = ahead = 0
    if upstream:
        counts = (run(["git", "rev-list", "--left-right", "--count", "@{u}...HEAD"]) or "").split()
        if len(counts) == 2 and all(c.isdigit() for c in counts):
            behind, ahead = int(counts[0]), int(counts[1])
    return branch, upstream, ahead, behind, head


def branch_line(state: tuple[str, str, int, int, str]) -> str:
    branch, upstream, ahead, behind, _head = state
    if not branch:
        return "Branch: unknown (git unavailable)"
    if not upstream:
        return f"Branch: {branch} (no upstream)"
    if ahead and behind:
        where = f"{ahead} ahead, {behind} behind {upstream}"
    elif ahead:
        where = f"{ahead} ahead of {upstream}"
    elif behind:
        where = f"{behind} behind {upstream}"
    else:
        where = f"up to date with {upstream}"
    return f"Branch: {branch} ({where})"


def _path_of(status_line: str) -> str:
    path = status_line[3:].strip()
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    return path.strip('"')


def change_lines(run: Runner, layout: Layout = DEFAULT_LAYOUT) -> list[str]:
    out = run(["git", "status", "--short"])
    if out is None:
        return ["Uncommitted: unknown (git status failed)"]
    lines = [line for line in out.splitlines() if line.strip()]
    if not lines:
        result = ["Uncommitted: none."]
    else:
        result = [f"Uncommitted ({len(lines)}):"]
        result += [f"  {line}" for line in lines[:MAX_CHANGES]]
        if len(lines) > MAX_CHANGES:
            result.append(f"  … and {len(lines) - MAX_CHANGES} more")
    managed = [_path_of(line) for line in lines if layout.is_managed_path(_path_of(line))]
    if managed:
        result.append(f"Status and plan edits waiting: {', '.join(managed)}. Commit them with "
                      "your next change; never revert them.")
    else:
        result.append("Status and plan edits waiting: none. (When listed: commit them with your next "
                      "change; never revert them.)")
    return result


def _describe(runs: list) -> str:
    if not runs:
        return "no run"
    latest = runs[0]
    if latest.get("status") == "completed":
        return f"CI {latest.get('conclusion') or 'finished'}"
    return f"CI {latest.get('status') or 'unknown'}"


def _runs_for(run: Runner, sha: str) -> list | None:
    out = run(["gh", "run", "list", "--commit", sha, "--limit", "1",
               "--json", "status,conclusion,workflowName"])
    if out is None:
        return None
    try:
        runs = json.loads(out or "[]")
    except ValueError:
        return None
    return runs if isinstance(runs, list) else None


def ci_line(run: Runner, head: str, upstream: str, ahead: int) -> str:
    if not head:
        return "CI: unknown (no HEAD)"
    runs = _runs_for(run, head)
    if runs is None:
        return "CI: unknown (gh unavailable)"
    short = head[:7]
    if runs:
        return f"CI on HEAD {short}: {_describe(runs)}."
    if ahead and upstream:
        upstream_sha = (run(["git", "rev-parse", upstream]) or "").strip()
        upstream_runs = _runs_for(run, upstream_sha) if upstream_sha else None
        if upstream_runs is None:
            return f"CI on HEAD {short}: no run (not pushed). {upstream}: CI unknown."
        return (f"CI on HEAD {short}: no run (not pushed). "
                f"{upstream} {upstream_sha[:7]}: {_describe(upstream_runs)}.")
    return f"CI on HEAD {short}: no run yet."


def current_plan(status_md: str, layout: Layout = DEFAULT_LAYOUT) -> str | None:
    for line in status_md.splitlines():
        if line.lstrip().startswith("|") and "in progress" in line.lower():
            match = layout.plan_pattern.search(line)
            if match:
                return match.group(0)
    match = layout.plan_pattern.search(status_md)
    return match.group(0) if match else None


def _section(markdown: str, title: str) -> str:
    lines = markdown.splitlines()
    out: list[str] = []
    inside = False
    for line in lines:
        if line.startswith("## "):
            if inside:
                break
            inside = line[3:].strip().lower() == title.lower()
            continue
        if inside:
            out.append(line)
    return "\n".join(out)


_NUMBER = re.compile(r"(?<![\w\-/.])(\d{1,3})(?![\w\-/]|\.\w)")


def step_order(plan_md: str) -> list[int]:
    order: list[int] = []
    for line in _section(plan_md, "Order").splitlines():
        text = re.sub(r"`[^`]*`", " ", line)
        text = re.sub(r"^\s*(?:\d+\.|[-*])\s+", " ", text)
        text = re.sub(r"\*\*(\s*\d{1,3}\s*)\*\*", r" \1 ", text)
        text = re.sub(r"\*\*.*?\*\*", " ", text)
        previous = None
        while previous != text:
            previous = text
            text = re.sub(r"\([^()]*\)", " ", text)
        for match in _NUMBER.finditer(text):
            number = int(match.group(1))
            if number not in order:
                order.append(number)
    return order


_STATUS_ROW = re.compile(r"^\|\s*(\d+)\s+([^|]*?)\s*\|\s*([^|]*?)\s*\|")


def step_states(plan_md: str) -> dict[int, tuple[str, str]]:
    states: dict[int, tuple[str, str]] = {}
    for line in _section(plan_md, "Status").splitlines():
        match = _STATUS_ROW.match(line.strip())
        if match:
            states[int(match.group(1))] = (match.group(2), match.group(3))
    return states


def is_open(state: str) -> bool:
    lowered = state.strip().lower()
    return not (lowered.startswith("done") or lowered.startswith("✅")
                or lowered.startswith("not needed"))


def _in_order(order: list[int], states: dict[int, tuple[str, str]]) -> list[int]:
    known = [n for n in order if n in states]
    return known + [n for n in states if n not in known]


def is_claimed(state: str) -> bool:
    lowered = state.strip().lower()
    return lowered.startswith("started") or lowered.startswith("in progress")


def has_note(state: str) -> bool:
    return state.strip() not in ("", "—", "–", "-")


def next_open(order: list[int], states: dict[int, tuple[str, str]]) -> int | None:
    for number in _in_order(order, states):
        state = states[number][1]
        if is_open(state) and not is_claimed(state):
            return number
    return None


def started(order: list[int], states: dict[int, tuple[str, str]]) -> list[int]:
    return [n for n in _in_order(order, states) if is_claimed(states[n][1])]


def next_plan(status_md: str, current: str | None, layout: Layout = DEFAULT_LAYOUT) -> str | None:
    for line in status_md.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        for match in layout.plan_pattern.finditer(line):
            if match.group(0) != current:
                return match.group(0)
    return None


_STEP_HEADING = re.compile(r"^###\s+(\d{1,3})\b")


def step_sections(plan_md: str) -> dict[int, str]:
    sections: dict[int, list[str]] = {}
    number = None
    for line in plan_md.splitlines():
        heading = _STEP_HEADING.match(line)
        if heading:
            number = int(heading.group(1))
            sections[number] = []
            continue
        if line.startswith("## ") or line.startswith("### "):
            number = None
            continue
        if number is not None:
            sections[number].append(line)
    return {n: "\n".join(body) for n, body in sections.items()}


def step_field(section: str, label: str) -> str | None:
    pattern = re.compile(r"^\*\*" + re.escape(label) + r":?\*\*:?\s*(.*)$")
    for line in section.splitlines():
        match = pattern.match(line.strip())
        if match:
            return match.group(1).strip()
    return None


_WHO_ROW = re.compile(r"^\|\s*(\d+)\s+[^|]*?\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|")


def who_rows(plan_md: str) -> dict[int, tuple[str, str]]:
    rows: dict[int, tuple[str, str]] = {}
    for line in _section(plan_md, "Who does what").splitlines():
        match = _WHO_ROW.match(line.strip())
        if match:
            rows[int(match.group(1))] = (match.group(2), match.group(3))
    return rows


_SKILL = re.compile(r"/devflow:([\w-]+)")
RUN_SKILLS = ("fix-bug", "add-feature")


def runner(who: str, how: str) -> tuple[str | None, str | None]:
    both = f"{who} {how}".lower()
    if "by hand" in how.lower():
        return None, "is done by hand"
    if "manage-project" in both or "project manager" in both:
        return None, "is the project manager's"
    skills = _SKILL.findall(how)
    runnable = [s for s in skills if s in RUN_SKILLS]
    if runnable and "coding session" in who.lower():
        return runnable[0], None
    others = [s for s in skills if s not in RUN_SKILLS]
    if others:
        return None, f"runs with /devflow:{others[0]}"
    return None, f"waits on {who.strip() or 'someone'}"


_OTHER_STEP = re.compile(r"\b[A-Za-z][\w.]*-(\d{1,3})\b")


def needs(text: str) -> tuple[list[int], list[tuple[str, int]], bool]:
    text = re.sub(r"`([A-Za-z][\w.]*-\d{1,3})`", r" \1 ", text)
    text = re.sub(r"`[^`]*`", " ", text)
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\([^()]*\)", " ", text)
    text = re.split(r"\.(?:\s|$)", text.strip(), maxsplit=1)[0]
    other = [(match.group(0), int(match.group(1))) for match in _OTHER_STEP.finditer(text)]
    rest = _OTHER_STEP.sub(" ", text)
    own: list[int] = []
    for match in _NUMBER.finditer(rest):
        number = int(match.group(1))
        if number not in own:
            own.append(number)
    return own, other, bool(re.search(r"\bevery\b", rest, re.IGNORECASE))


BEHAVIOUR_MAP = "docs/BEHAVIOUR.md"
CHANGELOG = "CHANGELOG.md"


def step_files(text: str, layout: Layout = DEFAULT_LAYOUT) -> list[str]:
    files: list[str] = []
    for raw in re.findall(r"`([^`]*)`", text):
        path = raw.strip().replace("\\", "/")
        while path.startswith("./"):
            path = path[2:]
        if not path or path in (BEHAVIOUR_MAP, CHANGELOG) or layout.is_managed_path(path.rstrip("/")):
            continue
        if path not in files:
            files.append(path)
    return files


def _covers(a: str, b: str) -> bool:
    return a == b or (a.endswith("/") and b.startswith(a)) or fnmatch.fnmatchcase(b, a)


def overlaps(a: list[str], b: list[str]) -> bool:
    return any(_covers(x, y) or _covers(y, x) for x in a for y in b)


class PlanView(NamedTuple):
    path: str
    md: str
    order: list[int]
    states: dict[int, tuple[str, str]]
    sections: dict[int, str]
    who: dict[int, tuple[str, str]]


def read_plan(path: str, md: str) -> PlanView:
    return PlanView(path, md, step_order(md), step_states(md), step_sections(md), who_rows(md))


def _readable(path: str | None, md: str | None) -> PlanView | None:
    if not path or md is None:
        return None
    view = read_plan(path, md)
    return view if view.order and view.states else None


_CLEARED = re.compile(r"\bcleared\b", re.IGNORECASE)


def _open_gate(view: PlanView, number: int) -> str | None:
    gate = step_field(view.sections.get(number, ""), "Gate")
    if gate is None or _CLEARED.search(gate):
        return None
    return gate


def _not_done(states: dict[int, tuple[str, str]], number: int) -> bool:
    return number not in states or is_open(states[number][1])


def _missing(view: PlanView, number: int, other: PlanView | None, text: str) -> list[str]:
    own, tokens, every = needs(text)
    numbers = list(own)
    if every:
        numbers += [n for n in _in_order(view.order, view.states) if n != number and n not in numbers]
    missing = [str(n) for n in numbers if _not_done(view.states, n)]
    missing += [token for token, n in tokens if other is None or _not_done(other.states, n)]
    return missing


InProgress = list[tuple[str, Optional[list[str]]]]


def blockers(view: PlanView, number: int, other: PlanView | None,
             in_progress: InProgress | None = None, layout: Layout = DEFAULT_LAYOUT) -> list[str]:
    reasons: list[str] = []
    if is_claimed(view.states.get(number, ("", ""))[1]):
        reasons.append("is claimed by another tab")
    if _open_gate(view, number) is not None:
        reasons.append("is at an uncleared Gate")
    row = view.who.get(number)
    reason = runner(*row)[1] if row else "has no Who does what row"
    if reason:
        reasons.append(reason)
    section = view.sections.get(number, "")
    text = step_field(section, "Needs")
    if text:
        missing = _missing(view, number, other, text)
        if missing:
            reasons.append("needs " + ", ".join(missing))
    if in_progress is not None:
        line = step_field(section, "Files")
        if line is None:
            reasons.append("has no Files line")
        else:
            mine = step_files(line, layout)
            for label, files in in_progress:
                if files is None or overlaps(mine, files):
                    reasons.append(f"overlaps {label} in progress")
                    break
    return reasons


def _in_progress(own: PlanView, other: PlanView, layout: Layout) -> InProgress:
    found: InProgress = []
    for view, suffix in ((own, f" of {own.path}"), (other, "")):
        for number in started(view.order, view.states):
            line = step_field(view.sections.get(number, ""), "Files")
            found.append((f"step {number}{suffix}", None if line is None else step_files(line, layout)))
    return found


class Choice(NamedTuple):
    plan: str
    number: int | None
    title: str
    note: str
    run: str | None
    stop: str | None
    next_action: str | None
    gate: str | None
    why: list[str] | None
    skipped: list[str]
    fallback: bool


GATE_ACTION = "the maintainer does what the Gate line says, then runs /devflow:next-step again"
IN_PROGRESS_ACTION = "the steps in progress land first"


def next_action(reason: str) -> str:
    if reason.startswith("is at an uncleared Gate"):
        return GATE_ACTION
    if reason.startswith("is done by hand"):
        return "the maintainer does it by hand, as the plan says"
    if reason.startswith("is the project manager's") or reason.startswith("has no Who does what row"):
        return "run /devflow:manage-project"
    if reason.startswith("runs with "):
        return f"the maintainer runs {reason[len('runs with '):]} when ready"
    if reason.startswith("waits on "):
        return f"it {reason}"
    if reason.startswith("needs "):
        return "the steps it needs land first"
    return IN_PROGRESS_ACTION


def _take(view: PlanView, number: int, why: list[str] | None = None,
          skipped: list[str] | None = None, fallback: bool = False) -> Choice:
    title, state = view.states[number]
    skill = runner(*view.who[number])[0]
    return Choice(view.path, number, title, state.strip() if has_note(state) else "", skill,
                  None, None, None, why, skipped or [], fallback)


def _stop(view: PlanView, number: int | None, stop: str, action: str,
          why: list[str] | None = None, skipped: list[str] | None = None) -> Choice:
    title = note = ""
    gate = None
    if number is not None:
        title, state = view.states[number]
        note = state.strip() if has_note(state) else ""
        gate = _open_gate(view, number)
    return Choice(view.path, number, title, note, None, stop, action, gate, why, skipped or [], False)


def _why_text(why: list[str] | None) -> str:
    return "; ".join(why or []) or "every open step is in progress"


def choose_step(current: PlanView, nxt: PlanView | None, layout: Layout = DEFAULT_LAYOUT) -> Choice:
    ordered = _in_order(current.order, current.states)
    open_steps = [n for n in ordered if is_open(current.states[n][1])]
    if not open_steps:
        return _stop(current, None, f"every step of {current.path} is done",
                     "run /devflow:manage-project to close the plan")
    candidates = [n for n in open_steps if not is_claimed(current.states[n][1])]
    reasons = {n: blockers(current, n, nxt, layout=layout) for n in candidates}
    if candidates:
        first = candidates[0]
        if not reasons[first]:
            return _take(current, first)
        if any(not reasons[n] for n in candidates[1:]):
            return _stop(current, first, f"step {first} {reasons[first][0]}", next_action(reasons[first][0]))
    why = [f"{n} {reasons[n][0]}" for n in candidates]
    skipped: list[str] = []
    stop = f"no step of {current.path} can start: {_why_text(why)}"
    if nxt is not None:
        in_progress = _in_progress(current, nxt, layout)
        for number in _in_order(nxt.order, nxt.states):
            state = nxt.states[number][1]
            if not is_open(state) or is_claimed(state):
                continue
            found = blockers(nxt, number, current, in_progress, layout)
            if not found:
                return _take(nxt, number, why, skipped, True)
            skipped.append(f"{number} {found[0]}")
        stop += f"; nor can any step of the next plan, {nxt.path}"
        if skipped:
            stop += ": " + "; ".join(skipped)
    first = candidates[0] if candidates else None
    action = next_action(reasons[first][0]) if first is not None else IN_PROGRESS_ACTION
    return _stop(current, first, stop, action, why, skipped)


def _choice(plan: str | None, plan_md: str | None, next_path: str | None, next_md: str | None,
            layout: Layout) -> Choice | None:
    current = _readable(plan, plan_md)
    nxt = _readable(next_path, next_md)
    if current is None or nxt is None:
        return None
    return choose_step(current, nxt, layout)


def plan_lines(plan: str | None, plan_md: str | None,
               layout: Layout = DEFAULT_LAYOUT, next_plan: str | None = None,
               next_md: str | None = None) -> list[str]:
    if not plan:
        return [f"Plan: none found in {layout.status_file}."]
    lines = [f"Plan: {plan}"]
    if plan_md is None:
        return lines + [f"Next step: couldn't read the Order and Status of {plan}; "
                        f"read {layout.status_file}."]
    order = step_order(plan_md)
    states = step_states(plan_md)
    if not order or not states:
        return lines + [f"Next step: couldn't read the Order and Status of {plan}; "
                        f"read {layout.status_file}."]
    claimed = started(order, states)
    number = next_open(order, states)
    choice = _choice(plan, plan_md, next_plan, next_md, layout)
    if choice is not None and choice.fallback:
        lines.append(f"Next open step in Order: {choice.number} {choice.title}, from the next plan "
                     f"{choice.plan} (no step of {plan} can start: {_why_text(choice.why)})")
        if choice.note:
            lines.append(f"  Last state: {choice.note}")
    elif choice is not None and choice.why is not None:
        detail = _why_text(choice.why)
        if choice.skipped:
            detail += "; next plan: " + "; ".join(choice.skipped)
        lines.append(f"Next open step in Order: none can start in {plan} or the next plan, "
                     f"{next_plan} ({detail})")
    elif number is not None:
        lines.append(f"Next open step in Order: {number} {states[number][0]}")
        if has_note(states[number][1]):
            lines.append(f"  Last state: {states[number][1].strip()}")
    elif not claimed:
        return lines + [f"Every step of {plan} is done."]
    else:
        lines.append("Next open step in Order: none; every open step is in progress.")
    if claimed:
        lines.append("In progress (claimed by another tab, don't take): "
                     + "; ".join(f"{n} {states[n][0]}" for n in claimed))
    return lines


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, ValueError):
        return None


def profile_line(project: Path) -> str | None:
    if (project / ".claude" / "devflow.md").is_file():
        return None
    return ("Profile: .claude/devflow.md is missing; the devflow skills need it. "
            "Run /devflow:setup to write it.")


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
VIEW_PATH = TOOLS_DIR / "model_check.py"


def models_line(layout: Layout, plan_md: str | None, step: int | None = None) -> str:
    try:
        if step is None and plan_md:
            step = next_open(step_order(plan_md), step_states(plan_md))
        if str(TOOLS_DIR) not in sys.path:
            sys.path.insert(0, str(TOOLS_DIR))
        import model_check
        config = {"models": layout.models} if layout.has_board else {}
        step_lines = model_check.step_model_lines(plan_md).get(step, []) if plan_md and step is not None else []
        pins = model_check.load_pins(model_check.PINS_DIR)
        return model_check.board_summary(config, pins, step, step_lines, str(VIEW_PATH))
    except Exception as error:
        return (f"Models: couldn't read the board ({type(error).__name__}: {error}). "
                f"Full view: python {VIEW_PATH} --board")


def report(run: Runner, project: Path, layout: Layout = DEFAULT_LAYOUT) -> str:
    state = upstream_state(run)
    _branch, upstream, ahead, _behind, head = state
    lines = [f"{layout.name} session start", branch_line(state)]
    lines += change_lines(run, layout)
    lines.append(ci_line(run, head, upstream, ahead))
    status_md = _read(project / layout.status_file)
    plan = current_plan(status_md, layout) if status_md else None
    plan_md = _read(project / plan) if plan else None
    next_path = next_plan(status_md, plan, layout) if status_md and plan else None
    next_md = _read(project / next_path) if next_path else None
    lines += plan_lines(plan, plan_md, layout, next_path, next_md)
    choice = _choice(plan, plan_md, next_path, next_md, layout)
    if choice is not None and choice.fallback:
        lines.append(models_line(layout, next_md, choice.number))
    else:
        lines.append(models_line(layout, plan_md))
    missing = profile_line(project)
    if missing:
        lines.append(missing)
    return "\n".join(lines)


def next_step_lines(project: Path, layout: Layout = DEFAULT_LAYOUT) -> list[str]:
    status_md = _read(project / layout.status_file)
    plan = current_plan(status_md, layout) if status_md else None
    if not plan:
        return [f"Plan: none found in {layout.status_file}.",
                f"Stop: no current plan in {layout.status_file}. Next: run /devflow:manage-project."]
    current = _readable(plan, _read(project / plan))
    if current is None:
        return [f"Plan: {plan}",
                f"Stop: couldn't read the Order and Status of {plan}. Next: run /devflow:manage-project."]
    next_path = next_plan(status_md, plan, layout)
    nxt = _readable(next_path, _read(project / next_path) if next_path else None)
    choice = choose_step(current, nxt, layout)
    lines = [f"Plan: {choice.plan}" + (" (the next plan)" if choice.fallback else "")]
    if choice.run:
        if choice.fallback:
            lines.append(f"Why: no step of {plan} can start: {_why_text(choice.why)}")
        if choice.skipped:
            lines.append("Skipped: " + "; ".join(choice.skipped))
        lines.append(f"Step: {choice.number} {choice.title}")
        if choice.note:
            lines.append(f"Last state: {choice.note}")
        lines.append(f"Run: /devflow:{choice.run}")
        return lines
    if choice.number is not None:
        lines.append(f"Step: {choice.number} {choice.title}")
    if choice.gate:
        lines.append(f"Gate: {choice.gate}")
    lines.append(f"Stop: {choice.stop}. Next: {choice.next_action}.")
    return lines


def load_config(project: Path) -> dict | None:
    path = project / ".claude" / "devflow.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return None
    if not isinstance(data, dict):
        raise ValueError(f"{path} must hold a JSON object")
    return data


NEXT_STEP_FLAG = "--next-step"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if args and args != [NEXT_STEP_FLAG]:
        print(f"usage: session_start.py [{NEXT_STEP_FLAG}]", file=sys.stderr)
        return 2
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    try:
        config = load_config(project)
        if config is None:
            if args:
                print(f"No .claude/devflow.json in {project}: run /devflow:setup first.")
                return 1
            return 0
        if args:
            text = "\n".join(next_step_lines(project, Layout(config)))
        else:
            deadline = time.monotonic() + DEADLINE_SECONDS
            text = report(runner_until(deadline, str(project)), project, Layout(config))
    except Exception as error:
        print(f"session_start.py failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
