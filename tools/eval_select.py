from __future__ import annotations

import argparse
import datetime
import fnmatch
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

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
    (re.compile(r"(?:^|[^\\])(?:\\\\)*\(\?\("), "a conditional (?( that JavaScript lacks"),
)
BRACE_QUANTIFIER = re.compile(r"\{\d+(?:,\d*)?\}")


def has_possessive_quantifier(pattern: str) -> bool:
    index = 0
    in_class = False
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            index += 2
            continue
        if in_class:
            in_class = char != "]"
        elif char == "[":
            in_class = True
        elif char in "*+?":
            if pattern[index + 1:index + 2] == "+":
                return True
        elif char == "{":
            match = BRACE_QUANTIFIER.match(pattern, index)
            if match:
                if pattern[match.end():match.end() + 1] == "+":
                    return True
                index = match.end()
                continue
        index += 1
    return False


def pattern_problem(pattern: str, flags: str = "") -> str | None:
    if not JS_FLAGS.match(flags):
        return f"flags '{flags}' are not among dgimsuvy"
    for rule, message in PYTHON_ONLY:
        if rule.search(pattern):
            return f"'{pattern}' uses {message}"
    if has_possessive_quantifier(pattern):
        return f"'{pattern}' uses a possessive quantifier that JavaScript lacks"
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
        try:
            fields, _ = frontmatter(prompt.read_text(encoding="utf-8"))
        except ValueError as error:
            raise ValueError(f"{prompt}: {error}") from error
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


def case_paths(case: Case, depends: dict, every: bool = True) -> list[str]:
    paths = [case.rel + "/"]
    if case.suite == "behaviour":
        if every:
            paths.extend(depends.get("every_behaviour_case", []))
        paths.extend(depends.get("skills", {}).get(case.skill or "", []))
    if case.scaffolded:
        paths.append(FIXTURE)
    paths.extend(f"{FIXTURE_UI}{name}/" for name in case.ui_fixtures)
    return paths


def reaches(case: Case, path: str, depends: dict) -> bool:
    groups = depends.get("hook_files", {}).get(path)
    mapped = case.suite == "behaviour" and groups is not None
    if mapped and case.skill in groups:
        return True
    for prefix in case_paths(case, depends, every=not mapped):
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


def skill_path(repo: str | Path, skill: str) -> str:
    root = f"skills/{skill}/SKILL.md"
    if (Path(repo) / root).is_file():
        return root
    found = sorted((Path(repo) / "plugins").glob(f"*/skills/{skill}/SKILL.md"))
    if found:
        return found[0].relative_to(repo).as_posix()
    return root


def frontmatter_changed(repo: str | Path, commit: str, skill: str) -> bool:
    relative = skill_path(repo, skill)
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
            return f"{skill_path(repo, skill)} front matter since {commit[:7]}"
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


def command_for(suite: str, glob: str, scaffold: bool, runs: int = 1) -> str:
    case = f' --case "{glob}"' if glob else ""
    if suite == "behaviour":
        return (f"TMPDIR=$HOME/ev claude plugin eval . --tag behaviour{case} --runs {runs} "
                "--ablation none --scaffold --allow-tools Bash Write Edit --trust-plugin "
                "--no-publish -j 2 --judge-model sonnet --max-cost-usd 25")
    extra = " --scaffold" if scaffold else ""
    return (f"claude plugin eval . --tag trigger{case} --ablation none --runs {runs}{extra} "
            "--trust-plugin --no-publish -j 2")


def commands(selection: dict[str, list[tuple[str, str]]], cases: list[Case],
             runs: int = 1) -> list[str]:
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
            lines.append(command_for(suite, glob, any(case.scaffolded for case in covered), runs))
    return lines


def unfinished_reason(runs: list[dict]) -> str | None:
    if not runs:
        return "no runs"
    for number, item in enumerate(runs, 1):
        if item.get("error") is not None:
            return f"run {number} has an error"
        if item.get("skippedPaidGraders"):
            return f"run {number} skipped paid graders"
    return None


def listed(items: list[str]) -> str:
    return " and ".join([", ".join(items[:-1]), items[-1]]) if len(items) > 1 else items[0]


