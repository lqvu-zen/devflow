#!/usr/bin/env bash
. "$(dirname "$0")/../../../fixture/build.sh"
ci_flaky_history
ci_state red
