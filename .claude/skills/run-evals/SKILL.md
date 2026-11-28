---
name: run-evals
description: 'Run an eval step of this repo''s plan: the cases its Evals line names, one at a time from a checkout frozen at a pushed, green commit of the branch work lands on (in WSL on Windows), each with --max-cost-usd set to what is left of the step''s approved Budget, stopping when the budget is spent or the usage limit cuts a run; then record the passes with tools/eval_select.py record, write the README Recorded-runs row, commit it after the maintainer''s yes, cherry-pick it onto develop, and report each failing case for the maintainer to rule on. Started by /devflow:next-step when a step''s Who does what row names `/run-evals`. Do NOT use it for a step without an Evals line and an approved Budget, to rule on a failure, or to edit a case, grader or skill.'
---

# Running an eval step

You run one eval step of this repo's plan: the cases its `**Evals:**` line names, within the dollars its `**Budget:**` line approves. You delegate to no agent. What a run shows is reported, never judged: whether a failure is real, a flaky grader or a wrong judge is the maintainer's call.

The two lines, as `/devflow:manage-project` writes them (the format is in `README.md` under Skill evals):

```
**Evals:** cases select | select --release | <case names>; runs <N>; model <default | Sonnet | Opus>; judge sonnet; jobs <J>
**Budget:** $<amount> for the eval runs, cases and judge (this session's own cost not counted); approved YYYY-MM-DD HH:MM by the maintainer
```

## 1. Refuse without the format

Read the step your arguments name. Stop, editing and claiming nothing, when it has no `**Evals:**` line, or when its `**Budget:**` line (the first one, if it has more, as `--next-step` reads it) lacks a `$<amount>` or a dated `approved YYYY-MM-DD` clause at the start of the field or after `.`, `;`, `!` or `?` ("not approved", "**not** approved", "(proposed)" and an undated "approved" never count). Say which is missing: the project manager writes the lines, and only the maintainer's own words approve the budget.

## 2. Claim the step and check CI

Claim the step, keep its Status row and `**Tried:**` line, and check CI on HEAD first, exactly as `add-feature`'s "Before you start, and where you stop" says. A red run on HEAD stops the step there.

## 3. Where the commands run

Every command in sections 4 to 7 runs in Linux: directly on Linux, and on Windows in WSL, each wrapped as `wsl.exe -e bash -lc '<command>'`, with the repo's path there from `wsl.exe wslpath -a '<repo root>'`. Use `python3`. Behaviour cases need `TMPDIR` outside `/tmp`, so each `claude plugin eval` starts `mkdir -p $HOME/ev && TMPDIR=$HOME/ev`. Never run an eval in the working folder: coding sessions commit there, and a skill edit during a run spoils it.

## 4. The frozen checkout

- **Where:** `$EVAL_DEVFLOW_CHECKOUT`, relative to the repo root, when that is set; else `$HOME/devflow-eval`.
- **Which commit:** the newest commit of the branch work lands on (`develop` here) whose CI run section 2 saw green, and which `origin` has (`git branch -r --contains <sha>` names it). With none, stop: the row says why.
- **Move it there:** when the folder is missing, `git clone -q <repo root> <checkout>`. Then `git -C <checkout> fetch -q <repo root> <branch>` and `git -C <checkout> checkout -q --detach <sha>`. `git -C <checkout> status --porcelain` must print nothing; if it prints anything, stop and report it, cleaning nothing.

## 5. The cases

- **`select` or `select --release`:** in the checkout, `python3 tools/eval_select.py select [--release] --each --runs <N> --jobs <J>`. Its commands, one per case, in the order printed, are the cases. When it prints `nothing to run`, the row says `done: nothing to run` and you report that.
- **Case names:** one command per name, in the line's order, in the form `select --each` prints. A behaviour case: `claude plugin eval . --tag behaviour --case "<name>" --runs <N> --ablation none --scaffold --allow-tools Bash Write Edit --trust-plugin --no-publish -j <J> --judge-model sonnet --max-cost-usd 25`. A trigger case (`trigger-…`): `claude plugin eval . --tag trigger --case "<name>" --ablation none --runs <N> --scaffold --trust-plugin --no-publish -j <J>`, leaving out `--scaffold` when its folder has no `scaffold.sh`.
- **Model and judge:** `model Sonnet` or `model Opus` appends `--model sonnet` or `--model opus`; `model default` appends nothing. `judge <model>` is the `--judge-model` value.
- **The cost cap:** a behaviour command ends `--max-cost-usd 25`; replace that value. A trigger command has none; append `--max-cost-usd <left>`. Never two.

