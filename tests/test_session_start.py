from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SESSION_PATH = ROOT / "hooks" / "session_start.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


session_start = _load("devflow_session_start", SESSION_PATH)

PLAN = """# Release 2.4.0

## Steps

### 1 — Fix

## Order

1. **Fixes** 1, 2, 3 (small, independent). Done.
2. **Harness and loop rules, before step 11** (added 2026-10-19): 31, then 32. 33 runs alongside (docs only).
3. **Part A**, the riskiest:
   1. 4 and 6 can run in parallel;
   2. then 5, 7;
   3. then **12**, the early candidate, so A gets real use for the rest of 2.4.
4. **Backlog** 13, then `step 99` (P22).

## Parallel lanes and merging

Nothing 77 here.

## Status

| Step | State |
| --- | --- |
| 1 Fix OP-15 | done: fixed |
| 2 Fix GR-33 | done: fixed |
| 3 Fix SM-16 | ✅ |
| 4 A1 Find and download | done |
| 5 A1 Background | — |
| 6 A2 Signature | done |
| 7 The maintainer makes the key | — |
| 12 Early candidate | — |
| 13 Backlog | — |
| 31 Harness: permissions, hooks, checks | — |
| 32 Loop rules | — |
| 33 The plan as a graph | started 2026-10-19: Gate lines |
| 40 Not in the order | — |
"""

STATUS = """# Status

| Release | What | Plan |
|---|---|---|
| **2.3.1** (published) | fixes | `docs/archive/release-2.3.1.md` |
| **2.4** (in progress, 10 of 36 steps done) | self-update | `docs/plans/release-2.4.0.md` (approved) |

See also docs/plans/release-2.5.0.md.
"""


