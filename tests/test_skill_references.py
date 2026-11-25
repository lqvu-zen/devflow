from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "references" / "ui"
CORE = "references/ui/core.md"
CORE_PHRASE = ("(`references/ui/core.md`, two folders up from this skill's base directory; "
               "pass it as an absolute path)")
MASTER = ROOT / "plugins" / "devflow-ui" / "skills" / "review-ui" / "references"
COPIES = ("core.md", "build.md", "motion.md")


def _copy_errors(base: Path, master: Path, names: tuple[str, ...] = COPIES) -> list[str]:
    errors = []
    for name in names:
        copy, original = base / name, master / name
        missing = [str(path) for path in (copy, original) if not path.is_file()]
        if missing:
            errors.append(f"{name}: missing {', '.join(missing)}")
        elif copy.read_bytes() != original.read_bytes():
            errors.append(f"{name}: {copy} differs from {original}")
    return errors


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
                self.assertIn(CORE_PHRASE, _bullet(path, heading, role))

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
                cited = re.findall(r"`(references/ui/[\w.-]+)`", _bullet(path, heading, role))
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


class TestBaseCopies(unittest.TestCase):
    def test_each_base_copy_is_byte_equal_to_devflow_uis(self):
        self.assertEqual(_copy_errors(REFERENCES, MASTER), [])

    def test_a_copy_that_differs_is_named(self):
        tmp = Path(tempfile.mkdtemp(prefix="devflow-copies-"))
        try:
            base, master = tmp / "base", tmp / "master"
            base.mkdir()
            master.mkdir()
            (master / "core.md").write_bytes(b"# Core\r\nOne rule.\r\n")
            (base / "core.md").write_bytes(b"# Core\r\nOne other rule.\r\n")
            (master / "build.md").write_bytes(b"# Build\r\nA floor.\r\n")
            (base / "build.md").write_bytes(b"# Build\nA floor.\n")
            (master / "motion.md").write_bytes(b"# Motion\r\n")
            errors = _copy_errors(base, master)
            self.assertEqual(len(errors), 3, errors)
            for error, name in zip(errors, COPIES):
                self.assertTrue(error.startswith(f"{name}: "), error)
            self.assertIn("differs", errors[0])
            self.assertIn("differs", errors[1])
            self.assertIn("missing", errors[2])
            self.assertIn(str(base / "motion.md"), errors[2])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
