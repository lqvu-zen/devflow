#!/usr/bin/env bash
case_dir="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$case_dir/../../../.." && pwd)"
. "$case_dir/../../../fixture/build.sh"
set_row 1 "done: fixed"
set_row 2 "done"
set_row 3 "done"
set_row 4 "done"
set_row 5 "done"
plan_edit "1, then 2 to 5, then 6." "1, then 2 to 5, then 7, then 6."
plan_edit "| 6 Release 0.3.0 | coding session + maintainer |" "| 7 Run the tally evals | coding session | \`/run-evals\` |
| 6 Release 0.3.0 | coding session + maintainer |"
plan_edit "| 6 Release 0.3.0 | — |" "| 6 Release 0.3.0 | — |
| 7 Run the tally evals | — |"
plan_edit "## Order" "### 7 — Run the tally evals

_Added 2026-10-21 from Ada's decision._ The three tally cases check the median and JSON steps.

**Files:** \`evals/passes.json\`, \`README.md\`
**Needs** nothing.
**Evals:** cases case-a, case-b, case-c; runs 2; model default; judge sonnet; jobs 1
**Budget:** \$1.00 for the eval runs, cases and judge (this session's own cost not counted); approved 2026-10-21 09:00 by the maintainer
**Done when** every listed case is recorded in \`evals/passes.json\`, or reported as failing or not run; a README Recorded-runs row names the result and the cost.

## Order"

mkdir -p "$work/tools" "$work/.claude/skills/run-evals"
cp "$repo/tools/eval_select.py" "$repo/tools/eval_summary.py" "$work/tools/"
cp "$repo/.claude/skills/run-evals/SKILL.md" "$work/.claude/skills/run-evals/SKILL.md"
cp "$case_dir/claude" "$work/bin/claude"
chmod +x "$work/bin/claude"
for name in case-a case-b case-c; do
  mkdir -p "$work/evals/cases/tally/$name/graders"
  printf -- '---\nname: %s\ntags: [tally, behaviour]\nruns: 1\n---\n\nRun tally on 1 2 3.\n' "$name" > "$work/evals/cases/tally/$name/prompt.md"
  printf -- '---\ntype: regex\npattern: total\ntarget: last_message\n---\n' > "$work/evals/cases/tally/$name/graders/total.md"
done
printf '{\n  "every_behaviour_case": [],\n  "skills": {"tally": ["tally/"]}\n}\n' > "$work/evals/depends.json"
printf '{}\n' > "$work/evals/passes.json"
printf 'evals/results/\n' >> "$work/.gitignore"
printf '# tally\n\nA tiny calculator.\n\n## Skill evals\n\nRecorded runs:\n\n| Date | Suite | Result | Cost |\n|---|---|---|---|\n' > "$work/README.md"
git add -A
git commit -q -m "Add the tally evals"
git push -q origin main
head_sha="$(git rev-parse HEAD)"
short="$(git rev-parse --short=7 HEAD)"
git clone -q "$work" "$work/.frozen"
printf '.frozen/\n' >> "$work/.git/info/exclude"
ci_state green
