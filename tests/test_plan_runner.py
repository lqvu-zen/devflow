from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "tools" / "plan_runner.py"


def _load():
    spec = importlib.util.spec_from_file_location("devflow_plan_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["devflow_plan_runner"] = module
    spec.loader.exec_module(module)
    return module


plan_runner = _load()

PLAN = "docs/plans/release-x.md"
STATUS = "docs/STATUS.md"

STATUS_MD = """# Status

## Releases

| Release | What | Plan |
|---|---|---|
| **x** (in progress) | three small steps | `docs/plans/release-x.md` |
"""


def plan_md(gate: bool = False) -> str:
    gate_line = "**Gate:** Ada signs the wording off before anything is committed.\n" if gate else ""
    return f"""# x

## Who does what

| Step | Who | How |
|---|---|---|
| 1 Alpha | coding session | `/devflow:add-feature` |
| 2 Beta | coding session | `/devflow:add-feature` |
| 3 Gamma | coding session | `/devflow:add-feature` |

## Steps

### 1 — Alpha

**Files:** `a.txt`.
**Needs** nothing.
{gate_line}
### 2 — Beta

**Files:** `b.txt`.
**Needs** nothing.

### 3 — Gamma

**Files:** `c.txt`.
**Needs** nothing.

## Order

1, 2, 3

## Status

| Step | State |
|---|---|
| 1 Alpha | — |
| 2 Beta | — |
| 3 Gamma | — |
"""


FAKE_CLAUDE = r'''
import json
import os
import re
import subprocess
import sys
import time

start = time.time()
log = os.environ["FAKE_LOG"]
with open(os.environ["FAKE_SCRIPT"], encoding="utf-8") as handle:
    calls = json.load(handle)
try:
    with open(log, encoding="utf-8") as handle:
        index = sum(1 for _ in handle)
except FileNotFoundError:
    index = 0
spec = calls[index] if index < len(calls) else {}
record = {"argv": sys.argv[1:], "pid": os.getpid(), "start": start, "cwd": os.getcwd(),
          "token": os.environ.get("DEVFLOW_COMMIT_WITHOUT_ASKING")}
if spec.get("waived"):
    done = subprocess.run([sys.executable, os.environ["FAKE_RUNNER"], "--waived"], capture_output=True,
                          text=True)
    record["waived"] = [done.returncode, done.stdout.strip()]
if "row" in spec:
    plan = os.path.join("docs", "plans", "release-x.md")
    with open(plan, encoding="utf-8", newline="") as handle:
        text = handle.read()
    lines = text.split("\n")
    for number, state in spec["row"].items():
        for i, line in enumerate(lines):
            match = re.match(r"\| (\d+) ([^|]*?) \|", line)
            if match and match.group(1) == number and line.rstrip("\r").count("|") == 3:
                lines[i] = f"| {number} {match.group(2)} | {state} |" + ("\r" if line.endswith("\r") else "")
    with open(plan, "w", encoding="utf-8", newline="") as handle:
        handle.write("\n".join(lines))
    with open(plan, encoding="utf-8", newline="") as handle:
        record["plan_after"] = handle.read()
if spec.get("commit"):
    with open(spec["commit"], "w", encoding="utf-8") as handle:
        handle.write("work\n")
    subprocess.run(["git", "add", "--", spec["commit"]], check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "work " + spec["commit"]], check=True, capture_output=True)
if spec.get("foreign"):
    with open(spec["foreign"], "w", encoding="utf-8") as handle:
        handle.write("left behind\n")
time.sleep(spec.get("sleep", 0))
if spec.get("out") == "text":
    print("this is not json")
else:
    denials = [d if isinstance(d, list) else [d, {}] for d in spec.get("denials", [])]
    result = {"type": "result", "subtype": spec.get("subtype", "success"), "is_error": spec.get("error", False),
              "session_id": f"s{index}",
              "permission_denials": [{"tool_name": name, "tool_use_id": "t", "tool_input": given}
                                     for name, given in denials]}
    if spec.get("cost", 0.25) is not None:
        result["total_cost_usd"] = spec.get("cost", 0.25)
    print("progress line")
    print(json.dumps(result))
record["end"] = time.time()
with open(log, "a", encoding="utf-8") as handle:
    handle.write(json.dumps(record) + "\n")
'''


def green(project, head):
    return "success"


class RunnerCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project = self.tmp / "p"
        self.project.mkdir()
        self.fake = self.tmp / "fake_claude.py"
        self.fake.write_text(FAKE_CLAUDE, encoding="utf-8")
        self.log = self.tmp / "log.jsonl"
        self.script = self.tmp / "script.json"
        self.claude = [sys.executable, str(self.fake)]
        self.env = mock.patch.dict(os.environ, {"FAKE_LOG": str(self.log), "FAKE_SCRIPT": str(self.script),
                                                "FAKE_RUNNER": str(RUNNER_PATH),
                                                "CLAUDE_PROJECT_DIR": str(self.project)})
        self.env.start()
        self.addCleanup(self.env.stop)
        os.environ.pop(plan_runner.WAIVER_ENV, None)
        self.scaffold()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.project, check=True, capture_output=True, text=True,
                              encoding="utf-8").stdout

    def write_files(self, config=None, gate=False):
        (self.project / ".claude").mkdir(exist_ok=True)
        (self.project / ".claude" / "devflow.json").write_text(json.dumps(config or {"name": "x"}),
                                                              encoding="utf-8")
        (self.project / "docs" / "plans").mkdir(parents=True, exist_ok=True)
        (self.project / STATUS).write_text(STATUS_MD, encoding="utf-8")
        (self.project / PLAN).write_text(plan_md(gate), encoding="utf-8")
        (self.project / "README.md").write_text("x\n", encoding="utf-8")

    def scaffold(self):
        self.write_files()
        self.git("init", "-q", "-b", "develop")
        self.git("config", "user.name", "t")
        self.git("config", "user.email", "t@t")
        self.git("config", "core.autocrlf", "false")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "start")

    def reset(self, config=None, gate=False):
        self.write_files(config, gate)
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", "reset")

    def calls(self, specs):
        self.script.write_text(json.dumps(specs), encoding="utf-8")

    def records(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def run_plan(self, steps=5, dollars=None, flag=False, model=None, mode=None, ci=green, token=None):
        said = []
        rows, reason, code = plan_runner.run_plan(self.project, steps, dollars, flag, model, mode,
                                                  self.claude, ci=ci, token=token, say=said.append)
        return rows, reason, code

    def main(self, *args, ci=green):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = plan_runner.main(list(args), claude=self.claude, ci=ci)
        return code, out.getvalue()


class TestRunsSteps(RunnerCase):
    def test_two_ready_steps_run_one_after_the_other_each_in_its_own_process(self):
        self.calls([{"row": {"1": "done: abc first"}, "commit": "a.txt", "sleep": 0.3, "cost": 0.25},
                    {"row": {"2": "done: def second"}, "commit": "b.txt", "cost": 0.5}])
        code, out = self.main("--steps", "2")
        first, second = self.records()
        self.assertNotEqual(first["pid"], second["pid"])
        self.assertGreaterEqual(second["start"], first["end"])
        self.assertEqual(first["argv"][:4], ["-p", "/devflow:next-step", "--output-format", "json"])
        hashes = self.git("log", "--reverse", "--format=%h", "-2").split()
        self.assertIn(f"- 1 Alpha: done; commits {hashes[0]}; $0.25", out)
        self.assertIn(f"- 2 Beta: done; commits {hashes[1]}; $0.50", out)
        self.assertIn("Plan runner: --commit-without-asking off; 2 steps; $0.75 spent", out)
        self.assertIn("Stopped: the step limit (2) is reached.", out)
        self.assertEqual(code, 0)

    def test_the_step_limit_ends_the_run(self):
        self.calls([{"row": {"1": "done"}}, {"row": {"2": "done"}}])
        rows, reason, code = self.run_plan(steps=1)
        self.assertEqual((len(rows), len(self.records()), reason, code),
                         (1, 1, "the step limit (1) is reached", 0))

    def test_the_dollar_limit_ends_the_run_and_passes_what_is_left(self):
        self.calls([{"row": {"1": "done"}, "cost": 0.6}, {"row": {"2": "done"}, "cost": 0.4}])
        rows, reason, code = self.run_plan(dollars=1.0)
        budgets = [record["argv"][record["argv"].index("--max-budget-usd") + 1] for record in self.records()]
        self.assertEqual(budgets, ["1.00", "0.40"])
        self.assertEqual((reason, code), ("the dollar limit ($1.00) is reached: $1.00 spent", 0))

    def test_an_unread_cost_says_cost_not_read_and_stops_a_dollar_limited_run(self):
        self.calls([{"row": {"1": "done"}, "out": "text"}, {"row": {"2": "done"}}])
        rows, reason, code = self.run_plan(dollars=5.0)
        self.assertEqual(len(self.records()), 1)
        self.assertEqual((reason, code), ("a session's cost was not read, so the dollar limit can't be kept", 1))
        lines = plan_runner.summary(rows, reason, False, None)
        self.assertIn("cost not read", lines[0])
        self.assertTrue(lines[1].endswith("; cost not read"), lines[1])

    def test_without_a_dollar_limit_an_unread_cost_does_not_stop(self):
        self.calls([{"row": {"1": "done"}, "out": "text"}, {"row": {"2": "done"}}])
        rows, reason, code = self.run_plan(steps=2)
        self.assertEqual((len(rows), reason), (2, "the step limit (2) is reached"))

    def test_the_board_orchestrator_model_is_passed(self):
        self.assertEqual(plan_runner.orchestrator_model({}), "sonnet")
        self.assertEqual(plan_runner.orchestrator_model({"models": {"orchestrator": "Opus"}}), "opus")
        self.reset(config={"name": "x", "models": {"orchestrator": "Opus"}})
        self.calls([{"row": {"1": "done"}}])
        self.main("--steps", "1")
        argv = self.records()[0]["argv"]
        self.assertEqual(argv[argv.index("--model") + 1], "opus")
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "acceptEdits")
        self.assertNotIn("--max-budget-usd", argv)

    def test_the_permission_mode_defaults_to_accept_edits_and_default_passes_through(self):
        self.calls([{"row": {"1": "done"}}, {"row": {"2": "done"}}])
        self.main("--steps", "1")
        self.main("--steps", "1", "--permission-mode", "default")
        modes = [record["argv"][record["argv"].index("--permission-mode") + 1] for record in self.records()]
        self.assertEqual(modes, ["acceptEdits", "default"])

    def test_each_step_says_it_is_starting_before_its_session_runs(self):
        self.calls([{"row": {"1": "done"}}])
        said = []
        plan_runner.run_plan(self.project, 1, None, False, None, None, self.claude, ci=green, say=said.append)
        self.assertEqual(said[0], f"Running step 1 Alpha ({PLAN}) with /devflow:add-feature...")
        self.assertTrue(said[1].startswith("- 1 Alpha: done"), said)

    def test_the_command_line(self):
        self.assertEqual(plan_runner.claude_argv("claude", "sonnet", 2.5, "acceptEdits"),
                         ["claude", "-p", "/devflow:next-step", "--output-format", "json", "--model", "sonnet",
                          "--max-budget-usd", "2.50", "--permission-mode", "acceptEdits"])
        self.assertEqual(self.main("--steps", "1", "--permission-mode", "bypassPermissions")[0], 2)
        self.assertEqual(self.main("--steps", "0")[0], 2)
        self.assertEqual(self.main("--waived", "--steps", "1")[0], 2)
        self.assertEqual(self.records(), [])


