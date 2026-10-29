#!/usr/bin/env bash
. "$(dirname "$0")/../../../fixture/build.sh"
set_row 1 "done (2026-10-21)"
set_row 2 "done (2026-10-21)"
set_row 3 "done (2026-10-21)"
set_row 4 "done (2026-10-21)"
set_row 5 "done (2026-10-21)"
built_candidate
printf 'sig\n' > dist/SHA256SUMS.txt.sig
touch .gate_fail
ci_state green
