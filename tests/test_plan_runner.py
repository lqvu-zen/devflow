from __future__ import annotations

import contextlib
import datetime
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
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

OPTION_PREFIX = "CLAUDE_PLUGIN_OPTION_"
_SAVED_ENV: dict[str, str | None] = {}
_USER_CONFIG: list[tempfile.TemporaryDirectory] = []


def setUpModule():
    _USER_CONFIG.append(tempfile.TemporaryDirectory(prefix="devflow-user-config-"))
    names = [name for name in os.environ if name.startswith(OPTION_PREFIX)] + ["CLAUDE_CONFIG_DIR"]
    for name in names:
        _SAVED_ENV[name] = os.environ.pop(name, None)
    os.environ["CLAUDE_CONFIG_DIR"] = _USER_CONFIG[0].name


def tearDownModule():
    os.environ.pop("CLAUDE_CONFIG_DIR", None)
    for name, value in _SAVED_ENV.items():
        if value is not None:
            os.environ[name] = value
    _SAVED_ENV.clear()
    _USER_CONFIG.pop().cleanup()

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
if spec.get("deciding"):
    done = subprocess.run([sys.executable, os.environ["FAKE_RUNNER"], "--deciding"], capture_output=True,
                          text=True)
    record["deciding"] = [done.returncode, done.stdout.strip()]
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
if spec.get("child"):
    subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], stdout=sys.stdout, stderr=sys.stderr,
                     close_fds=False)
time.sleep(spec.get("sleep", 0))
if spec.get("crash"):
    sys.stderr.write(spec["crash"]["stderr"])
    record["end"] = time.time()
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
    sys.exit(spec["crash"]["code"])
if spec.get("out") == "text":
    print("this is not json")
else:
    denials = [d if isinstance(d, list) else [d, {}] for d in spec.get("denials", [])]
    result = {"type": "result", "subtype": spec.get("subtype", "success"), "is_error": spec.get("error", False),
              "session_id": f"s{index}",
              "permission_denials": [{"tool_name": name, "tool_use_id": "t", "tool_input": given}
                                     for name, given in denials]}
    if spec.get("no_session"):
        del result["session_id"]
    if spec.get("limit"):
        sentence = "You've hit your session limit \u00b7 resets 2:10am (Asia/Bangkok)"
        result["is_error"] = True
        if spec.get("limit_on") == "stderr":
            sys.stderr.write(sentence + "\n")
        else:
            result["result"] = sentence
    if spec.get("cost", 0.25) is not None:
        result["total_cost_usd"] = spec.get("cost", 0.25)
    print("progress line")
    print(json.dumps(result))
record["end"] = time.time()
with open(log, "a", encoding="utf-8") as handle:
    handle.write(json.dumps(record) + "\n")