class TestStops(RunnerCase):
    def test_a_stop_line_ends_the_run_with_its_reason(self):
        self.reset(gate=True)
        self.calls([{"row": {"1": "done"}}])
        code, out = self.main("--steps", "3")
        self.assertEqual(self.records(), [])
        self.assertEqual(code, 0)
        self.assertIn("Stopped: step 1 is at an uncleared Gate. Next: the maintainer does what the Gate line "
                      "says, then runs /devflow:next-step again.", out)
        self.assertIn("0 steps", out)

    def test_a_session_that_leaves_its_row_not_done_ends_the_run_and_names_the_step(self):
        self.calls([{"row": {"1": "stopped: still red, see Tried"}}, {"row": {"2": "done"}}])
        rows, reason, code = self.run_plan()
        self.assertEqual(len(self.records()), 1)
        self.assertEqual((reason, code), ("step 1 ended `stopped: still red, see Tried`, not done", 1))
        self.assertEqual(rows[0].outcome, "stopped")

    def test_a_session_that_leaves_its_row_untouched_names_the_step(self):
        self.calls([{}])
        rows, reason, code = self.run_plan()
        self.assertEqual((reason, code), ("step 1 ended `—`, not done", 1))

    def test_without_the_flag_a_row_waiting_for_the_yes_stops_and_names_the_step(self):
        self.calls([{"row": {"1": "in progress (2026-11-22 10:00), waiting for the maintainer's yes"}}])
        rows, reason, code = self.run_plan()
        self.assertEqual((reason, code), ("step 1's code commit waits for the maintainer's yes", 1))
        self.assertIn("- 1 Alpha: stopped (step 1's code commit waits for the maintainer's yes); commits none",
                      plan_runner.summary(rows, reason, False, 0.25)[1])

    def test_a_permission_denial_stops_the_run_naming_the_tool(self):
        self.calls([{"row": {"1": "done"}, "denials": ["Bash", "Bash", "Edit"]}, {"row": {"2": "done"}}])
        rows, reason, code = self.run_plan()
        self.assertEqual(len(self.records()), 1)
        self.assertEqual((reason, code), ("the session met permission asks it could not answer: Bash, Edit", 1))

    def test_a_permission_denial_names_the_command_or_file(self):
        long = "git log " + "x" * 200
        self.calls([{"row": {"1": "done"}, "denials": [
            ["Bash", {"command": "git check-ignore -q docs/plans/x.md;" + chr(10) + " echo ignored=$?"}],
            ["Bash", {"command": "git check-ignore -q docs/plans/x.md;" + chr(10) + " echo ignored=$?"}],
            ["Edit", {"file_path": "docs/plans/x.md", "old_string": "a", "new_string": "b"}],
            ["Bash", {"command": long}]]}])
        rows, reason, code = self.run_plan()
        cut = " ".join(long.split())[:plan_runner.DENIAL_TEXT - 3] + "..."
        self.assertEqual(reason, "the session met permission asks it could not answer: "
                                 "Bash `git check-ignore -q docs/plans/x.md; echo ignored=$?`, "
                                 f"Edit `docs/plans/x.md`, Bash `{cut}`")

    def test_a_session_that_ends_in_an_error_says_so(self):
        self.calls([{"error": True, "subtype": "error_max_budget_usd"}])
        rows, reason, code = self.run_plan()
        self.assertEqual((reason, code), ("step 1 ended `—`, not done; the session ended with error_max_budget_usd", 1))

    def test_a_session_whose_result_cannot_be_read_says_so(self):
        self.calls([{"out": "text"}])
        rows, reason, code = self.run_plan()
        self.assertEqual((reason, code), ("step 1 ended `—`, not done; the session's result could not be read", 1))

    def test_red_or_unread_ci_stops_the_run(self):
        for conclusion in ("CI failure", "unread (gh unavailable)", "missing (no run)"):
            with self.subTest(conclusion=conclusion):
                self.log.unlink(missing_ok=True)
                self.git("checkout", "-q", "--", PLAN)
                self.calls([{"row": {"1": "done"}}, {"row": {"2": "done"}}])
                rows, reason, code = self.run_plan(ci=lambda project, head: conclusion)
                head = self.git("rev-parse", "--short=7", "HEAD").strip()
                self.assertEqual((reason, code), (f"CI on HEAD {head} is {conclusion}, not green", 1))
                self.assertEqual(len(self.records()), 1)

    def test_ci_conclusion_reads_the_run_on_head(self):
        session_start = plan_runner._session_start()
        for runs, expected in ((None, "unread (gh unavailable)"), ([], "missing (no run)"),
                               ([{"status": "completed", "conclusion": "success"}], "success"),
                               ([{"status": "completed", "conclusion": "failure"}], "CI failure"),
                               ([{"status": "in_progress", "conclusion": ""}], "CI in_progress")):
            with self.subTest(runs=runs), mock.patch.object(session_start, "_runs_for", return_value=runs):
                self.assertEqual(plan_runner.ci_conclusion(self.project, "abc"), expected)

    def test_a_session_that_leaves_foreign_changes_stops(self):
        self.calls([{"row": {"1": "done"}, "foreign": "junk.txt"}, {"row": {"2": "done"}}])
        rows, reason, code = self.run_plan()
        self.assertEqual((reason, code), ("the session left changes beyond the status and plan files: junk.txt", 1))

    def test_a_session_that_leaves_another_branch_stops(self):
        self.calls([{"row": {"1": "done"}}])
        with mock.patch.object(plan_runner, "current_branch", return_value="feature"):
            rows, reason, code = self.run_plan()
        self.assertEqual((reason, code), ("the branch is now feature, not develop", 1))


