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
        self.assertTrue(layout.is_secretary_path("STATUS.md"))
        self.assertTrue(layout.is_secretary_path("work/plans/v1.md"))
        self.assertFalse(layout.is_secretary_path("docs/STATUS.md"))
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

    def test_changes_and_secretary_line(self):
        many = "\n".join(f"?? file{i}.txt" for i in range(17))
        lines = session_start.change_lines(lambda argv: " M docs/STATUS.md\n" + many)
        self.assertEqual(lines[0], "Uncommitted (18):")
        self.assertEqual(lines[1], "   M docs/STATUS.md")
        self.assertEqual(lines[16], "  … and 3 more")
        self.assertTrue(lines[-1].startswith("Secretary edits waiting: docs/STATUS.md."))


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
        (self.project / ".claude" / "devflow.md").write_text("# profile\n", encoding="utf-8")
        self.assertNotIn("Run /devflow:setup", self.run_hook().stdout)


if __name__ == "__main__":
    unittest.main()
