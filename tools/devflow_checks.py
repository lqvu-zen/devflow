from __future__ import annotations

import argparse
import fnmatch
import io
import json
import os
import re
import subprocess
import sys
import tokenize
from collections import Counter
from typing import Any, Mapping, NamedTuple
from urllib.parse import unquote

RELEASE_TITLE = re.compile(r"^Release candidate (\d+\.\d+\.\d+-rc\d+)$|^Release (\d+\.\d+\.\d+)$")
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
VERSIONS_RULE = "(.claude/devflow.md, Release)"
COMMENTS_RULE = "(.claude/devflow.md, Architecture rules)"
DIRECTIVE = re.compile(r"#\s*(noqa|type:\s*ignore|pragma|pyright:|mypy:|ruff:|fmt:)", re.IGNORECASE)
CODING = re.compile(r"^#.*coding[:=]\s*[-\w.]+")
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
ATTRIBUTION_RULE = "(.claude/devflow.json, attribution)"
CLAUDE_TRAILER = re.compile(r"^[ \t]*co-authored-by:.*(?:(?<![\w-])claude\b|noreply@anthropic\.com)",
                            re.IGNORECASE | re.MULTILINE)
GENERATED_LINE = re.compile(r"^[ \t]*(?:\U0001F916\ufe0f?[ \t]*)?generated with \[?claude code",
                            re.IGNORECASE | re.MULTILINE)
DOCS_DIR = "docs/architecture"
ANCHORS_RULE = "(docs/architecture/README.md, Writing rules)"
ROUTING_SECTION = "When to read an area's doc first"
ROUTING_HEADING = re.compile(r"^#{1,6}[ \t]+When to read an area's doc first[ \t]*$")
ANY_HEADING = re.compile(r"^#{1,6}[ \t]")
FENCE = re.compile(r"^[ \t]*(```|~~~)")
CODE_LINK = re.compile(r"\[`([^`]+)`\]\(([^)\s]+)\)")
LINE_FRAGMENT = re.compile(r"#L\d+(?:-L?\d+)?")
FILE_LINE = re.compile(r"[\w./-]+\.[A-Za-z0-9]+:\d+(?:-\d+)?")
LINE_FRAGMENT_ONLY = re.compile(r"^L\d+(?:-L?\d+)?$")
FILE_LINE_TARGET = re.compile(r":\d+(?:-\d+)?$")
URL_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
BACKTICKS = re.compile(r"`([^`]+)`")
DOCS_UNAFFECTED = re.compile(r"^Docs-unaffected:[ \t]+(\S+\.md)[ \t]+-[ \t]+\S", re.MULTILINE)


class GitError(Exception):
    pass


class VersionFile(NamedTuple):
    path: str
    pattern: re.Pattern
    numbers_only: bool


class Checks(NamedTuple):
    version_files: tuple[VersionFile, ...]
    comment_dirs: tuple[str, ...]
    default_base: str
    no_attribution: bool
    docs_routing: str | None = None


class Route(NamedTuple):
    patterns: tuple[str, ...]
    doc: str


def checks_from(config: Mapping[str, Any]) -> Checks:
    section = config.get("checks") if isinstance(config.get("checks"), Mapping) else {}
    files: list[VersionFile] = []
    for item in section.get("version_files") or []:
        if isinstance(item, Mapping) and isinstance(item.get("path"), str) \
                and isinstance(item.get("pattern"), str):
            files.append(VersionFile(item["path"], re.compile(item["pattern"], re.MULTILINE),
                                     bool(item.get("numbers_only"))))
    dirs = tuple(d.replace("\\", "/") for d in section.get("no_new_python_comments") or []
                 if isinstance(d, str) and d)
    branch = config.get("main_branch") if isinstance(config.get("main_branch"), str) else "main"
    routing = section.get("docs_routing")
    routing = routing.replace("\\", "/") if isinstance(routing, str) and routing else None
    return Checks(tuple(files), dirs, f"origin/{branch}", config.get("attribution") == "none", routing)