class TestPlanReading(unittest.TestCase):
    def test_order_from_the_plan(self):
        self.assertEqual(session_start.step_order(PLAN), [1, 2, 3, 31, 32, 33, 4, 6, 5, 7, 12, 13])

    def test_a_file_with_a_mark_or_bad_bytes(self):
        path = Path(tempfile.mkdtemp(prefix="devflow-read-"))
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        path = path / "STATUS.md"
        path.write_bytes(b"\xff\xfe\x00")
        self.assertIsNone(session_start._read(path))
        path.write_bytes(b"\xef\xbb\xbfx\n")
        self.assertEqual(session_start._read(path), "x\n")

    def test_a_bold_number_and_a_sentence_final_number(self):
        plan = "## Order\n\n1. First **12**, then 40.\n2. **Part B** 41 and 7.\n"
        self.assertEqual(session_start.step_order(plan), [12, 40, 41, 7])

    def test_states_and_next_step(self):
        order = session_start.step_order(PLAN)
        states = session_start.step_states(PLAN)
        self.assertEqual(states[31], ("Harness: permissions, hooks, checks", "—"))
        self.assertEqual(session_start.next_open(order, states), 31)
        self.assertEqual(session_start.started(order, states), [33])

    def test_rows_missing_from_the_order_come_last(self):
        plan = "## Order\n\n1. 1, then 2.\n\n## Status\n\n| 1 A | done |\n| 9 C | — |\n| 2 B | done |\n"
        order = session_start.step_order(plan)
        self.assertEqual(session_start.next_open(order, session_start.step_states(plan)), 9)

    def test_plan_lines(self):
        lines = session_start.plan_lines("docs/plans/release-2.4.0.md", PLAN)
        self.assertEqual(lines, [
            "Plan: docs/plans/release-2.4.0.md",
            "Next open step in Order: 31 Harness: permissions, hooks, checks",
            "In progress (claimed by another tab, don't take): 33 The plan as a graph",
        ])

    def test_a_stopped_step_shows_its_last_state(self):
        note = "stopped 2026-10-21: still red after two fix rounds"
        plan = PLAN.replace("| 31 Harness: permissions, hooks, checks | — |",
                            f"| 31 Harness: permissions, hooks, checks | {note} |")
        lines = session_start.plan_lines("docs/plans/release-2.4.0.md", plan)
        self.assertEqual(lines[1], "Next open step in Order: 31 Harness: permissions, hooks, checks")
        self.assertEqual(lines[2], f"  Last state: {note}")
        self.assertEqual(lines[3], "In progress (claimed by another tab, don't take): "
                                   "33 The plan as a graph")

    def test_a_bare_dash_shows_no_last_state(self):
        for dash in ("—", "–", "-"):
            plan = PLAN.replace("| 31 Harness: permissions, hooks, checks | — |",
                                f"| 31 Harness: permissions, hooks, checks | {dash} |")
            lines = session_start.plan_lines("docs/plans/release-2.4.0.md", plan)
            self.assertFalse(any("Last state" in line for line in lines), dash)

    def test_a_claimed_step_is_skipped(self):
        plan = PLAN.replace("| 31 Harness: permissions, hooks, checks | — |",
                            "| 31 Harness: permissions, hooks, checks | in progress (2026-10-19 23:30) |")
        lines = session_start.plan_lines("docs/plans/release-2.4.0.md", plan)
        self.assertEqual(lines[1], "Next open step in Order: 32 Loop rules")
        self.assertEqual(lines[2], "In progress (claimed by another tab, don't take): "
                                   "31 Harness: permissions, hooks, checks; 33 The plan as a graph")

    def test_a_started_row_counts_as_claimed(self):
        plan = "\n".join(["## Order", "", "1. 1 then 2.", "", "## Status", "",
                          "| 1 A | started 2026-10-19 |", "| 2 B | — |"])
        lines = session_start.plan_lines("docs/plans/x.md", plan)
        self.assertEqual(lines[1], "Next open step in Order: 2 B")
        self.assertEqual(lines[2], "In progress (claimed by another tab, don't take): 1 A")

    def test_every_open_step_claimed(self):
        plan = "\n".join(["## Order", "", "1. 1 then 2 then 3.", "", "## Status", "",
                          "| 1 A | done |", "| 2 B | in progress (x) |", "| 3 C | started |"])
        lines = session_start.plan_lines("docs/plans/x.md", plan)
        self.assertEqual(lines[1], "Next open step in Order: none; every open step is in progress.")
        self.assertEqual(lines[2], "In progress (claimed by another tab, don't take): 2 B; 3 C")

    def test_fallbacks(self):
        lines = session_start.plan_lines("docs/plans/x.md", "garbage, no sections at all")
        self.assertIn("couldn't read the Order and Status of docs/plans/x.md", lines[-1])
        done = "## Order\n\n1. 1 then 2.\n\n## Status\n\n| 1 A | done |\n| 2 B | done: yes |\n"
        self.assertEqual(session_start.plan_lines("docs/plans/x.md", done)[-1],
                         "Every step of docs/plans/x.md is done.")

    def test_current_plan(self):
        self.assertEqual(session_start.current_plan(STATUS), "docs/plans/release-2.4.0.md")
        self.assertEqual(session_start.current_plan("Read docs/plans/release-9.md first."),
                         "docs/plans/release-9.md")
        self.assertIsNone(session_start.current_plan("nothing"))

    def test_another_layout(self):
        layout = session_start.Layout({"status_file": "STATUS.md", "plans_dir": "work\\plans",
                                       "name": "Notes"})
        self.assertEqual(session_start.current_plan("See work/plans/v1.md.", layout),
                         "work/plans/v1.md")
        self.assertIsNone(session_start.current_plan("See docs/plans/v1.md.", layout))
        self.assertTrue(layout.is_managed_path("STATUS.md"))
        self.assertTrue(layout.is_managed_path("work/plans/v1.md"))
        self.assertFalse(layout.is_managed_path("docs/STATUS.md"))
        self.assertEqual(session_start.plan_lines(None, None, layout),
                         ["Plan: none found in STATUS.md."])


