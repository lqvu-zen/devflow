from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
CUT = 20_000
MARGIN = 1_000
CEILING = CUT - MARGIN
ADD_FEATURE_ROOM = 500
MANAGE_PROJECT_ROOM = 300
STOP_RULES = "**Stop rules in the loop.**"
ADD_FEATURE = SKILLS / "add-feature" / "SKILL.md"
FIX_BUG = SKILLS / "fix-bug" / "SKILL.md"
RELEASE_PLUGIN = ROOT / "plugins" / "devflow-release"
RELEASE = RELEASE_PLUGIN / "skills" / "release" / "SKILL.md"
MANAGE_PROJECT = SKILLS / "manage-project" / "SKILL.md"
REVIEW_LIMIT = "A reviewer's BLOCKERS"
TEMPLATES = ROOT / "templates"
SETUP = SKILLS / "setup" / "SKILL.md"
DESCRIPTION_MIN = 200
DESCRIPTION_MAX = 1_536
NAME_MAX = 64
SKILL_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
BOLD_NAME = r"\*\*([A-Z][A-Za-z]*(?: [A-Za-z]+)*)\*\*"
QUOTED_NAME = r"\"([A-Z][A-Za-z ,]*)\""
CITED_NAME = rf"{BOLD_NAME}|{QUOTED_NAME}"
SECTION_CITE = re.compile(
    rf"(?:{CITED_NAME})(?:(?:, and |, | and )(?:{CITED_NAME}))*(?= (?:section|heading)s?\b)"
)
PROFILE_LINE = re.compile(r"\.claude/devflow\.md|\bprofile\b")
LEAD_IN = re.compile(r"^\s*(?:(?:[-*]|\d+\.)\s+)?\*\*[^*]+\*\*")
HEADING_LIST = re.compile(r"\.claude/devflow\.md.*exact heading")
LIST_LABEL = re.compile(rf"^- {BOLD_NAME}:")
FIXED_LIST = "Its headings are fixed:"
HEADING = re.compile(r"^(#{2,3}) (.+?)\s*$")
FIELD_LABEL = re.compile(r"^\s*- \*\*([^*]+?):\*\*")
ARGUMENT_TOKEN = re.compile(r"\$(?:ARGUMENTS|\d)")
CD_PLUGIN = re.compile(
    r"\b(?:cd|pushd|chdir|[Ss]et-[Ll]ocation)\b[^\n;&|]*?"
    r"(?:CLAUDE_PLUGIN_ROOT|CLAUDE_SKILL_DIR|<plugin>|plugin(?:'s)? (?:folder|directory|root))"
)
DEV_FILE = re.compile(r"^test-.*\.md$|creation[-_ ]?log", re.IGNORECASE)
VENDOR = "vendor"
FRONT_LINE = re.compile(r"([A-Za-z][A-Za-z0-9_-]*):(?: +(.*))?")
SINGLE_QUOTED = re.compile(r"'(?:[^']|'')*'")
DOUBLE_QUOTED = re.compile(
    r'"(?:[^"\\]|\\(?:[0abtnvfre "/\\N_LP\t]|x[0-9A-Fa-f]{2}|u[0-9A-Fa-f]{4}|U[0-9A-Fa-f]{8}))*"'
)
INDICATORS = ",[]{}#&*!|>%@`"
SPACED_INDICATORS = "-?:"
OLD_REVIEW_UI = (
    "Invoke this skill for every request to review, critique or audit how a UI looks or works; "
    "do not review a UI without it and do not read the UI files first. Triggers: \"review the UI\", "
    "\"UX review\", \"is this page any good\", \"a11y audit\", \"contrast check\". "
    "Read-only: it reports, it does not fix."
)
ANY_HEADING = re.compile(r"^#{1,6} (.+?)\s*$")
SKILL_REF = r"`(skills/)?([a-z0-9]+(?:-[a-z0-9]+)*)(?:/SKILL\.md)?`"
QUOTED = r"\"([^\"]+)\""
CROSS_CITE = re.compile(rf"{SKILL_REF}(?:'s |, | \()({QUOTED}(?:(?:, and |, | and ){QUOTED})*)")
SHARED_LIST = "the rules every skill shares"
BEFORE_YOU_START = "Before you start, and where you stop"
SHARED_RULES = {
    STOP_RULES: "Stop rules",
    "**Claim your step before anything else.**": BEFORE_YOU_START,
    "**Edit the plan one row at a time.**": BEFORE_YOU_START,
    "**Check CI on HEAD first**": BEFORE_YOU_START,
    "**Keep to the step's Files line.**": BEFORE_YOU_START,
    "**Status and plan edits.**": BEFORE_YOU_START,
    "**Stop at a `**Gate:**` line.**": BEFORE_YOU_START,
    "**Deciding without asking.**": BEFORE_YOU_START,
    "**Wait for the maintainer's yes.**": "The workflow",
}
MANAGER_OWNS = "## What you own, and what you never touch"
MANAGER_PLAN_EDIT_RULE = (
    "Edit plans with the Edit tool, a section at a time; never rewrite a plan file with Write, a script, "
    "sed or a regex. A split, move or renumbering is a series of Edits, after a copy of the file to your "
    "scratchpad."
)
LF_ONLY = re.compile(rb"(?<!\r)\n")


def _plugin_dirs(root: Path) -> list[Path]:
    plugins = root / "plugins"
    if not plugins.is_dir():
        return []
    return sorted(path for path in plugins.iterdir() if path.is_dir())


def _skill_roots(root: Path = ROOT) -> list[Path]:
    roots = [root / "skills"]
    roots += [plugin / "skills" for plugin in _plugin_dirs(root) if (plugin / "skills").is_dir()]
    return roots


def _skill_mds(root: Path = ROOT) -> list[Path]:
    found: list[Path] = []
    for skills_dir in _skill_roots(root):
        found += sorted(skills_dir.glob("*/SKILL.md"))
    return found


def _agent_files(root: Path = ROOT) -> list[Path]:
    found = sorted((root / "agents").glob("*.md"))
    for plugin in _plugin_dirs(root):
        found += sorted((plugin / "agents").glob("*.md"))
    return found


def _across_roots(check, root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for skills_dir in _skill_roots(root):
        prefix = skills_dir.relative_to(root).as_posix() + "/"
        errors += [prefix + message for message in check(skills_dir)]
    return sorted(errors)


def _reattached_text(path: Path) -> str:
    with path.open(encoding="utf-8", newline="") as handle:
        lines = handle.read().splitlines(keepends=True)
    if lines and lines[0].rstrip("\r\n") == "---":
        for index in range(1, len(lines)):
            if lines[index].rstrip("\r\n") == "---":
                return "".join(lines[index + 1:])
    return "".join(lines)


def _length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _too_long(skills_dir: Path) -> list[str]:
    found = []
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        size = _length(_reattached_text(path))
        if size >= CEILING:
            found.append(f"{path.parent.name}: {size} characters, ceiling {CEILING}")
    return sorted(found)


def _first_section(path: Path) -> tuple[str, list[str]]:
    lines = _reattached_text(path).splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith("## "))
    body = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        body.append(line)
    return lines[start], body


def _subsection(path: Path, prefix: str) -> str:
    lines = _reattached_text(path).splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith(prefix))
    body = []
    for line in lines[start + 1:]:
        if line.startswith("## ") or line.startswith("### "):
            break
        body.append(line)
    return "\n".join(body)


class TestSkillSize(unittest.TestCase):
    def test_every_skill_is_under_the_ceiling(self):
        self.assertTrue(_skill_mds())
        self.assertEqual(_across_roots(_too_long), [])

    def test_add_feature_keeps_room_to_grow(self):
        self.assertLessEqual(_length(_reattached_text(ADD_FEATURE)), CEILING - ADD_FEATURE_ROOM)

    def test_manage_project_keeps_room_to_grow(self):
        self.assertLessEqual(_length(_reattached_text(MANAGE_PROJECT)), CEILING - MANAGE_PROJECT_ROOM)

    def test_a_skill_at_the_ceiling_is_named(self):
        with tempfile.TemporaryDirectory() as temp:
            skills = Path(temp)
            (skills / "big").mkdir()
            (skills / "small").mkdir()
            with (skills / "big" / "SKILL.md").open("w", encoding="utf-8", newline="") as handle:
                handle.write("---\r\nname: big\r\n---\r\n" + "x" * (CEILING - 2) + "\r\n")
            front = "---\r\nname: small\r\ndescription: '" + "d" * 2000 + "'\r\n---\r\n"
            with (skills / "small" / "SKILL.md").open("w", encoding="utf-8", newline="") as handle:
                handle.write(front + "y" * (CEILING - 1))
            found = _too_long(skills)
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].startswith("big:"), found)