def case_verdict(runs: list[dict], suite: str) -> tuple[str, str | None]:
    reason = unfinished_reason(runs)
    if reason:
        return "skipped", reason
    failed = [(str(number), str(item.get("score")))
              for number, item in enumerate(runs, 1) if item.get("score") != 1]
    if not failed:
        return "kept", None
    first = f"run {failed[0][0]} scored {failed[0][1]}"
    if suite == "trigger":
        return "skipped", first
    if len(failed) > 1:
        numbers, scores = (listed(list(column)) for column in zip(*failed))
        return "failing", f"runs {numbers} scored {scores}"
    if len(runs) - len(failed) >= 2:
        return "retried", first
    return "rerun", first


def started_date(data: dict) -> str | None:
    text = data.get("startedAt")
    if not isinstance(text, str):
        return None
    if not re.match(r"^\d{4}-\d{2}-\d{2}(?:$|[T ])", text):
        return None
    try:
        datetime.date.fromisoformat(text[:10])
    except ValueError:
        return None
    return text[:10]


class RecordResult(NamedTuple):
    recorded: dict[str, dict]
    refused: list[str]
    skipped: list[str]
    retried: dict[str, str]
    reruns: list[tuple[str, str]]
    failing: list[str]


def record(repo: str | Path, result_paths: list[str | Path]) -> RecordResult:
    depends = load_depends(repo)
    cases = {case.name: case for case in find_cases(repo, depends)}
    head = git(repo, "rev-parse", "HEAD").strip()
    cache: dict = {}
    dirty = changed_paths(repo, head, cache) or set()
    result = RecordResult({}, [], [], {}, [], [])
    gathered: dict[str, list[dict]] = {}
    dates: dict[str, str] = {}
    for result_path in result_paths:
        data = json.loads(Path(result_path).read_text(encoding="utf-8"))
        if data.get("schemaVersion") != 1:
            result.refused.append(
                f"{result_path}: schemaVersion {data.get('schemaVersion')} is not 1")
            continue
        date = started_date(data)
        if date is None:
            result.refused.append(
                f"{result_path}: startedAt {data.get('startedAt')!r} is not YYYY-MM-DD")
            continue
        for entry in data.get("cases", []):
            name = entry.get("name", "")
            gathered.setdefault(name, []).extend(entry.get("arms", {}).get("with", []))
            dates[name] = max(date, dates.get(name, date))
    for name, runs in gathered.items():
        case = cases.get(name)
        verdict, reason = case_verdict(runs, case.suite if case else "behaviour")
        if verdict == "skipped":
            result.skipped.append(f"{name}: {reason}")
            continue
        if verdict == "failing":
            result.failing.append(f"{name}: {reason}")
            continue
        if case is None:
            result.refused.append(f"{name}: no such case on disk")
            continue
        if verdict == "rerun":
            result.reruns.append((name, reason))
            continue
        moved = next((path for path in sorted(dirty) if reaches(case, path, depends)), None)
        if moved is None:
            moved = next((f"{skill_path(repo, skill)} front matter"
                          for skill in case_skill_frontmatters(case)
                          if frontmatter_changed(repo, head, skill)), None)
        if moved:
            result.refused.append(f"{name}: {moved} differs from HEAD, commit first")
            continue
        clean = sum(1 for item in runs if item.get("score") == 1)
        result.recorded[name] = {"commit": head, "date": dates[name], "runs": clean}
        if verdict == "retried":
            result.retried[name] = reason
    return result


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


def print_record(repo: str, result: RecordResult) -> None:
    for name in sorted(result.recorded):
        note = f", one run failed: {result.retried[name]}" if name in result.retried else ""
        print(f"recorded {name}{note}")
    for note in result.skipped:
        print(f"skipped {note}")
    for name, reason in result.reruns:
        print(f"rerun {name}: {reason}")
    for note in result.failing:
        print(f"failing {note}")
    for problem in result.refused:
        print(f"refused {problem}")
    if result.reruns:
        print()
        print("two more runs for each rerun case, then record the first result file "
              "and the new one together:")
        cases = find_cases(repo, load_depends(repo))
        for line in commands({"behaviour": result.reruns}, cases, runs=2):
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
        result = record(args.repo, args.results)
        if result.recorded:
            passes = load_passes(args.repo)
            passes.update(result.recorded)
            write_passes(args.repo, passes)
        print_record(args.repo, result)
        return 1 if result.refused else 0
    except GitError as error:
        print(f"eval_select {args.action}: {error}")
        return 2
    except (OSError, ValueError) as error:
        print(f"eval_select {args.action}: {error}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