if spec.get("limit"):
    sys.exit(1)
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

    def run_plan(self, steps=5, dollars=None, flag=False, model=None, mode=None, ci=green, token=None,
                 session_seconds=None):
        said = []
        extra = {} if session_seconds is None else {"session_seconds": session_seconds}
        rows, reason, code = plan_runner.run_plan(self.project, steps, dollars, flag, model, mode,
                                                  self.claude, ci=ci, token=token, say=said.append, **extra)
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

    def test_without_a_step_limit_three_ready_steps_run_and_the_run_ends_at_the_stop_line(self):
        self.calls([{"row": {"1": "done"}}, {"row": {"2": "done"}}, {"row": {"3": "done"}}])
        code, out = self.main()
        self.assertEqual(len(self.records()), 3)
        self.assertIn("Plan runner: --commit-without-asking off; 3 steps;", out)
        self.assertNotIn("step limit", out)
        self.assertIn("Stopped: ", out.splitlines()[-1])
        self.assertEqual(code, 0)

    def test_with_two_steps_it_ends_after_two(self):
        self.calls([{"row": {"1": "done"}}, {"row": {"2": "done"}}, {"row": {"3": "done"}}])
        rows, reason, code = self.run_plan(steps=2)
        self.assertEqual((len(rows), len(self.records()), reason, code),
                         (2, 2, "the step limit (2) is reached", 0))

    def test_run_plan_without_a_limit_runs_until_the_plan_stops(self):
        self.calls([{"row": {"1": "done"}}, {"row": {"2": "done"}}, {"row": {"3": "done"}}])
        rows, reason, code = self.run_plan(steps=None)
        self.assertEqual((len(rows), code), (3, 0))
        self.assertNotIn("step limit", reason)

    def test_the_dollar_limit_ends_the_run_and_passes_what_is_left(self):
        self.calls([{"row": {"1": "done"}, "cost": 0.6}, {"row": {"2": "done"}, "cost": 0.4}])
        rows, reason, code = self.run_plan(dollars=1.0)
        budgets = [record["argv"][record["argv"].index("--max-budget-usd") + 1] for record in self.records()]
        self.assertEqual(budgets, ["1.00", "0.40"])
        self.assertEqual((reason, code), ("the dollar limit ($1.00) is reached: $1.00 spent", 0))

    def test_the_budget_passed_is_rounded_to_cents(self):
        self.calls([{"row": {"1": "done"}, "cost": 0.7}, {"row": {"2": "done"}, "cost": 0.2},
                    {"row": {"3": "done"}, "cost": 0.25}])
        self.run_plan(dollars=1.0)
        budgets = [record["argv"][record["argv"].index("--max-budget-usd") + 1] for record in self.records()]
        self.assertEqual(budgets, ["1.00", "0.30", "0.10"])

    def test_less_than_a_cent_left_counts_as_the_limit(self):
        self.calls([{"row": {"1": "done"}, "cost": 0.6}, {"row": {"2": "done"}, "cost": 0.396},
                    {"row": {"3": "done"}}])
        rows, reason, code = self.run_plan(dollars=1.0)
        self.assertEqual(len(self.records()), 2)
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

    def test_a_user_orchestrator_default_is_used_and_the_board_wins(self):
        option = "CLAUDE_PLUGIN_OPTION_DEFAULT_MODELS"
        with mock.patch.dict(os.environ, {option: "orchestrator: opus; implementer: sonnet, low"}):
            self.assertEqual(plan_runner.orchestrator_model({}), "opus")
            self.assertEqual(plan_runner.orchestrator_model({"models": {"orchestrator": "Haiku"}}), "haiku")
            self.reset(config={"name": "x"})
            self.calls([{"row": {"1": "done"}}])
            self.main("--steps", "1")
        argv = self.records()[0]["argv"]
        self.assertEqual(argv[argv.index("--model") + 1], "opus")
        settings = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "settings.json"
        settings.write_text(json.dumps({"pluginConfigs": {"devflow@devflow": {
            "options": {"default_models": "orchestrator: haiku"}}}}), encoding="utf-8")
        try:
            self.assertEqual(plan_runner.orchestrator_model({}), "haiku")
        finally:
            settings.unlink()
        self.assertEqual(plan_runner.orchestrator_model({}), "sonnet")

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
        self.start_stamp(said[0])
        self.assertTrue(said[1].startswith("- 1 Alpha: done"), said)

    def start_stamp(self, line):
        prefix = f"Running step 1 Alpha ({PLAN}) with /devflow:add-feature... (started "
        self.assertTrue(line.startswith(prefix), line)
        self.assertTrue(line.endswith(")"), line)
        return datetime.datetime.strptime(line[len(prefix):-1], plan_runner.START_FORMAT)

    def test_the_start_time_is_out_while_the_session_still_runs(self):
        self.calls([{"row": {"1": "done"}, "sleep": 3}])
        said = []
        returned = []

        def run():
            returned.append(plan_runner.run_plan(self.project, 1, None, False, None, None, self.claude, ci=green,
                                                 say=said.append))

        before = datetime.datetime.now().astimezone().replace(microsecond=0)
        thread = threading.Thread(target=run)
        thread.start()
        self.addCleanup(thread.join)
        deadline = time.time() + 20
        while not said and time.time() < deadline:
            time.sleep(0.05)
        self.assertTrue(said, "no start line while the session ran")
        self.assertTrue(thread.is_alive())
        self.assertEqual(self.records(), [])
        started = self.start_stamp(said[0])
        self.assertTrue(before <= started <= datetime.datetime.now().astimezone(), said[0])
        thread.join(60)
        self.assertFalse(thread.is_alive())
        self.assertTrue(said[1].startswith("- 1 Alpha: done"), said)
        rows, reason, code = returned[0]
        self.assertTrue(plan_runner.summary(rows, reason, False, 0.25)[0].startswith("Plan runner: "))

    def test_the_command_line(self):
        self.assertEqual(plan_runner.claude_argv("claude", "sonnet", 2.5, "acceptEdits"),
                         ["claude", "-p", "/devflow:next-step", "--output-format", "json", "--model", "sonnet",
                          "--max-budget-usd", "2.50", "--permission-mode", "acceptEdits"])
        self.assertEqual(self.main("--steps", "1", "--permission-mode", "bypassPermissions")[0], 2)
        self.assertEqual(self.main("--steps", "0")[0], 2)
        self.assertIsNone(plan_runner.parser().parse_args([]).steps)
        self.assertEqual(plan_runner.parser().parse_args(["--steps", "2"]).steps, 2)
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

    def test_a_step_with_a_budget_stops_the_run_before_its_session_starts(self):
        budget = "$1.00 for the eval runs; approved 2026-10-21 09:00 by the maintainer"
        text = plan_md().replace("**Files:** `b.txt`.\n**Needs** nothing.\n",
                                 f"**Files:** `b.txt`.\n**Needs** nothing.\n**Budget:** {budget}\n")
        self.assertIn("**Budget:**", text)
        (self.project / PLAN).write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "budget step")
        self.calls([{"row": {"1": "done"}, "commit": "a.txt"}, {"row": {"2": "done"}}])
        code, out = self.main("--steps", "3", "--dollars", "5")
        self.assertEqual(len(self.records()), 1)
        self.assertEqual(code, 0)
        self.assertIn("- 1 Alpha: done", out)
        self.assertIn(f"Stopped: step 2 has a Budget of its own ({budget}): its spend is outside --dollars and "
                      "its runs outlive a headless turn; take it with /devflow:next-step in a session.", out)
        self.assertEqual(plan_runner.ask_next_step(self.project).budget, budget)

    def test_a_step_without_a_budget_reads_none(self):
        self.assertIsNone(plan_runner.ask_next_step(self.project).budget)

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

    def test_a_done_step_with_refusals_lists_them_and_the_run_goes_on(self):
        self.calls([{"row": {"1": "done"}, "denials": ["Bash", "Bash", "Edit"]}, {"row": {"2": "done"}}])
        said = []
        rows, reason, code = plan_runner.run_plan(self.project, 2, None, False, None, None, self.claude, ci=green,
                                                  say=said.append)
        self.assertEqual(len(self.records()), 2)
        self.assertEqual((reason, code), ("the step limit (2) is reached", 0))
        self.assertEqual((rows[0].outcome, rows[0].refused), ("done", ("Bash", "Edit")))
        listed = [plan_runner.row_line(rows[0]), "  - refused Bash", "  - refused Edit"]
        for lines in (plan_runner.summary(rows, reason, False, 0.5), said):
            at = lines.index(listed[0])
            self.assertEqual(lines[at:at + 3], listed)

    def test_a_not_done_step_names_its_refusals_in_its_stop(self):
        claim = "in progress (2026-11-27 10:00)"
        self.calls([{"row": {"1": claim}, "denials": [["Bash", {"command": "sed -n 1p x"}]]},
                    {"row": {"2": "done"}}])
        rows, reason, code = self.run_plan()
        self.assertEqual(len(self.records()), 1)
        self.assertEqual((reason, code),
                         (f"step 1 ended `{claim}`, not done; the session met permission asks it could not answer: "
                          "Bash `sed -n 1p x`", 1))
        self.assertEqual(rows[0].refused, ())

    def test_a_done_step_with_refusals_and_red_ci_stops_naming_both(self):
        self.calls([{"row": {"1": "done"}, "denials": ["Bash"]}, {"row": {"2": "done"}}])
        rows, reason, code = self.run_plan(ci=lambda project, head: "CI failure")
        head = self.git("rev-parse", "--short=7", "HEAD").strip()
        self.assertEqual(len(self.records()), 1)
        self.assertEqual((reason, code),
                         (f"CI on HEAD {head} is CI failure, not green; the session met permission asks it could "
                          "not answer: Bash", 1))
        self.assertEqual(rows[0].refused, ())

    def test_a_refusal_names_the_command_or_file(self):
        long = "git log " + "x" * 200
        self.calls([{"row": {"1": "done"}, "denials": [
            ["Bash", {"command": "git check-ignore -q docs/plans/x.md;" + chr(10) + " echo ignored=$?"}],
            ["Bash", {"command": "git check-ignore -q docs/plans/x.md;" + chr(10) + " echo ignored=$?"}],
            ["Edit", {"file_path": "docs/plans/x.md", "old_string": "a", "new_string": "b"}],
            ["Bash", {"command": long}]]}])
        rows, reason, code = self.run_plan()
        cut = " ".join(long.split())[:plan_runner.DENIAL_TEXT - 3] + "..."
        self.assertEqual(rows[0].refused, ("Bash `git check-ignore -q docs/plans/x.md; echo ignored=$?`",
                                           "Edit `docs/plans/x.md`", f"Bash `{cut}`"))

    def test_a_session_that_ends_in_an_error_says_so(self):
        self.calls([{"error": True, "subtype": "error_max_budget_usd"}])
        rows, reason, code = self.run_plan()
        self.assertEqual((reason, code), ("step 1 ended `—`, not done; the session ended with error_max_budget_usd", 1))

    def test_a_stopped_step_says_how_to_resume_its_session(self):
        self.calls([{"row": {"1": "in progress (2026-11-23 23:03)"}}])
        code, out = self.main("--steps", "2")
        self.assertEqual(out.splitlines()[-1], "To answer step 1's session: claude --resume s0")

    def test_a_done_run_gives_no_resume_line(self):
        self.calls([{"row": {"1": "done"}}])
        code, out = self.main("--steps", "1")
        self.assertNotIn("--resume", out)

    def test_a_session_whose_result_cannot_be_read_says_so(self):
        self.calls([{"out": "text"}])
        rows, reason, code = self.run_plan()
        self.assertEqual((reason, code), ("step 1 ended `—`, not done; the session's result could not be read", 1))

    def hung_session(self, **spec):
        claim = "in progress (2026-11-24 10:00)"
        self.calls([{"row": {"1": claim}, "sleep": 60, **spec}])
        started = time.time()
        rows, reason, code = self.run_plan(session_seconds=2)
        self.assertLess(time.time() - started, 30)
        self.assertEqual((reason, code),
                         ("step 1's session ran past the session timeout (2 seconds) and was ended; "
                          "its row was left as it was", 1))
        self.assertEqual((rows[0].outcome, rows[0].cost), ("stopped", None))
        self.assertEqual(plan_runner.row_state(self.project, PLAN, 1), claim)

    def test_a_hung_session_ends_the_run_at_the_timeout(self):
        self.hung_session()

    def test_a_hung_session_with_a_child_holding_its_output_is_ended_too(self):
        self.hung_session(child=True)

    def test_a_crashed_session_gives_its_exit_and_error_line(self):
        stderr = "C:\\x\\cli.js:1\nTypeError: boom\n    at main (cli.js:1)\n"
        self.calls([{"crash": {"code": 3, "stderr": stderr}}])
        rows, reason, code = self.run_plan()
        self.assertEqual((reason, code),
                         ("step 1 ended `—`, not done; the session's result could not be read "
                          "(exit 3: TypeError: boom)", 1))
        self.assertEqual(plan_runner.crash_text(3, ""), "exit 3")
        self.assertIsNone(plan_runner.crash_text(0, "TypeError: boom"))
        self.assertEqual(plan_runner.crash_text(1, "first\nlast line\n"), "exit 1: last line")
        cut = plan_runner.crash_text(1, "Error: " + "x" * 300)
        self.assertEqual(len(cut), len("exit 1: ") + plan_runner.CRASH_TEXT)
        self.assertTrue(cut.endswith("..."))

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


