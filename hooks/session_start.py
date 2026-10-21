from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

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

    def is_secretary_path(self, path: str) -> bool:
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
    secretary = [_path_of(line) for line in lines if layout.is_secretary_path(_path_of(line))]
    if secretary:
        result.append(f"Secretary edits waiting: {', '.join(secretary)}. Commit them with your "
                      "next change; never revert them.")
    else:
        result.append("Secretary edits waiting: none. (When listed: commit them with your next "
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


def plan_lines(plan: str | None, plan_md: str | None,
               layout: Layout = DEFAULT_LAYOUT) -> list[str]:
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
    if number is not None:
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
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def profile_line(project: Path) -> str | None:
    if (project / ".claude" / "devflow.md").is_file():
        return None
    return ("Profile: .claude/devflow.md is missing; the devflow skills need it. "
            "Run /devflow:setup to write it.")


def report(run: Runner, project: Path, layout: Layout = DEFAULT_LAYOUT) -> str:
    state = upstream_state(run)
    _branch, upstream, ahead, _behind, head = state
    lines = [f"{layout.name} session start", branch_line(state)]
    lines += change_lines(run, layout)
    lines.append(ci_line(run, head, upstream, ahead))
    status_md = _read(project / layout.status_file)
    plan = current_plan(status_md, layout) if status_md else None
    plan_md = _read(project / plan) if plan else None
    lines += plan_lines(plan, plan_md, layout)
    missing = profile_line(project)
    if missing:
        lines.append(missing)
    return "\n".join(lines)


def load_config(project: Path) -> dict | None:
    path = project / ".claude" / "devflow.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    if not isinstance(data, dict):
        raise ValueError(f"{path} must hold a JSON object")
    return data


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    try:
        config = load_config(project)
        if config is None:
            return 0
        deadline = time.monotonic() + DEADLINE_SECONDS
        text = report(runner_until(deadline, str(project)), project, Layout(config))
    except Exception as error:
        print(f"session_start.py failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
