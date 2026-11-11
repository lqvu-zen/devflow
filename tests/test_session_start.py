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


CURRENT_PATH = "docs/plans/release-0.3.0.md"
NEXT_PATH = "docs/plans/release-0.4.0.md"

CURRENT = """# tally v0.3.0: median, JSON output and an empty-list fix

## Who does what

| Step | Who | How |
|---|---|---|
| 1 Fix #3: average of an empty list | coding session | `/devflow:fix-bug` |
| 2 Median | coding session | `/devflow:add-feature` |
| 3 JSON output | coding session | `/devflow:add-feature` |
| 4 Reject non-numbers | coding session | `/devflow:add-feature` |
| 5 Top N | coding session | `/devflow:add-feature` |
| 6 Release 0.3.0 | coding session + maintainer | `/devflow:release`; the maintainer names the version |

## Steps

### 1 — Fix #3: average of an empty list

**Files:** `tally/core.py`, `tests/test_core.py`, `docs/BEHAVIOUR.md`.
**Needs** nothing.

### 2 — Median

**Files:** `tally/core.py`, `tests/test_core.py`, `docs/BEHAVIOUR.md`.
**Needs** nothing.

### 3 — JSON output

**Files:** `tally/cli.py`, `tests/test_cli.py`, `docs/BEHAVIOUR.md`.
**Needs** nothing.

### 4 — Reject non-numbers

**Files:** `tally/cli.py`, `tests/test_cli.py`, `docs/BEHAVIOUR.md`.
**Needs** nothing.
**Gate:** Ada chooses the error wording and signs it off before anything is committed.

### 5 — Top N

**Files:** `tally/cli.py`, `tests/test_cli.py`.
**Needs** nothing.

### 6 — Release 0.3.0

**Files:** `tally/__init__.py`.
**Needs** every step above, plus green CI.

## Order

1, then 2, 3, 4 and 5, then 6.

## Status

| Step | State |
| --- | --- |
| 1 Fix #3: average of an empty list | — |
| 2 Median | — |
| 3 JSON output | — |
| 4 Reject non-numbers | — |
| 5 Top N | — |
| 6 Release 0.3.0 | — |
"""

NEXT = """# tally v0.4.0: mode, range and sum of squares

## Who does what

| Step | Who | How |
|---|---|---|
| 1 Mode | coding session | `/devflow:add-feature` |
| 2 Range | coding session | `/devflow:add-feature` |
| 3 Sum of squares | coding session | `/devflow:add-feature` |
| 4 Release 0.4.0 | maintainer | by hand, no candidate |

## Steps

### 1 — Mode

**Files:** `tally/stats.py`.
**Needs** `v0.3.0-4` (the CLI rejects non-numbers first).

### 2 — Range

**Files:** `tally/core.py`, `tests/test_core.py`.
**Needs** nothing.

### 3 — Sum of squares

**Files:** `tally/stats.py` (new), `tests/test_stats.py` (new), `docs/BEHAVIOUR.md`, `CHANGELOG.md`.
**Needs** v0.3.0-1.
**Model:** implementer: Opus, medium; the sums are subtle

### 4 — Release 0.4.0

**Files:** `tally/__init__.py`.
**Needs** every step above.

## Order

1, then 2, then 3, then 4.

## Status

| Step | State |
| --- | --- |
| 1 Mode | — |
| 2 Range | — |
| 3 Sum of squares | — |
| 4 Release 0.4.0 | — |
"""

TWO_STATUS = """# Status

## Releases

| Release | What | Plan |
|---|---|---|
| **0.3.0** (in progress) | median, JSON output, empty-list fix | `docs/plans/release-0.3.0.md` |
| **0.4.0** (next) | mode, range, sum of squares | `docs/plans/release-0.4.0.md` |
"""


def with_states(plan_md: str, states: dict) -> str:
    lines = []
    for line in plan_md.split("\n"):
        match = session_start._STATUS_ROW.match(line)
        if match and int(match.group(1)) in states and line.startswith("| ") and line.count("|") == 3:
            line = f"| {match.group(1)} {match.group(2)} | {states[int(match.group(1))]} |"
        lines.append(line)
    return "\n".join(lines)