class TestGitAndCi(unittest.TestCase):
    def test_ci_when_gh_is_missing(self):
        self.assertEqual(session_start.ci_line(lambda argv: None, "d900395abc", "origin/main", 1),
                         "CI: unknown (gh unavailable)")

    def test_ci_not_pushed(self):
        def answers(argv):
            if argv[:3] == ["gh", "run", "list"]:
                return "[]" if argv[4] == "d900395abc" else (
                    '[{"status": "completed", "conclusion": "success", "workflowName": "CI"}]')
            if argv == ["git", "rev-parse", "origin/main"]:
                return "ef7600d1234"
            return None

        self.assertEqual(session_start.ci_line(answers, "d900395abc", "origin/main", 1),
                         "CI on HEAD d900395: no run (not pushed). origin/main ef7600d: CI success.")

    def test_ci_success_and_in_progress(self):
        def success(argv):
            return '[{"status": "completed", "conclusion": "success", "workflowName": "CI"}]'

        def running(argv):
            return '[{"status": "in_progress", "conclusion": "", "workflowName": "CI"}]'

        self.assertEqual(session_start.ci_line(success, "abcdef123", "origin/main", 0),
                         "CI on HEAD abcdef1: CI success.")
        self.assertEqual(session_start.ci_line(running, "abcdef123", "origin/main", 0),
                         "CI on HEAD abcdef1: CI in_progress.")

    def test_nothing_runs_past_the_deadline(self):
        bounded = session_start.runner_until(100.0, clock=lambda: 100.5)
        self.assertIsNone(bounded([sys.executable, "-c", "print('ran')"]))
        bounded = session_start.runner_until(100.0, clock=lambda: 90.0)
        self.assertEqual(bounded([sys.executable, "-c", "print('ran')"]), "ran")

    def test_branch_line(self):
        self.assertEqual(session_start.branch_line(("main", "origin/main", 1, 0, "abc")),
                         "Branch: main (1 ahead of origin/main)")
        self.assertEqual(session_start.branch_line(("main", "origin/main", 0, 0, "abc")),
                         "Branch: main (up to date with origin/main)")
        self.assertEqual(session_start.branch_line(("x", "", 0, 0, "abc")), "Branch: x (no upstream)")

    def test_changes_and_managed_line(self):
        many = "\n".join(f"?? file{i}.txt" for i in range(17))
        lines = session_start.change_lines(lambda argv: " M docs/STATUS.md\n" + many)
        self.assertEqual(lines[0], "Uncommitted (18):")
        self.assertEqual(lines[1], "   M docs/STATUS.md")
        self.assertEqual(lines[16], "  … and 3 more")
        self.assertTrue(lines[-1].startswith("Status and plan edits waiting: docs/STATUS.md."))
        clean = session_start.change_lines(lambda argv: "")
        self.assertTrue(clean[-1].startswith("Status and plan edits waiting: none."))


MODEL_PLAN = PLAN.replace("### 1 — Fix\n", "### 1 — Fix\n\n### 31 — Harness\n\n"
                                           "**Model:** implementer: Opus, medium; the download is subtle\n")
VIEW = f"Full view: python {ROOT / 'tools' / 'model_check.py'} --board"


