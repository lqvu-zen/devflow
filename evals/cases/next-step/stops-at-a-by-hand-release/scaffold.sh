#!/usr/bin/env bash
. "$(dirname "$0")/../../../fixture/build.sh"
plan_edit "\`/devflow:release\`; the maintainer names the version" "by hand, no candidate; the maintainer names the version"
plan_edit "Run \`/devflow:release\`. The maintainer names the version." "Ada releases it by hand, with no candidate, and names the version."
set_row 1 "done: fixed"
set_row 2 "done"
set_row 3 "done"
set_row 4 "done"
set_row 5 "done"
ci_state green
