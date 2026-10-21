from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRACT_PATH = ROOT / "tools" / "session_extract.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


extract = _load("session_extract", EXTRACT_PATH)


def record(kind: str, content, **extra) -> dict:
    base = {"type": kind, "sessionId": "s1", "gitBranch": "main", "isSidechain": False,
            "timestamp": "2026-10-21T10:00:00.000Z"}
    if kind in ("user", "assistant"):
        base["message"] = {"role": kind, "content": content}
    base.update(extra)
    return base


def write_session(folder: Path, name: str, records: list, raw_lines: list[str] | None = None) -> Path:
    path = folder / f"{name}.jsonl"
    lines = [json.dumps(item) for item in records] + (raw_lines or [])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class SessionCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = Path(self._tmp.name) / "sessions"
        self.folder.mkdir()
        self.out = Path(self._tmp.name) / "out"

    def lines_of(self, records: list, raw_lines: list[str] | None = None) -> tuple[str, ...]:
        path = write_session(self.folder, "case", records, raw_lines)
        result = extract.extract_session(path)
        assert result is not None
        return result.lines


class RecordTypes(SessionCase):
    def test_keeps_user_and_assistant_only(self):
        lines = self.lines_of([
            record("user", "hello"),
            record("assistant", [{"type": "text", "text": "hi"}]),
            record("attachment", "x"),
            record("api-request", "x"),
            record("api-request-blob", "x"),
            record("ai-title", "x"),
            record("queue-operation", "x"),
            record("file-history-snapshot", "x"),
        ])
        self.assertEqual(lines, ("U: hello", "A: hi"))

    def test_drops_thinking(self):
        lines = self.lines_of([record("assistant", [
            {"type": "thinking", "thinking": "secret reasoning"},
            {"type": "text", "text": "answer"},
        ])])
        self.assertEqual(lines, ("A: answer",))

    def test_cuts_tool_result(self):
        lines = self.lines_of([record("user", [
            {"type": "tool_result", "tool_use_id": "t", "content": "x" * 5000},
        ])])
        self.assertEqual(len(lines), 1)
        self.assertLessEqual(len(lines[0]), extract.RESULT_LIMIT + 4)
        self.assertTrue(lines[0].endswith("…"))

    def test_tool_result_list_content_and_error_marker(self):
        lines = self.lines_of([record("user", [
            {"type": "tool_result", "content": [{"type": "text", "text": "boom"}], "is_error": True},
        ])])
        self.assertEqual(lines, ("R!: boom",))

    def test_tool_calls_are_one_line_with_key_input(self):
        lines = self.lines_of([record("assistant", [
            {"type": "tool_use", "name": "Bash", "input": {"command": "git status\n--short"}},
            {"type": "tool_use", "name": "Edit", "input": {"file_path": "a/b.py", "old_string": "x"}},
            {"type": "tool_use", "name": "Agent",
             "input": {"subagent_type": "devflow:reviewer", "description": "Review", "prompt": "long"}},
            {"type": "tool_use", "name": "Grep", "input": {"pattern": "foo", "path": "src"}},
        ])])
        self.assertEqual(lines, (
            "T: Bash: git status --short",
            "T: Edit: a/b.py",
            "T: Agent: devflow:reviewer | Review",
            "T: Grep: foo in src",
        ))

    def test_strips_system_reminders(self):
        lines = self.lines_of([record("user", "<system-reminder>noise</system-reminder>do it")])
        self.assertEqual(lines, ("U: do it",))

    def test_sidechain_records_are_marked(self):
        lines = self.lines_of([
            record("assistant", [{"type": "text", "text": "main"}]),
            record("assistant", [{"type": "text", "text": "sub"}], isSidechain=True),
        ])
        self.assertEqual(lines, ("A: main", "[sub] A: sub"))


