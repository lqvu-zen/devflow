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
COST_PATH = ROOT / "tools" / "eval_cost.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ec = _load("eval_cost", COST_PATH)

OPUS = "claude-opus-5-5"
SONNET = "claude-sonnet-5-5"


def message(msg_id, model, **usage):
    return {"type": "assistant", "message": {"id": msg_id, "model": model, "usage": usage}}


def write_lines(path: Path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def write_workspace(base: Path, name: str, with_cost: bool = True) -> Path:
    workspace = base / name
    project = workspace / "config" / "projects" / "proj"
    cost_state = {
        "type": "cost-state",
        "totalCostUSD": 0.45,
        "modelUsage": {OPUS: {"costUSD": 0.40}, SONNET: {"costUSD": 0.05}},
    }
    main_entries = [
        message("m1", OPUS, input_tokens=0, output_tokens=0, cache_creation_input_tokens=1000,
                cache_creation={"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 1000}),
        message("m1", OPUS, input_tokens=0, output_tokens=0, cache_creation_input_tokens=1000,
                cache_creation={"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 1000}),
        message("syn", "<synthetic>", input_tokens=0, output_tokens=0),
    ]
    if with_cost:
        main_entries.append(cost_state)
    write_lines(project / "sess.jsonl", main_entries)
    for index in (1, 2):
        agent = project / "sess" / "subagents" / f"agent-d{index}"
        write_lines(agent.with_suffix(".jsonl"), [
            message(f"d{index}", OPUS, input_tokens=0, output_tokens=0, cache_creation_input_tokens=800,
                    cache_creation={"ephemeral_5m_input_tokens": 800, "ephemeral_1h_input_tokens": 0})])
        agent.with_suffix(".meta.json").write_text(
            json.dumps({"agentType": "devflow:designer"}), encoding="utf-8")
    impl = project / "sess" / "subagents" / "agent-i1"
    write_lines(impl.with_suffix(".jsonl"), [
        message("i1", SONNET, input_tokens=0, cache_read_input_tokens=10000, output_tokens=100)])
    impl.with_suffix(".meta.json").write_text(
        json.dumps({"agentType": "devflow:implementer"}), encoding="utf-8")
    return workspace


def write_aggregate(path: Path, trace_paths):
    runs = [{"tracePath": t, "judgeCostUsd": 0.01} for t in trace_paths]
    path.write_text(json.dumps({"cases": [{"name": "case-a", "arms": {"with": runs}}]}), encoding="utf-8")


def run_main(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = ec.main(list(argv))
    return code, out.getvalue()


class SplitTests(unittest.TestCase):
    def test_splits_cost_by_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            split = ec.split_run(write_workspace(Path(tmp), "claude-eval-A"))
        self.assertNotIsInstance(split, str)
        self.assertAlmostEqual(split.cost["main"], 0.20)
        self.assertAlmostEqual(split.cost["designer"], 0.20)
        self.assertAlmostEqual(split.cost["implementer"], 0.05)
        self.assertAlmostEqual(sum(split.cost.values()) + split.unattributed, 0.45)
        self.assertEqual(split.calls["designer"], 2)
        self.assertEqual(split.messages["main"], 1)

    def test_synthetic_model_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            split = ec.split_run(write_workspace(Path(tmp), "claude-eval-A"))
        self.assertAlmostEqual(split.unattributed, 0.0)
        self.assertNotIn("<synthetic>", split.cost)

    def test_no_cost_state_returns_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = ec.split_run(write_workspace(Path(tmp), "claude-eval-A", with_cost=False))
        self.assertIsInstance(result, str)
        self.assertIn("no cost-state", result)

    def test_no_session_files_returns_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = ec.split_run(Path(tmp))
        self.assertIsInstance(result, str)
        self.assertIn("no session files", result)


class CliTests(unittest.TestCase):
    def test_aggregate_with_root_names_missing_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_workspace(base, "claude-eval-A")
            aggregate = base / "aggregate-result.json"
            write_aggregate(aggregate, [
                "/home/u/ev/claude-eval-A/out/trace.jsonl",
                "/home/u/ev/claude-eval-gone/out/trace.jsonl"])
            code, out = run_main(str(aggregate), "--root", str(base))
        self.assertEqual(code, 0)
        self.assertIn("designer", out)
        self.assertIn("missing case-a run 2", out)
        self.assertIn("judge $0.0100", out)

    def test_workspace_of_handles_windows_and_posix_paths(self):
        expected = Path("root") / "claude-eval-B"
        self.assertEqual(ec.workspace_of("C:\\Users\\x\\claude-eval-B\\out\\trace.jsonl", "root"), expected)
        self.assertEqual(ec.workspace_of("/home/u/ev/claude-eval-B/out/trace.jsonl", "root"), expected)

    def test_all_workspaces_missing_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            aggregate = base / "aggregate-result.json"
            write_aggregate(aggregate, ["/home/u/ev/claude-eval-gone/out/trace.jsonl"])
            code, out = run_main(str(aggregate), "--root", str(base))
        self.assertEqual(code, 1)
        self.assertIn("missing case-a run 1", out)

    def test_workspace_folder_argument_prints_one_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = write_workspace(Path(tmp), "claude-eval-A")
            code, out = run_main(str(workspace))
        self.assertEqual(code, 0)
        self.assertIn("claude-eval-A", out)
        self.assertIn("implementer", out)
        self.assertNotIn("all runs", out)


if __name__ == "__main__":
    unittest.main()