Run nothing else: no case the line doesn't name, and no other runs, model, judge or jobs than the line's.

## 6. The budget loop

Keep three amounts: `left` (the budget, from the step's first `**Budget:**` line), `spent` (zero) and `dearest` (the dearest case so far, zero). For each command, in order:

1. Start it only while `left`, rounded down to the cent, is at least 0.01 and at least `dearest`; the first starts whenever that much budget is left, so `--max-cost-usd 0` is never passed. When one can't start, it and every later case are `not run (budget)`.
2. Set its `--max-cost-usd` to `left`, rounded down to the cent.
3. Run it in the checkout in the background (Bash with `run_in_background: true` and `timeout: 7200000`) and wait for its notification. Never run two at once: the budget is counted one case at a time.
4. Its result is the `evals/results/<timestamp>/aggregate-result.json` it wrote, in the folder it names. When no new result folder appeared since the command started, stop the loop as for `Cost: not recorded` below. Run `python3 tools/eval_summary.py <that file>`.
5. Its `Cost: $<x>` line is the case's cost: add it to `spent`, set `left` to the budget less `spent`, and `dearest` to the larger of `dearest` and `<x>`. `Cost: not recorded` stops the loop, since the spend can't be counted: the rest are `not run (budget)`.
6. An error reason that names a usage or session limit stops the loop: the run was cut by the usage limit at that case, and the rest are `not run`.

A command's exit code (1 below the threshold, 2 for a partial run) never stops the loop by itself.

## 7. Record, and the commit

1. In the checkout, `python3 tools/eval_select.py record <every result file> --jobs <J>`. Each line it prints starts `recorded`, `skipped`, `rerun`, `failing` or `refused`.
2. For the `rerun` lines it prints commands for two more runs each (`--runs 2`), sometimes folded into a glob such as `release-*`. Run them through section 6's loop, on the same budget and start rule, one case at a time: a glob becomes one command per rerun case it covers, with `--case "<name>"`, and the cost cap replaced. A rerun the budget doesn't reach is `rerun not run`. Then run `record` again with every result file, the first ones and the new. Run no other rerun.
3. Add one row to the Recorded runs table in the checkout's `README.md`: `| <date> | <suite> (<cases>, <N> runs each, -j <J>, <judge> judge), <model> model, <WSL or Linux>, Claude Code <version from claude --version>; step <N>, on <short commit> | <n> pass; failing <case> (<record's reason>); rerun not run: <cases>; not run (budget): <cases> | $<spent> |`, leaving out the clauses with no case; the cost is the sum of the `Cost:` lines.
4. Wait for the maintainer's yes as `add-feature`'s "6. Commit and push" says: show section 8's full report, `record`'s lines and `git -C <checkout> diff --stat`, set the row as section 8 says with `, waiting for the maintainer's yes` added, and end your turn. Under `next-step`'s "Deciding without asking", the mode takes this yes and nothing else here.
5. After the yes, in the checkout, commit `evals/passes.json` and `README.md` alone, by path, titled `Evals: step <N>, <n> recorded`, with the message rules of `add-feature`'s "6. Commit and push". In the repo root, fetch that commit and cherry-pick it as `README.md` "Where to run them" step (4) says (`git fetch <checkout> HEAD`, then `git cherry-pick FETCH_HEAD`; from Windows the checkout's path is its `//wsl.localhost/<distro>/…` form), keep both sides' lines on an `evals/passes.json` conflict, and push the branch.

## 8. The Status row and the report

Set the row in place, as section 2's rule says:

- every listed case recorded: `done: <n> recorded, $<spent> of $<budget>`;
- otherwise: `stopped (YYYY-MM-DD HH:MM): <n> recorded; failing <case>: <reason>, for the maintainer to rule on; not run (budget spent): <cases>; $<spent> of $<budget>; see Tried`, leaving out the clauses with no case. When the usage limit cut a run, it ends `; cut by the usage limit at <case>; retake it` instead of `; see Tried`.

The report lists each case once: `recorded`, `failing` (quoting `record`'s line, for the maintainer to rule on), `rerun not run`, `not run (budget)`, `skipped` or `refused` (quoting its line); then `$<spent> of $<budget>` and the commit hashes.

## Never

- Judge a failure: never call it flaky, or a grader or judge wrong. Report it as `record` prints it.
- Edit a case, grader, skill, fixture or tool, or the step's Evals or Budget lines.
- Rerun anything `record` doesn't ask for.
- Change the runs, model, judge, jobs or budget, or spend past it: only the one case the start rule lets run over may.
