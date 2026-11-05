#!/usr/bin/env bash
. "$(dirname "$0")/../../../fixture/build.sh"
built_candidate
printf 'sig\n' > dist/SHA256SUMS.txt.sig
ci_state green
