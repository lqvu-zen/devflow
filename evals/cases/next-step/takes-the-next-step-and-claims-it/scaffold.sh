#!/usr/bin/env bash
. "$(dirname "$0")/../../../fixture/build.sh"
set_row 1 "done: fixed"
ci_state green
