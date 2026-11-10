# devflow

A Claude Code plugin that brings the RYOS working method to any project. A maintainer decides. Fresh agents with pinned models do the work, and hooks turn the process rules into checks.

## What's in it

| | Name | What it does |
|---|---|---|
| Skill | `/devflow:setup` | Adopts devflow in a project. It reads the codebase, drafts the profile and guard config, and starts the behaviour map, status file and plans. Nothing is written before the maintainer approves. |
| Skill | `/devflow:add-feature` | A feature or improvement: understand → locate (Haiku) → design (Opus) → implement and test (Sonnet) → review (Opus) → commit. |
| Skill | `/devflow:fix-bug` | The same pipeline for a bug: reproduce it, write a failing test, find the root cause and fix it. Adds an escape line when the bug got past a release. |
| Skill | `/devflow:release` | Ships through a release candidate: version → build → gate → pre-release → tester → the maintainer's checklist → release review → promotion. |
| Skill | `/devflow:manage-project` | Keeps the status file and the decision log, triages issues, and turns decisions into plan steps with paste-ready prompts. Keeps the prompt book (`docs/PROMPTS.md`, from `templates/PROMPTS.md`). Reviews recent sessions for process rules the agents broke (`tools/session_extract.py` shrinks them) and proposes Harness escapes lines for the maintainer to approve. |
| Skill | `/devflow:review-ui` | One evidence-based UI/UX review of a web page, a desktop or mobile app screen, or game UI, in one report format. On the web it measures the page in headless Chrome, reads phone and desktop screenshots, drives the states and audits WCAG 2.2 AA. For apps and games it reads screenshots of each state at each size or resolution, and the UI source. Prioritized report with file:line fixes. Read-only. The web path needs Node 22+ and Chrome, Edge or Chromium. Bundles MIT-licensed code from taste-skill under `skills/review-ui/vendor/`. |
| Agent | `devflow:locator` | Haiku, read-only. Quotes the code and the behaviour-map rows. |
| Agent | `devflow:designer` | Opus, medium effort (high for `fix-bug`'s diagnosis). A plan or a root cause, never code. |
| Agent | `devflow:implementer` | Sonnet. Implements and verifies, with at most two fix rounds. Never commits. |
| Agent | `devflow:reviewer` | Opus, high effort. Diff review, or a release review before publishing. |
| Agent | `devflow:planner` | Opus, high effort, read-only. Drafts release plans for the project manager. |
| Agent | `devflow:tester` | Sonnet, read-only. Uses a candidate the way a user would. |
| Hook | guard (PreToolUse) | Refuses writes to the project's real data, anything touching or reading secrets (shell, file tools, Read, Grep, Glob), maintainer-only scripts, and reverting uncommitted status and plan edits. Asks before `gh release` writes and forced pushes. |
| Hook | session start | Shows the branch, uncommitted files, CI on HEAD, and the plan's next open step (skipping steps another tab has claimed). |
| Tool | `tools/model_check.py --board` | Prints each agent's model and effort, where each comes from (the plugin's pin, the `models` board in `.claude/devflow.json`, a step's Model line or a floor) and what a call passes. The agent rows above are defaults; a project sets its own in the `models` board. Without `--board` it checks a session's agent calls against the same values. |
| Tool | `tools/devflow_checks.py` | A CI check. It fails a commit that changes the version unless the commit is titled `Release candidate X.Y.Z-rcN` or `Release X.Y.Z`, fails a release commit that leaves any listed version file at another version, fails new Python comment lines in the listed folders and, where the project turns attribution off, a commit carrying Claude's `Co-Authored-By:` trailer or a "Generated with Claude Code" line. |

## How a project plugs in

Facts about each project live in that project, in two files that `/devflow:setup` writes:

- **`.claude/devflow.md`** is the profile that every skill and agent reads. It has fixed headings: Project, Where things live, Architecture rules, Verify, Edit bounds, Escalate, See it working, Design system, Release, Try it, Standing rules. Briefs paste these sections word for word, so the agents work to this project's rules. See `templates/devflow.md`.
- **`.claude/devflow.json`** configures the guard and the CI check: real data folders, secrets, maintainer-only scripts, how the product starts and which environment variables must point at a scratch folder, and the version files. See `templates/devflow.json`. **The hooks do nothing in a project without this file**, so installing the plugin for your user account is safe.

The method also expects `docs/BEHAVIOUR.md` (the behaviour map), `docs/STATUS.md` (the status file), `docs/plans/` and `docs/archive/`. The status file and plans folder can be moved in `devflow.json`.

## What the guard is

The guard is a guardrail against accidents, not a sandbox. It reads the command text, so it catches the ways an agent normally reaches real data or a secret: variables, `~`, globs, wrappers, heredocs, `cd`, and command substitutions that build a path. It cannot see a path assembled at run time inside a script (`python -c "... 'My' + 'App' ..."`). If the guard cannot run (an exception, a broken config, `uv` missing), the call is not allowed silently: the user is asked, with the reason "not checked". Keep real secrets out of reach of the agent's OS account as well if they matter.

## Install

The repository is its own marketplace:

```
/plugin marketplace add lqvu-zen/devflow
/plugin install devflow@devflow
```

From a local clone, give its path instead: `/plugin marketplace add D:/Projects/devflow`. To turn it off in one project, add `"enabledPlugins": {"devflow@devflow": false}` to that project's `.claude/settings.json`.

Then, in a project: `/devflow:setup`.

## Updating

The install is a snapshot in the plugin cache, so changes to the repository (or a local clone) reach it only when you update:

```
/plugin marketplace update devflow
/plugin update devflow@devflow
```

From a terminal: `claude plugin marketplace update devflow`, then `claude plugin update devflow@devflow`. Restart the session to apply. An update only picks up a new version number, which is bumped in release commits.

To run a checkout without installing or updating, start a session with `claude --plugin-dir D:/Projects/devflow`. It loads the folder as it is on disk, so edits apply on the next start. Disable the installed copy for that session to avoid loading both.

## Reviewing a UI

`/devflow:review-ui` works without `/devflow:setup`, the profile or the config files. With a profile it reads **Design system** and **See it working**. The web path needs Node 22+ and Chrome, Edge or Chromium.

1. For a web page, start the app's dev server, or have a built `.html` file ready. For an app or a game, have screenshots of the states ready, or a **See it working** entry that says how to take them safely.
2. Run `/devflow:review-ui` and say what to review, for example `review the pricing page on mobile` or `review the HUD`. By default a web page is reviewed whole at 375 px and 1440 px.
3. On the web it measures the page in headless Chrome, reads the screenshots and tries the interactive states. For an app or a game it reads the screenshots of each state at each size or resolution, and the UI source. It answers in chat with a prioritized report (P0 to P3, file:line, fix, effort). It never edits code.

Optional: put `.claude/ui-review.json` in the project to set the server URL, pages, widths, output folder, and the style choices it should not flag (`allow`). The format is in `skills/review-ui/SKILL.md` under Config.

## Requirements

- `uv` on `PATH`. The hooks run as `uv run --no-project python …`, using only the standard library.
- Node 22+ and Chrome, Edge or Chromium, only for `/devflow:review-ui` on a web page.
- `git`. `gh`, logged in, for the CI line, issues and releases.
- The hooks are run by `bash`. On Windows, that's the Git Bash that Claude Code uses.

## Tests

```
python -m unittest discover -s tests
```

`tests/test_guard.py` runs the RYOS guard's test cases against an RYOS-shaped config to show the generic guard behaves the same, and adds a Linux-style project and a minimal config. `tests/test_session_start.py` and `tests/test_checks.py` cover the other hook and the CI check; the CI-check tests use real throwaway git repositories.

## Skill evals

The skills are rules in prose, so `evals/` checks that an edit hasn't broken them. It uses Claude Code's own runner, `claude plugin eval` (2.1.269 or later; written against 2.1.306), which loads devflow as a plugin, hooks included. Docs: https://code.claude.com/docs/en/plugin-evals.md.

What is in it:

- `evals/fixture/`: a tiny Python project, `tally`, with a filled-in `.claude/devflow.md` and `.claude/devflow.json` (release stamp configured), a behaviour map, a status file, a plan with steps in different states, a release gate, and a stand-in `bin/gh` that answers from canned files in `.gh/`. `build.sh` builds it, with a local bare `origin`, in the run's empty workspace. The case's system prompt says `gh` is `./bin/gh`.
- `evals/cases/<skill>/<case>/`: 39 behaviour cases. `add-feature` 13, `fix-bug` 7, `release` 8, `review-ui` 4, `manage-project` 7. Each has `prompt.md`, `case.yaml` (only to name `scaffold.sh`), a `scaffold.sh` that sources the fixture and sets up that case's state, and `graders/*.md`.
- `evals/cases/trigger/`: 31 trigger cases: six per skill, three prompts that should fire it and three near misses that belong to another skill, and seven for `review-ui` (four that should fire it, three near misses). They allow only `Skill` and need no shell. The four `review-ui` cases that name a file (1, 2, 3 and 7) have a scaffold (`ui_fixture`), so run them with `--scaffold`.
- `evals/depends.json`: which files each skill's cases depend on (the skill's folder, the agents it calls, the review references it cites), which skill each near miss points at, and `hooks/` for every behaviour case. `tests/test_evals.py` checks it against what each `SKILL.md` cites.
- `evals/passes.json`: the latest pass of every case, as `{commit, date, runs}`, one line per case. `tools/eval_select.py` compares it with the working tree to say which cases a change can reach.

