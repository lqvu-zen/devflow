from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

SEPARATORS = (" · ", " — ", "; ", ". ")


def reason_of(error) -> str:
    text = " ".join(str(error).split())
    cut = len(text)
    for sep in SEPARATORS:
        at = text.find(sep)
        if at != -1:
            cut = min(cut, at)
    head = text[:cut]
    depth = 0
    end = len(head)
    for i, ch in enumerate(head):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0 and head[i + 1:i + 2] == " ":
            end = i
            break
    reason = head[:end].rstrip(" .")
    return reason or text


def has_error(run: dict) -> bool:
    error = run.get("error")
    return error is not None and error != ""


@dataclass
class Tally:
    runs: int = 0
    finished: int = 0
    passed: int = 0
    score: float = 0.0

    def add(self, run: dict) -> None:
        self.runs += 1
        if not has_error(run):
            self.finished += 1
            if run.get("passed") is True:
                self.passed += 1
            value = run.get("score")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                self.score += value


def summarise(data: dict):
    rows = []
    total = Tally()
    reasons: Counter = Counter()
    for case in data.get("cases") or []:
        if not isinstance(case, dict):
            continue
        name = case.get("name") or "case"
        arms = case.get("arms")
        made = False
        if isinstance(arms, dict):
            for arm, runs in arms.items():
                if not isinstance(runs, list) or not runs:
                    continue
                tally = Tally()
                for run in runs:
                    if not isinstance(run, dict):
                        continue
                    tally.add(run)
                    total.add(run)
                    if has_error(run):
                        reasons[reason_of(run["error"])] += 1
                label = name if arm == "with" else f"{name} ({arm})"
                rows.append((label, tally))
                made = True
        if not made:
            rows.append((name, Tally()))
    return rows, total, reasons


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def cell(n: int, m: int) -> str:
    return f"{n} of {m} {100 * n / m:.1f}%"


def graders(t: Tally) -> str:
    if t.finished == 0:
        return "none finished"
    return f"{100 * t.score / t.finished:.1f}%"


def cells_of(t: Tally) -> list[str]:
    return [str(t.runs), cell(t.finished, t.runs), cell(t.passed, t.runs), graders(t)]


def amount(value) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def cost_line(data: dict) -> str:
    total = 0.0
    judge_total = 0.0
    recorded = False
    for case in data.get("cases") or []:
        arms = case.get("arms") if isinstance(case, dict) else None
        if not isinstance(arms, dict):
            continue
        for runs in arms.values():
            for run in runs if isinstance(runs, list) else []:
                if not isinstance(run, dict):
                    continue
                cost = amount(run.get("costUsd"))
                judge = amount(run.get("judgeCostUsd"))
                if cost is None and judge is None:
                    continue
                recorded = True
                judge_total += judge or 0.0
                total += judge if cost is None else cost
    if not recorded:
        return "Cost: not recorded"
    own = max(0.0, total - judge_total)
    return f"Cost: ${total:.4f} (runs ${own:.4f}, judge ${judge_total:.4f})"


def format_summary(data: dict, source: str) -> list[str]:
    rows, total, reasons = summarise(data)
    started = data.get("startedAt")
    if not isinstance(started, str):
        started = source
    n_cases = len(data.get("cases") or [])
    first = f"{started}: {plural(n_cases, 'case')}, {plural(total.runs, 'run')}"
    if data.get("partial") is True:
        first += ", partial"
    header = ["runs", "finished", "passed", "graders"]
    body = [(label, cells_of(t) if t.runs else None) for label, t in rows]
    body.append(("total", cells_of(total) if total.runs else None))
    label_width = max(len("case"), *(len(label) for label, _ in body))
    widths = [len(h) for h in header]
    for _, cells in body:
        if cells:
            widths = [max(w, len(c)) for w, c in zip(widths, cells)]
    lines = [first]
    lines.append("case".ljust(label_width) + "  " + "  ".join(h.rjust(w) for h, w in zip(header, widths)))
    for label, cells in body:
        if cells is None:
            lines.append(f"{label.ljust(label_width)}  0 runs")
        else:
            lines.append(label.ljust(label_width) + "  " + "  ".join(c.rjust(w) for c, w in zip(cells, widths)))
    lines.append(cost_line(data))
    if reasons:
        count_width = max(len(str(n)) for n in reasons.values())
        lines.append("")
        lines.append("errors:")
        for reason, n in sorted(reasons.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"  {n:>{count_width}}  {reason}")
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Summarise an eval run from its aggregate-result.json.")
    parser.add_argument("source", help="aggregate-result.json of an eval run")
    args = parser.parse_args(argv)
    try:
        data = json.loads(Path(args.source).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("not a JSON object")
        if not isinstance(data.get("cases"), list):
            raise ValueError("no cases list")
    except (OSError, ValueError) as exc:
        print(f"cannot read {args.source}: {exc}")
        return 1
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure:
        reconfigure(errors="replace")
    print("\n".join(format_summary(data, args.source)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
