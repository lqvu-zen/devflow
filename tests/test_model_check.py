from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import model_check
import session_extract

PINS = {
    "designer": "model: opus\r\neffort: medium\r\n",
    "implementer": "model: sonnet\r\neffort: medium\r\n",
    "reviewer": "model: opus\r\neffort: high\r\n",
    "locator": "model: haiku\r\n",
}


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")


def _call(tool_id: str, kind: str, **extra) -> dict:
    params = {"description": f"run {kind}", "subagent_type": f"devflow:{kind}", "prompt": "brief"}
    params.update(extra)
    return {"type": "assistant", "message": {"id": f"main-{tool_id}", "model": "claude-sonnet-5-5",
            "content": [{"type": "tool_use", "id": tool_id, "name": "Agent", "input": params}]}}


def _reply(message_id: str, model: str, effort: str | None = None) -> dict:
    entry = {"type": "assistant", "isSidechain": True,
             "message": {"id": message_id, "model": model, "content": [{"type": "text", "text": "x"}]}}
    if effort is not None:
        entry["effort"] = effort
    return entry


def _subagent(folder: Path, name: str, meta: dict, replies: list[dict]) -> None:
    _write_jsonl(folder / f"agent-{name}.jsonl", replies)
    (folder / f"agent-{name}.meta.json").write_text(json.dumps(meta), encoding="utf-8")


def make_agents(base: Path) -> Path:
    agents = base / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    for role, fields in PINS.items():
        (agents / f"{role}.md").write_text(f"---\r\nname: {role}\r\n{fields}---\r\n\r\nBody.\r\n", encoding="utf-8")
    return agents


def make_session(folder: Path, session_id: str = "s1") -> Path:
    main = folder / f"{session_id}.jsonl"
    _write_jsonl(main, [
        {"type": "user", "message": {"role": "user", "content": "go"}},
        _call("t1", "designer"),
        _call("t2", "implementer", model="opus", effort="medium"),
        _call("t3", "reviewer"),
        _call("t4", "locator"),
        {"type": "assistant", "message": "not a dict"},
        {"type": "assistant", "message": {"content": "not a list"}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "bad", "name": "Agent",
                                                        "input": "not a dict"}]}},
        {"type": "assistant", "message": {"id": "main-t5", "content": [
            {"type": "tool_use", "id": "t5", "name": "Agent",
             "input": {"description": "look around", "subagent_type": "general-purpose", "model": "sonnet"}}]}},
    ])
    subagents = folder / session_id / "subagents"
    _subagent(subagents, "a1", {"agentType": "devflow:designer", "toolUseId": "t1",
                                "launchedWithDefaults": True, "finished": True}, [
        _reply("m1", "claude-opus-5-5", "medium"),
        _reply("m1", "claude-opus-5-5", "medium"),
        _reply("m2", "claude-opus-5-5[1m]", "medium"),
        _reply("m3", "<synthetic>"),
    ])
    _subagent(subagents, "a2", {"agentType": "devflow:implementer", "toolUseId": "t2",
                                "model": "opus", "effort": "medium", "finished": True}, [
        _reply("m4", "claude-opus-5-5"),
    ])
    _subagent(subagents, "a3", {"agentType": "devflow:reviewer", "toolUseId": "t3",
                                "launchedWithDefaults": True, "finished": True}, [
        _reply("m5", "claude-sonnet-5-5", "high"),
    ])
    _subagent(subagents, "a5", {"agentType": "general-purpose", "toolUseId": "t5", "model": "sonnet"}, [
        _reply("m6", "claude-sonnet-5-5", "medium"),
    ])
    return main


def run(argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = model_check.main(argv)
    return code, out.getvalue()


def rows(output: str) -> dict[str, list[str]]:
    found = {}
    for line in output.splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) == 6 and cells[0] != "role":
            found[cells[0]] = cells
    return found


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.agents = make_agents(self.base)
        self.session = make_session(self.base / "sessions")

    def tearDown(self):
        self.temp.cleanup()

    def check(self, *extra: str) -> tuple[int, str]:
        return run([str(self.session), "--agents", str(self.agents), *extra])


