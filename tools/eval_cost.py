from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

WEIGHTS = {"input": 1, "cache_5m": 1.25, "cache_1h": 2, "cache_read": 0.05, "output": 5}
TRACE_TAIL = ("out", "trace.jsonl")


def read_jsonl(path: Path) -> Iterator[dict]:
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict):
                yield entry


def token_weight(usage: dict) -> float:
    creation = usage.get("cache_creation") or {}
    five = creation.get("ephemeral_5m_input_tokens", 0) or 0
    hour = creation.get("ephemeral_1h_input_tokens", 0) or 0
    rest = max((usage.get("cache_creation_input_tokens", 0) or 0) - five - hour, 0)
    return (
        WEIGHTS["input"] * (usage.get("input_tokens", 0) or 0)
        + WEIGHTS["cache_5m"] * (five + rest)
        + WEIGHTS["cache_1h"] * hour
        + WEIGHTS["cache_read"] * (usage.get("cache_read_input_tokens", 0) or 0)
        + WEIGHTS["output"] * (usage.get("output_tokens", 0) or 0)
    )


def agent_name(meta_path: Path) -> str:
    try:
        data = json.loads(Path(meta_path).read_text(encoding="utf-8"))
        kind = data["agentType"]
    except (OSError, ValueError, KeyError, TypeError):
        return "unknown"
    if not isinstance(kind, str) or not kind:
        return "unknown"
    return kind.split(":")[-1] or "unknown"


def session_files(workspace: Path) -> list[tuple[str, Path]]:
    base = Path(workspace) / "config" / "projects"
    files: list[tuple[str, Path]] = []
    for path in sorted(base.glob("*/*.jsonl")):
        files.append(("main", path))
    for path in sorted(base.glob("*/*/subagents/agent-*.jsonl")):
        files.append((agent_name(path.with_name(path.stem + ".meta.json")), path))
    return files


@dataclass
class Split:
    total: float = 0.0
    cost: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    messages: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    calls: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    unattributed: float = 0.0


def split_run(workspace: Path) -> Split | str:
    workspace = Path(workspace)
    files = session_files(workspace)
    if not files:
        return f"no session files under {workspace / 'config' / 'projects'}"
    weights: dict[tuple[str, str], float] = defaultdict(float)
    counts: dict[tuple[str, str], int] = defaultdict(int)
    calls: dict[str, int] = defaultdict(int)
    cost_state: dict | None = None
    for label, path in files:
        if label != "main":
            calls[label] += 1
        seen: dict[str, dict] = {}
        for entry in read_jsonl(path):
            if entry.get("type") == "cost-state" and label == "main":
                cost_state = entry
            if entry.get("type") == "assistant" and isinstance(entry.get("message"), dict):
                message = entry["message"]
                key = message.get("id") or f"line-{len(seen)}"
                seen[key] = message
        for message in seen.values():
            usage = message.get("usage")
            if not isinstance(usage, dict):
                continue
            model = message.get("model") or "unknown"
            weights[(label, model)] += token_weight(usage)
            counts[(label, model)] += 1
    if cost_state is None:
        main_files = [str(p) for label, p in files if label == "main"]
        return f"no cost-state in {main_files[0] if main_files else workspace}"
    usage_by_model = cost_state.get("modelUsage") or {}
    model_totals: dict[str, float] = defaultdict(float)
    for (_, model), weight in weights.items():
        model_totals[model] += weight
    result = Split(total=float(cost_state.get("totalCostUSD", 0) or 0))
    for (label, model), weight in weights.items():
        entry = usage_by_model.get(model)
        if not isinstance(entry, dict):
            continue
        if model_totals[model] > 0:
            result.cost[label] += float(entry.get("costUSD", 0) or 0) * weight / model_totals[model]
    for model, entry in usage_by_model.items():
        if isinstance(entry, dict) and model_totals.get(model, 0) <= 0:
            result.unattributed += float(entry.get("costUSD", 0) or 0)
    for (label, model), count in counts.items():
        if isinstance(usage_by_model.get(model), dict):
            result.messages[label] += count
    result.calls.update(calls)
    return result


