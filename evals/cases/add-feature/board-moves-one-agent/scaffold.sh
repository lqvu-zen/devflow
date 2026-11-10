#!/usr/bin/env bash
. "$(dirname "$0")/../../../fixture/build.sh"
python3 - "$work/.claude/devflow.json" <<'PY'
import json
import sys

path = sys.argv[1]
config = json.load(open(path, encoding="utf-8"))
config["models"] = {"designer": "Sonnet, medium", "reviewer": "Sonnet, medium"}
open(path, "w", encoding="utf-8", newline="\n").write(json.dumps(config, indent=2) + "\n")
PY
git add -A
git commit -q -m "Board moves the designer and tries to move the reviewer"
git push -q origin main
head_sha="$(git rev-parse HEAD)"
short="$(git rev-parse --short=7 HEAD)"
ci_state green
