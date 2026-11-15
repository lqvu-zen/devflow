#!/usr/bin/env bash
. "$(dirname "$0")/../../../fixture/build.sh"
cat > docs/plans/release-0.4.0.md <<'PLAN'
# tally v0.4.0: precision and CSV input

_Draft by Ada, 2026-10-21, for the project manager to check before the team starts. Not yet accepted._

## Goals

1. Results print with a chosen number of decimals.
2. Numbers can be read from a CSV file.
3. Ship **0.4.0** through the release-candidate phase.

## Who does what

| Step | Who | How |
|---|---|---|
| 1 Precision | coding session | `/devflow:add-feature` |
| 2 CSV input | coding session | `/devflow:add-feature` |
| 3 Release 0.4.0 | coding session + maintainer | `/devflow:release`; the maintainer names the version |

## Steps

### 1 — Precision

Add `--precision N` to the CLI so `total` and `average` print with N decimals.

Behaviour map: a new entry AR-08 (CLI).

**Files:** `tally/cli.py`, `tests/test_cli.py`, `docs/BEHAVIOUR.md`.
**Needs** nothing.
**Done when** a CLI test checks that `--precision 2` prints `total=3.00 average=1.50` for `1 2`; AR-08 names it.

### 2 — CSV input

Add `--csv PATH` to read the numbers from a CSV file instead of the arguments. Handle edge cases. Which column to read is TBD.

Behaviour map: a new entry AR-09 (CLI).

**Files:** `tally/cli.py`, `tests/test_cli.py`, `docs/BEHAVIOUR.md`.
**Needs** 1.
**Done when** it works with CSV files; AR-09 names it.

### 3 — Release 0.4.0

**Files:** `tally/__init__.py`.
**Needs** every step above, plus green CI.
Run `/devflow:release`. The maintainer names the version.
**Done when** v0.4.0 is published with every artifact in the lineup.

## Order

1, then 2, then 3.

## Status

| Step | State |
| --- | --- |
| 1 Precision | — |
| 2 CSV input | — |
| 3 Release 0.4.0 | — |
PLAN
python3 - "$work/docs/STATUS.md" <<'PY'
import sys

path = sys.argv[1]
text = open(path, encoding="utf-8").read()
row = "| **0.3.0** (in progress) | median, JSON output, empty-list fix | `docs/plans/release-0.3.0.md` |\n"
assert row in text
text = text.replace(row, row + "| **0.4.0** (draft) | precision, CSV input | `docs/plans/release-0.4.0.md` |\n", 1)
open(path, "w", encoding="utf-8", newline="\n").write(text)
PY
git add docs
git commit -q -m "Status: Ada's 0.4.0 draft"
git push -q origin main
head_sha="$(git rev-parse HEAD)"
short="$(git rev-parse --short=7 HEAD)"
ci_state green