class TestRefuses(RunnerCase):
    def test_refuses_on_main(self):
        self.git("checkout", "-q", "-b", "main")
        self.calls([{"row": {"1": "done"}}])
        code, out = self.main("--steps", "1")
        self.assertEqual(code, 1)
        self.assertIn("Plan runner refused: the branch is main, not develop", out)
        self.assertEqual(self.records(), [])

    def test_refuses_on_a_foreign_dirty_tree(self):
        for change in ("untracked", "modified"):
            with self.subTest(change=change):
                if change == "untracked":
                    (self.project / "notes").mkdir(exist_ok=True)
                    (self.project / "notes" / "junk.txt").write_text("x\n", encoding="utf-8")
                    expected = "notes/junk.txt"
                else:
                    shutil.rmtree(self.project / "notes")
                    (self.project / "README.md").write_text("changed\n", encoding="utf-8")
                    expected = "README.md"
                self.calls([{"row": {"1": "done"}}])
                code, out = self.main("--steps", "1")
                self.assertEqual(code, 1)
                self.assertIn(f"Plan runner refused: the tree has changes beyond the status and plan files: "
                              f"{expected}", out)
                self.assertEqual(self.records(), [])

    def test_refuses_without_claude(self):
        layout = plan_runner._session_start().Layout({})
        self.assertIn("claude was not found", plan_runner.preflight(self.project, layout, None))

    def test_status_and_plan_edits_do_not_count_as_foreign(self):
        (self.project / STATUS).write_text(STATUS_MD + "\nmore\n", encoding="utf-8")
        (self.project / "docs" / "plans" / "release-y.md").write_text("# y\n", encoding="utf-8")
        layout = plan_runner._session_start().Layout({})
        self.assertEqual(plan_runner.foreign_changes(self.project, layout), [])
        self.assertIsNone(plan_runner.preflight(self.project, layout, "claude"))


