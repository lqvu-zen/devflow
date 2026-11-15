#!/usr/bin/env bash
. "$(dirname "$0")/../../../fixture/build.sh"
python3 - "$work/docs/STATUS.md" <<'PY'
import sys

path = sys.argv[1]
text = open(path, encoding="utf-8").read()
row = "- 2026-10-20 18:00: **Adopted devflow.** The method gives each change a review and each release a gate.\n"
assert row in text
added = (
    "- 2026-10-20 17:30: **Top N breaks ties by first appearance, for now.** Step 5 can start without a tie rule. Review by 2026-10-21\n"
    "- 2026-10-20 17:00: **Median stays in the library until 0.4.0.** Keeps 0.3.0 small. Review by 2026-11-30\n"
)
text = text.replace(row, row + added, 1)
open(path, "w", encoding="utf-8", newline="\n").write(text)
PY
git add docs/STATUS.md
git commit -q -m "Status: two dated decisions"
git push -q origin main
head_sha="$(git rev-parse HEAD)"
short="$(git rev-parse --short=7 HEAD)"
ci_state green
