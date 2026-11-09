from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
CUT = 20_000
MARGIN = 1_000
CEILING = CUT - MARGIN
STOP_RULES = "**Stop rules in the loop.**"
ADD_FEATURE = SKILLS / "add-feature" / "SKILL.md"
FIX_BUG = SKILLS / "fix-bug" / "SKILL.md"
RELEASE = SKILLS / "release" / "SKILL.md"
SECRETARY = SKILLS / "secretary" / "SKILL.md"
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
    "**Secretary edits.**": BEFORE_YOU_START,
    "**Stop at a `**Gate:**` line.**": BEFORE_YOU_START,
}
LF_ONLY = re.compile(rb"(?<!\r)\n")


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
        self.assertTrue(list(SKILLS.glob("*/SKILL.md")))
        self.assertEqual(_too_long(SKILLS), [])

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


def _front_matter(path: Path) -> dict[str, str] | None:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        return None
    fields: dict[str, str] = {}
    key = None
    for line in lines[1:]:
        if line == "---":
            return {name: _unquoted(value) for name, value in fields.items()}
        if line[:1].isspace() and key is not None:
            fields[key] = f"{fields[key]} {line.strip()}".strip()
        elif ":" in line and not line[:1].isspace():
            key, _, value = line.partition(":")
            key = key.strip()
            fields[key] = value.strip()
    return None


def _front_matter_errors(skills_dir: Path) -> list[str]:
    errors = []
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        skill = path.parent.name
        fields = _front_matter(path)
        if fields is None:
            errors.append(f"{skill}: no front matter")
            continue
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
        self.assertTrue(list(SKILLS.glob("*/SKILL.md")))
        self.assertEqual(_front_matter_errors(SKILLS), [])

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


class TestProfileHeadings(unittest.TestCase):
    def test_every_cited_heading_is_in_the_template(self):
        self.assertEqual(_citation_errors(SKILLS, TEMPLATES), [])

    def test_the_skills_cite_every_template_heading(self):
        cited: set[str] = set()
        for path in SKILLS.glob("*/SKILL.md"):
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
        self.assertTrue(_skill_files(SKILLS))
        self.assertEqual(_forbidden_content(SKILLS), [])

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
        self.assertEqual(_lf_files(SKILLS), [])

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


class TestCrossSkillCitations(unittest.TestCase):
    def test_every_cited_heading_of_another_skill_exists(self):
        self.assertEqual(_cross_citation_errors(SKILLS), [])

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


class TestSharedRules(unittest.TestCase):
    def test_each_shared_rule_sits_under_its_heading(self):
        for lead_in, heading in SHARED_RULES.items():
            with self.subTest(lead_in):
                self.assertEqual(_section_of(ADD_FEATURE, lead_in), heading)

    def test_the_secretary_cites_every_heading_holding_a_shared_rule(self):
        lines = [line for line in _reattached_text(SECRETARY).splitlines() if SHARED_LIST in line]
        self.assertEqual(len(lines), 1)
        cited = {
            name
            for _, skill, names in _cross_citations(lines[0])
            if skill == "add-feature"
            for name in names
        }
        self.assertEqual(set(SHARED_RULES.values()) - cited, set())


MODEL_RULES = (
    "Don't pass `model`",
    "**A step's Model line.**",
    "**A design's parts.**",
    "**If the `devflow:*` agent types aren't listed**",
    "**Check the models.**",
)
DESIGNER_CALL = 'subagent_type: "devflow:designer"'
DESIGNER = ROOT / "agents" / "designer.md"
IMPLEMENTER = ROOT / "agents" / "implementer.md"


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
    paths = sorted(SKILLS.glob("*/SKILL.md")) + [ROOT / "README.md", ROOT / "CLAUDE.md"]
    paths += sorted((ROOT / "agents").glob("*.md"))
    found = []
    for path in paths:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            lowered = line.lower()
            if "designer" in lowered and "high" in lowered and "fix-bug" not in lowered and "diagnos" not in lowered:
                found.append(f"{path.relative_to(ROOT).as_posix()}:{number}")
    return found


class TestModelRules(unittest.TestCase):
    def test_model_rules_are_the_same_words(self):
        for lead_in in MODEL_RULES:
            with self.subTest(lead_in):
                paragraph = _paragraph(ADD_FEATURE, lead_in)
                self.assertTrue(paragraph.startswith(lead_in), paragraph)
                self.assertEqual(paragraph, _paragraph(FIX_BUG, lead_in))

    def test_the_designer_effort(self):
        effort = [
            line for line in DESIGNER.read_text(encoding="utf-8").split("---")[1].splitlines()
            if line.startswith("effort:")
        ]
        self.assertEqual(effort, ["effort: medium"])
        self.assertIn('effort: "high"', _designer_call(FIX_BUG))
        self.assertIn(DESIGNER_CALL, _designer_call(ADD_FEATURE))
        self.assertNotIn("effort", _designer_call(ADD_FEATURE))

    def test_no_line_says_the_designer_runs_at_high_effort(self):
        self.assertEqual(_high_designer_lines(), [])

    def test_the_model_line_is_in_the_plan_template_and_the_secretary(self):
        self.assertIn("**Model:**", (TEMPLATES / "plan.md").read_text(encoding="utf-8"))
        self.assertIn("**Model:**", _section(SECRETARY, "## Adding a plan step"))

    def test_parts_keep_the_stop_rules_and_one_review(self):
        paragraph = _paragraph(ADD_FEATURE, "**A design's parts.**")
        self.assertIn("a part still red stops the step on its model", paragraph)
        self.assertIn("One review follows the last part", paragraph)

    def test_the_designer_lists_parts_and_the_implementer_takes_one(self):
        for heading in ("## Feature mode: design", "## Bug mode: diagnose"):
            with self.subTest(heading):
                self.assertIn("- **Parts**", _section(DESIGNER, heading))
        self.assertIn("part N of M", IMPLEMENTER.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
