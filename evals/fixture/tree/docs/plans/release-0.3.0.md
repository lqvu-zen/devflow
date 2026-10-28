# tally v0.3.0: median, JSON output and an empty-list fix

_Created 2026-10-20 by the secretary from Ada's decisions. Each code step goes through the devflow agent team via its skill._

## Goals

1. An empty list no longer crashes the average (#3).
2. The median is available.
3. Ship **0.3.0** through the release-candidate phase.

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

`tally.core.average([])` raises `ZeroDivisionError`, so `tally` with no arguments prints a traceback. It should return 0.

Behaviour map: AR-02 (CLI, LIB).

**Files:** `tally/core.py`, `tests/test_core.py`, `docs/BEHAVIOUR.md`.
**Needs** nothing.
**Done when** a regression test reproduces the crash on the old code and passes on the fix; both surfaces; AR-02 names the test.

### 2 — Median

Add `core.median(items)`: the middle number, or the mean of the two middle ones.

Behaviour map: a new entry AR-04 (LIB).

**Files:** `tally/core.py`, `tests/test_core.py`, `docs/BEHAVIOUR.md`.
**Needs** nothing.
**Done when** `median` has tests for odd and even lengths; AR-04 names them.

### 3 — JSON output

Add `--json` to the CLI so the result prints as one JSON object.

Behaviour map: a new entry AR-05 (CLI).

**Files:** `tally/cli.py`, `tests/test_cli.py`, `docs/BEHAVIOUR.md`.
**Needs** nothing.
**Done when** a CLI test checks the JSON keys; AR-05 names it.

### 4 — Reject non-numbers

The CLI should refuse input that is not a number. The wording of the error is the maintainer's call.

Behaviour map: a new entry AR-06 (CLI).

**Files:** `tally/cli.py`, `tests/test_cli.py`, `docs/BEHAVIOUR.md`.
**Needs** nothing.
**Gate:** Ada chooses the error wording and signs it off before anything is committed.
**Done when** a CLI test covers a non-number; AR-06 names it.

### 5 — Top N

Add `--top N` to the CLI, printing the N largest numbers through the existing helper `core.top` in `tally/core.py`, which has no tie rule yet and needs one.

Behaviour map: AR-03 (LIB), and a new entry AR-07 (CLI).

**Files:** `tally/cli.py`, `tests/test_cli.py`.
**Needs** nothing.
**Done when** a CLI test covers `--top 2`; AR-07 names it.

### 6 — Release 0.3.0

**Files:** `tally/__init__.py`.
**Needs** every step above, plus green CI.
Run `/devflow:release`. The maintainer names the version.
**Done when** v0.3.0 is published with every artifact in the lineup.

## Order

1, then 2 to 5, then 6.

## Status

| Step | State |
| --- | --- |
| 1 Fix #3: average of an empty list | — |
| 2 Median | — |
| 3 JSON output | in progress (2026-10-19 22:05) |
| 4 Reject non-numbers | — |
| 5 Top N | — |
| 6 Release 0.3.0 | — |
