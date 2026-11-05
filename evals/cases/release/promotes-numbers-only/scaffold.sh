#!/usr/bin/env bash
. "$(dirname "$0")/../../../fixture/build.sh"
set_row 1 "done (2026-10-21)"
set_row 2 "done (2026-10-21)"
set_row 3 "done (2026-10-21)"
set_row 4 "done (2026-10-21)"
set_row 5 "done (2026-10-21)"
numbers_only_versions
built_candidate 0.3.0
git tag v0.3.0-rc1
git push -q origin v0.3.0-rc1
printf 'v0.3.0-rc1\tPre-release\tv0.3.0-rc1\t2026-10-21\nv0.2.0\tLatest\tv0.2.0\t2026-10-01\n' > .gh/releases.txt
set_row 6 "candidate v0.3.0-rc1 published 2026-10-21 12:00; TESTER: PASS (2026-10-21); checklist ticked by Ada 2026-10-22: [x] A fresh download from the candidate's release page unpacks and runs. [x] tally 2 4 prints total=6.0 average=3.0"
ci_state green