How the runner reads a case (so you can write more):

- A case is a folder with `prompt.md` (frontmatter, then the prompt), `case.yaml`, or both, and at least one grader. Frontmatter keys: `name`, `tags`, `runs` (default 3), `max_turns` (default 10; reaching it is a run error), `timeout_seconds`, `allowed_tools`, `append_system_prompt`, `model`, `env`. Unknown keys are an error. Only `case.yaml` can set `context.scaffold_script`.
- Grader types: `llm` (a rubric in the body; passes on 2 of 3 votes; judge it on `last_message`, because the judge sees a trace with its middle elided), `tool_used` (`tool`, `input_match` regex on the call's JSON, `min`, `max`; "never" is `min: 0`, `max: 0`), `tool_order` (`before`, `after`), `regex` (`target`, `match: not_contains`), `file_exists` (`exists: false` for absence) and `baseline`. A run's score is the weighted share of its graders that passed; a case passes at `--threshold` (default 1.0).
- A trigger check is a `tool_used: Skill` grader with `input_match: '"skill"\s*:\s*"(?:[\w-]+:)?add-feature"'`. With `arm: both` it is scored even when the plugin is compared against a run without it.
- The scaffold runs only with `--scaffold`, as you, in the empty workspace, with a temporary `HOME`; it times out at 120 seconds. Project config it writes is not loaded: the fixture's `.claude/devflow.md` is read by the skills as a file, and the guard hook starts because `.claude/devflow.json` exists.
- Only read-only tools are granted unless you pass `--allow-tools`. Granting `Bash` runs every command under the OS sandbox, which native Windows doesn't have: run the behaviour cases in WSL2 or Linux (with `claude`, `git`, `uv`, `python3`, `bubblewrap` and `socat` installed there). Cases that grant `Bash` are refused on native Windows, not run unconfined.
- **Set `TMPDIR` to a folder outside `/tmp`** when you run the behaviour cases (for example `mkdir -p ~/ev && TMPDIR=$HOME/ev …`). The runner builds each workspace under the temp folder, and under `/tmp` the sandbox mounts the workspace read-only, so every `git commit` fails with "Read-only file system".
- Tool graders (`tool_used`, `tool_order`) see every call in the run, including the subagents' own, and match the call's whole JSON input, file contents included. To check which file an edit touched, match the path (`"file_path"\s*:\s*"[^"]*/tally/`), not the file name alone.
- `--case` takes one glob with `*` and `?` only (no braces, and it cannot be repeated), anchored to the whole name, so a name that is the start of another (`add-feature-claims-step-first`) must be passed exactly, without `*`. Trigger cases are named `trigger-<skill>-<n>-...`, so a skill's are `trigger-<skill>-*`; `<skill>-*` matches no trigger case.
- A `tool_order` grader cannot pass unless both calls are in the trace. Write every `input_match` and `pattern` in single quotes (backslashes stay literal); `tests/test_evals.py` compiles them all, the way the runner does (`new RegExp`), so a pattern that does not compile fails there, not in a paid run.
- `--tag` is "any tag matches": every behaviour case carries `behaviour`, so `--tag manage-project --tag behaviour` runs all of them. Use `--case` to pick a skill.

Which cases to run: `python tools/eval_select.py select [--release]` lists the cases a change can reach since each one's last recorded pass, with the reason, and prints the `claude plugin eval` commands to run (one per `--case` glob). A change to a skill's body reruns its behaviour cases; a change to its `name` or `description` also reruns its trigger cases and the near misses that point at it; `--release` also lists every trigger case. After the run, once the inputs are committed, `python tools/eval_select.py record evals/results/<timestamp>/aggregate-result.json` stores the cases whose every run scored 1 and prints `skipped <case>: <reason>` for the others; commit `evals/passes.json` together with the Recorded runs row below.

Run them from the plugin root:

```
claude plugin eval . --tag trigger --ablation none --runs 1 --scaffold --trust-plugin --no-publish -j 4
TMPDIR=$HOME/ev claude plugin eval . --tag behaviour --runs 1 --ablation none --scaffold --allow-tools Bash Write Edit --trust-plugin --no-publish -j 3 --judge-model sonnet --max-cost-usd 25
```

`--case "<glob>"` picks one case (`"release-*"` for a skill), and `--tag costly` the six that run real agent pipelines. `--ablation none` skips the no-plugin arm, which can't follow a `/devflow:*` prompt. `--judge-model sonnet` is worth the cost: the default Haiku judge disagrees with itself on rubrics of more than one clause. Results land in `evals/results/` (not committed): `aggregate-result.json` and `report.html`. The run exits 1 below the threshold. A full behaviour run costs about $11 to $14 and a subscription can hit its session limit partway: runs that hit it are reported as errors scoring 0, so rerun just those cases.

To see where a run's cost goes, `python tools/eval_cost.py evals/results/<timestamp>/aggregate-result.json` splits each run's recorded cost across the main session and each agent type (add `--root DIR` for workspaces moved elsewhere, such as `//wsl.localhost/Ubuntu-24.04/home/ubuntu/ev` from Windows). It reads the transcripts the runner keeps under the workspace's `config/projects`, so run it before the temporary workspaces are deleted. It does not use `out/trace.jsonl`, whose assistant lines carry partial output tokens. Measured on `add-feature-ui-change-covers-states-and-inputs` (devflow 0.2.1, before the design trim), a session total of $1.9969 plus $0.0087 for the judge:

| Part | Model | Cost | Share |
|---|---|---|---|
| main session | Opus | $0.7578 | 38.0% |
| designer | Opus | $0.8093 | 40.5% |
| reviewer | Opus | $0.3111 | 15.6% |
| implementer | Sonnet | $0.1186 | 5.9% |

The Opus main session and designer are about 80% of the run, the reviewer 16% and the Sonnet implementer 6%, so trimming should target the orchestrator's context and the designer's brief.

To see which model each agent actually ran on, `python tools/model_check.py [SOURCE]` reads a session's transcripts (a session `.jsonl`, an eval run's workspace, or a project path, which takes its newest session; `--count N` and `--exclude ID` pick more) and prints, per agent call, the role, what the call passed, the model each reply ran on, the effort where the transcript records it, and what was expected: the agent file's pin, or a `--model "<role>: <Model>, <effort>"` line for a role the run moved. It marks every mismatch, exits 1 when there is one, and says what it could not read (a call with no transcript, effort not recorded, an unfinished agent, the role of a `general-purpose` call). It refuses a line that moves the locator, reviewer or planner below its pin. With one `--part "implementer: <Model>, <effort>"` per part of a design, in order, it judges the implementer calls against the parts. `add-feature` and `fix-bug` run it at the end, and the project manager's session review reads it. A plan step's `**Model:** <role>: <Model>, <effort>; <why>` line is how a step moves one role off its pin.

