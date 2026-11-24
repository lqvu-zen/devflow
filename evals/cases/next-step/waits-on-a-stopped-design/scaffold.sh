#!/usr/bin/env bash
. "$(dirname "$0")/../../../fixture/build.sh"
plan_edit "1, then 2 to 5, then 6." "1, then 2, then 4, then 3 and 5, then 6."
plan_edit "Ada chooses the error wording and signs it off before anything is committed." "Ada approves the error wording the designer proposes, at the design stop, before implementation."
plan_edit "**Done when** a CLI test covers a non-number; AR-06 names it." $'**Done when** a CLI test covers a non-number; AR-06 names it.\n**Tried:** 2026-10-22: designed; the error reads "not a number: <input>"; stopped at the design Gate for Ada. Design: `docs/plans/designs/release-0.3.0-step-4.md`.'
mkdir -p "$work/docs/plans/designs"
printf '# Step 4 design: Reject non-numbers\n\n`tally/cli.py` checks each argument with `float()` and exits with code 2 and `not a number: <input>` on stderr. `tests/test_cli.py` adds a test for a non-number; AR-06 names it.\n\nFor Ada: is the wording `not a number: <input>` right?\n' > "$work/docs/plans/designs/release-0.3.0-step-4.md"
git add docs/plans/designs/release-0.3.0-step-4.md
git commit -q -m "Plan: step 4 design"
git push -q origin main
set_row 1 "done: fixed"
set_row 2 "done"
set_row 4 "stopped (2026-10-22 09:50): at the design stop, waiting for Ada; see Tried"
set_row 5 "in progress (2026-10-22 09:30)"
ci_state green
