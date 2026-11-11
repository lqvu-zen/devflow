#!/usr/bin/env bash
. "$(dirname "$0")/../../../fixture/build.sh"
plan_edit "1, then 2 to 5, then 6." "1, then 2, then 4, then 3 and 5, then 6."
set_row 1 "done: fixed"
set_row 2 "done"
set_row 5 "in progress (2026-10-22 09:30)"
ci_state green