def load_config(repo: str) -> dict:
    path = os.path.join(repo, ".claude", "devflow.json")
    with open(path, encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must hold a JSON object")
    return data


def git(repo: str, *args: str) -> str:
    result = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise GitError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def _sha(repo: str, ref: str) -> str | None:
    try:
        return git(repo, "rev-parse", "--verify", "--quiet", ref + "^{commit}").strip() or None
    except GitError:
        return None


def _merge_base(repo: str, a: str, b: str) -> str | None:
    try:
        return git(repo, "merge-base", a, b).strip() or None
    except GitError:
        return None


def commit_range(repo: str, base: str | None, head: str, default: str = "origin/main") -> str | None:
    head_sha = _sha(repo, head)
    if head_sha is None:
        raise GitError(f"unknown head {head}")
    if base and base.strip("0") and _sha(repo, base):
        start = _merge_base(repo, base, head_sha)
        if start:
            return start
    start = _merge_base(repo, default, head_sha) if _sha(repo, default) else None
    if start and start != head_sha:
        return start
    return _sha(repo, head_sha + "^")


def commits_in(repo: str, start: str | None, head: str) -> list[str]:
    span = f"{start}..{head}" if start else head
    return git(repo, "rev-list", "--no-merges", "--reverse", span).split()


def version_of(text: str, file: VersionFile) -> str | None:
    match = file.pattern.search(text)
    return match.group(1) if match else None


def _show(repo: str, commit: str, path: str) -> str | None:
    if not git(repo, "ls-tree", "--full-tree", "--name-only", commit, "--", path).strip():
        return None
    return git(repo, "show", f"{commit}:{path}")


def _first_parent(repo: str, commit: str) -> str | None:
    parents = git(repo, "rev-list", "--parents", "-n", "1", commit).split()[1:]
    return parents[0] if parents else None


def version_changes(repo: str, commit: str,
                    files: tuple[VersionFile, ...]) -> dict[str, tuple[str | None, str | None]]:
    paths = [f.path for f in files]
    touched = set(git(repo, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r",
                      commit, "--", *paths).split())
    parent = _first_parent(repo, commit)
    changes: dict[str, tuple[str | None, str | None]] = {}
    for file in files:
        if file.path not in touched:
            continue
        old_text = _show(repo, parent, file.path) if parent else None
        new_text = _show(repo, commit, file.path)
        old = version_of(old_text, file) if old_text is not None else None
        new = version_of(new_text, file) if new_text is not None else None
        if old != new:
            changes[file.path] = (old, new)
    return changes


def _title(repo: str, commit: str) -> str:
    return git(repo, "log", "-1", "--format=%s", commit).strip()


def _short_title(title: str) -> str:
    return title if len(title) <= 50 else title[:49] + "…"


def _release_problem(repo: str, commit: str, label: str, file: VersionFile, expected: str,
                     changed: bool) -> str | None:
    text = _show(repo, commit, file.path)
    if text is None:
        return f"{label} has no {file.path}; it should say {expected} {VERSIONS_RULE}"
    value = version_of(text, file)
    if value is None:
        return (f"{label} has no version in {file.path} that its pattern matches; it should say "
                f"{expected} {VERSIONS_RULE}")
    if value == expected:
        return None
    if changed:
        return f"{label} sets the version in {file.path} to {value}, not {expected} {VERSIONS_RULE}"
    return f"{label} leaves the version in {file.path} at {value}, not {expected} {VERSIONS_RULE}"


def version_problems_in(repo: str, commits: list[str],
                        files: tuple[VersionFile, ...]) -> list[str]:
    if not files:
        return []
    problems: list[str] = []
    for commit in commits:
        changes = version_changes(repo, commit, files)
        title = _title(repo, commit)
        match = RELEASE_TITLE.match(title)
        label = f'{commit[:7]} "{_short_title(title)}"'
        if not match:
            if not changes:
                continue
            for path, (old, new) in changes.items():
                problems.append(f'{label} changes the version in {path} {old} -> {new}: only '
                                f'"Release candidate X.Y.Z-rcN" or "Release X.Y.Z" may '
                                f'{VERSIONS_RULE}')
            continue
        wanted = match.group(1) or match.group(2)
        numbers = re.sub(r"-rc\d+$", "", wanted)
        parent = _first_parent(repo, commit)
        for file in files:
            if _show(repo, commit, file.path) is None and (
                    parent is None or _show(repo, parent, file.path) is None):
                continue
            expected = numbers if file.numbers_only else wanted
            problem = _release_problem(repo, commit, label, file, expected, file.path in changes)
            if problem:
                problems.append(problem)
    return problems


def _message(repo: str, commit: str) -> str:
    return git(repo, "log", "-1", "--format=%B", commit).replace("\r", "")


def attribution_lines(message: str) -> list[str]:
    lines = message.replace("\r", "").splitlines()
    return [line.strip() for line in lines
            if CLAUDE_TRAILER.match(line) or GENERATED_LINE.match(line)]


def attribution_problems_in(repo: str, commits: list[str], off: bool) -> list[str]:
    if not off:
        return []
    problems: list[str] = []
    for commit in commits:
        found = attribution_lines(_message(repo, commit))
        if not found:
            continue
        label = f'{commit[:7]} "{_short_title(_title(repo, commit))}"'
        for line in found:
            problems.append(f'{label} carries "{line}", but .claude/devflow.json sets '
                            f'"attribution": "none" {ATTRIBUTION_RULE}')
    return problems


def comment_tokens(source: str) -> list[tuple[int, str]]:
    found = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            found.append((token.start[0], token.string))
    return found


def is_directive(text: str, line: int) -> bool:
    if line == 1 and text.startswith("#!"):
        return True
    if line <= 2 and CODING.match(text):
        return True
    return bool(DIRECTIVE.match(text))


def _hunks(diff: str) -> tuple[set[int], set[int]]:
    removed: set[int] = set()
    added: set[int] = set()
    for line in diff.splitlines():
        match = HUNK.match(line)
        if not match:
            continue
        old_start, old_count = int(match.group(1)), int(match.group(2) or "1")
        new_start, new_count = int(match.group(3)), int(match.group(4) or "1")
        removed.update(range(old_start, old_start + old_count))
        added.update(range(new_start, new_start + new_count))
    return removed, added


def _diff_lines(repo: str, start: str | None, head: str, path: str) -> tuple[set[int], set[int]]:
    diff = git(repo, "diff", "-U0", "--no-renames", start or EMPTY_TREE, head, "--", path)
    return _hunks(diff)


def _changed_python(repo: str, start: str | None, head: str) -> list[tuple[str, str]]:
    out = git(repo, "diff", "--name-status", "--no-renames", start or EMPTY_TREE, head)
    changed = []
    for line in out.splitlines():
        status, _, path = line.partition("\t")
        if path.endswith(".py"):
            changed.append((status[:1], path))
    return changed


def comment_problems_in(repo: str, start: str | None, head: str,
                        dirs: tuple[str, ...]) -> list[str]:
    if not dirs:
        return []
    changed = _changed_python(repo, start, head)
    removed: Counter[str] = Counter()
    if start:
        for status, path in changed:
            if status not in ("M", "D"):
                continue
            old = _show(repo, start, path)
            if old is None:
                continue
            lines = _diff_lines(repo, start, head, path)[0]
            try:
                tokens = comment_tokens(old)
            except (tokenize.TokenError, SyntaxError):
                continue
            removed.update(text.strip() for line, text in tokens if line in lines)
    problems: list[str] = []
    for status, path in changed:
        if status not in ("A", "M") or not path.startswith(dirs):
            continue
        new = _show(repo, head, path)
        if new is None:
            continue
        lines = _diff_lines(repo, start, head, path)[1]
        try:
            tokens = comment_tokens(new)
        except (tokenize.TokenError, SyntaxError) as error:
            problems.append(f"{path}: could not read its tokens ({error})")
            continue
        for line, text in tokens:
            if line not in lines or is_directive(text, line):
                continue
            key = text.strip()
            if removed[key] > 0:
                removed[key] -= 1
                continue
            problems.append(f'{path}:{line}: new comment "{key}" {COMMENTS_RULE}')
    return problems


def _cells(line: str) -> list[str]:
    row = line.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [cell.strip() for cell in row.split("|")]


def _routing_rows(text: str) -> list[str]:
    lines = text.replace("\r", "").split("\n")
    start = next((index for index, line in enumerate(lines) if ROUTING_HEADING.match(line)), None)
    if start is None:
        return []
    rows: list[str] = []
    for line in lines[start + 1:]:
        if ANY_HEADING.match(line):
            break
        if line.lstrip().startswith("|"):
            rows.append(line)
        elif rows:
            break
    return rows


def routes_in(text: str) -> list[Route]:
    rows = _routing_rows(text)
    if len(rows) < 2:
        return []
    header = [cell.lower() for cell in _cells(rows[0])]
    if "paths" not in header or "doc" not in header:
        return []
    paths_at, doc_at = header.index("paths"), header.index("doc")
    routes: list[Route] = []
    for row in rows[2:]:
        cells = _cells(row)
        if max(paths_at, doc_at) >= len(cells):
            continue
        patterns = tuple(span.strip().lstrip("/") for span in BACKTICKS.findall(cells[paths_at])
                         if span.strip().lstrip("/"))
        docs = [span.strip().lstrip("/") for span in BACKTICKS.findall(cells[doc_at])]
        if patterns and docs and docs[0]:
            routes.append(Route(patterns, docs[0]))
    return routes


def _routed(path: str, pattern: str) -> bool:
    if pattern.endswith("/"):
        return path.startswith(pattern)
    return fnmatch.fnmatchcase(path, pattern)


def doc_paths(repo: str, names: list[str]) -> tuple[list[str], list[str]]:
    if not names:
        folder = os.path.join(repo, *DOCS_DIR.split("/"))
        if not os.path.isdir(folder):
            return [], []
        return sorted(f"{DOCS_DIR}/{name}" for name in os.listdir(folder)
                      if name.endswith(".md") and os.path.isfile(os.path.join(folder, name))), []
    found: list[str] = []
    problems: list[str] = []
    for name in names:
        clean = name.replace("\\", "/")
        path = clean if "/" in clean else f"{DOCS_DIR}/{clean}"
        if os.path.isfile(os.path.join(repo, *path.split("/"))):
            found.append(path)
        else:
            problems.append(f"{path}: no such doc {ANCHORS_RULE}")
    return found, problems


def _inside(root: str, path: str) -> bool:
    try:
        return os.path.commonpath([root, path]) == root
    except ValueError:
        return False


def _symbol_problem(repo: str, doc: str, where: str, symbol: str, target: str) -> str | None:
    path, _, fragment = target.partition("#")
    if LINE_FRAGMENT_ONLY.match(fragment) or FILE_LINE_TARGET.search(path):
        return f'{where}: line anchor "{target}"; anchor by symbol {ANCHORS_RULE}'
    root = os.path.realpath(repo)
    path = unquote(path)
    if path.startswith("/"):
        full = os.path.join(root, *path.lstrip("/").split("/"))
    else:
        full = os.path.join(root, *doc.split("/")[:-1], *path.split("/"))
    full = os.path.realpath(full)
    if not _inside(root, full):
        return f"{where}: [`{symbol}`] names {path}, which is outside the repo {ANCHORS_RULE}"
    shown = os.path.relpath(full, root).replace("\\", "/")
    if not os.path.isfile(full):
        return f"{where}: [`{symbol}`] names {shown}, which does not exist {ANCHORS_RULE}"
    with open(full, encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    name = symbol.strip()
    if name.endswith("()"):
        name = name[:-2]
    name = name.rsplit(".", 1)[-1]
    if not name or name not in text:
        return f'{where}: {shown} has no "{symbol}" {ANCHORS_RULE}'
    return None


def _line_anchor_problems(where: str, text: str) -> list[str]:
    found = [*LINE_FRAGMENT.finditer(text), *FILE_LINE.finditer(text)]
    return [f'{where}: line anchor "{match.group(0)}"; anchor by symbol {ANCHORS_RULE}'
            for match in sorted(found, key=lambda match: match.start())]


def anchor_problems(repo: str, names: list[str]) -> tuple[list[str], int]:
    docs, problems = doc_paths(repo, names)
    count = 0
    for doc in docs:
        with open(os.path.join(repo, *doc.split("/")), encoding="utf-8-sig", errors="replace") as handle:
            lines = handle.read().replace("\r", "").split("\n")
        fence = None
        for number, line in enumerate(lines, 1):
            marker = FENCE.match(line)
            if fence:
                if marker and marker.group(1) == fence:
                    fence = None
                continue
            if marker:
                fence = marker.group(1)
                continue
            where = f"{doc}:{number}"
            rest = line
            for link in CODE_LINK.finditer(line):
                symbol, target = link.group(1), link.group(2)
                if URL_SCHEME.match(target):
                    continue
                count += 1
                rest = rest.replace(link.group(0), " ", 1)
                problem = _symbol_problem(repo, doc, where, symbol, target)
                if problem:
                    problems.append(problem)
            problems.extend(_line_anchor_problems(where, rest))
    return problems, count


def _changed_in(repo: str, commit: str) -> list[str]:
    out = git(repo, "-c", "core.quotepath=false", "diff-tree", "--root", "--no-commit-id",
              "--name-only", "-r", "--no-renames", commit)
    return [line for line in out.splitlines() if line]


def _doc_name(path: str) -> str:
    return path.replace("\\", "/").rsplit("/", 1)[-1]


def docs_problems_in(repo: str, commits: list[str], routing: str | None) -> list[str]:
    if not routing:
        return []
    problems: list[str] = []
    for commit in commits:
        table = _show(repo, commit, routing)
        routes = routes_in(table) if table is not None else []
        if not routes:
            continue
        changed = _changed_in(repo, commit)
        excused: set[str] | None = None
        for route in routes:
            if route.doc in changed:
                continue
            hit = next((path for path in changed
                        if any(_routed(path, pattern) for pattern in route.patterns)), None)
            if hit is None:
                continue
            if excused is None:
                excused = {_doc_name(name) for name in DOCS_UNAFFECTED.findall(_message(repo, commit))}
            name = _doc_name(route.doc)
            if name in excused:
                continue
            label = f'{commit[:7]} "{_short_title(_title(repo, commit))}"'
            problems.append(f'{label} changes {hit} (routed to {route.doc}) but not {route.doc}, '
                            f'and has no "Docs-unaffected: {name} - <why>" line '
                            f'({routing}, {ROUTING_SECTION})')
    return problems


def _anchors(repo: str, names: list[str]) -> int:
    try:
        problems, count = anchor_problems(repo, names)
        docs = len(doc_paths(repo, names)[0])
    except OSError as error:
        print(f"devflow_checks anchors: {error}")
        return 1
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print(f"anchors: ok ({docs} docs, {count} anchors)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="devflow process checks for CI.")
    parser.add_argument("check", choices=("version", "comments", "attribution", "anchors", "docs"))
    parser.add_argument("names", nargs="*", help="anchors only: the docs to check")
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--repo", default=".")
    args = parser.parse_intermixed_args(argv)
    if args.names and args.check != "anchors":
        parser.error(f"only anchors takes doc names, not {args.check}")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if args.check == "anchors":
        return _anchors(args.repo, args.names)
    try:
        checks = checks_from(load_config(args.repo))
        start = commit_range(args.repo, args.base or None, args.head, checks.default_base)
        commits = commits_in(args.repo, start, args.head)
        if args.check == "version":
            problems = version_problems_in(args.repo, commits, checks.version_files)
        elif args.check == "attribution":
            problems = attribution_problems_in(args.repo, commits, checks.no_attribution)
        elif args.check == "docs":
            problems = docs_problems_in(args.repo, commits, checks.docs_routing)
        else:
            problems = comment_problems_in(args.repo, start, args.head, checks.comment_dirs)
    except (GitError, OSError, ValueError) as error:
        print(f"devflow_checks {args.check}: {error}")
        return 1
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print(f"{args.check}: ok ({len(commits)} commits)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
