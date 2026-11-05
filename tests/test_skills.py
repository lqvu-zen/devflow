from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
