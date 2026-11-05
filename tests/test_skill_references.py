from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "skills" / "review-ui" / "references"
CORE = "skills/review-ui/references/core.md"


def _section(path: Path, heading: str) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    start = lines.index(heading)
    body = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        body.append(line)
    return body


def _bullet(path: Path, heading: str, role: str) -> str:
    matches = [line for line in _section(path, heading) if line.startswith(f"- **{role} (step")]
    if len(matches) != 1:
        raise AssertionError(f"{path.name}: expected one {role} bullet under {heading}")
    return matches[0]


ADD_FEATURE = ROOT / "skills" / "add-feature" / "SKILL.md"
FIX_BUG = ROOT / "skills" / "fix-bug" / "SKILL.md"
IMPLEMENTER = ROOT / "agents" / "implementer.md"
REVIEWER = ROOT / "agents" / "reviewer.md"

BULLETS = {
    "add-feature designer": (ADD_FEATURE, "## UI changes", "Designer"),
    "add-feature reviewer": (ADD_FEATURE, "## UI changes", "Reviewer"),
    "fix-bug designer": (FIX_BUG, "## UI bugs", "Designer"),
    "fix-bug reviewer": (FIX_BUG, "## UI bugs", "Reviewer"),
}


class TestUiBriefReferences(unittest.TestCase):
    def test_designer_and_reviewer_bullets_name_core(self):
        for label, (path, heading, role) in BULLETS.items():
            with self.subTest(label):
                self.assertIn(CORE, _bullet(path, heading, role))

    def test_add_feature_designer_names_build_and_motion(self):
        bullet = _bullet(ADD_FEATURE, "## UI changes", "Designer")
        self.assertRegex(bullet, r"`build\.md`")
        self.assertRegex(bullet, r"`motion\.md`")

    def test_reference_files_exist(self):
        for name in ("core.md", "build.md", "motion.md"):
            with self.subTest(name):
                self.assertTrue((REFERENCES / name).is_file())

    def test_core_path_in_bullets_resolves(self):
        for label, (path, heading, role) in BULLETS.items():
            with self.subTest(label):
                cited = re.findall(r"`(skills/review-ui/references/[\w.-]+)`", _bullet(path, heading, role))
                self.assertTrue(cited)
                for rel in cited:
                    self.assertTrue((ROOT / rel).is_file(), rel)

    def test_build_md_goes_to_the_add_feature_implementer_only(self):
        add_feature = _bullet(ADD_FEATURE, "## UI changes", "Implementer")
        self.assertIn("`build.md` (same folder as `core.md`)", add_feature)
        self.assertIn("build.md §5", add_feature)
        self.assertNotIn("build.md", _bullet(FIX_BUG, "## UI bugs", "Implementer"))

    def test_reviewer_bullets_pass_motion_in_the_same_words(self):
        tails = []
        for path, heading in ((ADD_FEATURE, "## UI changes"), (FIX_BUG, "## UI bugs")):
            bullet = _bullet(path, heading, "Reviewer")
            with self.subTest(path.parent.name):
                self.assertIn("`motion.md`", bullet)
                tail = bullet[bullet.index("`motion.md`"):]
                self.assertIn("motion.md §5", tail)
                tails.append(tail)
        self.assertEqual(tails[0], tails[1])

    def test_implementer_report_has_the_build_floor(self):
        lines = [line for line in _section(IMPLEMENTER, "## Report") if "build.md" in line]
        self.assertEqual(len(lines), 1)
        for needle in ("§5", "**met**", "**not met**", "**not checked**"):
            self.assertIn(needle, lines[0])

    def test_reviewer_item_7_grades_motion(self):
        lines = [line for line in _section(REVIEWER, "## What to check (diff mode)") if line.startswith("7. **UI**")]
        self.assertEqual(len(lines), 1)
        for needle in ("`motion.md`", "§5", "**(M)**", "**(T)**"):
            self.assertIn(needle, lines[0])


if __name__ == "__main__":
    unittest.main()