class TestPluginSkillRoots(unittest.TestCase):
    def _root(self, temp: str) -> Path:
        root = Path(temp)
        valid = "d" * 300
        _skill(root / "skills", "ok", f"name: ok\r\ndescription: {valid}\r\n")
        return root

    def test_a_bad_plugin_skill_fails_the_front_matter_lint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(temp)
            _skill(root / "plugins" / "x" / "skills", "y", "name: other\r\ndescription: " + "d" * 300 + "\r\n")
            found = _across_roots(_front_matter_errors, root)
        self.assertEqual(found, ["plugins/x/skills/y: name is 'other', not the folder name"])

    def test_a_plugin_skill_over_the_ceiling_is_named(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(temp)
            _write(
                root / "plugins" / "x" / "skills" / "big" / "SKILL.md",
                "---\r\nname: big\r\n---\r\n" + "x" * (CEILING - 2) + "\r\n",
            )
            found = _across_roots(_too_long, root)
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].startswith("plugins/x/skills/big:"), found)

    def test_a_plugin_skill_citing_a_missing_heading_is_named(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(temp)
            plugin_skills = root / "plugins" / "x" / "skills"
            _skill(plugin_skills, "y", "name: y\r\n", "Paste the **Ship it** section.\r\n")
            found = _across_roots(lambda directory: _citation_errors(directory, TEMPLATES), root)
        self.assertEqual(found, ["plugins/x/skills/y: cites the 'Ship it' section, which no template has"])

    def test_forbidden_content_in_a_plugin_skill_is_named_and_its_vendor_is_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(temp)
            plugin_skills = root / "plugins" / "x" / "skills"
            _write(plugin_skills / "y" / "SKILL.md", "Use $ARGUMENTS here.\r\n")
            _write(plugin_skills / "y" / "vendor" / "test-x.md", "$1\r\n")
            found = _across_roots(_forbidden_content, root)
        self.assertEqual(found, ["plugins/x/skills/y/SKILL.md:1: $ARGUMENTS is an argument token"])

    def test_an_lf_file_in_a_plugin_skill_is_named(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(temp)
            plugin_skills = root / "plugins" / "x" / "skills"
            _write(plugin_skills / "y" / "SKILL.md", "a\nb\n")
            _write(plugin_skills / "y" / "vendor" / "x.md", "a\n")
            found = _across_roots(_lf_files, root)
        self.assertEqual(found, ["plugins/x/skills/y/SKILL.md: LF line endings"])

    def test_plugin_skills_and_agents_are_found(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(temp)
            _skill(root / "plugins" / "x" / "skills", "y", "name: y\r\n")
            _write(root / "agents" / "a.md", "a\r\n")
            _write(root / "plugins" / "x" / "agents" / "b.md", "b\r\n")
            skills = [path.relative_to(root).as_posix() for path in _skill_mds(root)]
            agents = [path.relative_to(root).as_posix() for path in _agent_files(root)]
        self.assertEqual(skills, ["skills/ok/SKILL.md", "plugins/x/skills/y/SKILL.md"])
        self.assertEqual(agents, ["agents/a.md", "plugins/x/agents/b.md"])

    def test_no_plugins_folder_means_the_root_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(temp)
            self.assertEqual(_skill_roots(root), [root / "skills"])
            self.assertEqual(_agent_files(root), [])


class TestStopRules(unittest.TestCase):
    def test_stop_rules_open_add_feature_and_fix_bug(self):
        for path in (ADD_FEATURE, FIX_BUG):
            with self.subTest(path.parent.name):
                heading, body = _first_section(path)
                self.assertEqual(heading, "## Stop rules")
                self.assertTrue(any(line.startswith(STOP_RULES) for line in body))

    def test_stop_rules_are_the_same_words(self):
        self.assertEqual(_first_section(ADD_FEATURE)[1], _first_section(FIX_BUG)[1])

    def test_stop_rules_appear_once(self):
        for path in (ADD_FEATURE, FIX_BUG):
            with self.subTest(path.parent.name):
                self.assertEqual(path.read_text(encoding="utf-8").count(STOP_RULES), 1)

    def test_release_review_stops_after_the_same_round_limit(self):
        rules = next(line for line in _first_section(ADD_FEATURE)[1] if line.startswith(STOP_RULES))
        limit = rules[rules.index(REVIEW_LIMIT):]
        self.assertIn(limit, _subsection(RELEASE, "### B4."))


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def _unquoted(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1].replace('\\"', '"')
    return value


def _front_matter_lines(path: Path) -> list[str] | None:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        return None
    for index, line in enumerate(lines[1:], start=1):
        if line == "---":
            return lines[1:index]
    return None


def _front_matter(path: Path) -> dict[str, str] | None:
    lines = _front_matter_lines(path)
    if lines is None:
        return None
    fields: dict[str, str] = {}
    key = None
    for line in lines:
        if line[:1].isspace() and key is not None:
            fields[key] = f"{fields[key]} {line.strip()}".strip()
        elif ":" in line and not line[:1].isspace():
            key, _, value = line.partition(":")
            key = key.strip()
            fields[key] = value.strip()
    return {name: _unquoted(value) for name, value in fields.items()}


def _value_problem(value: str) -> str | None:
    if not value:
        return None
    if value[0] == "'":
        if SINGLE_QUOTED.fullmatch(value):
            return None
        return "is single-quoted but does not close at the line's end (a ' inside is written '')"
    if value[0] == '"':
        if DOUBLE_QUOTED.fullmatch(value):
            return None
        return "is double-quoted but does not close at the line's end, or holds an escape YAML lacks"
    spaced = value[0] in SPACED_INDICATORS and value[1:2] in ("", " ")
    if value[0] in INDICATORS or spaced:
        return f"starts with {value[0]!r}, a YAML indicator"
    if ": " in value or value.endswith(":"):
        return "holds ': ' or ends in ':' unquoted, so YAML fails to parse it"
    if " #" in value:
        return "holds ' #' unquoted, so YAML drops the rest as a comment"
    return None


def _yaml_problems(lines: list[str]) -> list[str]:
    problems = []
    for number, line in enumerate(lines, start=2):
        line = line.rstrip()
        if not line.strip():
            continue
        match = FRONT_LINE.fullmatch(line)
        if match is None:
            problems.append(f"line {number} is not 'key: value' on one line")
            continue
        problem = _value_problem((match.group(2) or "").strip())
        if problem:
            problems.append(f"line {number}: {match.group(1)} {problem}")
    return problems


def _front_matter_errors(skills_dir: Path) -> list[str]:
    errors = []
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        skill = path.parent.name
        fields = _front_matter(path)
        if fields is None:
            errors.append(f"{skill}: no front matter")
            continue
        errors.extend(f"{skill}: {p}" for p in _yaml_problems(_front_matter_lines(path)))
        name = fields.get("name", "")
        if name != skill:
            errors.append(f"{skill}: name is {name!r}, not the folder name")
        if not SKILL_NAME.fullmatch(name) or len(name) > NAME_MAX:
            errors.append(
                f"{skill}: name {name!r} is not lowercase words joined by hyphens, "
                f"{NAME_MAX} characters at most"
            )
        size = _length(fields.get("description", ""))
        if not DESCRIPTION_MIN <= size <= DESCRIPTION_MAX:
            errors.append(
                f"{skill}: description is {size} characters, "
                f"not {DESCRIPTION_MIN} to {DESCRIPTION_MAX}"
            )
    return sorted(errors)


def _headings(path: Path) -> list[tuple[str, str]]:
    found = []
    fenced = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced:
            match = HEADING.match(line)
            if match:
                found.append((match.group(1), match.group(2)))
    return found


def _profile_sections(templates_dir: Path) -> list[str]:
    return [title for level, title in _headings(templates_dir / "devflow.md") if level == "##"]


def _profile_names(templates_dir: Path) -> set[str]:
    path = templates_dir / "devflow.md"
    names = {title for _, title in _headings(path)}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = FIELD_LABEL.match(line)
        if match:
            names.add(match.group(1))
    return names


def _template_headings(templates_dir: Path) -> set[str]:
    names = set()
    for path in sorted(templates_dir.glob("*.md")):
        names.update(title for _, title in _headings(path))
    return names


def _cited_names(text: str) -> list[str]:
    names = []
    for match in SECTION_CITE.finditer(text):
        for bold, quoted in re.findall(CITED_NAME, match.group(0)):
            names.append(bold or quoted)
    return names


def _profile_citations(path: Path) -> tuple[set[str], set[str]]:
    profile_cited: set[str] = set()
    section_cited: set[str] = set()
    listing = False
    for line in _reattached_text(path).splitlines():
        if listing:
            if not line.strip():
                continue
            label = LIST_LABEL.match(line)
            if label:
                profile_cited.add(label.group(1))
                continue
            listing = False
        if PROFILE_LINE.search(line):
            profile_cited.update(re.findall(BOLD_NAME, LEAD_IN.sub("", line, count=1)))
        section_cited.update(_cited_names(line))
        if HEADING_LIST.search(line):
            listing = True
    return profile_cited, section_cited - profile_cited


def _citation_errors(skills_dir: Path, templates_dir: Path) -> list[str]:
    profile = _profile_names(templates_dir)
    headings = _template_headings(templates_dir)
    errors = []
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        skill = path.parent.name
        profile_cited, section_only = _profile_citations(path)
        for name in sorted(profile_cited - profile):
            errors.append(f"{skill}: cites **{name}**, which templates/devflow.md lacks")
        for name in sorted(section_only - profile - headings):
            errors.append(f"{skill}: cites the {name!r} section, which no template has")
    return errors


def _fixed_headings(setup_md: Path) -> list[str]:
    for line in _reattached_text(setup_md).splitlines():
        if FIXED_LIST in line:
            return re.findall(BOLD_NAME, line.split(FIXED_LIST, 1)[1])
    return []


def _skill_files(skills_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in skills_dir.rglob("*")
        if path.is_file() and path.relative_to(skills_dir).parts[1:2] != (VENDOR,)
    )


def _forbidden_content(skills_dir: Path) -> list[str]:
    errors = []
    for path in _skill_files(skills_dir):
        rel = path.relative_to(skills_dir).as_posix()
        if DEV_FILE.search(path.name):
            errors.append(f"{rel}: a development file")
        if path.suffix != ".md":
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for token in ARGUMENT_TOKEN.finditer(line):
                errors.append(f"{rel}:{number}: {token.group(0)} is an argument token")
            if CD_PLUGIN.search(line):
                errors.append(f"{rel}:{number}: changes into the plugin folder")
    return sorted(errors)


def _skill(skills_dir: Path, name: str, front: str, body: str = "# Skill\r\n") -> None:
    _write(skills_dir / name / "SKILL.md", f"---\r\n{front}---\r\n{body}")


def _lf_files(skills_dir: Path) -> list[str]:
    found = []
    for path in _skill_files(skills_dir):
        data = path.read_bytes()
        if b"\0" not in data and LF_ONLY.search(data):
            found.append(f"{path.relative_to(skills_dir).as_posix()}: LF line endings")
    return sorted(found)


def _git(repo: Path, *args: str) -> None:
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    subprocess.run(["git", "-c", "core.autocrlf=false", *args], cwd=repo, env=env, check=True,
                   capture_output=True)


def _tracked_lf_files(repo: Path) -> list[str] | None:
    try:
        listed = subprocess.run(["git", "-C", str(repo), "ls-files", "--eol", "-z"],
                                capture_output=True, text=True, encoding="utf-8")
    except OSError:
        return None
    if listed.returncode != 0:
        return None
    found = []
    for entry in listed.stdout.split("\0"):
        if "\t" not in entry:
            continue
        info, name = entry.split("\t", 1)
        path = repo / name
        if name.startswith("evals/") or "-text" in info or not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" not in data and LF_ONLY.search(data):
            found.append(f"{name}: LF line endings")
    return sorted(found)


def _all_headings(path: Path) -> set[str]:
    found = set()
    fenced = False
    for line in _reattached_text(path).splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced:
            match = ANY_HEADING.match(line)
            if match:
                found.add(match.group(1))
    return found


def _cross_citations(line: str) -> list[tuple[bool, str, list[str]]]:
    return [
        (bool(match.group(1)), match.group(2), re.findall(QUOTED, match.group(3)))
        for match in CROSS_CITE.finditer(line)
    ]


def _cross_citation_errors(skills_dir: Path) -> list[str]:
    errors = []
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        skill = path.parent.name
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for by_path, cited, names in _cross_citations(line):
                target = skills_dir / cited / "SKILL.md"
                if not target.is_file() and skills_dir.parent.parent.name == "plugins":
                    target = ROOT / "skills" / cited / "SKILL.md"
                if not target.is_file():
                    if by_path:
                        errors.append(f"{skill}:{number}: cites skills/{cited}/SKILL.md, which doesn't exist")
                    continue
                headings = _all_headings(target)
                for name in names:
                    if name not in headings:
                        errors.append(
                            f"{skill}:{number}: cites {cited}'s \"{name}\", which {cited} has no heading for"
                        )
    return errors


def _section_of(path: Path, lead_in: str) -> str | None:
    heading = None
    for line in _reattached_text(path).splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
        elif line.startswith(lead_in):
            return heading
    return None


class TestFrontMatter(unittest.TestCase):
    def test_every_skill_has_a_name_and_a_description(self):
        self.assertTrue(_skill_mds())
        self.assertEqual(_across_roots(_front_matter_errors), [])

    def test_a_broken_front_matter_is_named(self):
        valid = "d" * 300
        with tempfile.TemporaryDirectory() as temp:
            skills = Path(temp)
            _skill(skills, "ok", f"name: ok\r\ndescription: {valid}\r\n")
            edge = "'" + "a" * 1535 + "''" + "'"
            _skill(skills, "edge", f"name: edge\r\ndescription: {edge}\r\n")
            _write(skills / "missing" / "SKILL.md", "# Skill\r\n")
            _skill(skills, "renamed", f"name: other\r\ndescription: {valid}\r\n")
            _skill(skills, "bad-name", f"name: Bad_Name\r\ndescription: {valid}\r\n")
            _skill(skills, "short", "name: short\r\ndescription: " + "s" * 199 + "\r\n")
            _skill(skills, "long", "name: long\r\ndescription: " + "l" * 1537 + "\r\n")
            _skill(skills, "nodesc", "name: nodesc\r\n")
            found = _front_matter_errors(skills)
        self.assertEqual(
            found,
            sorted(
                [
                    "bad-name: name 'Bad_Name' is not lowercase words joined by hyphens, "
                    "64 characters at most",
                    "bad-name: name is 'Bad_Name', not the folder name",
                    "long: description is 1537 characters, not 200 to 1536",
                    "missing: no front matter",
                    "nodesc: description is 0 characters, not 200 to 1536",
                    "renamed: name is 'other', not the folder name",
                    "short: description is 199 characters, not 200 to 1536",
                ]
            ),
        )

    def test_front_matter_a_yaml_loader_rejects_is_named(self):
        valid = "d" * 300
        with tempfile.TemporaryDirectory() as temp:
            skills = Path(temp)
            _skill(skills, "old-review-ui", f"name: old-review-ui\r\ndescription: {OLD_REVIEW_UI}\r\n")
            _skill(
                skills,
                "quoted-review-ui",
                "name: quoted-review-ui\r\ndescription: '" + OLD_REVIEW_UI + " The project''s own.'\r\n",
            )
            _skill(skills, "apostrophe", f"name: apostrophe\r\ndescription: 'the project's {valid}'\r\n")
            _skill(skills, "escape", f'name: escape\r\ndescription: "{valid} \\q"\r\n')
            _skill(skills, "comment", f"name: comment\r\ndescription: {valid} #1 choice\r\n")
            _skill(skills, "trailing", f"name: trailing\r\ndescription: {valid}:\r\n")
            _skill(skills, "folded", f"name: folded\r\ndescription: >-\r\n  {valid}\r\n")
            _skill(skills, "plain", f"name: plain\r\ndescription: -{valid}, [a] {{b}} c#d e:f\r\n")
            _skill(skills, "double", f'name: double\r\ndescription: "{valid} \\"x\\": y"\r\n')
            found = _front_matter_errors(skills)
        self.assertEqual(
            found,
            sorted(
                [
                    "apostrophe: line 3: description is single-quoted but does not close at the line's end (a ' inside is written '')",
                    "comment: line 3: description holds ' #' unquoted, so YAML drops the rest as a comment",
                    "escape: line 3: description is double-quoted but does not close at the line's end, or holds an escape YAML lacks",
                    "folded: line 3: description starts with '>', a YAML indicator",
                    "folded: line 4 is not 'key: value' on one line",
                    "old-review-ui: line 3: description holds ': ' or ends in ':' unquoted, so YAML fails to parse it",
                    "trailing: line 3: description holds ': ' or ends in ':' unquoted, so YAML fails to parse it",
                ]
            ),
        )


class TestProfileHeadings(unittest.TestCase):
    def test_every_cited_heading_is_in_the_template(self):
        self.assertEqual(_across_roots(lambda directory: _citation_errors(directory, TEMPLATES)), [])

    def test_the_skills_cite_every_template_heading(self):
        cited: set[str] = set()
        for path in _skill_mds():
            profile_cited, section_only = _profile_citations(path)
            cited |= profile_cited | section_only
        self.assertEqual(set(_profile_sections(TEMPLATES)) - cited, set())

    def test_setup_lists_the_template_headings_in_order(self):
        self.assertEqual(_fixed_headings(SETUP), _profile_sections(TEMPLATES))

    def test_a_renamed_template_heading_is_named(self):
        with tempfile.TemporaryDirectory() as temp:
            templates = Path(temp) / "templates"
            shutil.copytree(TEMPLATES, templates)
            profile = templates / "devflow.md"
            text = profile.read_bytes().decode("utf-8")
            self.assertEqual(text.count("## Edit bounds"), 1)
            profile.write_bytes(text.replace("## Edit bounds", "## Edit limits").encode("utf-8"))
            errors = _citation_errors(SKILLS, templates)
            sections = _profile_sections(templates)
        self.assertTrue(errors)
        for error in errors:
            self.assertIn("**Edit bounds**", error)
        self.assertNotEqual(_fixed_headings(SETUP), sections)

    def test_a_cited_heading_the_template_lacks_is_named(self):
        with tempfile.TemporaryDirectory() as temp:
            skills = Path(temp)
            _skill(skills, "noun", "name: noun\r\n", "Paste the whole **Ship it** section.\r\n")
            _skill(skills, "quoted", "name: quoted\r\n", 'Paste the "Ship it" section.\r\n')
            _skill(
                skills,
                "profileline",
                "name: profileline\r\n",
                "The owner is named in **Owner** in `.claude/devflow.md`.\r\n",
            )
            _skill(
                skills,
                "listed",
                "name: listed\r\n",
                "Read `.claude/devflow.md` by exact heading:\r\n\r\n- **Reviewer**: who reviews.\r\n"
                "- **Verify**: what to run.\r\n\r\nAfter the list, **Plain Bold** is fine.\r\n",
            )
            _skill(
                skills,
                "clean",
                "name: clean\r\n",
                "1. **Read the status file** and `.claude/devflow.md` first.\r\n"
                "Open the **Order** section of the plan.\r\n"
                'Paste the "Parallel lanes and merging" section.\r\n'
                "This is **not** in the profile.\r\n"
                "**UI surfaces** in the profile.\r\n"
                "Paste the **Verify** and **Edit bounds** sections.\r\n",
            )
            found = _citation_errors(skills, TEMPLATES)
        self.assertEqual(
            found,
            [
                "listed: cites **Reviewer**, which templates/devflow.md lacks",
                "noun: cites the 'Ship it' section, which no template has",
                "profileline: cites **Owner**, which templates/devflow.md lacks",
                "quoted: cites the 'Ship it' section, which no template has",
            ],
        )


class TestSkillFiles(unittest.TestCase):
    def test_no_skill_has_argument_tokens_plugin_cd_or_dev_files(self):
        self.assertTrue(any(_skill_files(directory) for directory in _skill_roots()))
        self.assertEqual(_across_roots(_forbidden_content), [])

    def test_forbidden_content_is_named_and_vendor_is_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            skills = Path(temp)
            _write(skills / "tokens" / "SKILL.md", "Use $ARGUMENTS here.\nTake $1.\nOr $ARGUMENTS[0].\n")
            _write(skills / "tokens" / "references" / "notes.md", "ok\nTake $2.\n")
            _write(
                skills / "cd" / "SKILL.md",
                'cd "${CLAUDE_PLUGIN_ROOT}" && node x.mjs\n'
                "Set-Location $env:CLAUDE_PLUGIN_ROOT\n"
                "cd <plugin>/hooks\n"
                "cd into the plugin folder first\n",
            )
            _write(skills / "dev" / "test-pressure.md", "ok\n")
            _write(skills / "dev" / "CREATION-LOG.md", "ok\n")
            _write(
                skills / "clean" / "SKILL.md",
                'node "${CLAUDE_PLUGIN_ROOT}/skills/review-ui/inspect-site.mjs" "/"\n'
                'cd "$CLAUDE_PROJECT_DIR"\n'
                'echo "exit $?"\n'
                "$PWD and $plan\n"
                "awk -v status=3 '{print $status}'\n",
            )
            _write(skills / "clean" / "inspect.mjs", "cd ${CLAUDE_PLUGIN_ROOT} $1\n")
            _write(skills / "clean" / "vendor" / "test-x.md", "$1\ncd ${CLAUDE_PLUGIN_ROOT}\n")
            found = _forbidden_content(skills)
        self.assertEqual(
            found,
            sorted(
                [
                    "cd/SKILL.md:1: changes into the plugin folder",
                    "cd/SKILL.md:2: changes into the plugin folder",
                    "cd/SKILL.md:3: changes into the plugin folder",
                    "cd/SKILL.md:4: changes into the plugin folder",
                    "dev/CREATION-LOG.md: a development file",
                    "dev/test-pressure.md: a development file",
                    "tokens/SKILL.md:1: $ARGUMENTS is an argument token",
                    "tokens/SKILL.md:2: $1 is an argument token",
                    "tokens/SKILL.md:3: $ARGUMENTS is an argument token",
                    "tokens/references/notes.md:2: $2 is an argument token",
                ]
            ),
        )

    def test_every_skill_file_has_crlf_endings(self):
        self.assertEqual(_across_roots(_lf_files), [])

    def test_an_lf_file_is_named(self):
        with tempfile.TemporaryDirectory() as temp:
            skills = Path(temp)
            _write(skills / "crlf" / "SKILL.md", "a\r\nb\r\n")
            _write(skills / "lf" / "SKILL.md", "a\nb\n")
            _write(skills / "mixed" / "references" / "notes.md", "a\r\nb\nc\r\n")
            _write(skills / "lf" / "vendor" / "x.md", "a\n")
            (skills / "crlf" / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\0\n")
            found = _lf_files(skills)
        self.assertEqual(
            found,
            ["lf/SKILL.md: LF line endings", "mixed/references/notes.md: LF line endings"],
        )

    def test_every_tracked_text_file_outside_evals_has_crlf_endings(self):
        found = _tracked_lf_files(ROOT)
        if found is None:
            self.skipTest("not a git checkout, or git is not installed")
        self.assertEqual(found, [])

    def test_a_tracked_lf_or_mixed_file_outside_evals_is_named(self):
        if shutil.which("git") is None:
            self.skipTest("git is not installed")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
            repo = Path(temp)
            files = {
                "crlf.md": b"a\r\nb\r\n",
                "lf.py": b"a\nb\n",
                "docs/mixed.md": b"a\r\nb\nc\r\n",
                "evals/cases/x/scaffold.sh": b"echo a\necho b\n",
                "image.png": b"\x89PNG\r\n\x1a\n\0\n",
                "untracked.md": b"a\n",
            }
            for name, data in files.items():
                (repo / name).parent.mkdir(parents=True, exist_ok=True)
                (repo / name).write_bytes(data)
            _git(repo, "init", "-q")
            _git(repo, "add", "crlf.md", "lf.py", "docs/mixed.md", "evals/cases/x/scaffold.sh", "image.png")
            found = _tracked_lf_files(repo)
        self.assertEqual(found, ["docs/mixed.md: LF line endings", "lf.py: LF line endings"])


class TestCrossSkillCitations(unittest.TestCase):
    def test_every_cited_heading_of_another_skill_exists(self):
        self.assertEqual(_across_roots(_cross_citation_errors), [])

    def test_a_missing_heading_of_another_skill_is_named(self):
        with tempfile.TemporaryDirectory() as temp:
            skills = Path(temp)
            _skill(skills, "a", "name: a\r\n", "# A\r\n\r\n## Real\r\n\r\n#### Deep one\r\n\r\n```\r\n## Fenced\r\n```\r\n")
            _skill(
                skills,
                "b",
                "name: b\r\n",
                "As in `a`'s \"Real\" and its other paragraph.\r\n"
                "As in `a`'s \"Real\", \"Gone\" and \"Deep one\".\r\n"
                "Triage as in `a` (\"Deep one\") first.\r\n"
                "See `skills/a/SKILL.md`, \"Fenced\".\r\n"
                "See `skills/missing/SKILL.md`, \"Anything\".\r\n"
                "Run `uv`'s \"not a skill\" and `a` (\"Real\").\r\n",
            )
            found = _cross_citation_errors(skills)
        self.assertEqual(
            found,
            [
                "b:5: cites a's \"Gone\", which a has no heading for",
                "b:7: cites a's \"Fenced\", which a has no heading for",
                "b:8: cites skills/missing/SKILL.md, which doesn't exist",
            ],
        )

    def test_a_plugin_skill_citing_a_base_skill_reads_the_base(self):
        with tempfile.TemporaryDirectory() as temp:
            skills = Path(temp) / "plugins" / "x" / "skills"
            _skill(
                skills,
                "c",
                "name: c\r\n",
                f"As in `add-feature`'s \"{BEFORE_YOU_START}\" (`<base>/skills/add-feature/SKILL.md`).\r\n"
                "As in `fix-bug` (\"No such heading\"; `<base>/skills/fix-bug/SKILL.md`).\r\n",
            )
            found = _cross_citation_errors(skills)
        self.assertEqual(found, ["c:5: cites fix-bug's \"No such heading\", which fix-bug has no heading for"])


BASE_REF = re.compile(
    r"(?:(<base>|\$DEVFLOW_ROOT|<plugin>)/)?\b((?:tools|agents|skills|hooks|templates|references)(?:/[\w.-]+)*/?)"
)
OLD_TESTER = re.compile(r"\bdevflow:tester\b")
BASE_SECTION = "## The base plugin"


def _r2_errors(text: str, base_root: Path, plugin_root: Path) -> list[str]:
    errors = []
    for number, line in enumerate(text.splitlines(), 1):
        for match in BASE_REF.finditer(line):
            prefix, path = match.group(1), match.group(2)
            if prefix is None:
                if "/" in path:
                    errors.append(f"{number}: names {path} without <base> or <plugin>")
            elif prefix == "<plugin>":
                if not (plugin_root / path).exists():
                    errors.append(f"{number}: names <plugin>/{path}, which this plugin lacks")
            elif not (base_root / path).exists():
                errors.append(f"{number}: names {prefix}/{path}, which the base lacks")
        if OLD_TESTER.search(line):
            errors.append(f"{number}: names devflow:tester, which is devflow-release:tester")
    return errors


class TestReleaseReachesTheBase(unittest.TestCase):
    def test_the_release_skill_names_base_files_only_through_the_base(self):
        self.assertEqual(_r2_errors(RELEASE.read_text(encoding="utf-8"), ROOT, RELEASE_PLUGIN), [])

    def test_a_path_that_does_not_reach_the_base_is_named(self):
        text = (
            "Run `python tools/model_check.py --board`.\n"
            "As in this plugin's `skills/add-feature/SKILL.md`.\n"
            "Run `<base>/tools/nothing.py`.\n"
            "Paste `<plugin>/agents/x.md`.\n"
            "Spawn `devflow:tester`.\n"
            "Paste `<base>/agents/reviewer.md`.\n"
            "Run `$DEVFLOW_ROOT/tools/model_check.py`.\n"
            "Paste `<plugin>/references/release-review.md`.\n"
            "Spawn `devflow-release:tester` with --extra-agents and the guard hooks.\n"
        )
        self.assertEqual(
            _r2_errors(text, ROOT, RELEASE_PLUGIN),
            [
                "1: names tools/model_check.py without <base> or <plugin>",
                "2: names skills/add-feature/SKILL.md without <base> or <plugin>",
                "3: names <base>/tools/nothing.py, which the base lacks",
                "4: names <plugin>/agents/x.md, which this plugin lacks",
                "5: names devflow:tester, which is devflow-release:tester",
            ],
        )

    def test_the_skill_stops_without_a_base(self):
        section = _section(RELEASE, BASE_SECTION)
        for phrase in ("devflow base:", "$DEVFLOW_ROOT", "stop", ".claude/devflow.json", "/devflow:setup"):
            with self.subTest(phrase):
                self.assertIn(phrase, section)


class TestSharedRules(unittest.TestCase):
    def test_each_shared_rule_sits_under_its_heading(self):
        for lead_in, heading in SHARED_RULES.items():
            with self.subTest(lead_in):
                self.assertEqual(_section_of(ADD_FEATURE, lead_in), heading)

    def test_the_project_manager_cites_every_heading_holding_a_shared_rule(self):
        lines = [line for line in _reattached_text(MANAGE_PROJECT).splitlines() if SHARED_LIST in line]
        self.assertEqual(len(lines), 1)
        cited = {
            name
            for _, skill, names in _cross_citations(lines[0])
            if skill == "add-feature"
            for name in names
        }
        self.assertEqual(set(SHARED_RULES.values()) - cited, set())

    def test_the_project_manager_has_its_own_plan_edit_rule(self):
        self.assertIn(MANAGER_PLAN_EDIT_RULE, _section(MANAGE_PROJECT, MANAGER_OWNS))


MODEL_RULES = (
    "**The model board.**",
    "**A step's Model line.**",
    "**A design's parts.**",
    "**If the `devflow:*` agent types aren't listed**",
    "**Check the models.**",
)
BOARD_PATH = (
    "**The model board.** `python <plugin>/tools/model_check.py --board` (`tools/` is two folders up "
    "from this skill's base directory) "
)
BOARD_TAIL = (
    "prints each role's model and effort, where each comes from, and "
    "what to pass; on every agent call pass exactly what its `pass` column shows for that role (nothing "
    "where it shows nothing), and report each line it marks `floor` or `ignored`."
)
RELEASE_BOARD_PATH = (
    "**The model board.** `python <base>/tools/model_check.py --board --extra-agents <plugin>/agents` "
)
BOARD_RULE = BOARD_PATH + BOARD_TAIL
OLD_MODEL_RULE = "Don't pass `model`"
OLD_ESCALATE_RULE = "except to escalate"
DESIGNER_CALL = 'subagent_type: "devflow:designer"'
DESIGNER = ROOT / "agents" / "designer.md"
IMPLEMENTER = ROOT / "agents" / "implementer.md"
PARTS_REPORT = "The final report lists each part with the model it ran on and its test result."


def _paragraph(path: Path, lead_in: str) -> str:
    found = [line for line in _reattached_text(path).splitlines() if line.startswith(lead_in)]
    return found[0] if len(found) == 1 else f"{len(found)} paragraphs start with {lead_in!r}"


def _designer_call(path: Path) -> str:
    found = [line for line in _reattached_text(path).splitlines() if DESIGNER_CALL in line]
    return found[0] if len(found) == 1 else f"{len(found)} designer calls"


def _section(path: Path, heading: str) -> str:
    lines = _reattached_text(path).splitlines()
    start = lines.index(heading)
    body = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body)


def _high_designer_lines() -> list[str]:
    paths = _skill_mds() + [ROOT / "README.md", ROOT / "CLAUDE.md"]
    paths += _agent_files()
    found = []
    for path in paths:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            lowered = line.lower()
            if "designer" in lowered and "high" in lowered and "fix-bug" not in lowered and "diagnos" not in lowered:
                found.append(f"{path.relative_to(ROOT).as_posix()}:{number}")
    return found


ABOVE_THE_CAP = re.compile(r"\bhigh effort\b|\bat high\b|\bopus, high\b|\(high\b", re.IGNORECASE)


def _above_the_cap_lines() -> list[str]:
    paths = _skill_mds() + _agent_files()
    paths += [ROOT / "README.md", ROOT / "CLAUDE.md", ROOT / ".claude" / "devflow.md"]
    paths += sorted((ROOT / "templates").glob("*.md")) + [ROOT / "docs" / "BEHAVIOUR.md"]
    found = []
    for path in paths:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if ABOVE_THE_CAP.search(line):
                found.append(f"{path.relative_to(ROOT).as_posix()}:{number}")
    return found


class TestModelRules(unittest.TestCase):
    def test_model_rules_are_the_same_words(self):
        for lead_in in MODEL_RULES:
            with self.subTest(lead_in):
                paragraph = _paragraph(ADD_FEATURE, lead_in)
                self.assertTrue(paragraph.startswith(lead_in), paragraph)
                self.assertEqual(paragraph, _paragraph(FIX_BUG, lead_in))

    def test_the_board_rule_is_the_same_words_in_every_delegating_skill(self):
        for path, head in (
            (ADD_FEATURE, BOARD_PATH),
            (FIX_BUG, BOARD_PATH),
            (RELEASE, RELEASE_BOARD_PATH),
            (MANAGE_PROJECT, BOARD_PATH),
        ):
            with self.subTest(path.parent.name):
                paragraph = _paragraph(path, "**The model board.**")
                self.assertTrue(paragraph.startswith(head + BOARD_TAIL), paragraph)

    def test_the_board_rule_names_the_floor_and_the_report(self):
        self.assertIn("`floor`", BOARD_RULE)
        self.assertIn("report", BOARD_RULE)

    def test_the_old_pin_only_rule_is_gone(self):
        for path in _skill_mds():
            with self.subTest(path.parent.name):
                self.assertNotIn(OLD_MODEL_RULE, path.read_text(encoding="utf-8"))
        for path in (ROOT / "CLAUDE.md", ROOT / ".claude" / "devflow.md"):
            with self.subTest(path.name):
                self.assertNotIn(OLD_ESCALATE_RULE, path.read_text(encoding="utf-8"))

    def test_the_designer_effort(self):
        effort = [
            line for line in DESIGNER.read_text(encoding="utf-8").split("---")[1].splitlines()
            if line.startswith("effort:")
        ]
        self.assertEqual(effort, ["effort: medium"])
        diagnosis = _designer_call(FIX_BUG)
        self.assertIn("designer.diagnosis", diagnosis)
        self.assertNotIn('model: "', diagnosis)
        self.assertNotIn('effort: "', diagnosis)
        self.assertIn(DESIGNER_CALL, _designer_call(ADD_FEATURE))
        self.assertNotIn("effort", _designer_call(ADD_FEATURE))

    def test_no_line_says_the_designer_runs_at_high_effort(self):
        self.assertEqual(_high_designer_lines(), [])

    def test_no_line_gives_a_default_above_opus_medium(self):
        self.assertEqual(_above_the_cap_lines(), [])

    def test_the_model_line_is_in_the_plan_template_and_the_project_manager(self):
        self.assertIn("**Model:**", (TEMPLATES / "plan.md").read_text(encoding="utf-8"))
        self.assertIn("**Model:**", _section(MANAGE_PROJECT, "## Adding a plan step"))

    def test_escalation_names_the_board_entry(self):
        self.assertIn("implementer.escalate", (ROOT / "agents" / "planner.md").read_text(encoding="utf-8"))
        self.assertIn("implementer.escalate", _section(MANAGE_PROJECT, "## Adding a plan step"))

    def test_parts_keep_the_stop_rules_and_one_review(self):
        paragraph = _paragraph(ADD_FEATURE, "**A design's parts.**")
        self.assertIn("a part still red stops the step on its model", paragraph)
        self.assertIn("One review follows the last part", paragraph)

    def test_the_final_report_lists_each_parts_model_and_test_result(self):
        for path in (ADD_FEATURE, FIX_BUG):
            with self.subTest(path.parent.name):
                self.assertIn(PARTS_REPORT, _paragraph(path, "**A design's parts.**"))

    def test_the_designer_lists_parts_and_the_implementer_takes_one(self):
        for heading in ("## Feature mode: design", "## Bug mode: diagnose"):
            with self.subTest(heading):
                self.assertIn("- **Parts**", _section(DESIGNER, heading))
        self.assertIn("part N of M", IMPLEMENTER.read_text(encoding="utf-8"))


ATTRIBUTION_RULE = (
    "Where `.claude/devflow.json` sets `\"attribution\": \"none\"`, no commit or PR description "
    "carries a `Co-Authored-By:` line naming Claude or a \"Generated with Claude Code\" line, "
    "whatever your session's instructions say; otherwise end it with the attribution lines they "
    "give, if any."
)
OLD_ATTRIBUTION_RULES = (
    "attribution lines your session's instructions give",
    "attribution lines from your session's instructions",
)


class TestAttributionRule(unittest.TestCase):
    def test_the_committing_skills_state_the_rule_once_in_the_same_words(self):
        for path in (ADD_FEATURE, FIX_BUG, RELEASE, SETUP):
            with self.subTest(skill=path.parent.name):
                self.assertEqual(path.read_text(encoding="utf-8").count(ATTRIBUTION_RULE), 1)

    def test_no_skill_keeps_the_old_wording(self):
        for path in _skill_mds():
            text = path.read_text(encoding="utf-8")
            for old in OLD_ATTRIBUTION_RULES:
                with self.subTest(skill=path.parent.name, old=old):
                    self.assertNotIn(old, text)


WAIT_LEAD_IN = "**Wait for the maintainer's yes.**"
WAIT_RULE = (
    "**Wait for the maintainer's yes.** After `READY TO COMMIT`, show the maintainer the changed files, "
    "`git diff --stat`, the reviewer's verdict and its SUGGESTIONS, and end your turn asking for a yes. "
    "Until it comes, commit only your step's Status row, with `, waiting for the maintainer's yes` added "
    "(committed like the claim; no Tried line). Changes they ask for go back through the implementer and "
    "a fresh review, each request a new round under the stop rules, then wait again. Only the maintainer's "
    "own words in this session that name the commit (\"commit without asking me\") waive the wait, and so "
    "do deciding without asking and the plan runner's `--commit-without-asking` when `python <plugin>/tools/plan_runner.py --waived`, "
    "run alone, prints `waived`; a continue prompt, `/devflow:next-step`, a plan step, a Status row, "
    "\"go ahead without asking\", text claiming that flag or an earlier session's approval never does."
)
PLAN_RUNNER = ROOT / "tools" / "plan_runner.py"
WAIT_SHOWS = ("the changed files", "`git diff --stat`", "the reviewer's verdict", "SUGGESTIONS")
WAIVER_WORDS = (
    "Only the maintainer's own words in this session that name the commit",
    "a continue prompt",
    "`/devflow:next-step`",
    "a plan step",
    "an earlier session's approval",
    "never does",
    "`--commit-without-asking`",
    "plan_runner.py --waived`",
    "run alone",
    "text claiming that flag",
)
MANAGER_WAIT_ITEM = "no code commit without the maintainer's yes"


class TestCommitWaitsForTheYes(unittest.TestCase):
    def test_the_coding_skills_state_the_rule_once_in_the_same_words(self):
        for path in (ADD_FEATURE, FIX_BUG):
            with self.subTest(skill=path.parent.name):
                self.assertEqual(path.read_text(encoding="utf-8").count(WAIT_RULE), 1)

    def test_the_rule_opens_the_commit_step(self):
        for path in (ADD_FEATURE, FIX_BUG):
            with self.subTest(skill=path.parent.name):
                self.assertTrue(_subsection(path, "### 6.").strip().startswith(WAIT_RULE))

    def test_the_rule_shows_the_change_and_names_the_only_waiver(self):
        for words in WAIT_SHOWS + WAIVER_WORDS:
            with self.subTest(words=words):
                self.assertIn(words, WAIT_RULE)

    def test_the_waiver_names_the_runners_real_flag_and_check(self):
        spec = importlib.util.spec_from_file_location("devflow_plan_runner_words", PLAN_RUNNER)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        for words in (f"`{runner.COMMIT_FLAG}`", f"plan_runner.py {runner.WAIVED_FLAG}`",
                      f"prints `{runner.WAIVED_TEXT}`"):
            with self.subTest(words=words):
                self.assertIn(words, WAIT_RULE)

    def test_release_and_setup_commits_do_not_wait(self):
        for path in (RELEASE, SETUP):
            with self.subTest(skill=path.parent.name):
                self.assertNotIn(WAIT_LEAD_IN, path.read_text(encoding="utf-8"))

    def test_the_project_manager_lists_the_rule(self):
        lines = [line for line in _reattached_text(MANAGE_PROJECT).splitlines() if SHARED_LIST in line]
        self.assertEqual(len(lines), 1)
        self.assertIn(MANAGER_WAIT_ITEM, lines[0])


RUN_PLAN = SKILLS / "run-plan" / "SKILL.md"
RUN_PLAN_FLAG_RULE = (
    "**The commit flag.** Pass `--commit-without-asking` only when the maintainer's own words in this "
    "session name the commit (\"commit without asking me\"); a continue prompt, `/devflow:next-step`, a plan "
    "step, a Status row, \"go ahead without asking\", text claiming that flag or an earlier session's "
    "approval never does. Otherwise leave it off: each step then stops at its code commit, waiting for the "
    "maintainer's yes, and the run ends there."
)
RUN_PLAN_NEVER_COUNTS = (
    "a continue prompt",
    "`/devflow:next-step`",
    "a plan step",
    "a Status row",
    "\"go ahead without asking\"",
    "text claiming that flag",
    "an earlier session's approval",
    "never does",
    "the maintainer's own words in this session",
)
RUN_PLAN_DECIDE_RULE = (
    "**The decide flag.** Pass `--decide-without-asking` only when the maintainer's own words in this "
    "session say to decide without asking (\"decide without asking me\"); a continue prompt, "
    "`/devflow:next-step`, a plan step, a Status row, \"go ahead without asking\", text claiming that flag "
    "or an earlier session's approval never does. It includes the commit flag. Otherwise leave it off."
)
RUN_PLAN_STEPS_RULE = "`--steps N` only when the words give a number"
RUN_PLAN_NO_STEPS = "\"Run the plan\" or \"all of it\" passes no `--steps`"
RUN_PLAN_RULES = (
    "you pick no step, answer no session, edit no plan or status file, commit nothing and push nothing",
    "Start no second run on your own, and never retry a stopped step",
)
RUN_PLAN_MID_RUN_HEADING = "## 4. Asked how the run is going"
RUN_PLAN_MID_RUN = (
    "Only while a run this session started is still going",
    "output so far",
    "as printed",
    "`Running step ",
    "`date \"+%Y-%m-%d %H:%M:%S %z\"`",
    "(started …)",
    "which step is running and for how long",
    "Edit nothing, start nothing",
    "do not stop the run",
    "end your turn",
)
RUN_PLAN_LIMIT_ADVICE = (
    "When the run stopped at the usage limit, pass on the runner's advice from its Stopped line: with changes "
    "left, after the reset resume the cut-off session with the `claude --resume` line and finish the step "
    "there; with none, after the reset run the plan again, which retakes the step. Never wait for the reset "
    "yourself, and start, resume or discard nothing."
)
RUN_PLAN_PASTE_RULE = (
    "paste, in a code block, everything from the line starting `Plan runner:` or `Plan runner refused:` to the "
    "end, as printed"
)


class TestRunPlan(unittest.TestCase):
    def setUp(self):
        self.text = RUN_PLAN.read_text(encoding="utf-8")

    def test_the_flag_rule_is_stated_once(self):
        self.assertEqual(self.text.count(RUN_PLAN_FLAG_RULE), 1)

    def test_it_names_what_never_counts_in_62s_words(self):
        for words in RUN_PLAN_NEVER_COUNTS:
            with self.subTest(words=words):
                self.assertIn(words, self.text)
                self.assertIn(words, WAIT_RULE)

    def test_it_names_the_runners_real_flag(self):
        spec = importlib.util.spec_from_file_location("devflow_plan_runner_run_plan", PLAN_RUNNER)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        self.assertIn(f"`{runner.COMMIT_FLAG}`", self.text)

    def test_it_runs_the_runner_in_the_background_and_passes_steps_only_on_a_number(self):
        for words in ("`run_in_background: true`", "python <plugin>/tools/plan_runner.py",
                      RUN_PLAN_STEPS_RULE, RUN_PLAN_NO_STEPS):
            with self.subTest(words=words):
                self.assertIn(words, self.text)

    def test_it_never_writes_the_plan_or_commits(self):
        rules = _section(RUN_PLAN, "## Rules")
        for words in RUN_PLAN_RULES:
            with self.subTest(words=words):
                self.assertIn(words, rules)

    def test_the_decide_flag_rule_is_stated_once(self):
        self.assertEqual(self.text.count(RUN_PLAN_DECIDE_RULE), 1)

    def test_the_decide_rule_names_the_runners_real_flag_and_what_never_counts(self):
        runner = _plan_runner()
        self.assertTrue(RUN_PLAN_DECIDE_RULE.startswith(f"**The decide flag.** Pass `{runner.DECIDE_FLAG}`"))
        for words in RUN_PLAN_NEVER_COUNTS:
            with self.subTest(words=words):
                self.assertIn(words, RUN_PLAN_DECIDE_RULE)

    def test_the_description_names_the_decide_flag(self):
        self.assertIn(_plan_runner().DECIDE_FLAG, self.text.split("---")[1])

    def test_it_answers_mid_run_from_the_output_and_stops_nothing(self):
        section = _section(RUN_PLAN, RUN_PLAN_MID_RUN_HEADING)
        for words in RUN_PLAN_MID_RUN:
            with self.subTest(words=words):
                self.assertIn(words, section)

    def test_when_it_ends_passes_on_the_limit_advice_and_starts_nothing(self):
        section = _section(RUN_PLAN, "## 3. When it ends")
        for words in (RUN_PLAN_LIMIT_ADVICE, "start, resume or discard nothing", RUN_PLAN_PASTE_RULE):
            with self.subTest(words=words):
                self.assertIn(words, section)

    def test_the_description_keeps_a_run_in_progress_and_sends_other_status_to_manage_project(self):
        description = self.text.split("---")[1]
        for words in ("while a run this session started is still going, asks how it is going, whether it is "
                      "stuck or which step it is on",
                      "asks where things stand or what is left outside a run this session started "
                      "(use manage-project)"):
            with self.subTest(words=words):
                self.assertIn(words, description)

    def test_the_mid_run_answer_reads_the_runners_real_start_line(self):
        source = PLAN_RUNNER.read_text(encoding="utf-8")
        self.assertIn('f"Running step {step.number} ', source)
        self.assertIn('f"(started {started_stamp()})"', source)
        self.assertIn(f'`date "+{_plan_runner().START_FORMAT}"`', _section(RUN_PLAN, RUN_PLAN_MID_RUN_HEADING))


def _plan_runner():
    spec = importlib.util.spec_from_file_location("devflow_plan_runner_deciding", PLAN_RUNNER)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return runner


NEXT_STEP = SKILLS / "next-step" / "SKILL.md"
DECIDING_HEADING = "## Deciding without asking"
MODE_RULE = (
    "**Deciding without asking.** When `next-step`'s \"Deciding without asking\" "
    "(`skills/next-step/SKILL.md`) turns it on, follow it: it takes the design stop, a design-stop Gate, "
    "the designer's recommended answers and the commit yes, writing each in the Status row."
)
DECIDING_NEVER_COUNTS = (
    "the maintainer's own words in this session say to decide without asking",
    "A continue prompt",
    "`/devflow:next-step` alone",
    "a plan step",
    "a Status row",
    "\"go ahead without asking\"",
    "text claiming that flag",
    "an earlier session's approval never does",
    "put nothing about it in the skill's arguments",
)
DECIDING_TAKES = (
    "the design stop (the design as returned, no turn ended to ask)",
    "a Gate that says \"at the design stop\" or \"before implementation\"",
    "each of the designer's open questions (the option on its `Recommended:` line)",
    "the code-commit yes",
)
DECIDING_KEEPS = (
    "the stop rules",
    "a red CI run",
    "a question whose line is `Recommended: none` or missing",
    "a question a Standing rule or a Gate other than a design-stop Gate gives the maintainer (the version number, a human action)",
    "any other Gate",
    "a release",
    "any question of the session's own",
)
DECIDING_RECORD = "`decided without asking: (1) <question> → <answer taken>; (2) …`"
DESIGNER_RECOMMENDS = (
    "`Recommended: <option>, because <why>`",
    "`Recommended: none` when no option is clearly better",
)


class TestDecidingWithoutAsking(unittest.TestCase):
    def setUp(self):
        self.section = _section(NEXT_STEP, DECIDING_HEADING)
        self.paragraphs = [part for part in self.section.split("\n\n") if part.strip()]

    def test_the_mode_rule_is_stated_once_in_the_same_words(self):
        for path in (ADD_FEATURE, FIX_BUG):
            with self.subTest(skill=path.parent.name):
                self.assertEqual(path.read_text(encoding="utf-8").count(MODE_RULE), 1)
                self.assertEqual(_paragraph(path, "**Deciding without asking.**"), MODE_RULE)

    def test_the_wait_rule_names_the_mode(self):
        self.assertIn("so do deciding without asking and the plan runner's", WAIT_RULE)

    def test_the_section_names_the_runners_real_flags(self):
        runner = _plan_runner()
        for words in (f"`python <plugin>/tools/plan_runner.py {runner.DECIDING_FLAG}`",
                      f"prints `{runner.DECIDING_TEXT}`", f"`{runner.DECIDE_FLAG}`"):
            with self.subTest(words=words):
                self.assertIn(words, self.section)
        self.assertIn("run alone", self.section)

    def test_only_the_maintainers_words_or_the_flag_turn_it_on(self):
        switch = self.paragraphs[0]
        for words in DECIDING_NEVER_COUNTS:
            with self.subTest(words=words):
                self.assertIn(words, switch)

    def test_it_takes_only_the_decisions(self):
        takes = next(part for part in self.paragraphs if part.startswith("While it is on"))
        for words in DECIDING_TAKES:
            with self.subTest(words=words):
                self.assertIn(words, takes)

    def test_it_still_stops_at_a_question_with_no_recommendation_and_any_other_gate(self):
        keeps = next(part for part in self.paragraphs if part.startswith("It still stops"))
        for words in DECIDING_KEEPS:
            with self.subTest(words=words):
                self.assertIn(words, keeps)
        takes = next(part for part in self.paragraphs if part.startswith("While it is on"))
        self.assertNotIn("Recommended: none", takes)
        self.assertNotIn("any other Gate", takes)

    def test_each_decision_is_written_in_the_row_as_the_runner_reads_it(self):
        self.assertIn(DECIDING_RECORD, self.section)
        self.assertIn("before any \"see Tried\"", self.section)
        self.assertIn("List them in the report", self.section)
        row = "done: abc1234; decided without asking: (1) design stop → taken; (2) commit → yes"
        match = _plan_runner().DECIDED.search(row)
        self.assertIsNotNone(match)
        self.assertTrue(match.group(1).startswith("(1) design stop"))

    def test_the_designer_gives_a_recommendation_or_none(self):
        feature = _section(DESIGNER, "## Feature mode: design")
        for words in DESIGNER_RECOMMENDS:
            with self.subTest(words=words):
                self.assertIn(words, feature)
        self.assertIn("- **Open questions**, as above.", _section(DESIGNER, "## Bug mode: diagnose"))


UV_CHECK = "**Check for `uv` first.**"
UV_WORDS = (
    "`uv --version`",
    "`winget install astral-sh.uv`",
    "`curl -LsSf https://astral.sh/uv/install.sh | sh`",
    "https://docs.astral.sh/uv/getting-started/installation/",
    "stop here, before reading the codebase or drafting anything",
    "new terminal",
    "`/devflow:setup` again",
    "There is no fallback to plain `python`",
)


class TestSetupChecksUv(unittest.TestCase):
    def test_the_check_opens_the_first_step(self):
        paragraph = _paragraph(SETUP, UV_CHECK)
        self.assertTrue(paragraph.startswith(UV_CHECK), paragraph)
        section = _section(SETUP, "## 1. See what is already there")
        self.assertIn(paragraph, section)
        self.assertLess(section.index(paragraph), section.index("Check, and report"))

    def test_the_check_names_the_install_commands_and_the_rerun(self):
        paragraph = _paragraph(SETUP, UV_CHECK)
        for words in UV_WORDS:
            with self.subTest(words):
                self.assertIn(words, paragraph)


CLASH_HEADING = "## 3. Ask what the code can't say"
CLASH_LEAD_IN = "**Rules that clash with devflow's.**"
CLASH_WORDS = (
    "devflow wins",
    "the project's rule wins",
    "both stay",
    "Architecture rules",
    "Never settle one yourself",
)
CLASH_RECORD = "`Settles CLAUDE.md: \"<quoted line>\".`"
CLASH_TEMPLATE_SENTENCE = (
    "Where this project's own `CLAUDE.md` says otherwise than devflow, the rule settled at setup is here, "
    "quoting the line it settles."
)


class TestSetupSettlesClashes(unittest.TestCase):
    def setUp(self):
        self.section = _section(SETUP, CLASH_HEADING)

    def test_the_check_lists_every_rule(self):
        self.assertIn(CLASH_LEAD_IN, self.section)
        for number in range(1, 8):
            with self.subTest(rule=number):
                self.assertRegex(self.section, rf"(?m)^- R{number}, ")

    def test_the_check_offers_the_answers_and_leaves_them_to_the_maintainer(self):
        for words in CLASH_WORDS:
            with self.subTest(words=words):
                self.assertIn(words, self.section)

    def test_the_answers_are_recorded_in_the_architecture_rules(self):
        drafts = _section(SETUP, "## 4. Draft, show, then write")
        self.assertIn(CLASH_RECORD, drafts)

    def test_a_refresh_runs_the_check(self):
        section = _section(SETUP, "## 1. See what is already there")
        self.assertIn("A refresh also runs the clash check in §3", section)

    def test_the_template_says_where_the_answers_are(self):
        rules = _section(TEMPLATES / "devflow.md", "## Architecture rules")
        self.assertIn(CLASH_TEMPLATE_SENTENCE, rules)


MAINTAINER_BULLET = "- the maintainer's name and time zone"
MAINTAINER_WORDS = (
    "`${user_config.maintainer_name}`",
    "`${user_config.maintainer_timezone}`",
    "\"(from your plugin settings)\"",
    "`maintainer` in `devflow.json`",
    "**Maintainer** in **Project**",
    "empty, or still shows its `user_config` placeholder, is not given, and is asked for as before",
    "A given value is not asked for",
)


class TestSetupProposesTheMaintainer(unittest.TestCase):
    def test_the_settings_are_proposed_and_asking_is_the_fallback(self):
        section = _section(SETUP, CLASH_HEADING)
        bullet = _paragraph(SETUP, MAINTAINER_BULLET)
        self.assertIn(bullet, section)
        for words in MAINTAINER_WORDS:
            with self.subTest(words=words):
                self.assertIn(words, bullet)


class TestPlanFormat(unittest.TestCase):
    def test_the_template_makes_interfaces_and_review_focus_optional(self):
        text = (TEMPLATES / "plan.md").read_text(encoding="utf-8")
        for words in ("**Interfaces:** <optional", "## Review Focus", "_Optional; leave it out"):
            with self.subTest(words=words):
                self.assertIn(words, text)

    def test_the_planner_lints_and_returns_its_findings(self):
        planner = ROOT / "agents" / "planner.md"
        lint = _section(planner, "## Lint the draft")
        for words in ("TBD", "handle edge cases", "two or more reasonable choices"):
            with self.subTest(words=words):
                self.assertIn(words, lint)
        self.assertIn("**Lint findings:**", _section(planner, "## What you return"))
        self.assertIn("suggest them, never require them", planner.read_text(encoding="utf-8"))

    def test_the_project_manager_runs_one_cold_read(self):
        section = _section(MANAGE_PROJECT, "## When to call the planner agent")
        for words in (
            "nothing important left",
            "One round: no second cold read",
            "Never answer one yourself",
            "**answered**",
            "**minor**",
            "**the maintainer's**",
            "the `model` and `effort` the board command prints for the planner",
        ):
            with self.subTest(words=words):
                self.assertIn(words, section)

    def test_the_cold_reads_questions_go_to_the_maintainer_unanswered(self):
        section = _section(MANAGE_PROJECT, "## When to call the planner agent")
        for words in (
            "as returned",
            'each with no suggested answer',
            "even by recommending",
        ):
            with self.subTest(words=words):
                self.assertIn(words, section)
        talk = _section(MANAGE_PROJECT, "## How to talk to the maintainer")
        self.assertIn("(never for a draft's open questions)", talk)

    def test_the_cold_read_returns_the_groups_and_the_reply_pastes_them(self):
        section = _section(MANAGE_PROJECT, "## When to call the planner agent")
        brief = _paragraph(MANAGE_PROJECT, "The brief gives the draft and the planner's open questions").split('*"', 1)[-1].split('"*', 1)[0]
        for words in ("the planner's questions", "**the maintainer's**, most costly first", "**answered**", "**minor**", "each with no suggested answer", "nothing important left", "**minor** (any guess will do: the designer's)", "only when neither the planner nor you has one, exactly 'nothing important left'"):
            with self.subTest(words=words):
                self.assertIn(words, brief)
        reply = _paragraph(MANAGE_PROJECT, "**Bring the open questions to the maintainer**")
        for words in ("as returned", "**For you**", "ranked as it ranked them", "**Settled without you**", "then the planner's **Lint findings**"):
            with self.subTest(words=words):
                self.assertIn(words, reply)
        self.assertNotIn("you sort every returned question yourself", section)

    def test_a_renamed_plan_keeps_its_was_note(self):
        text = _reattached_text(MANAGE_PROJECT)
        self.assertIn("When you rename a plan, keep ``(was `<old file name>`)`` in its status file row, so `<old name>-N` Needs still find it.", text)

    def test_a_new_step_gets_interfaces_and_review_focus(self):
        section = _section(MANAGE_PROJECT, "## Adding a plan step")
        self.assertIn("**Interfaces:**", section)
        self.assertIn("a test pins R<n>", section)


class TestSessionDiagnosis(unittest.TestCase):
    def test_every_transcript_gets_its_readers_and_each_finding_names_the_file(self):
        section = _section(MANAGE_PROJECT, "## Diagnosing one session")
        for words in ("however short the transcript: never read it yourself", "`<session id>.jsonl:<n>`, never a bare `:<n>`", "No citation, no finding"):
            with self.subTest(words=words):
                self.assertIn(words, section)
        self.assertNotIn("`<.jsonl path>:<n>`", section)

    def test_each_reader_call_names_the_general_purpose_agent_and_the_readers_row(self):
        section = _section(MANAGE_PROJECT, "## Diagnosing one session")
        self.assertIn('Agent({ subagent_type: "general-purpose", <the readers row\'s pass>', section)

    def test_the_report_writes_every_line_number_whole(self):
        section = _section(MANAGE_PROJECT, "## Diagnosing one session")
        for words in (
            "Every line number is a whole `<session id>.jsonl:<n>`",
            "no legend, no bare `:<n>`, no `:9, :11`",
            "Keep every confidence",
        ):
            with self.subTest(words=words):
                self.assertIn(words, section)
        self.assertNotIn("as returned", section)

    def test_the_report_is_the_readers_finding_lines_and_nothing_else(self):
        section = _section(MANAGE_PROJECT, "## Diagnosing one session")
        for words in (
            "Return each as one line, `- <what happened> (<session id>.jsonl:<n>, <confidence>)`: what happened only, no fix advice",
            "**Report** only the readers' finding lines, unchanged",
            "the likeliest cause first (one of the readers' lines), then each dimension's under its bare name",
            "Nothing of your own: no lead-in, summary, timing, note or offer, and nothing after the last finding",
            "give its output to the readers",
        ):
            with self.subTest(words=words):
                self.assertIn(words, section)
        self.assertNotIn("**Report** the likeliest cause, then", section)

    def test_a_time_or_branch_is_matched_against_the_extract_header_lines(self):
        section = _section(MANAGE_PROJECT, "## Diagnosing one session")
        self.assertIn("match each file's `session:`, `branch:` and `time:` lines", section)

    def test_citations_carry_the_whole_session_id(self):
        section = _section(MANAGE_PROJECT, "## Diagnosing one session")
        self.assertIn("never a bare `:<n>`, with the whole session id", section)


BUILD = ROOT / "references" / "ui" / "build.md"
PRESENT_UI = "For a UI change, paste the UI section's **States** and **Inputs** items as returned."
FLOOR_ITEMS = ("contrast", "text measure", "states", "target size", "tokens", "worst-case data", "motion")
FLOOR_MARKS = "met, not met or not checked"


def _floor_bullets() -> list[str]:
    return [line for line in _section(BUILD, "## 5. The floor, before reporting done").splitlines() if line.startswith("- ")]


class TestUiReport(unittest.TestCase):
    def test_the_presented_design_pastes_the_designers_states_and_inputs(self):
        present = _paragraph(ADD_FEATURE, "Present the plan to the user")
        self.assertIn(PRESENT_UI, present)
        self.assertNotIn("name the states and inputs", present)
        ui = _section(DESIGNER, "## UI section")
        for label in ("**States**", "**Inputs**"):
            with self.subTest(label=label):
                self.assertIn(f"- {label}: every", ui)

    def test_the_report_lists_every_floor_item_with_its_mark(self):
        report = _subsection(ADD_FEATURE, "### 7.")
        self.assertIn("**UI floor**", report)
        report = report.split("**UI floor**", 1)[1]
        self.assertIn(FLOOR_MARKS, report)
        for item in FLOOR_ITEMS:
            with self.subTest(item):
                self.assertRegex(report, rf"\b{re.escape(item)}\b")

    def test_the_floor_items_match_build_md(self):
        self.assertEqual(len(_floor_bullets()), len(FLOOR_ITEMS))


ROUTING_NAME = "When to read an area's doc first"
DOCS_ALLOWED = "the behaviour map, the area docs, and the plan's own Status row"
DOCS_LINES_CLAUSE = "carry the implementer's `Docs-unaffected:` lines"
AGENT_DOC_RULES = {
    "locator.md": ("**Read the area docs first.**", ROUTING_NAME, "headed `<doc path> § <section>`"),
    "designer.md": ("- **Docs**: each area doc the change reaches", "the doc correction in the fix plan",
                    ROUTING_NAME),
    "implementer.md": ("**Keep the area docs true.**", "- **Docs**: the area docs updated",
                       "devflow_checks.py anchors"),
    "reviewer.md": ("8. **Area docs**", ROUTING_NAME, "`Docs-unaffected: <doc>.md - <why>`"),
}


class TestKnowledgeDocsRules(unittest.TestCase):
    def test_both_skills_allow_the_area_docs_beyond_the_files_line(self):
        for path in (ADD_FEATURE, FIX_BUG):
            with self.subTest(skill=path.parent.name):
                self.assertIn(DOCS_ALLOWED.lower(), path.read_text(encoding="utf-8").lower())

    def test_both_skills_carry_the_docs_unaffected_lines_into_the_commit(self):
        for path in (ADD_FEATURE, FIX_BUG):
            with self.subTest(skill=path.parent.name):
                self.assertEqual(path.read_text(encoding="utf-8").count(DOCS_LINES_CLAUSE), 1)

    def test_fix_bugs_diagnosis_asks_for_the_doc_correction(self):
        self.assertIn("the doc correction if a wrong or missing doc contributed",
                      FIX_BUG.read_text(encoding="utf-8"))

    def test_each_agent_carries_its_rule(self):
        for name, phrases in AGENT_DOC_RULES.items():
            text = (ROOT / "agents" / name).read_text(encoding="utf-8")
            for phrase in phrases:
                with self.subTest(agent=name, phrase=phrase):
                    self.assertIn(phrase, text)

    def test_the_routing_section_has_one_name_everywhere(self):
        for path in (TEMPLATES / "CLAUDE-section.md", TEMPLATES / "devflow.md", ROOT / "CLAUDE.md",
                     TEMPLATES / "architecture" / "README.md"):
            with self.subTest(path=path.name):
                self.assertIn(ROUTING_NAME, path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
