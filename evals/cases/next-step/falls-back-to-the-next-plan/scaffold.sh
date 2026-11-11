#!/usr/bin/env bash
. "$(dirname "$0")/../../../fixture/build.sh"
set_row 1 "done: fixed"
set_row 2 "in progress (2026-10-22 09:30)"
set_row 5 "in progress (2026-10-22 09:45)"
next_plan
ci_state green
