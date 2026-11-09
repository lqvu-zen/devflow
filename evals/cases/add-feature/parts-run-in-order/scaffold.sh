#!/usr/bin/env bash
. "$(dirname "$0")/../../../fixture/build.sh"
python3 - "$work/docs/plans/release-0.3.0.md" <<'PY'
import re
import sys

path = sys.argv[1]
text = open(path, encoding="utf-8").read()
section = re.search(r"^### 2 — Median\n.*?(?=^### |\Z)", text, flags=re.M | re.S)
assert section
body = section.group(0)
old = "**Needs** nothing.\n"
assert old in body
parts = (
    "The design splits the implementation into three parts, in this order: "
    "`implementer: Sonnet, medium; core.median for odd lengths and its test`, "
    "`implementer: Opus, medium; the mean of the two middle numbers for even lengths, with its test`, "
    "`implementer: Sonnet, medium; the AR-04 map entry`.\n"
)
body = body.replace(old, old + parts, 1)
text = text[:section.start()] + body + text[section.end():]
open(path, "w", encoding="utf-8", newline="\n").write(text)
PY
git add -A
git commit -q -m "Step 2 splits the implementation into three parts"
git push -q origin main
head_sha="$(git rev-parse HEAD)"
short="$(git rev-parse --short=7 HEAD)"
ci_state green
