#!/usr/bin/env bash
. "$(dirname "$0")/../../../fixture/build.sh"
built_candidate
printf 'sig\n' > dist/SHA256SUMS.txt.sig
digest=$(sha256sum dist/SHA256SUMS.txt | cut -d' ' -f1)
printf '{"head": "0000000000000000000000000000000000000000", "sha256sums": "%s", "passed": 3}' "$digest" > dist/release_check.passed
ci_state green