LIMIT_SENTENCE = "You've hit your session limit \u00b7 resets 2:10am (Asia/Bangkok)"
CLAIMED = "in progress (2026-11-24 10:00)"
RETAKE = r"stopped \(\d{4}-\d\d-\d\d \d\d:\d\d\): cut off by the usage limit; retake it"


class TestUsageLimit(RunnerCase):
    def crlf_plan(self):
        text = (self.project / PLAN).read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        (self.project / PLAN).write_bytes(text)
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", "crlf")

    def test_a_session_cut_off_by_the_limit_stops_the_run_with_that_reason(self):
        self.calls([{"row": {"1": CLAIMED}, "limit": True}, {"row": {"2": "done"}}])
        code, out = self.main("--steps", "3")
        self.assertEqual(len(self.records()), 1)
        self.assertEqual(code, 1)
        self.assertIn("Stopped: the usage limit cut off step 1's session (You've hit your session limit", out)
        self.assertIn("resets 2:10am (Asia/Bangkok)", out)
        self.assertRegex(out, r"its row now reads `" + RETAKE + r"`, so the next run takes it again")
        self.assertIn("after the reset, run the plan again, which retakes the step", out)
        self.assertNotIn("resume the cut-off session", out)
        self.assertIn("- 1 Alpha: stopped (the usage limit cut off", out)
        self.assertEqual(out.splitlines()[-1], "To answer step 1's session: claude --resume s0")

    def test_its_claimed_row_is_marked_for_retaking_and_only_that_line_changes(self):
        self.crlf_plan()
        before = (self.project / PLAN).read_bytes()
        self.calls([{"row": {"1": CLAIMED}, "limit": True}])
        self.run_plan()
        after = (self.project / PLAN).read_bytes()
        self.assertNotIn(b"\n", after.replace(b"\r\n", b""))
        old = before.decode().replace("| 1 Alpha | — |", "| 1 Alpha | " + CLAIMED + " |").split("\r\n")
        new = after.decode().split("\r\n")
        self.assertEqual(len(old), len(new))
        changed = [(a, b) for a, b in zip(old, new) if a != b]
        self.assertEqual(len(changed), 1)
        self.assertRegex(changed[0][1], r"^\| 1 Alpha \| " + RETAKE + r" \|$")
        session_start = plan_runner._session_start()
        state = session_start.step_states(after.decode())[1][1]
        self.assertFalse(session_start.is_claimed(state))
        self.assertTrue(session_start.is_open(state))
        self.assertEqual((self.project / STATUS).read_text(encoding="utf-8"), STATUS_MD)

    def test_a_byte_order_mark_survives_the_row_write(self):
        text = plan_md().replace("| 1 Alpha | — |", "| 1 Alpha | " + CLAIMED + " |")
        (self.project / PLAN).write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
        self.assertTrue(plan_runner.mark_for_retake(self.project, PLAN, 1, CLAIMED, "2026-11-24 11:00"))
        data = (self.project / PLAN).read_bytes()
        self.assertTrue(data.startswith(b"\xef\xbb\xbf# x"))
        self.assertIn("| 1 Alpha | stopped (2026-11-24 11:00): cut off by the usage limit; retake it |".encode(),
                      data)

    def test_it_writes_nothing_unless_exactly_one_line_matches(self):
        for state in ("—", "done"):
            with self.subTest(state=state):
                text = plan_md().replace("| 1 Alpha | — |", f"| 1 Alpha | {state} |")
                (self.project / PLAN).write_text(text, encoding="utf-8")
                before = (self.project / PLAN).read_bytes()
                self.assertFalse(plan_runner.mark_for_retake(self.project, PLAN, 1, CLAIMED, "2026-11-24 11:00"))
                self.assertEqual((self.project / PLAN).read_bytes(), before)
        doubled = plan_md().replace("| 1 Alpha | — |", f"| 1 Alpha | {CLAIMED} |\n| 1 Alpha | {CLAIMED} |")
        (self.project / PLAN).write_text(doubled, encoding="utf-8")
        self.assertFalse(plan_runner.mark_for_retake(self.project, PLAN, 1, CLAIMED, "2026-11-24 11:00"))
        self.assertEqual((self.project / PLAN).read_text(encoding="utf-8"), doubled)
        self.assertFalse(plan_runner.mark_for_retake(self.project, "docs/plans/none.md", 1, CLAIMED, "x"))

    def test_the_next_run_takes_that_step_again(self):
        self.calls([{"row": {"1": CLAIMED}, "limit": True}, {"row": {"1": "done"}}, {"row": {"2": "done"}}])
        rows, reason, code = self.run_plan(steps=1)
        self.assertIn("usage limit", reason)
        self.assertEqual(len(self.records()), 1)
        rows, reason, code = self.run_plan(steps=1)
        self.assertEqual((len(rows), rows[0].number, rows[0].outcome, code), (1, 1, "done", 0))
        self.assertEqual(len(self.records()), 2)

    def test_the_limit_on_stderr_is_read_too(self):
        self.calls([{"row": {"1": CLAIMED}, "limit": True, "limit_on": "stderr"}])
        rows, reason, code = self.run_plan()
        self.assertTrue(reason.startswith("the usage limit cut off step 1's session (You've hit your session limit"),
                        reason)
        self.assertRegex(reason, RETAKE)
        self.assertEqual(code, 1)

    def test_a_row_waiting_for_the_yes_is_left_alone(self):
        waiting = "in progress (2026-11-24 10:00), waiting for the maintainer's yes"
        self.calls([{"row": {"1": waiting}, "limit": True}])
        rows, reason, code = self.run_plan()
        self.assertTrue(reason.endswith("; its row was left as it was" + plan_runner.RESUME_ONLY_ADVICE), reason)
        self.assertNotIn("would refuse this tree", reason)
        self.assertIn("| 1 Alpha | " + waiting + " |", (self.project / PLAN).read_text(encoding="utf-8"))

    def test_a_row_the_session_never_claimed_is_left_as_it_was(self):
        before = (self.project / PLAN).read_bytes()
        self.calls([{"limit": True}])
        rows, reason, code = self.run_plan()
        self.assertTrue(reason.endswith("; its row was left as it was" + plan_runner.RERUN_ADVICE), reason)
        self.assertEqual((self.project / PLAN).read_bytes(), before)

    def test_foreign_changes_are_named_as_well(self):
        self.calls([{"row": {"1": CLAIMED}, "limit": True, "foreign": "junk.txt"}])
        rows, reason, code = self.run_plan()
        self.assertIn("; it left changes beyond the status and plan files: junk.txt "
                      "(the next run refuses until they are dealt with)", reason)
        self.assertRegex(reason, RETAKE)
        self.assertTrue(reason.endswith(plan_runner.RESUME_ADVICE), reason)
        self.assertNotIn(plan_runner.RERUN_ADVICE, reason)

    def test_changes_left_without_a_session_id_say_to_deal_with_them_by_hand(self):
        self.calls([{"row": {"1": CLAIMED}, "limit": True, "no_session": True, "foreign": "junk.txt"}])
        code, out = self.main("--steps", "1")
        self.assertIn("(the next run refuses until they are dealt with)" + plan_runner.NO_SESSION_ADVICE + ".", out)
        self.assertNotIn("claude --resume", out)

    def test_no_changes_and_a_done_row_without_a_session_id_give_no_advice(self):
        self.calls([{"row": {"1": "done"}, "limit": True, "no_session": True}])
        rows, reason, code = self.run_plan()
        self.assertTrue(reason.endswith("; its row was left as it was"), reason)

    def test_an_unread_tree_advises_resuming_and_never_a_rerun(self):
        self.assertEqual(plan_runner.limit_advice(None, True, "s0"), plan_runner.RESUME_ONLY_ADVICE)
        self.assertEqual(plan_runner.limit_advice(None, True, None), "")

    def test_a_row_that_cannot_be_marked_says_to_set_it_by_hand(self):
        self.calls([{"row": {"1": CLAIMED}, "limit": True}])
        with mock.patch.object(plan_runner, "mark_for_retake", return_value=False):
            rows, reason, code = self.run_plan()
        self.assertTrue(reason.endswith("; its row could not be marked: set it to stopped by hand"
                                        + plan_runner.RERUN_ADVICE), reason)

    def test_another_error_is_not_the_limit(self):
        self.calls([{"error": True, "subtype": "error_max_budget_usd"}])
        rows, reason, code = self.run_plan()
        self.assertEqual(reason, "step 1 ended `—`, not done; the session ended with error_max_budget_usd")

    def test_only_a_failed_session_is_read_for_the_limit(self):
        ok = json.dumps({"is_error": False, "result": LIMIT_SENTENCE, "subtype": "success"})
        self.assertIsNone(plan_runner.read_result(ok, 0, LIMIT_SENTENCE).limit)
        bad = json.dumps({"is_error": True, "result": LIMIT_SENTENCE})
        self.assertIn("resets 2:10am", plan_runner.read_result(bad, 1).limit)
        self.assertIsNone(plan_runner.read_result(json.dumps({"is_error": True, "result": "boom"}), 1).limit)
        five = plan_runner.limit_message("a\nYou've hit your 5-hour limit \u00b7 resets 4:10pm (Asia/Bangkok)\nb")
        self.assertEqual(five, "You've hit your 5-hour limit \u00b7 resets 4:10pm (Asia/Bangkok)")
        long = plan_runner.limit_message("hit your session limit " + "x" * 300)
        self.assertEqual(len(long), plan_runner.LIMIT_TEXT)
        self.assertIsNone(plan_runner.limit_message("rate limit exceeded"))

    def test_session_env_drops_claudecode(self):
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}):
            env = plan_runner.session_env(self.project, None)
        self.assertNotIn("CLAUDECODE", env)
        self.assertEqual(env["CLAUDE_PROJECT_DIR"], str(self.project))


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


