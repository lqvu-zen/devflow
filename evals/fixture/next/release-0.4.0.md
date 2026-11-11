# tally v0.4.0: mode, range and sum of squares

_Created 2026-10-21 by the project manager from Ada's decisions. Each code step goes through the devflow agent team via its skill._

## Goals

1. The mode, the range and the sum of squares are available.
2. Ship **0.4.0** by hand, with no candidate.

## Who does what

| Step | Who | How |
|---|---|---|
| 1 Mode | coding session | `/devflow:add-feature` |
| 2 Range | coding session | `/devflow:add-feature` |
| 3 Sum of squares | coding session | `/devflow:add-feature` |
| 4 Release 0.4.0 | maintainer | by hand, no candidate |

## Steps

### 1 — Mode

Add `stats.mode(items)`: the most common number, the smallest on a tie.

Behaviour map: a new entry AR-08 (LIB).

**Files:** `tally/stats.py`.
**Needs** `v0.3.0-4` (the CLI rejects non-numbers first).
**Done when** `mode` has tests for a tie and a single number; AR-08 names them.

### 2 — Range

Add `core.range_of(items)`: the largest number minus the smallest.

Behaviour map: a new entry AR-09 (LIB).

**Files:** `tally/core.py`, `tests/test_core.py`.
**Needs** nothing.
**Done when** `range_of` has tests for one number and several; AR-09 names them.

### 3 — Sum of squares

Add `stats.sum_of_squares(items)` in a new module `tally/stats.py`: the sum of each number squared, 0 for an empty list.

Behaviour map: a new entry AR-10 (LIB).

**Files:** `tally/stats.py` (new), `tests/test_stats.py` (new), `docs/BEHAVIOUR.md`.
**Needs** v0.3.0-1.
**Done when** `sum_of_squares` has tests for an empty list and for negative numbers; AR-10 names them.

### 4 — Release 0.4.0

**Files:** `tally/__init__.py`.
**Needs** every step above.
Ada releases it by hand, with no candidate.
**Done when** v0.4.0 is published.

## Order

1, then 2, then 3, then 4.

## Status

| Step | State |
| --- | --- |
| 1 Mode | — |
| 2 Range | — |
| 3 Sum of squares | — |
| 4 Release 0.4.0 | — |