class Content(SessionCase):
    def test_string_content(self):
        self.assertEqual(self.lines_of([record("user", "plain string")]), ("U: plain string",))

    def test_list_content_with_several_parts(self):
        lines = self.lines_of([record("assistant", [
            {"type": "text", "text": "one"},
            {"type": "tool_use", "name": "Read", "input": {"file_path": "f.md"}},
            {"type": "text", "text": "two"},
        ])])
        self.assertEqual(lines, ("A: one", "T: Read: f.md", "A: two"))

    def test_malformed_lines_are_skipped(self):
        lines = self.lines_of([record("user", "kept")],
                              raw_lines=["{not json", "", "[1, 2]", '{"type": "user"}'])
        self.assertEqual(lines, ("U: kept",))

    def test_session_without_turns_gives_nothing(self):
        path = write_session(self.folder, "empty", [record("attachment", "x")])
        self.assertIsNone(extract.extract_session(path))

    def test_header_has_id_branch_and_time_range(self):
        path = write_session(self.folder, "case", [
            record("user", "a", timestamp="2026-10-21T10:00:00.000Z"),
            record("assistant", [{"type": "text", "text": "b"}], timestamp="2026-10-21T11:30:00.000Z",
                   gitBranch="feature"),
        ])
        text = extract.render(extract.extract_session(path))
        head = text.splitlines()[:3]
        self.assertEqual(head, ["session: s1", "branch: main, feature",
                                "time: 2026-10-21T10:00:00.000Z to 2026-10-21T11:30:00.000Z"])


class Folders(SessionCase):
    def test_folder_name_from_windows_path(self):
        self.assertEqual(extract.folder_names("d:\\Projects\\devflow")[0], "d--Projects-devflow")

    def test_folder_name_from_posix_path(self):
        self.assertEqual(extract.folder_names("/home/me/devflow")[0], "-home-me-devflow")

    def test_trailing_separator_is_ignored(self):
        self.assertEqual(extract.folder_names("d:\\Projects\\devflow\\")[0], "d--Projects-devflow")

    def test_finds_project_folder_with_other_drive_letter_case(self):
        root = Path(self._tmp.name) / "projects"
        (root / "D--Projects-devflow").mkdir(parents=True)
        found = extract.sessions_folder("d:\\Projects\\devflow", root)
        self.assertEqual(found, root / "D--Projects-devflow")

    def test_finds_folder_whose_name_replaces_dots_and_spaces(self):
        root = Path(self._tmp.name) / "projects"
        (root / "-home-me--claude-my-app").mkdir(parents=True)
        found = extract.sessions_folder("/home/me/.claude/my app", root)
        self.assertEqual(found, root / "-home-me--claude-my-app")

    def test_sessions_folder_given_directly(self):
        write_session(self.folder, "a", [record("user", "x")])
        self.assertEqual(extract.sessions_folder(str(self.folder), Path(self._tmp.name) / "none"),
                         self.folder)

    def test_unknown_project_gives_none(self):
        self.assertIsNone(extract.sessions_folder("d:\\Nowhere", Path(self._tmp.name)))


class Selection(SessionCase):
    def make_sessions(self, names: list[str]) -> None:
        for index, name in enumerate(names):
            path = write_session(self.folder, name, [record("user", f"from {name}")])
            os.utime(path, (1_000_000 + index, 1_000_000 + index))

    def test_newest_first_and_limited_by_count(self):
        self.make_sessions(["old", "mid", "new"])
        names = [f.stem for f in extract.recent_sessions(self.folder, 2)]
        self.assertEqual(names, ["new", "mid"])

    def test_leaves_out_the_current_session(self):
        self.make_sessions(["old", "mid", "current"])
        names = [f.stem for f in extract.recent_sessions(self.folder, 5, exclude="current")]
        self.assertEqual(names, ["mid", "old"])

    def test_count_applies_after_the_exclusion(self):
        self.make_sessions(["old", "mid", "current"])
        names = [f.stem for f in extract.recent_sessions(self.folder, 1, exclude="current")]
        self.assertEqual(names, ["mid"])

    def test_main_writes_one_file_per_session_and_prints_sizes(self):
        self.make_sessions(["old", "current"])
        buffer = StringIO()
        with redirect_stdout(buffer):
            code = extract.main([str(self.folder), "--count", "5", "--out", str(self.out),
                                 "--exclude", "current"])
        self.assertEqual(code, 0)
        self.assertEqual([p.name for p in self.out.iterdir()], ["old.txt"])
        self.assertIn("old.txt", buffer.getvalue())
        self.assertIn(" bytes", buffer.getvalue())
        self.assertIn("wrote 1 files", buffer.getvalue())

    def test_main_reports_a_missing_folder(self):
        buffer = StringIO()
        with redirect_stdout(buffer):
            code = extract.main(["d:\\Nowhere", "--out", str(self.out),
                                 "--projects-root", str(Path(self._tmp.name) / "none")])
        self.assertEqual(code, 1)
        self.assertIn("no sessions folder", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
