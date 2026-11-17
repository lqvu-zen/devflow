#!/usr/bin/env bash
. "$(dirname "$0")/../../../fixture/build.sh"
ci_state green

folder="$HOME/.claude/projects/$(printf '%s' "$work" | sed 's/[^A-Za-z0-9]/-/g')"
mkdir -p "$folder"

python3 - "$folder/d1a9c0de-0000-4000-8000-000000000002.jsonl" "$short" <<'PY'
import json
import sys
from datetime import datetime, timedelta, timezone

target, short = sys.argv[1], sys.argv[2]
session = "d1a9c0de-0000-4000-8000-000000000002"
start = datetime(2026, 10, 21, 9, 0, tzinfo=timezone.utc)
records = []
tool_number = [0]


def stamp():
    moment = start + timedelta(minutes=len(records))
    return moment.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def base(kind):
    return {"type": kind, "sessionId": session, "gitBranch": "main", "isSidechain": False,
            "timestamp": stamp()}


def hook(stdout):
    item = base("attachment")
    item["attachment"] = {"type": "hook_success", "hookEvent": "SessionStart",
                          "hookName": "SessionStart:startup", "stdout": stdout}
    records.append(item)


def user(text):
    item = base("user")
    item["message"] = {"role": "user", "content": text}
    records.append(item)


def assistant(parts):
    item = base("assistant")
    item["message"] = {"role": "assistant", "model": "claude-sonnet-4-5", "content": parts,
                       "usage": {"input_tokens": 1200, "output_tokens": 300,
                                 "cache_read_input_tokens": 8000,
                                 "cache_creation_input_tokens": 500}}
    records.append(item)


def call(name, params):
    tool_number[0] += 1
    identifier = "toolu_%02d" % tool_number[0]
    assistant([{"type": "tool_use", "id": identifier, "name": name, "input": params}])
    return identifier


def result(identifier, text):
    item = base("user")
    item["message"] = {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": identifier, "content": text}]}
    records.append(item)


def step(name, params, text):
    result(call(name, params), text)


hook("devflow session start\nBranch: main\nUncommitted: none.\n"
     "CI on HEAD %s: success.\nNext open step in Order: 2 Median" % short)
user("/devflow:add-feature step 2 of docs/plans/release-0.3.0.md (Median)")
step("Skill", {"skill": "devflow:add-feature", "args": "step 2 of docs/plans/release-0.3.0.md"},
     "Launching skill: devflow:add-feature")
step("Bash", {"command": "git commit -m \"Status: step 2 in progress\" -- docs/plans/release-0.3.0.md && git push"},
     "[main 1a2b3c4] Status: step 2 in progress")
step("Agent", {"subagent_type": "devflow:locator", "description": "Locate median",
               "prompt": "Find where core.median belongs."},
     "tally/core.py:1 holds mean and average; tests/test_core.py:1 holds their tests.")
step("Agent", {"subagent_type": "devflow:designer", "description": "Design median",
               "prompt": "Design core.median."},
     "Design: add median(items) to tally/core.py. Done when: tests for odd, even and empty lists.")
assistant([{"type": "text", "text": "The design adds median to tally/core.py. Approve it?"}])
user("Approved.")
step("Agent", {"subagent_type": "devflow:implementer", "description": "Implement median",
               "prompt": "Implement the approved design."},
     "Added median and tests for odd and even lists; Ran 9 tests OK")
step("Bash", {"command": "python -m unittest discover -s tests"}, "Ran 9 tests\n\nOK")
step("Bash", {"command": "git add tally/core.py tests/test_core.py docs/BEHAVIOUR.md "
                         "&& git commit -m \"Median (step 2)\" && git push"},
     "[main 5d6e7f8] Median (step 2)")
step("Edit", {"file_path": "docs/plans/release-0.3.0.md", "old_string": "| 2 Median | — |",
              "new_string": "| 2 Median | done |"},
     "The file docs/plans/release-0.3.0.md has been updated.")
assistant([{"type": "text", "text": "Step 2 is done: median is added and pushed."}])

with open(target, "w", encoding="utf-8", newline="\n") as handle:
    for item in records:
        handle.write(json.dumps(item) + "\n")
assert len(records) == 21, len(records)
PY
