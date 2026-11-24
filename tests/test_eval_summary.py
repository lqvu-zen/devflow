from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = ROOT / "tools" / "eval_summary.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


es = _load("eval_summary", SUMMARY_PATH)

LIMIT_A = "exit 1: You've hit your session limit · resets 2:10am (Asia/Bangkok)"
LIMIT_B = "exit 1: You've hit your session limit · resets 9:10pm (Asia/Bangkok)"
SANDBOX_REASON = (
    "exit 1: A shell tool (Bash or PowerShell) was granted but this machine cannot confine it "
    "(no sandbox backend on this platform, or it is not installed)"
)
SANDBOX = (
    SANDBOX_REASON
    + ", so the run was refused rather than run unconfined — drop the shell grant. "
    "Sandbox required but unavailable. · stderr:  Error: sandbox required but unavailable"
)


def run(passed, score, error=None):
    return {"passed": passed, "score": score, "error": error}


def result(cases, partial=False):
    return {"startedAt": "2026-11-22T05:51:02.728Z", "partial": partial, "cases": cases}


def case(name, runs, arm="with"):
    return {"name": name, "arms": {arm: runs}}


def fixture(partial=False):
    return result(
        [
            case("case-a", [run(True, 1), run(False, 0.5), run(False, 0, LIMIT_A)]),
            case("case-b", [run(True, 1), run(True, 1, SANDBOX), run(False, 0, LIMIT_B)]),
            case("case-c", []),
        ],
        partial,
    )


def write_json(path: Path, data) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def run_main(path):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = es.main([str(path)])
    return code, out.getvalue()


class TestSummary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def lines(self, data):
        return es.format_summary(data, "x.json")

    def line_for(self, data, prefix):
        return next(line for line in self.lines(data) if line.startswith(prefix))

    def test_counts_match_hand_counts(self):
        rows, total, _ = es.summarise(fixture())
        by_label = dict(rows)
        a = by_label["case-a"]
        self.assertEqual((a.runs, a.finished, a.passed, a.score), (3, 2, 1, 1.5))
        b = by_label["case-b"]
        self.assertEqual((b.runs, b.finished, b.passed, b.score), (3, 1, 1, 1.0))
        self.assertEqual((total.runs, total.finished, total.passed, total.score), (6, 3, 2, 2.5))

    def test_table_rows(self):
        data = fixture()
        a = self.line_for(data, "case-a")
        for text in ("2 of 3 66.7%", "1 of 3 33.3%", "75.0%"):
            self.assertIn(text, a)
        b = self.line_for(data, "case-b")
        for text in ("1 of 3 33.3%", "100.0%"):
            self.assertIn(text, b)
        total = self.line_for(data, "total")
        for text in ("3 of 6 50.0%", "2 of 6 33.3%", "83.3%"):
            self.assertIn(text, total)

    def test_error_with_score_one_is_neither_finished_nor_passed(self):
        data = result([case("solo", [run(True, 1, "exit 1: boom")])])
        line = self.line_for(data, "solo")
        self.assertEqual(line.count("0 of 1 0.0%"), 2)
        self.assertTrue(line.endswith("none finished"))

    def test_graders_are_the_mean_of_the_finished_runs(self):
        data = result([case("mix", [run(True, 1), run(False, 0.5), run(True, 1, LIMIT_A)])])
        self.assertTrue(self.line_for(data, "mix").endswith("75.0%"))
        self.assertTrue(self.line_for(data, "total").endswith("75.0%"))

    def test_graders_say_none_finished_when_every_run_errored(self):
        data = result([case("down", [run(True, 1, LIMIT_A), run(False, 0, LIMIT_B)])])
        self.assertTrue(self.line_for(data, "down").endswith("none finished"))
        self.assertTrue(self.line_for(data, "total").endswith("none finished"))

    def test_case_with_no_runs(self):
        data = fixture()
        self.assertTrue(self.line_for(data, "case-c").endswith("0 runs"))
        self.assertIn("6 runs", self.lines(data)[0])
        self.assertRegex(self.line_for(data, "total"), r"total\s+6 ")

    def test_no_runs_at_all(self):
        data = result([case("only", [])])
        self.assertEqual(self.line_for(data, "total"), "total  0 runs")

    def test_first_line(self):
        first = self.lines(fixture())[0]
        self.assertEqual(first, "2026-11-22T05:51:02.728Z: 3 cases, 6 runs")

    def test_partial_on_first_line(self):
        self.assertTrue(self.lines(fixture(True))[0].endswith(", partial"))
        self.assertNotIn("partial", self.lines(fixture(False))[0])

    def test_reasons(self):
        self.assertEqual(es.reason_of(LIMIT_A), es.reason_of(LIMIT_B))
        self.assertEqual(es.reason_of(LIMIT_A), "exit 1: You've hit your session limit")
        self.assertEqual(es.reason_of(SANDBOX), SANDBOX_REASON)
        self.assertEqual(es.reason_of("exit 1: Not logged in · Please run /login"), "exit 1: Not logged in")
        self.assertEqual(es.reason_of("exit 1"), "exit 1")

    def test_error_lines(self):
        lines = self.lines(fixture())
        self.assertIn("errors:", lines)
        self.assertIn("  2  exit 1: You've hit your session limit", lines)
        self.assertTrue(any(line.startswith("  1  exit 1: A shell tool") for line in lines))

    def test_no_error_block_without_errors(self):
        data = result([case("ok", [run(True, 1)])])
        self.assertNotIn("errors:", self.lines(data))

    def test_other_arm_is_labelled(self):
        data = result([case("case-x", [run(True, 1)], arm="without")])
        rows, _, _ = es.summarise(data)
        self.assertEqual(rows[0][0], "case-x (without)")

    def test_unreadable_exits_one(self):
        code, out = run_main(self.dir / "missing.json")
        self.assertEqual(code, 1)
        self.assertIn("cannot read", out)
        bad = self.dir / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        code, out = run_main(bad)
        self.assertEqual(code, 1)
        self.assertIn("cannot read", out)

    def test_main_exits_zero(self):
        path = write_json(self.dir / "aggregate-result.json", fixture())
        code, out = run_main(path)
        self.assertEqual(code, 0)
        self.assertIn("total", out)


if __name__ == "__main__":
    unittest.main()