class TestModelsLine(unittest.TestCase):
    def line(self, config: dict, plan_md: str | None = None) -> str:
        return session_start.models_line(session_start.Layout(config), plan_md)

    def test_no_board(self):
        self.assertEqual(self.line({}), f"Models: the plugin's pins (no board in .claude/devflow.json). {VIEW}")

    def test_a_board_that_moves_nothing(self):
        self.assertEqual(self.line({"models": {"designer": "default", "reviewer": "Opus, high"}}),
                         f"Models: board, every role on its default. {VIEW}")

    def test_a_board_that_moves_a_role_and_hits_a_floor(self):
        line = self.line({"models": {"designer": "Sonnet, medium", "reviewer": "Sonnet, medium", "x": "Opus"}})
        self.assertEqual(line, "Models: board moves designer to sonnet, medium; reviewer kept on opus, high "
                               f"(floor); 1 entry ignored. {VIEW}")

    def test_the_next_steps_model_line(self):
        self.assertEqual(session_start.next_open(session_start.step_order(MODEL_PLAN),
                                                 session_start.step_states(MODEL_PLAN)), 31)
        self.assertEqual(self.line({"models": {}}, MODEL_PLAN),
                         f"Models: step 31's Model line moves implementer. {VIEW}")
        self.assertEqual(self.line({"models": {}}, PLAN), f"Models: board, every role on its default. {VIEW}")

    def test_a_refused_model_line_is_marked(self):
        refused = MODEL_PLAN.replace("implementer: Opus, medium; the download is subtle", "reviewer: Sonnet, high; cheap")
        self.assertEqual(self.line({"models": {}}, refused),
                         f"Models: step 31's Model line for reviewer is not followed. {VIEW}")
        both = MODEL_PLAN.replace("**Model:** implementer: Opus, medium; the download is subtle\n",
                                  "**Model:** implementer: Opus, medium; x\n**Model:** reviewer: Sonnet, high; y\n")
        self.assertEqual(self.line({"models": {}}, both),
                         f"Models: step 31's Model line moves implementer; step 31's Model line for reviewer "
                         f"is not followed. {VIEW}")
        twice = MODEL_PLAN.replace("**Model:** implementer: Opus, medium; the download is subtle\n",
                                   "**Model:** implementer: Opus, medium; x\n**Model:** implementer: Opus, high; y\n")
        self.assertEqual(self.line({"models": {}}, twice),
                         f"Models: step 31's Model line moves implementer; step 31's Model line for implementer "
                         f"is not followed. {VIEW}")
        unreadable = MODEL_PLAN.replace("implementer: Opus, medium; the download is subtle", "implementer: Opus")
        self.assertEqual(self.line({"models": {}}, unreadable),
                         f"Models: step 31's Model line for an unreadable role is not followed. {VIEW}")

    def test_a_broken_board_gives_the_error_line(self):
        self.assertIn("1 entry ignored", self.line({"models": ["not", "an", "object"]}))
        import model_check
        original = model_check.board_summary

        def broken(*args):
            raise KeyError("models")

        model_check.board_summary = broken
        try:
            line = self.line({"models": {}})
        finally:
            model_check.board_summary = original
        self.assertEqual(line, f"Models: couldn't read the board (KeyError: 'models'). {VIEW}")

    def test_report_runs_no_more_commands_with_a_board(self):
        project = Path(tempfile.mkdtemp(prefix="devflow-models-"))
        self.addCleanup(shutil.rmtree, project, ignore_errors=True)
        counts = []
        for config in ({}, {"models": {"designer": "Sonnet, medium"}}):
            calls = []
            text = session_start.report(lambda argv: calls.append(argv) or None, project,
                                        session_start.Layout(config))
            counts.append(len(calls))
            self.assertIn("\nModels: ", text)
        self.assertLessEqual(counts[1], counts[0])


class TestMain(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp(prefix="devflow-session-"))

    def tearDown(self):
        shutil.rmtree(self.project, ignore_errors=True)

    def run_hook(self) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["CLAUDE_PROJECT_DIR"] = str(self.project)
        return subprocess.run([sys.executable, str(SESSION_PATH)], capture_output=True,
                              text=True, encoding="utf-8", env=env, timeout=60)

    def test_silent_without_a_config(self):
        result = self.run_hook()
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_reports_with_a_config_and_names_a_missing_profile(self):
        (self.project / ".claude").mkdir()
        (self.project / ".claude" / "devflow.json").write_text(
            json.dumps({"name": "Notes"}), encoding="utf-8")
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("Notes session start"))
        self.assertIn("Plan: none found in docs/STATUS.md.", result.stdout)
        self.assertIn("Run /devflow:setup", result.stdout)
        self.assertIn("\nModels: the plugin's pins (no board in .claude/devflow.json). Full view: python ",
                      result.stdout)
        (self.project / ".claude" / "devflow.md").write_text("# profile\n", encoding="utf-8")
        self.assertNotIn("Run /devflow:setup", self.run_hook().stdout)

    def test_prints_the_models_line_for_a_board(self):
        (self.project / ".claude").mkdir()
        (self.project / ".claude" / "devflow.json").write_text(
            json.dumps({"name": "Notes", "models": {"designer": "Sonnet, medium"}}), encoding="utf-8")
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("\nModels: board moves designer to sonnet, medium. Full view: python ", result.stdout)


if __name__ == "__main__":
    unittest.main()