def workspace_of(trace_path: str, root: str | Path | None) -> Path:
    parts = [p for p in re.split(r"[\\/]", trace_path) if p != ""]
    if len(parts) >= 2 and tuple(parts[-2:]) == TRACE_TAIL:
        parts = parts[:-2]
    if root is not None:
        return Path(root) / (parts[-1] if parts else "")
    prefix = ""
    if trace_path.startswith("//") or trace_path.startswith("\\\\"):
        prefix = "//"
    elif trace_path.startswith("/"):
        prefix = "/"
    if prefix:
        return Path(prefix + "/".join(parts))
    return Path(*parts) if parts else Path()


def runs_in(aggregate_path: Path, root: str | Path | None) -> list[tuple[str, Path | None, float]]:
    data = json.loads(Path(aggregate_path).read_text(encoding="utf-8"))
    runs: list[tuple[str, Path | None, float]] = []
    for case in data.get("cases", []):
        for arm, arm_runs in (case.get("arms") or {}).items():
            for index, run in enumerate(arm_runs, 1):
                label = f"{case.get('name', 'case')} run {index}"
                if arm != "with":
                    label += f" ({arm})"
                trace = run.get("tracePath")
                path = workspace_of(trace, root) if trace else None
                runs.append((label, path, float(run.get("judgeCostUsd", 0) or 0)))
    return runs


def rows_of(split: Split) -> list[tuple[str, str, int, float]]:
    rows: list[tuple[str, str, int, float]] = []
    if "main" in split.cost or "main" in split.messages:
        rows.append(("main", "-", split.messages.get("main", 0), split.cost.get("main", 0.0)))
    others = sorted(
        (name for name in set(split.cost) | set(split.calls) if name != "main"),
        key=lambda name: -split.cost.get(name, 0.0))
    for name in others:
        rows.append((name, str(split.calls.get(name, 0)), split.messages.get(name, 0), split.cost.get(name, 0.0)))
    if split.unattributed > 1e-9:
        rows.append(("unattributed", "-", 0, split.unattributed))
    return rows


def format_rows(rows: list[tuple[str, str, int, float]], total: float) -> list[str]:
    lines = [f"  {'agent':<12} {'calls':>5} {'messages':>9} {'cost':>8} {'share':>7}"]
    for name, calls, messages, cost in rows:
        share = 100 * cost / total if total else 0.0
        lines.append(f"  {name:<12} {calls:>5} {messages:>9} {'$%.4f' % cost:>8} {share:>6.1f}%")
    return lines


def format_split(label: str, split: Split, judge: float) -> list[str]:
    head = f"{label}  ${split.total:.4f} (judge ${judge:.4f})"
    return [head, *format_rows(rows_of(split), split.total)]


def format_all(splits: list[Split], judge: float) -> list[str]:
    merged = Split()
    for split in splits:
        merged.total += split.total
        merged.unattributed += split.unattributed
        for name, value in split.cost.items():
            merged.cost[name] += value
        for name, value in split.messages.items():
            merged.messages[name] += value
        for name, value in split.calls.items():
            merged.calls[name] += value
    return format_split("all runs", merged, judge)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Split an eval run's cost by agent.")
    parser.add_argument("source", help="aggregate-result.json or one run's workspace folder")
    parser.add_argument("--root", help="folder holding the claude-eval-* workspaces")
    args = parser.parse_args(argv)
    source = Path(args.source)
    if source.suffix.lower() == ".json":
        runs = runs_in(source, args.root)
    else:
        runs = [(source.name, source, 0.0)]
    read: list[Split] = []
    judge_total = 0.0
    blocks: list[str] = []
    for label, workspace, judge in runs:
        if workspace is None:
            blocks.append(f"missing {label}: no tracePath recorded")
            continue
        if not Path(workspace).is_dir():
            blocks.append(f"missing {label}: no workspace at {workspace}")
            continue
        split = split_run(workspace)
        if isinstance(split, str):
            blocks.append(f"missing {label}: {split}")
            continue
        read.append(split)
        judge_total += judge
        blocks.extend(format_split(label, split, judge))
    if len(read) > 1:
        blocks.extend(format_all(read, judge_total))
    for line in blocks:
        print(line)
    return 0 if read else 1


if __name__ == "__main__":
    sys.exit(main())