BLOCKED = with_states(CURRENT, {1: "done: fixed", 2: "in progress (2026-10-22 09:30)",
                                3: "in progress (2026-10-22 09:00)", 5: "in progress (2026-10-22 09:40)"})
GATE = ("Ada chooses the error wording and signs it off before anything is committed.")


def view(path: str, md: str):
    return session_start.read_plan(path, md)


class TestNextStep(unittest.TestCase):
    def test_the_next_plan_is_the_other_plan_in_a_status_table(self):
        self.assertEqual(session_start.next_plan(TWO_STATUS, CURRENT_PATH), NEXT_PATH)
        self.assertIsNone(session_start.next_plan(STATUS, "docs/plans/release-2.4.0.md"))
        self.assertEqual(session_start.next_plan(TWO_STATUS, None), CURRENT_PATH)

    def test_who_does_what_names_the_skill(self):
        self.assertEqual(session_start.who_rows(CURRENT)[6],
                         ("coding session + maintainer", "`/devflow:release`; the maintainer names the version"))
        cases = [
            (("coding session", "`/devflow:fix-bug`"), ("fix-bug", None)),
            (("coding session", "`/devflow:add-feature`"), ("add-feature", None)),
            (("maintainer", "by hand, no candidate"), (None, "is done by hand")),
            (("project manager", "session review"), (None, "is the project manager's")),
            (("coding session", "`/devflow:manage-project`"), (None, "is the project manager's")),
            (("coding session + maintainer", "`/devflow:release`; the maintainer names the version"),
             (None, "runs with /devflow:release")),
            (("Ada", "she decides on the call"), (None, "waits on Ada")),
            (("maintainer", "`/devflow:add-feature`"), (None, "waits on maintainer")),
        ]
        for (who, how), expected in cases:
            self.assertEqual(session_start.runner(who, how), expected, (who, how))
        plan = CURRENT.replace("| 2 Median | coding session | `/devflow:add-feature` |\n", "")
        self.assertEqual(session_start.blockers(view(CURRENT_PATH, plan), 2, None),
                         ["has no Who does what row"])

    def test_needs_read_own_and_other_plan_numbers(self):
        self.assertEqual(session_start.needs("nothing."), ([], [], False))
        self.assertEqual(session_start.needs("1 and 2 (not 9), `step 7`."), ([1, 2], [], False))
        self.assertEqual(session_start.needs("next-28 (the manager's name), next-2, `v0.3.0-4`."),
                         ([], [("next-28", 28), ("next-2", 2), ("v0.3.0-4", 4)], False))
        self.assertEqual(session_start.needs("every step above, plus green CI."), ([], [], True))
        self.assertEqual(session_start.needs("3. Before 28, the docs."), ([3], [], False))
        self.assertEqual(session_start.step_field(session_start.step_sections(NEXT)[3], "Needs"),
                         "v0.3.0-1.")

    def test_a_gate_blocks_until_cleared(self):
        self.assertEqual(session_start.step_field(session_start.step_sections(CURRENT)[4], "Gate"), GATE)
        self.assertEqual(session_start.blockers(view(CURRENT_PATH, CURRENT), 4, None),
                         ["is at an uncleared Gate"])
        cleared = CURRENT.replace(f"**Gate:** {GATE}", "**Gate:** cleared 2026-10-21: Ada chose the wording.")
        self.assertEqual(session_start.blockers(view(CURRENT_PATH, cleared), 4, None), [])
        uncleared = CURRENT.replace(f"**Gate:** {GATE}", "**Gate:** uncleared until Ada answers.")
        self.assertEqual(session_start.blockers(view(CURRENT_PATH, uncleared), 4, None),
                         ["is at an uncleared Gate"])

    def test_files_overlap_by_path_folder_and_glob_and_skip_the_map(self):
        line = ("`tally/core.py`, `docs/BEHAVIOUR.md`, `CHANGELOG.md`, `docs/STATUS.md`, "
                "`docs/plans/release-0.4.0.md`, `docs/plans/` (new), `src\\a.py`, `./b.py`")
        self.assertEqual(session_start.step_files(line), ["tally/core.py", "src/a.py", "b.py"])
        self.assertTrue(session_start.overlaps(["tally/core.py"], ["tests/x.py", "tally/core.py"]))
        self.assertTrue(session_start.overlaps(["evals/cases/"], ["evals/cases/x/case.yaml"]))
        self.assertTrue(session_start.overlaps(["evals/cases/x/case.yaml"], ["evals/cases/"]))
        self.assertTrue(session_start.overlaps(["evals/cases/trigger/next-step-*"],
                                               ["evals/cases/trigger/next-step-1-fires/case.yaml"]))
        self.assertTrue(session_start.overlaps(["skills/next-step/SKILL.md"], ["skills/*/SKILL.md"]))
        self.assertFalse(session_start.overlaps(["tally/core.py"], ["tally/cli.py", "evals/cases/"]))
        self.assertFalse(session_start.overlaps([], ["tally/core.py"]))

    def test_takes_the_next_open_step(self):
        choice = session_start.choose_step(view(CURRENT_PATH, CURRENT), view(NEXT_PATH, NEXT))
        self.assertEqual((choice.plan, choice.number, choice.title, choice.run, choice.stop, choice.fallback),
                         (CURRENT_PATH, 1, "Fix #3: average of an empty list", "fix-bug", None, False))
        plan = with_states(CURRENT, {1: "done: fixed", 2: "stopped 2026-10-21: red after two rounds"})
        choice = session_start.choose_step(view(CURRENT_PATH, plan), None)
        self.assertEqual((choice.number, choice.run, choice.note),
                         (2, "add-feature", "stopped 2026-10-21: red after two rounds"))
        claimed = with_states(CURRENT, {1: "in progress (2026-10-22 09:30)"})
        self.assertEqual(session_start.choose_step(view(CURRENT_PATH, claimed), None).number, 2)

    def test_stops_at_a_gate_and_says_what_next(self):
        plan = with_states(CURRENT, {1: "done", 2: "done", 3: "done"})
        choice = session_start.choose_step(view(CURRENT_PATH, plan), view(NEXT_PATH, NEXT))
        self.assertEqual((choice.number, choice.run, choice.gate, choice.fallback),
                         (4, None, GATE, False))
        self.assertEqual(choice.stop, "step 4 is at an uncleared Gate")
        self.assertEqual(choice.next_action, "the maintainer does what the Gate line says, then runs "
                                             "/devflow:next-step again")

    def test_stops_at_a_by_hand_step(self):
        plan = with_states(CURRENT.replace("`/devflow:release`; the maintainer names the version",
                                           "by hand, no candidate; the maintainer names the version"),
                           {n: "done" for n in range(1, 6)})
        choice = session_start.choose_step(view(CURRENT_PATH, plan), None)
        self.assertEqual((choice.number, choice.run), (6, None))
        self.assertEqual(choice.stop, f"no step of {CURRENT_PATH} can start: 6 is done by hand")
        self.assertEqual(choice.next_action, "the maintainer does it by hand, as the plan says")

    def test_every_step_done(self):
        plan = with_states(CURRENT, {n: "done" for n in range(1, 7)})
        choice = session_start.choose_step(view(CURRENT_PATH, plan), view(NEXT_PATH, NEXT))
        self.assertEqual((choice.number, choice.run, choice.fallback), (None, None, False))
        self.assertEqual(choice.stop, f"every step of {CURRENT_PATH} is done")
        self.assertEqual(choice.next_action, "run /devflow:manage-project to close the plan")

    def test_falls_back_to_the_next_plans_first_ready_step(self):
        choice = session_start.choose_step(view(CURRENT_PATH, BLOCKED), view(NEXT_PATH, NEXT))
        self.assertEqual((choice.plan, choice.number, choice.title, choice.run, choice.fallback),
                         (NEXT_PATH, 3, "Sum of squares", "add-feature", True))
        self.assertEqual(choice.why, ["4 is at an uncleared Gate", "6 runs with /devflow:release"])
        self.assertEqual(choice.skipped, ["1 needs v0.3.0-4",
                                          f"2 overlaps step 2 of {CURRENT_PATH} in progress"])
        no_files = BLOCKED.replace("**Files:** `tally/core.py`, `tests/test_core.py`, `docs/BEHAVIOUR.md`.\n"
                                   "**Needs** nothing.\n\n### 3", "**Needs** nothing.\n\n### 3")
        choice = session_start.choose_step(view(CURRENT_PATH, no_files), view(NEXT_PATH, NEXT))
        self.assertEqual((choice.plan, choice.run, choice.fallback), (CURRENT_PATH, None, False))
        self.assertIn(f"3 overlaps step 2 of {CURRENT_PATH} in progress", choice.skipped)
        missing = NEXT.replace("**Files:** `tally/stats.py` (new), `tests/test_stats.py` (new), "
                               "`docs/BEHAVIOUR.md`, `CHANGELOG.md`.\n", "")
        choice = session_start.choose_step(view(CURRENT_PATH, BLOCKED), view(NEXT_PATH, missing))
        self.assertIn("3 has no Files line", choice.skipped)
        self.assertEqual((choice.plan, choice.run), (CURRENT_PATH, None))

    def test_other_plan_needs_read_against_the_current_plan(self):
        nxt = view(NEXT_PATH, NEXT)
        self.assertEqual(session_start.blockers(nxt, 1, view(CURRENT_PATH, CURRENT)), ["needs v0.3.0-4"])
        self.assertEqual(session_start.blockers(nxt, 1, None), ["needs v0.3.0-4"])
        self.assertEqual(session_start.blockers(nxt, 3, view(CURRENT_PATH, BLOCKED)), [])
        self.assertEqual(session_start.blockers(nxt, 3, view(CURRENT_PATH, CURRENT)), ["needs v0.3.0-1"])
        gate_done = with_states(BLOCKED, {4: "done"})
        choice = session_start.choose_step(view(CURRENT_PATH, gate_done), nxt)
        self.assertEqual((choice.plan, choice.number, choice.why), (NEXT_PATH, 1, ["6 runs with /devflow:release"]))
        self.assertEqual(session_start.blockers(nxt, 4, None), ["is done by hand", "needs 1, 2, 3"])

    def test_no_next_plan_stops_with_the_reasons(self):
        choice = session_start.choose_step(view(CURRENT_PATH, BLOCKED), None)
        self.assertEqual((choice.plan, choice.number, choice.run, choice.gate), (CURRENT_PATH, 4, None, GATE))
        self.assertEqual(choice.stop, f"no step of {CURRENT_PATH} can start: 4 is at an uncleared Gate; "
                                      "6 runs with /devflow:release")
        self.assertEqual(choice.next_action, "the maintainer does what the Gate line says, then runs "
                                             "/devflow:next-step again")
        every = with_states(CURRENT, {n: "in progress (x)" for n in range(1, 7)})
        choice = session_start.choose_step(view(CURRENT_PATH, every), None)
        self.assertEqual(choice.stop, f"no step of {CURRENT_PATH} can start: every open step is in progress")
        self.assertEqual(choice.next_action, "the steps in progress land first")

    def test_the_summary_line_shows_the_fallback(self):
        lines = session_start.plan_lines(CURRENT_PATH, BLOCKED, session_start.DEFAULT_LAYOUT, NEXT_PATH, NEXT)
        self.assertEqual(lines, [
            f"Plan: {CURRENT_PATH}",
            f"Next open step in Order: 3 Sum of squares, from the next plan {NEXT_PATH} (no step of "
            f"{CURRENT_PATH} can start: 4 is at an uncleared Gate; 6 runs with /devflow:release)",
            "In progress (claimed by another tab, don't take): 2 Median; 3 JSON output; 5 Top N",
        ])
        stuck = with_states(NEXT, {3: "in progress (2026-10-22 09:50)"})
        lines = session_start.plan_lines(CURRENT_PATH, BLOCKED, session_start.DEFAULT_LAYOUT, NEXT_PATH, stuck)
        self.assertEqual(lines[1], f"Next open step in Order: none can start in {CURRENT_PATH} or the next plan, "
                                   f"{NEXT_PATH} (4 is at an uncleared Gate; 6 runs with /devflow:release; "
                                   f"next plan: 1 needs v0.3.0-4; 2 overlaps step 2 of {CURRENT_PATH} in progress; "
                                   "4 is done by hand)")

    def test_the_summary_is_unchanged_when_the_current_plan_can_start(self):
        layout = session_start.DEFAULT_LAYOUT
        for plan in (CURRENT, with_states(CURRENT, {1: "done", 2: "in progress (x)"}),
                     with_states(CURRENT, {1: "done", 2: "done", 3: "done"}),
                     with_states(CURRENT, {n: "done" for n in range(1, 7)})):
            self.assertEqual(session_start.plan_lines(CURRENT_PATH, plan, layout, NEXT_PATH, NEXT),
                             session_start.plan_lines(CURRENT_PATH, plan, layout))
        self.assertEqual(session_start.plan_lines(CURRENT_PATH, BLOCKED, layout, NEXT_PATH, None),
                         session_start.plan_lines(CURRENT_PATH, BLOCKED, layout))
        self.assertEqual(session_start.plan_lines(CURRENT_PATH, BLOCKED, layout)[1],
                         "Next open step in Order: 4 Reject non-numbers")

    def project_with(self, current: str, nxt: str | None = NEXT, config: dict | None = None) -> Path:
        project = Path(tempfile.mkdtemp(prefix="devflow-next-"))
        self.addCleanup(shutil.rmtree, project, ignore_errors=True)
        (project / "docs" / "plans").mkdir(parents=True)
        (project / "docs" / "STATUS.md").write_text(TWO_STATUS, encoding="utf-8")
        (project / CURRENT_PATH).write_text(current, encoding="utf-8")
        if nxt is not None:
            (project / NEXT_PATH).write_text(nxt, encoding="utf-8")
        if config is not None:
            (project / ".claude").mkdir()
            (project / ".claude" / "devflow.json").write_text(json.dumps(config), encoding="utf-8")
        return project

    def test_the_models_line_follows_the_fallback_step(self):
        layout = session_start.Layout({"models": {}})
        text = session_start.report(lambda argv: None, self.project_with(BLOCKED), layout)
        self.assertIn(f"\nModels: step 3's Model line moves implementer. {VIEW}", text)
        text = session_start.report(lambda argv: None, self.project_with(CURRENT), layout)
        self.assertIn(f"\nModels: board, every role on its default. {VIEW}", text)

    def test_the_flag_lines_for_a_fallback_and_a_stop(self):
        self.assertEqual(session_start.next_step_lines(self.project_with(BLOCKED)), [
            f"Plan: {NEXT_PATH} (the next plan)",
            f"Why: no step of {CURRENT_PATH} can start: 4 is at an uncleared Gate; 6 runs with /devflow:release",
            f"Skipped: 1 needs v0.3.0-4; 2 overlaps step 2 of {CURRENT_PATH} in progress",
            "Step: 3 Sum of squares",
            "Run: /devflow:add-feature",
        ])
        self.assertEqual(session_start.next_step_lines(self.project_with(BLOCKED, None)), [
            f"Plan: {CURRENT_PATH}",
            "Step: 4 Reject non-numbers",
            f"Gate: {GATE}",
            f"Stop: no step of {CURRENT_PATH} can start: 4 is at an uncleared Gate; 6 runs with "
            "/devflow:release. Next: the maintainer does what the Gate line says, then runs "
            "/devflow:next-step again.",
        ])
        self.assertEqual(session_start.next_step_lines(self.project_with("no plan here", None)), [
            f"Plan: {CURRENT_PATH}",
            f"Stop: couldn't read the Order and Status of {CURRENT_PATH}. Next: run /devflow:manage-project.",
        ])


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

    def run_next_step(self) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["CLAUDE_PROJECT_DIR"] = str(self.project)
        return subprocess.run([sys.executable, str(SESSION_PATH), "--next-step"], capture_output=True,
                              text=True, encoding="utf-8", env=env, timeout=60)

    def test_next_step_flag_prints_the_step(self):
        (self.project / ".claude").mkdir()
        (self.project / ".claude" / "devflow.json").write_text(json.dumps({"name": "tally"}), encoding="utf-8")
        (self.project / "docs" / "plans").mkdir(parents=True)
        (self.project / "docs" / "STATUS.md").write_text(TWO_STATUS, encoding="utf-8")
        (self.project / CURRENT_PATH).write_text(with_states(CURRENT, {1: "done: fixed"}), encoding="utf-8")
        result = self.run_next_step()
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(result.stdout, f"Plan: {CURRENT_PATH}\nStep: 2 Median\nRun: /devflow:add-feature\n")

    def test_next_step_flag_without_a_config(self):
        result = self.run_next_step()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, f"No .claude/devflow.json in {self.project}: run /devflow:setup first.\n")


if __name__ == "__main__":
    unittest.main()