class TestDecideWithoutAsking(RunnerCase):
    DECIDED_ROW = ("done: abc first; decided without asking: (1) design stop → design as returned; "
                   "(2) wording → Recommended A; (3) code commit yes → committed")

    def test_the_flag_gives_deciding_and_waived_and_the_token_is_gone_after(self):
        self.calls([{"row": {"1": "done"}, "waived": True, "deciding": True}])
        code, out = self.main("--steps", "1", "--decide-without-asking")
        record = self.records()[0]
        self.assertEqual(record["deciding"], [0, "deciding"])
        self.assertEqual(record["waived"], [0, "waived"])
        folder = self.project / ".git" / plan_runner.WAIVER_DIR
        self.assertFalse((folder / record["token"]).exists())
        self.assertIn("Plan runner: --commit-without-asking on; --decide-without-asking on; 1 step;", out)

    def test_the_commit_flag_alone_is_waived_but_not_deciding(self):
        self.calls([{"row": {"1": "done"}, "waived": True, "deciding": True}])
        code, out = self.main("--steps", "1", "--commit-without-asking")
        record = self.records()[0]
        self.assertEqual(record["waived"], [0, "waived"])
        self.assertEqual(record["deciding"], [1, "not deciding"])
        self.assertIn("Plan runner: --commit-without-asking on; 1 step;", out)
        self.assertNotIn("--decide-without-asking", out)

    def test_no_flag_gives_neither_and_the_first_line_is_unchanged(self):
        self.calls([{"row": {"1": "done"}, "waived": True, "deciding": True}])
        code, out = self.main("--steps", "1")
        record = self.records()[0]
        self.assertEqual(record["deciding"], [1, "not deciding"])
        self.assertEqual(record["waived"], [1, "not waived"])
        self.assertIn("Plan runner: --commit-without-asking off; 1 step;", out)

    def test_a_claimed_token_or_a_token_file_without_the_key_is_not_deciding(self):
        common = self.project / ".git"
        token, path = plan_runner.make_waiver(common, decide=True)
        self.assertTrue(plan_runner.deciding(self.project, {plan_runner.WAIVER_ENV: token}))
        for claimed in ("b" * 32, "../" + token, token.upper(), token + "0", "", "deciding"):
            with self.subTest(claimed=claimed):
                self.assertFalse(plan_runner.deciding(self.project, {plan_runner.WAIVER_ENV: claimed}))
        self.assertFalse(plan_runner.deciding(self.project, {}))
        plan_runner.drop_waiver(path)
        self.assertFalse(plan_runner.deciding(self.project, {plan_runner.WAIVER_ENV: token}))
        plain, plain_path = plan_runner.make_waiver(common)
        self.addCleanup(plan_runner.drop_waiver, plain_path)
        self.assertFalse(plan_runner.deciding(self.project, {plan_runner.WAIVER_ENV: plain}))
        bare = common / plan_runner.WAIVER_DIR / ("d" * 32)
        self.addCleanup(lambda: bare.exists() and bare.unlink())
        for content in ("{}", "not json", json.dumps({"decide": "true"})):
            with self.subTest(content=content):
                bare.write_text(content, encoding="utf-8")
                self.assertFalse(plan_runner.deciding(self.project, {plan_runner.WAIVER_ENV: "d" * 32}))

    def test_the_check_command_prints_its_verdict_and_wants_to_be_alone(self):
        token, path = plan_runner.make_waiver(self.project / ".git", decide=True)
        self.addCleanup(plan_runner.drop_waiver, path)
        env = dict(os.environ)
        for value, expected in ((token, (0, "deciding")), ("c" * 32, (1, "not deciding"))):
            env[plan_runner.WAIVER_ENV] = value
            done = subprocess.run([sys.executable, str(RUNNER_PATH), "--deciding"], capture_output=True,
                                  text=True, env=env, cwd=self.project)
            self.assertEqual((done.returncode, done.stdout.strip()), expected)
        self.assertEqual(self.main("--deciding", "--steps", "1")[0], 2)
        self.assertEqual(self.records(), [])

    def test_a_done_row_lists_its_decisions_live_and_in_the_summary(self):
        self.calls([{"row": {"1": self.DECIDED_ROW}}])
        said = []
        rows, reason, code = plan_runner.run_plan(self.project, 1, None, True, None, None, self.claude,
                                                  ci=green, say=said.append)
        expected = ["  - decided (1) design stop → design as returned",
                    "  - decided (2) wording → Recommended A",
                    "  - decided (3) code commit yes → committed"]
        self.assertEqual(said[2:5], expected)
        self.assertEqual(rows[0].decisions, tuple(line[len("  - decided "):] for line in expected))
        lines = plan_runner.summary(rows, reason, True, 0.25, True)
        self.assertEqual(lines[1:5], [plan_runner.row_line(rows[0])] + expected)
        self.assertTrue(lines[0].startswith("Plan runner: --commit-without-asking on; --decide-without-asking on;"))

    def test_a_row_with_no_decisions_lists_none(self):
        self.calls([{"row": {"1": "done: abc first"}}])
        rows, reason, code = self.run_plan(steps=1)
        self.assertEqual(rows[0].decisions, ())
        self.assertEqual(len(plan_runner.summary(rows, reason, False, 0.25)), 3)

    def test_a_stopped_row_lists_its_decisions_without_see_tried_and_the_run_stops_naming_the_step(self):
        self.calls([{"row": {"1": "stopped (2026-11-25 10:00): question without a recommendation; "
                                  "decided without asking: (1) design stop → as returned; "
                                  "(2) wording → A, see Tried"}},
                    {"row": {"2": "done"}}])
        rows, reason, code = self.run_plan()
        self.assertEqual(len(self.records()), 1)
        self.assertEqual(rows[0].decisions, ("(1) design stop → as returned", "(2) wording → A"))
        self.assertTrue(reason.startswith("step 1 ended `stopped"), reason)
        self.assertEqual(code, 1)
        lines = plan_runner.summary(rows, reason, True, 0.25, True)
        self.assertIn("  - decided (2) wording → A", lines)
        self.assertFalse([line for line in lines if line.startswith("  - decided") and "see Tried" in line])

    def test_decisions_in_reads_the_clause_and_splits_on_numbers_only(self):
        self.assertEqual(plan_runner.decisions_in("done: x"), ())
        self.assertEqual(plan_runner.decisions_in(None), ())
        self.assertEqual(plan_runner.decisions_in("done; decided without asking: (1) a; b → c; (2) d → e."),
                         ("(1) a; b → c", "(2) d → e."))
        self.assertEqual(plan_runner.decisions_in("stopped: q; decided without asking: (1) a → b; see Tried"),
                         ("(1) a → b",))

    def test_an_uncleared_human_action_gate_stops_the_run_and_the_session_never_starts(self):
        self.reset(gate=True)
        self.calls([{"row": {"1": "done"}}])
        code, out = self.main("--steps", "3", "--decide-without-asking")
        self.assertEqual(self.records(), [])
        self.assertIn("Stopped: step 1 is at an uncleared Gate.", out)
        self.assertTrue(out.startswith("Plan runner: --commit-without-asking on; --decide-without-asking on;"))

    def test_red_ci_stops_the_run_naming_ci(self):
        self.calls([{"row": {"1": self.DECIDED_ROW}}, {"row": {"2": "done"}}])
        rows, reason, code = self.run_plan(flag=True, ci=lambda project, head: "failure")
        self.assertEqual(len(self.records()), 1)
        self.assertIn("CI on HEAD", reason)
        self.assertEqual(code, 1)

    def test_a_second_blockers_stopped_row_stops_the_run_naming_the_step(self):
        self.calls([{"row": {"1": "stopped (2026-11-25 10:00): blockers after the second review, "
                                  "decided without asking: (1) design stop → as returned; see Tried"}},
                    {"row": {"2": "done"}}])
        rows, reason, code = self.run_plan(flag=True)
        self.assertEqual(len(self.records()), 1)
        self.assertTrue(reason.startswith("step 1 ended `stopped"), reason)
        self.assertEqual(rows[0].decisions, ("(1) design stop → as returned",))


if __name__ == "__main__":
    unittest.main()