class TestModelCheck(Fixture):
    def test_names_each_model_and_marks_the_mismatch(self):
        code, output = self.check("--model", "implementer: Opus, medium; the guard")
        found = rows(output)
        self.assertEqual(code, 1)
        self.assertEqual(found["reviewer"][5], "MISMATCH")
        self.assertIn("claude-sonnet-5-5 (1)", found["reviewer"][2])
        self.assertEqual(found["designer"][5], "ok")
        self.assertIn("claude-opus-5-5 (1)", found["designer"][2])
        self.assertIn("claude-opus-5-5[1m] (1)", found["designer"][2])
        self.assertNotIn("synthetic", found["designer"][2])
        self.assertEqual(found["designer"][1], "nothing")
        self.assertEqual(found["designer"][4], "opus, medium (pin)")
        self.assertIn("mismatches: 1", output)

    def test_says_what_it_could_not_read(self):
        code, output = self.check()
        found = rows(output)
        not_read = next(line for line in output.splitlines() if line.startswith("not read: "))
        self.assertIn("implementer (call 2): effort not recorded", not_read)
        self.assertIn("locator (call 4): no transcript", not_read)
        self.assertEqual(found["implementer"][3], "not recorded")
        self.assertEqual(found["locator"][2], "-")
        self.assertEqual(found["locator"][5], "not read")
        self.assertIn("general-purpose (call 5): not finished", not_read)
        self.assertIn("general-purpose (call 5): role not known", not_read)
        self.assertEqual(found["general-purpose"][5], "no pin")
        self.assertIn("mismatches: 2", output)
        self.assertEqual(len(found), 5)
        self.assertIn(model_check.CLOSING, output)

    def test_model_line_moves_only_its_role(self):
        code, before = self.check()
        self.assertEqual(rows(before)["implementer"][5], "MISMATCH")
        code, after = self.check("--model", "implementer: Opus, medium; the guard")
        moved = rows(after)
        self.assertEqual(moved["implementer"][5], "ok")
        self.assertEqual(moved["implementer"][4], "opus, medium (Model line)")
        for role in ("designer", "reviewer", "locator"):
            self.assertEqual(moved[role], rows(before)[role])
        code, prefixed = self.check("--model", "**Model:** implementer: Opus, medium; the guard")
        self.assertEqual(rows(prefixed)["implementer"][5], "ok")
        role, expect = model_check.parse_model_line("**Model:** designer: Sonnet, medium; a one-line fix")
        self.assertEqual((role, expect.model, expect.effort), ("designer", "sonnet", "medium"))

    def test_a_line_that_moves_the_reviewer_or_locator_down_is_refused(self):
        for line in ("reviewer: Sonnet, high", "reviewer: Opus, medium"):
            with self.subTest(line):
                code, output = self.check("--model", line)
                self.assertEqual(code, 2)
                self.assertIn("refused", output)
        code, output = self.check("--model", "designer: Sonnet, medium")
        self.assertNotEqual(code, 2)
        self.assertEqual(rows(output)["designer"][4], "sonnet, medium (Model line)")
        pins = model_check.load_pins(self.agents)
        self.assertIsNone(model_check.refusal("locator", model_check.Expect("haiku", "low", "Model line"), pins))
        self.assertIsNone(model_check.refusal("reviewer", model_check.Expect("opus", "max", "Model line"), pins))

    def test_two_lines_for_one_role_are_refused(self):
        code, output = self.check("--model", "designer: Opus, high", "--model", "designer: Sonnet, medium")
        self.assertEqual(code, 2)
        self.assertIn("a second --model line for designer", output)

    def test_a_bad_line_is_refused(self):
        for line in ("designer: Opus", "designer: Gpt, high", "builder: Opus, high"):
            with self.subTest(line):
                code, output = self.check("--model", line)
                self.assertEqual(code, 2)
                self.assertTrue(output.startswith("model_check: "), output)


PARTS = ("implementer: Sonnet, medium; the core", "implementer: Opus, medium; the parser",
         "implementer: Sonnet, medium; the map")


def make_parts_session(folder: Path) -> Path:
    main = folder / "parts.jsonl"
    _write_jsonl(main, [
        {"type": "user", "message": {"role": "user", "content": "go"}},
        _call("p1", "designer"),
        _call("p2", "implementer", model="sonnet", effort="medium"),
        _call("p3", "implementer", model="opus", effort="medium"),
        _call("p4", "implementer", model="sonnet", effort="medium"),
        _call("p5", "reviewer"),
    ])
    subagents = folder / "parts" / "subagents"
    runs = (("p1", "designer", "claude-opus-5-5", "medium"), ("p2", "implementer", "claude-sonnet-5-5", "medium"),
            ("p3", "implementer", "claude-opus-5-5", "medium"), ("p4", "implementer", "claude-sonnet-5-5", "medium"),
            ("p5", "reviewer", "claude-opus-5-5", "high"))
    for tool_id, kind, model, effort in runs:
        _subagent(subagents, tool_id, {"agentType": f"devflow:{kind}", "toolUseId": tool_id, "finished": True},
                  [_reply(f"r-{tool_id}", model, effort)])
    return main


def implementer_rows(output: str) -> list[list[str]]:
    found = []
    for line in output.splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) == 6 and cells[0] == "implementer":
            found.append(cells)
    return found