class TestNeverWritesThePlan(RunnerCase):
    def test_the_runner_never_writes_the_plan_or_status_file(self):
        before = {path: (self.project / path).read_bytes() for path in (PLAN, STATUS)}
        self.reset(gate=True)
        gated = {path: (self.project / path).read_bytes() for path in (PLAN, STATUS)}
        self.main("--steps", "2")
        self.assertEqual(gated, {path: (self.project / path).read_bytes() for path in (PLAN, STATUS)})
        self.reset()
        self.calls([{}])
        self.run_plan()
        self.assertEqual(before, {path: (self.project / path).read_bytes() for path in (PLAN, STATUS)})
        self.log.unlink()
        self.calls([{"row": {"1": "done: a1"}}, {"row": {"2": "stopped: red, see Tried"}}])
        self.run_plan()
        written = self.records()[-1]["plan_after"]
        self.assertEqual((self.project / PLAN).read_bytes(), written.encode("utf-8"))
        self.assertEqual((self.project / STATUS).read_bytes(), before[STATUS])


class TestWaiver(RunnerCase):
    def test_with_the_flag_the_session_check_says_waived_and_the_token_is_gone_after(self):
        self.calls([{"row": {"1": "done"}, "waived": True}])
        code, out = self.main("--steps", "1", "--commit-without-asking")
        record = self.records()[0]
        self.assertEqual(record["waived"], [0, "waived"])
        self.assertRegex(record["token"], r"^[0-9a-f]{32}$")
        folder = self.project / ".git" / plan_runner.WAIVER_DIR
        self.assertFalse((folder / record["token"]).exists())
        self.assertIn("Plan runner: --commit-without-asking on; 1 step;", out)

    def test_without_the_flag_the_check_says_not_waived(self):
        with mock.patch.dict(os.environ, {plan_runner.WAIVER_ENV: "a" * 32}):
            self.calls([{"row": {"1": "done"}, "waived": True}])
            self.run_plan(steps=1)
        record = self.records()[0]
        self.assertEqual(record["waived"], [1, "not waived"])
        self.assertIsNone(record["token"])

    def test_a_claimed_token_without_its_file_or_malformed_is_not_waived(self):
        common = self.project / ".git"
        token, path = plan_runner.make_waiver(common)
        self.assertTrue(plan_runner.waived(self.project, {plan_runner.WAIVER_ENV: token}))
        for claimed in ("b" * 32, "../" + token, token.upper(), token + "0", "", "waived"):
            with self.subTest(claimed=claimed):
                self.assertFalse(plan_runner.waived(self.project, {plan_runner.WAIVER_ENV: claimed}))
        self.assertFalse(plan_runner.waived(self.project, {}))
        plan_runner.drop_waiver(path)
        self.assertFalse(plan_runner.waived(self.project, {plan_runner.WAIVER_ENV: token}))
        self.assertFalse((common / plan_runner.WAIVER_DIR).exists())

    def test_the_check_command_prints_its_verdict(self):
        token, path = plan_runner.make_waiver(self.project / ".git")
        self.addCleanup(plan_runner.drop_waiver, path)
        env = dict(os.environ)
        for value, expected in ((token, (0, "waived")), ("c" * 32, (1, "not waived"))):
            env[plan_runner.WAIVER_ENV] = value
            done = subprocess.run([sys.executable, str(RUNNER_PATH), "--waived"], capture_output=True, text=True,
                                  env=env, cwd=self.project)
            self.assertEqual((done.returncode, done.stdout.strip()), expected)


if __name__ == "__main__":
    unittest.main()
