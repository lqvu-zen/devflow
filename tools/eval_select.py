from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

FIXTURE = "evals/fixture/"
FIXTURE_UI = "evals/fixture/ui/"
GRADER_TYPES = ("llm", "tool_used", "tool_order", "regex", "file_exists", "baseline")
JS_FLAGS = re.compile(r"^[dgimsuvy]*$")
PY_FLAGS = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL}
TRIGGER_NAME = re.compile(r"^(?P<skill>[a-z-]+)-\d+-(fires|near-miss)$")


class GitError(RuntimeError):
    pass


def git(repo: str | Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise GitError(result.stderr.strip() or f"git {args[0]} failed")
    return result.stdout


def frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("no front matter")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError("front matter is not closed")
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        match = re.match(r"^([A-Za-z_][\w-]*):(?: (.*))?$", line)
        if not match:
            raise ValueError(f"cannot read front matter line: {line}")
        fields[match.group(1)] = (match.group(2) or "").strip()
    return fields, "\n".join(lines[end + 1:])


def frontmatter_block(text: str) -> str | None:
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None
    return "\n".join(lines[1:end])


def scalar(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith('"'):
        raise ValueError("use single quotes")
    if len(raw) >= 2 and raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1].replace("''", "'")
    return raw


def split_outside_quotes(text: str, separator: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quoted = False
    for char in text:
        if char == "'":
            quoted = not quoted
        if char == separator and not quoted:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    parts.append("".join(current))
    return parts


def flow_map(raw: str) -> dict[str, str]:
    raw = raw.strip()
    if not raw.startswith("{"):
        return {"tool": scalar(raw)}
    if not raw.endswith("}"):
        raise ValueError("unclosed flow map")
    result: dict[str, str] = {}
    for item in split_outside_quotes(raw[1:-1], ","):
        if not item.strip():
            continue
        key, separator, value = item.strip().partition(": ")
        if not separator:
            raise ValueError(f"cannot read flow map item: {item.strip()}")
        result[key.strip()] = scalar(value)
    return result


PYTHON_ONLY = (
    (re.compile(r"\(\?P"), "Python-only (?P group"),
    (re.compile(r"\(\?>"), "atomic group (?> that JavaScript lacks"),
    (re.compile(r"\(\?#"), "comment group (?# that JavaScript lacks"),
    (re.compile(r"(?:^|[^\\])(?:\\\\)*\\[AZ]"), "\\A or \\Z, which JavaScript lacks"),
    (re.compile(r"^\(\?[a-zA-Z]+\)"), "a leading flag group that JavaScript lacks"),
)


def pattern_problem(pattern: str, flags: str = "") -> str | None:
    if not JS_FLAGS.match(flags):
        return f"flags '{flags}' are not among dgimsuvy"
    for rule, message in PYTHON_ONLY:
        if rule.search(pattern):
            return f"'{pattern}' uses {message}"
    translated = re.sub(r"\(\?<([A-Za-z_]\w*)>", r"(?P<\1>", pattern)
    translated = re.sub(r"\\k<([A-Za-z_]\w*)>", r"(?P=\1)", translated)
    python_flags = 0
    for letter in flags:
        python_flags |= PY_FLAGS.get(letter, 0)
    try:
        re.compile(translated, python_flags)
    except re.error as error:
        return f"'{pattern}' does not compile ({error})"
    return None


def integer(raw: str) -> int | None:
    return int(raw) if re.fullmatch(r"\d+", raw) else None


def flow_problems(label: str, raw: str) -> list[str]:
    try:
        step = flow_map(raw)
    except ValueError as error:
        return [f"{label}: {error}"]
    problems: list[str] = []
    if not step.get("tool"):
        problems.append(f"{label} has no tool")
    if "input_match" in step:
        problem = pattern_problem(step["input_match"])
        if problem:
            problems.append(f"{label} input_match {problem}")
    return problems


def grader_problems(text: str) -> list[str]:
    try:
        fields, _ = frontmatter(text)
    except ValueError as error:
        return [str(error)]
    kind = fields.get("type", "")
    if kind not in GRADER_TYPES:
        return [f"type '{kind}' is not one of {', '.join(GRADER_TYPES)}"]
    problems: list[str] = []
    try:
        values = {key: scalar(value) for key, value in fields.items()
                  if key not in ("before", "after")}
    except ValueError as error:
        return [str(error)]
    if kind == "tool_used":
        if not values.get("tool"):
            problems.append("tool_used has no tool")
        if "input_match" in values:
            problem = pattern_problem(values["input_match"])
            if problem:
                problems.append(f"input_match {problem}")
        bounds: dict[str, int] = {}
        for key in ("min", "max"):
            if key in values:
                number = integer(values[key])
                if number is None:
                    problems.append(f"{key} '{values[key]}' is not an integer")
                else:
                    bounds[key] = number
        if "min" in bounds and "max" in bounds and bounds["min"] > bounds["max"]:
            problems.append("min is greater than max")
    elif kind == "tool_order":
        for side in ("before", "after"):
            if side not in fields:
                problems.append(f"tool_order has no {side}")
            else:
                problems.extend(flow_problems(side, fields[side]))
    elif kind == "regex":
        if not values.get("pattern"):
            problems.append("regex has no pattern")
        else:
            problem = pattern_problem(values["pattern"], values.get("flags", ""))
            if problem:
                problems.append(f"pattern {problem}")
        match = values.get("match")
        if match is not None and match not in ("contains", "not_contains") \
                and not re.fullmatch(r"count:\d+", match):
            problems.append(f"match '{match}' is not contains, not_contains or count:N")
    return problems


@dataclass
class Case:
    name: str
    folder: Path
    rel: str
    suite: str
    skill: str | None
    scaffolded: bool
    ui_fixtures: list[str] = field(default_factory=list)
    points_at: str | None = None


def load_json(path: Path, default):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_depends(repo: str | Path) -> dict:
    return load_json(Path(repo) / "evals" / "depends.json", {})


def load_passes(repo: str | Path) -> dict:
    return load_json(Path(repo) / "evals" / "passes.json", {})


def find_cases(repo: str | Path, depends: dict) -> list[Case]:
    root = Path(repo) / "evals" / "cases"
    near_misses = depends.get("near_misses", {})
    cases: list[Case] = []
    if not root.is_dir():
        return cases
    for prompt in sorted(root.glob("*/*/prompt.md")):
        folder = prompt.parent
        group = folder.parent.name
        fields, _ = frontmatter(prompt.read_text(encoding="utf-8"))
        name = scalar(fields.get("name", ""))
        trigger = group == "trigger"
        if trigger:
            match = TRIGGER_NAME.match(folder.name)
            skill = match.group("skill") if match else None
        else:
            skill = group
        scaffold = folder / "scaffold.sh"
        fixtures: list[str] = []
        if scaffold.is_file():
            fixtures = re.findall(r"^\s*ui_fixture\s+(\S+)",
                                  scaffold.read_text(encoding="utf-8"), re.MULTILINE)
        cases.append(Case(
            name=name, folder=folder, rel=f"evals/cases/{group}/{folder.name}",
            suite="trigger" if trigger else "behaviour", skill=skill,
            scaffolded=scaffold.is_file(), ui_fixtures=fixtures,
            points_at=near_misses.get(folder.name) if trigger else None))
    return cases


def case_paths(case: Case, depends: dict) -> list[str]:
    paths = [case.rel + "/"]
    if case.suite == "behaviour":
        paths.extend(depends.get("every_behaviour_case", []))
        paths.extend(depends.get("skills", {}).get(case.skill or "", []))
    if case.scaffolded:
        paths.append(FIXTURE)
    paths.extend(f"{FIXTURE_UI}{name}/" for name in case.ui_fixtures)
    return paths


def reaches(case: Case, path: str, depends: dict) -> bool:
    for prefix in case_paths(case, depends):
        if prefix == FIXTURE and path.startswith(FIXTURE_UI):
            continue
        if prefix.endswith("/"):
            if path.startswith(prefix):
                return True
        elif path == prefix:
            return True
    return False


def case_skill_frontmatters(case: Case) -> list[str]:
    if case.suite != "trigger":
        return []
    skills = [case.skill] if case.skill else []
    if case.points_at:
        skills.append(case.points_at)
    return skills


def changed_paths(repo: str | Path, commit: str,
                  cache: dict | None = None) -> set[str] | None:
    key = (str(repo), commit)
    if cache is not None and key in cache:
        return cache[key]
    try:
        git(repo, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}")
    except GitError:
        result = None
    else:
        diff = git(repo, "diff", "--name-only", "--no-renames", "-z", commit, "--")
        untracked = git(repo, "ls-files", "--others", "--exclude-standard", "-z")
        result = {path for path in (diff + "\0" + untracked).split("\0") if path}
    if cache is not None:
        cache[key] = result
    return result


def frontmatter_changed(repo: str | Path, commit: str, skill: str) -> bool:
    relative = f"skills/{skill}/SKILL.md"
    path = Path(repo) / relative
    if not path.is_file():
        return True
    try:
        old = git(repo, "show", f"{commit}:{relative}")
    except GitError:
        return True
    return frontmatter_block(old) != frontmatter_block(path.read_text(encoding="utf-8"))


def reason_for(repo: str | Path, case: Case, record: dict | None, depends: dict,
               cache: dict, release: bool) -> str | None:
    if not record or not record.get("commit"):
        return "no recorded pass"
    commit = record["commit"]
    changed = changed_paths(repo, commit, cache)
    if changed is None:
        return f"recorded commit {commit[:7]} is not in this clone"
    for path in sorted(changed):
        if reaches(case, path, depends):
            return f"{path} since {commit[:7]}"
    for skill in case_skill_frontmatters(case):
        if frontmatter_changed(repo, commit, skill):
            return f"skills/{skill}/SKILL.md front matter since {commit[:7]}"
    if release and case.suite == "trigger":
        return "release"
    return None


def select(repo: str | Path, release: bool = False) -> dict[str, list[tuple[str, str]]]:
    git(repo, "rev-parse", "--git-dir")
    depends = load_depends(repo)
    passes = load_passes(repo)
    cache: dict = {}
    selection: dict[str, list[tuple[str, str]]] = {"behaviour": [], "trigger": []}
    for case in sorted(find_cases(repo, depends), key=lambda c: c.name):
        reason = reason_for(repo, case, passes.get(case.name), depends, cache, release)
        if reason:
            selection[case.suite].append((case.name, reason))
    return selection


def case_globs(selected: set[str], suite_names: list[str], prefixes: list[str]) -> list[str]:
    if not selected:
        return []
    if selected >= set(suite_names):
        return [""]
    globs: list[str] = []
    remaining = set(selected)
    for prefix in prefixes:
        group = [name for name in suite_names if name.startswith(prefix)]
        if len(group) > 1 and set(group) <= remaining:
            globs.append(prefix + "*")
            remaining -= set(group)
    globs.extend(sorted(remaining))
    return globs


def command_for(suite: str, glob: str, scaffold: bool) -> str:
    case = f' --case "{glob}"' if glob else ""
    if suite == "behaviour":
        return (f"TMPDIR=$HOME/ev claude plugin eval . --tag behaviour{case} --runs 1 "
                "--ablation none --scaffold --allow-tools Bash Write Edit --trust-plugin "
                "--no-publish -j 3 --judge-model sonnet --max-cost-usd 25")
    extra = " --scaffold" if scaffold else ""
    return (f"claude plugin eval . --tag trigger{case} --ablation none --runs 1{extra} "
            "--trust-plugin --no-publish -j 4")


def commands(selection: dict[str, list[tuple[str, str]]], cases: list[Case]) -> list[str]:
    lines: list[str] = []
    for suite in ("behaviour", "trigger"):
        in_suite = [case for case in cases if case.suite == suite]
        names = sorted(case.name for case in in_suite)
        selected = {name for name, _ in selection.get(suite, [])}
        skills = sorted({case.skill for case in in_suite if case.skill})
        prefixes = [(f"trigger-{skill}-" if suite == "trigger" else f"{skill}-")
                    for skill in skills]
        for glob in case_globs(selected, names, prefixes):
            covered = [case for case in in_suite
                       if not glob or fnmatch.fnmatchcase(case.name, glob)]
            lines.append(command_for(suite, glob, any(case.scaffolded for case in covered)))
    return lines


def run_clean(run: dict) -> bool:
    return (run.get("score") == 1 and run.get("error") is None
            and not run.get("skippedPaidGraders"))


def record(repo: str | Path, result_paths: list[str | Path]) -> tuple[dict[str, dict], list[str]]:
    depends = load_depends(repo)
    cases = {case.name: case for case in find_cases(repo, depends)}
    head = git(repo, "rev-parse", "HEAD").strip()
    cache: dict = {}
    dirty = changed_paths(repo, head, cache) or set()
    recorded: dict[str, dict] = {}
    refused: list[str] = []
    for result_path in result_paths:
        data = json.loads(Path(result_path).read_text(encoding="utf-8"))
        if data.get("schemaVersion") != 1:
            refused.append(f"{result_path}: schemaVersion {data.get('schemaVersion')} is not 1")
            continue
        date = str(data.get("startedAt", ""))[:10]
        for entry in data.get("cases", []):
            name = entry.get("name", "")
            runs = entry.get("arms", {}).get("with", [])
            if not runs or not all(run_clean(run) for run in runs):
                continue
            case = cases.get(name)
            if case is None:
                refused.append(f"{name}: no such case on disk")
                continue
            moved = next((path for path in sorted(dirty) if reaches(case, path, depends)), None)
            if moved is None:
                moved = next((f"skills/{skill}/SKILL.md front matter"
                              for skill in case_skill_frontmatters(case)
                              if frontmatter_changed(repo, head, skill)), None)
            if moved:
                refused.append(f"{name}: {moved} differs from HEAD, commit first")
                continue
            recorded[name] = {"commit": head, "date": date, "runs": len(runs)}
    return recorded, refused


def write_passes(repo: str | Path, passes: dict[str, dict]) -> None:
    if passes:
        rows = [f"  {json.dumps(name)}: {json.dumps(passes[name])}" for name in sorted(passes)]
        text = "{\n" + ",\n".join(rows) + "\n}\n"
    else:
        text = "{}\n"
    target = Path(repo) / "evals" / "passes.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=target.parent, prefix="passes-", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temp, target)
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise


def print_selection(repo: str, release: bool) -> None:
    selection = select(repo, release)
    cases = find_cases(repo, load_depends(repo))
    for suite in ("behaviour", "trigger"):
        total = sum(1 for case in cases if case.suite == suite)
        print(f"{suite}: {len(selection[suite])} of {total} cases")
        for name, reason in selection[suite]:
            print(f"  {name}: {reason}")
    lines = commands(selection, cases)
    print()
    if not lines:
        print("nothing to run")
        return
    for line in lines:
        print(line)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pick and record the evals a change can reach.")
    sub = parser.add_subparsers(dest="action", required=True)
    pick = sub.add_parser("select")
    pick.add_argument("--release", action="store_true")
    pick.add_argument("--repo", default=".")
    keep = sub.add_parser("record")
    keep.add_argument("results", nargs="+")
    keep.add_argument("--repo", default=".")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        if args.action == "select":
            print_selection(args.repo, args.release)
            return 0
        recorded, refused = record(args.repo, args.results)
        if recorded:
            passes = load_passes(args.repo)
            passes.update(recorded)
            write_passes(args.repo, passes)
        for name in sorted(recorded):
            print(f"recorded {name}")
        for problem in refused:
            print(f"refused {problem}")
        return 1 if refused else 0
    except GitError as error:
        print(f"eval_select {args.action}: {error}")
        return 2
    except (OSError, ValueError) as error:
        print(f"eval_select {args.action}: {error}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