class TestParts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.agents = make_agents(self.base)
        self.session = make_parts_session(self.base / "sessions")

    def tearDown(self):
        self.temp.cleanup()

    def check(self, *lines: str, option: str = "--part") -> tuple[int, str]:
        extra = [item for line in lines for item in (option, line)]
        return run([str(self.session), "--agents", str(self.agents), *extra])

    def test_parts_match_in_order(self):
        code, output = self.check(*PARTS)
        found = implementer_rows(output)
        self.assertEqual(code, 0, output)
        self.assertEqual([row[5] for row in found], ["ok", "ok", "ok"])
        self.assertEqual([row[4] for row in found], ["sonnet, medium (part 1 of 3)", "opus, medium (part 2 of 3)",
                                                     "sonnet, medium (part 3 of 3)"])
        self.assertIn("mismatches: 0", output)
        self.assertIn("not read: nothing", output)

    def test_without_parts_the_split_mismatches(self):
        code, output = self.check()
        self.assertEqual(code, 1)
        self.assertEqual([row[5] for row in implementer_rows(output)], ["ok", "MISMATCH", "ok"])
        code, output = self.check("implementer: Opus, medium; the guard", option="--model")
        self.assertEqual(code, 1)
        self.assertEqual([row[5] for row in implementer_rows(output)], ["MISMATCH", "ok", "MISMATCH"])

    def test_parts_out_of_order_mismatch(self):
        code, output = self.check(PARTS[1], PARTS[0], PARTS[2])
        self.assertEqual(code, 1)
        self.assertEqual([row[5] for row in implementer_rows(output)], ["MISMATCH", "MISMATCH", "ok"])
        self.assertIn("mismatches: 2", output)

    def test_a_part_not_run_is_named_and_not_counted(self):
        code, output = self.check(*PARTS, "implementer: Opus, high; the release notes")
        not_read = next(line for line in output.splitlines() if line.startswith("not read: "))
        self.assertEqual(code, 0, output)
        self.assertIn("part 4 of 4 (opus, high): no implementer call", not_read)
        self.assertIn("mismatches: 0", output)

    def test_a_call_beyond_the_parts_is_judged_against_the_pin(self):
        code, output = self.check(PARTS[0], PARTS[1])
        found = implementer_rows(output)
        self.assertEqual(code, 0, output)
        self.assertEqual(found[2][4], "sonnet, medium (pin, beyond the 2 parts)")
        self.assertEqual(found[2][5], "ok")

    def test_bad_parts_are_refused(self):
        for lines, option in ((("designer: Sonnet, medium; a part",), "--part"),
                              (("implementer: Opus",), "--part")):
            with self.subTest(lines):
                code, output = self.check(*lines, option=option)
                self.assertEqual(code, 2)
                self.assertTrue(output.startswith("model_check: "), output)
        code, output = run([str(self.session), "--agents", str(self.agents),
                            "--model", "implementer: Opus, medium; the guard", "--part", PARTS[0]])
        self.assertEqual(code, 2)
        self.assertTrue(output.startswith("model_check: "), output)
        self.assertIn("one or the other", output)
        code, output = self.check("designer: Sonnet, medium")
        self.assertIn("a part is an implementer line", output)


class TestFindsTheSession(unittest.TestCase):
    def test_finds_the_session(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            agents = make_agents(base)
            workspace = base / "claude-eval-1"
            make_session(workspace / "config" / "projects" / "-tmp-project", "w1")
            code, output = run([str(workspace), "--agents", str(agents)])
            self.assertIn("session w1 (", output)
            self.assertEqual(code, 1)

            project = base / "my-project"
            project.mkdir()
            root = base / "projects"
            folder = root / session_extract.folder_names(str(project.resolve()))[0]
            old = make_session(folder, "old")
            new = make_session(folder, "new")
            now = time.time()
            os.utime(old, (now - 100, now - 100))
            os.utime(new, (now, now))
            code, output = run([str(project), "--projects-root", str(root), "--agents", str(agents)])
            self.assertIn("session new (", output)
            self.assertNotIn("session old (", output)
            code, output = run([str(project), "--projects-root", str(root), "--agents", str(agents),
                                "--count", "2", "--exclude", "new"])
            self.assertIn("session old (", output)
            self.assertNotIn("session new (", output)

            code, output = run([str(base / "nowhere"), "--projects-root", str(root), "--agents", str(agents)])
            self.assertEqual(code, 2)
            self.assertIn("no sessions folder", output)


class TestRealPins(unittest.TestCase):
    def test_reads_the_real_pins(self):
        pins = model_check.load_pins(model_check.PINS_DIR)
        self.assertEqual((pins["designer"].model, pins["designer"].effort), ("opus", "medium"))
        self.assertEqual((pins["reviewer"].model, pins["reviewer"].effort), ("opus", "high"))
        self.assertEqual((pins["planner"].model, pins["planner"].effort), ("opus", "high"))
        self.assertEqual((pins["locator"].model, pins["locator"].effort), ("haiku", None))


if __name__ == "__main__":
    unittest.main()