The cases are written so that a session which stops and asks, as the skills tell it to, passes. The fixture's CI and plan facts are made to agree with each other, because the sessions check them.

Known gap: no case reaches the "at most two fix rounds, then report Still red" rule. The sessions find a conflict while designing and stop earlier, which `add-feature-stops-on-conflicting-check` covers. A fixture that only fails during implementation would be needed, and a reviewer BLOCKERS rule needs a scripted reviewer.

Recorded runs:

| Date | Suite | Result | Cost |
|---|---|---|---|
| 2026-10-22 | trigger (24 cases, 1 run each) | 23 pass; `add-feature-3-fires` ("Make the tally output show a thousands separator") did not fire the skill, 2 of 5 on a rerun | $2.94 |
| 2026-10-27 | behaviour (26 cases, 1 run each, Sonnet judge) | 20 pass; 2 judge failures on rubrics that were then rewritten; 4 not run (session limit) | $11.48 |
| 2026-10-28 | behaviour, those 6 cases rerun | 6 pass. With the first run, all 26 pass, in two invocations | $2.02 |
| 2026-10-28 | trigger, `add-feature` (6 cases, 5 runs each), after widening its description | 30 of 30 pass; `add-feature-3-fires` went from 2 of 5 to 5 of 5 | $3.78 |
| 2026-10-28 | trigger (24 cases, 1 run each), on the release candidate | 24 pass, including `add-feature-3-fires` | $2.96 |
| 2026-10-29 | behaviour, release (6 cases, 1 run each, Sonnet judge), run in WSL; before 0.2.1 | 5 pass; `release-stops-on-failed-gate` failed (the agent stopped on open plan steps before running the gate). Scaffold and report grader fixed, then 3 of 3 pass. Before the fix it was 2 of 4 across two invocations, with one correct stop failing the judge on wording | $3.11, plus $1.01 on runs cut short by a session limit or a missing sandbox |
| 2026-11-03 | behaviour, `review-ui` (4 cases) and the 2 new `add-feature` UI cases (1 run each, Sonnet judge), WSL | 5 pass first time; `add-feature-ui-change-covers-states-and-inputs` failed once (a grader regex that did not compile, and the judge failing the final report), then 3 of 3 graders passed on a rerun | $5.01 plus $2.01 |
| 2026-11-03 | trigger, `review-ui`: with the first description the 4 that should fire scored 0 of 3 each (the model reviewed the files itself); after the description was made imperative and the cases given fixture files, 12 of 12 | $4.17 plus about $4 on earlier runs |
| 2026-11-03 | trigger (31 cases, 1 run each), after that change | 31 pass, including the near misses of the other four skills | $5.15 |
| 2026-11-04 | behaviour, `fix-bug` (6 cases, 1 run each, Sonnet judge), WSL; before 0.2.2 | 6 pass | $4.66 |
| 2026-11-04 | behaviour, `add-feature` (9 cases, 1 run each, Sonnet judge), WSL; before 0.2.2 (the 7 older cases and the 2 UI cases) | 9 pass | $6.35 |
| 2026-11-05 | behaviour, `release` (7 cases, Sonnet judge), WSL; step 4, numbers-only promotion | `release-promotes-numbers-only`: 2 of 2 pass on the fix, 0 of 2 on the old B2 (it never reached `--allow-empty`). The other 6 release cases pass 1 run each, except `waits-for-the-version`, whose judge failed 1 of 3 runs on the fix and 1 of 3 on the old skill (the case stops before B, so the change cannot reach it) | $2.81 |
| 2026-11-09 | behaviour, the 2 new §5 cases (1 run each, Sonnet judge), WSL; step 9 | `fix-bug-ui-bug-reviewer-gets-motion` passes. `add-feature-new-ui-gets-build-and-motion` failed `floor-in-report` (3 of 3 judge votes: `add-feature` never told the orchestrator to carry the implementer's §5 floor into its report); after one line in step 7, 4 of 4 graders pass | $1.62 plus $2.24 before and $2.45 after the fix |

## Where it came from

This is RYOS's `.claude/` setup with the RYOS-specific parts moved out into the profile. RYOS keeps its own copies (`add-ryos-feature`, `fix-ryos-bug`, `release-ryos`, `ryos-secretary`, the `ryos-*` agents and its hooks). Until RYOS moves over, keep devflow disabled in RYOS, or simply don't give RYOS a `.claude/devflow.json`.
