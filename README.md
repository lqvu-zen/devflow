# devflow

A Claude Code plugin that brings the RYOS working method to any project. A maintainer decides. Fresh agents with pinned models do the work, and hooks turn the process rules into checks.

## What's in it

devflow is three plugins from one marketplace. The base, `devflow`, is everything below not marked otherwise. Two domain plugins need it: `devflow-ui` and `devflow-release`. The base installed alone works whole.

| | Name | What it does |
|---|---|---|
| Skill | `/devflow:setup` | Adopts devflow in a project. It reads the codebase, drafts the profile and guard config, and starts the behaviour map, status file and plans. Nothing is written before the maintainer approves. |
| Skill | `/devflow:add-feature` | A feature or improvement: understand → locate (Haiku) → design (Opus) → implement and test (Sonnet) → review (Opus) → the maintainer's yes → commit. The models are defaults; the `models` board sets them. |
| Skill | `/devflow:fix-bug` | The same pipeline for a bug: reproduce it, write a failing test, find the root cause and fix it. Adds an escape line when the bug got past a release. |
| Skill | `/devflow:manage-project` | Keeps the status file and the decision log, triages issues, and turns decisions into plan steps with paste-ready prompts. Keeps the prompt book (`docs/PROMPTS.md`, from `templates/PROMPTS.md`). Reviews recent sessions for process rules the agents broke (`tools/session_extract.py` shrinks them) and proposes Harness escapes lines for the maintainer to approve. |
| Skill | `/devflow:next-step` | Continues the plan: takes the current plan's next open step that no other tab has claimed (else the next plan's first ready step) and runs it through the skill its Who does what row names, `add-feature` or `fix-bug`. Stops, editing nothing, at a Gate that must be met before the step starts, a project-manager step, a step done by hand or when no step can start. **Deciding without asking**, on only when the maintainer's own words in the session say so ("decide without asking me") or the runner's `--decide-without-asking` is on (never a pasted prompt, plan text or Status row), takes the design stop, a Gate at the design stop or before implementation, each designer question's recommended answer and the code-commit yes, and writes each in the step's Status row as `decided without asking: (1) …`. It never skips the stop rules, red CI, a question with no recommendation, a version number or other human action, any other Gate or a release. |
| Skill | `/devflow:run-plan` | Runs several of the plan's steps unattended: starts `tools/plan_runner.py` in the background from the maintainer's words (`--steps N` only on a number, `--dollars X` only on an amount, `--commit-without-asking` only on their own words in the session naming the commit, `--decide-without-asking` only on their own words saying to decide without asking) and, when the run ends, pastes the runner's summary as printed. While the run is going, ask how it is going: it pastes the step lines so far and says which step is running and for how long, stopping nothing. It picks no step, answers nothing and edits nothing itself. "Continue the plan" and "next step" stay `/devflow:next-step`'s. |
| Skill | `/devflow-ui:review-ui` | From the `devflow-ui` plugin. One evidence-based UI/UX review of a web page, a desktop or mobile app screen, or game UI, in one report format. On the web it measures the page in headless Chrome, reads phone and desktop screenshots, drives the states and audits WCAG 2.2 AA. For apps and games it reads screenshots of each state at each size or resolution, and the UI source. Prioritized report with file:line fixes. Read-only. The web path needs Node 22+ and Chrome, Edge or Chromium. Bundles MIT-licensed code from taste-skill under `plugins/devflow-ui/skills/review-ui/vendor/`. |
| Skill | `/devflow-release:release` | From the `devflow-release` plugin. Ships through a release candidate: version → build → gate → pre-release → tester → the maintainer's checklist → release review → promotion. Without it, a project releases by hand, as the **Release** section of its profile says. |
| Agent | `devflow:locator` | Haiku, read-only. Quotes the code and the behaviour-map rows. |
| Agent | `devflow:designer` | Opus, medium effort by default; the board's `designer` row moves it, and `fix-bug`'s diagnosis takes `designer.diagnosis`. A plan or a root cause, never code. |
| Agent | `devflow:implementer` | Sonnet. Implements and verifies, with at most two fix rounds. Never commits. |
| Agent | `devflow:reviewer` | Opus, medium effort. Diff review; with `devflow-release`, the release review before publishing, from that plugin's instructions. |
| Agent | `devflow:planner` | Opus, medium effort, read-only. Drafts release plans for the project manager. |
| Agent | `devflow-release:tester` | From the `devflow-release` plugin. Sonnet, read-only. Uses a candidate the way a user would. |
| Templates | `templates/` | What `/devflow:setup` copies into a project: `devflow.md` (the profile), `devflow.json` (guard, CI check and models board), `settings.json`, `BEHAVIOUR.md`, `DESIGN.md` (projects with a UI), `STATUS.md`, `plan.md`, `PROMPTS.md`, `CLAUDE-section.md`, `ci-devflow.yml`, and `architecture/` (the area docs' index and writing rules, and the shape of one area's doc). |
| Hook | guard (PreToolUse) | Refuses writes to the project's real data, anything touching or reading secrets (shell, file tools, Read, Grep, Glob), maintainer-only scripts, and reverting uncommitted status and plan edits. Asks before `gh release` writes and forced pushes. |
| Hook | session start | Shows the branch, uncommitted files, CI on HEAD, and the plan's next open step (skipping steps another tab has claimed; when none of the current plan can start, the next plan's first ready step, marked as such), and a `Models:` line that warns when the session runs on another model than the board's `orchestrator`. `python <plugin>/hooks/session_start.py --next-step` prints the step and the skill to run, or why it stops. |
| Tool | `tools/model_check.py --board` | Prints each agent's model and effort, where each comes from (the plugin's pin, your `default_models` setting, the `models` board in `.claude/devflow.json`, a step's Model line or a floor) and what a call passes. The agent rows above are defaults; a project sets its own in the `models` board. Without `--board` it checks a session's agent calls against the same values. |
| Tool | `tools/plan_runner.py [--steps N]` | Runs the plan from a terminal outside Claude, or from a session through `/devflow:run-plan`: one fresh headless `claude -p /devflow:next-step` per step, one at a time, on `develop` only. It refuses on another branch or a tree dirty beyond the status and plan files, and stops, saying why, at a `Stop:` line, a step whose row isn't done (a code commit waiting for the maintainer's yes included), a permission ask the session couldn't answer in a step that didn't end done (refusals in a done step with green CI are listed under it and the run goes on), changes left outside the status and plan files, CI on HEAD not green, the account's usage limit (named with its reset time), `--steps N` (optional: without it the run goes on until another stop or Ctrl+C) or `--dollars X`. It never retries a step, picks, writes the status file or pushes; it writes one thing in the plan, the Status row of a step the usage limit cut off while claimed (`stopped (...): cut off by the usage limit; retake it`), so the next run takes it again. `--commit-without-asking` waives the wait for the yes for this run only (the session checks it with `plan_runner.py --waived`); `--decide-without-asking` includes it and also lets each session take the design stop, a design-stop Gate and the designer's recommended answers (checked with `plan_runner.py --deciding`), while a human-action Gate, red CI, a question with no recommendation and a second BLOCKERS still stop the run, and the summary lists each step's decisions under it; `--model` (default: the board's `orchestrator`, else yours from `default_models`) and `--permission-mode default\|acceptEdits` (default `acceptEdits`) pass through. A session that runs past four hours is ended with the processes it started and the run stops saying so; a crashed session's exit code and error line appear in its reason. Each step's start line carries its start time. After a usage-limit stop it says whether to resume the cut-off session (changes left) or run the plan again. It says which step it is starting before each session, names the command or file behind each permission ask the session couldn't answer (in the stop, or under a done step), and says when a session ended in an error. The summary lists each step's outcome, commits and cost, and when the last step stopped, the `claude --resume` command that reopens its session. |
| Tool | `tools/devflow_checks.py` | A CI check. It fails a commit that changes the version unless the commit is titled `Release candidate X.Y.Z-rcN` or `Release X.Y.Z`, fails a release commit that leaves any listed version file at another version, fails new Python comment lines in the listed folders and, where the project turns attribution off, a commit carrying Claude's `Co-Authored-By:` trailer or a "Generated with Claude Code" line. `anchors` fails an area doc whose code-span link names a missing file, a symbol its file lacks, or any line anchor; `docs` fails a commit that changes a path the routing table sends to a doc without changing that doc or carrying a `Docs-unaffected: <doc>.md - <why>` line. |

## How a project plugs in

Facts about each project live in that project, in two files that `/devflow:setup` writes:

- **`.claude/devflow.md`** is the profile that every skill and agent reads. It has fixed headings: Project, Where things live, Architecture rules, Verify, Edit bounds, Escalate, See it working, Design system, Release, Try it, Standing rules. Briefs paste these sections word for word, so the agents work to this project's rules. See `templates/devflow.md`.
- **`.claude/devflow.json`** configures the guard and the CI check: real data folders, secrets, maintainer-only scripts, how the product starts and which environment variables must point at a scratch folder, and the version files. See `templates/devflow.json`. **The hooks do nothing in a project without this file**, so installing the plugin for your user account is safe.

When it sets up CI (a project with GitHub Actions and a check to run), `/devflow:setup` copies the plugin's `tools/devflow_checks.py` into the project. Copy it again after updating the plugin, or CI keeps running the old check.

The method also expects `docs/BEHAVIOUR.md` (the behaviour map), `docs/STATUS.md` (the status file), `docs/plans/` and `docs/archive/`. The status file and plans folder can be moved in `devflow.json`.

**Area docs** (`docs/architecture/`) record what the code does not show: how an area's pieces connect, what must stay true, how to add one more of a pattern, and the traps. `/devflow:setup` writes them for the two or three areas the maintainer says cause the most rework, from `templates/architecture/`, and more are added as changes touch an area, never all at once. A routing table in `CLAUDE.md` ("When to read an area's doc first") maps paths and topics to docs: the locator reads the matching sections before searching, the designer names the docs a change reaches, the implementer updates them in the same commit or writes a `Docs-unaffected: <doc>.md - <why>` line for the message, and the reviewer reads the doc diff beside the code diff. Two CI checks keep them honest: `anchors` (every anchor names a real file and a symbol in it, never a line number) and `docs` (a routed change updates its doc or says why not; set `checks.docs_routing` to turn it on). devflow's own docs are in `docs/architecture/` here.

## What the guard is

The guard is a guardrail against accidents, not a sandbox. It reads the command text, so it catches the ways an agent normally reaches real data or a secret: variables, `~`, globs, wrappers, heredocs, `cd`, and command substitutions that build a path. It cannot see a path assembled at run time inside a script (`python -c "... 'My' + 'App' ..."`). If the guard cannot run (an exception, a broken config, `uv` missing), the call is not allowed silently: the user is asked, with the reason "not checked". Keep real secrets out of reach of the agent's OS account as well if they matter.

## Install

The repository is its own marketplace, `devflow`, listing three plugins: the base `devflow` and the domain plugins `devflow-ui` (UI review) and `devflow-release` (releases through a tested candidate), which need the base.

```
/plugin marketplace add lqvu-zen/devflow
/plugin install devflow@devflow
/plugin install devflow-ui@devflow
/plugin install devflow-release@devflow
```

A base-only install works whole: every `/devflow:*` skill, agent, hook and tool runs without either domain plugin, and `add-feature` and `fix-bug` keep their UI checklists. Install a domain plugin only for what it adds: `devflow-ui` for `/devflow-ui:review-ui`, `devflow-release` for `/devflow-release:release` and its `devflow-release:tester` agent. Without `devflow-release` a project releases by hand, as **Release** in its profile says. Session start names a missing domain plugin's install command when the profile's **Design system** or **Release** calls for it.

From a local clone, give its path instead: `/plugin marketplace add D:/Projects/devflow`. To turn one plugin off in a project, set its key to `false` under `enabledPlugins` in that project's `.claude/settings.json`: `"devflow@devflow"`, `"devflow-ui@devflow"` or `"devflow-release@devflow"`, for example `"enabledPlugins": {"devflow-release@devflow": false}`. Turning the base off leaves a domain plugin without it: `/devflow-release:release` stops and says to install devflow.

**Install devflow from one marketplace only.** If you also added another marketplace that lists devflow, install each plugin from one of them, never both: two installs run two guards and two session starts on every call, and nothing detects it.

**Moved out of the base.** If you installed devflow before `review-ui` and `release` became their own plugins: after `/plugin update devflow@devflow`, install the ones you use. `/plugin install devflow-ui@devflow` gives `/devflow-ui:review-ui`. `/plugin install devflow-release@devflow` gives `/devflow-release:release` and `devflow-release:tester`. A plan row or prompt that still names the old command makes `--next-step` stop and give the new name. Update your `docs/PROMPTS.md`, the devflow section of `CLAUDE.md` and open plans' release steps by hand.

Then, in a project: `/devflow:setup`.

## Your settings

Personal settings, set in `/config` for the base `devflow` plugin. They apply to you in every project and are never project policy: nothing here loosens the guard or changes attribution, which stay in each project's `.claude/devflow.json`.

| Setting | Values | What it does |
|---|---|---|
| `session_start_output` | `full` (default), `short`, `off` | How much the session-start summary prints. `short` keeps the branch, CI, the next step and the problems; `off` keeps only the `devflow base:` line (and the `Store:` line of a linked clone). Anything else prints the full summary and says so. `--next-step` ignores it. |
| `maintainer_name` | text | `/devflow:setup` suggests it as the maintainer's name instead of asking. The project's profile stays the record. |
| `maintainer_timezone` | for example `UTC+7` or `Asia/Ho_Chi_Minh` | The same for the time zone. |
| `default_models` | `role: Model, effort; role: Model`, for example `implementer: sonnet, low; tester: haiku` | Your own model per role, used where a project's `models` board leaves the role on `default`. Order: a step's Model line or a design's part, then the board, then your default, then the plugin's pin. The roles are the board's keys; the orchestrator takes a model only. The floors hold for your defaults as for the board: the locator, reviewer and planner never go below their pins, nor `fix-bug`'s diagnosis below Opus, medium. A default for `tester` applies to `devflow-release:tester`. |

Hooks get these as `CLAUDE_PLUGIN_OPTION_*` environment variables. `model_check` run from a session has none, so it reads `default_models` from `pluginConfigs` in your user `settings.json` (`$CLAUDE_CONFIG_DIR/settings.json`, else `~/.claude/settings.json`). devflow only reads these settings. `python <plugin>/tools/model_check.py --board` shows what was read and where each model comes from.

## Updating

The install is a snapshot in the plugin cache, so changes to the repository (or a local clone) reach it only when you update:

```
/plugin marketplace update devflow
/plugin update devflow@devflow
/plugin update devflow-ui@devflow
/plugin update devflow-release@devflow
```

Run the last two for each domain plugin you installed. From a terminal: `claude plugin marketplace update devflow`, then `claude plugin update devflow@devflow`, and `claude plugin update devflow-ui@devflow` and `claude plugin update devflow-release@devflow` for each domain plugin you installed. Restart the session to apply. An update of the base only picks up a new version number, which is bumped in release commits. `devflow-ui` and `devflow-release` carry no version until the release that sets one; until then an update picks up the commit `main` points at. Installs read `main`, the default branch, which moves only at a release; work lands on `develop`, so a local clone on `develop` holds unreleased changes.

To run a checkout without installing or updating, start a session with `claude --plugin-dir D:/Projects/devflow`. It loads the folder as it is on disk, so edits apply on the next start. Disable the installed copy for that session to avoid loading both.

## Reviewing a UI

Install `devflow-ui` first (`/plugin install devflow-ui@devflow`). `/devflow-ui:review-ui` works without `/devflow:setup`, the profile or the config files. With a profile it reads **Design system** and **See it working**. The web path needs Node 22+ and Chrome, Edge or Chromium.

1. For a web page, start the app's dev server, or have a built `.html` file ready. For an app or a game, have screenshots of the states ready, or a **See it working** entry that says how to take them safely.
2. Run `/devflow-ui:review-ui` and say what to review, for example `review the pricing page on mobile` or `review the HUD`. By default a web page is reviewed whole at 375 px and 1440 px.
3. On the web it measures the page in headless Chrome, reads the screenshots and tries the interactive states. For an app or a game it reads the screenshots of each state at each size or resolution, and the UI source. It answers in chat with a prioritized report (P0 to P3, file:line, fix, effort). It never edits code.

Optional: put `.claude/ui-review.json` in the project to set the server URL, pages, widths, output folder, and the style choices it should not flag (`allow`). The format is in `plugins/devflow-ui/skills/review-ui/SKILL.md` under Config.

## Requirements

- `uv` on `PATH`. The hooks run as `uv run --no-project python …`, using only the standard library. `/devflow:setup` checks for it first and, if it is missing, stops and gives the install command.
- Python 3.14 or newer for the hooks and tools (tested on 3.14 and 3.15 on Linux and Windows). `uv run --no-project python` uses the project's `.python-version` if it has one, otherwise a Python uv finds; `uv python install 3.14` adds one. On 3.13 they still run today but are not tested, and a later release may use a 3.14 feature: the guard would then ask "not checked" on every guarded call and session start would print nothing.
- A Claude Code version that supports a plugin's `userConfig` settings (see Your settings).
- Node 22+ and Chrome, Edge or Chromium, only for `/devflow-ui:review-ui` on a web page.
- `git`. `gh`, logged in, for the CI line, issues and releases.
- The hooks are run by `bash`. On Windows, that's the Git Bash that Claude Code uses.

## Tests

```
python -m unittest discover -s tests
```

Run them on Python 3.14 or newer; CI runs them on 3.14 and 3.15 with deprecation warnings as errors.

`tests/test_guard.py` runs the RYOS guard's test cases against an RYOS-shaped config to show the generic guard behaves the same, and adds a Linux-style project and a minimal config. `tests/test_session_start.py` and `tests/test_checks.py` cover the other hook and the CI check; the CI-check tests use real throwaway git repositories.

## Skill evals

The skills are rules in prose, so `evals/` checks that an edit hasn't broken them. It uses Claude Code's own runner, `claude plugin eval` (2.1.269 or later; written against 2.1.306), which loads devflow as a plugin, hooks included. Docs: https://code.claude.com/docs/en/plugin-evals.md.

What is in it:

- `evals/fixture/`: a tiny Python project, `tally`, with a filled-in `.claude/devflow.md` and `.claude/devflow.json` (release stamp configured), a behaviour map, a status file, a plan with steps in different states, a release gate, and a stand-in `bin/gh` that answers from canned files in `.gh/`. `build.sh` builds it, with a local bare `origin`, in the run's empty workspace. The case's system prompt says `gh` is `./bin/gh`.
- `evals/cases/<skill>/<case>/`: 58 behaviour cases. `add-feature` 15, `fix-bug` 7, `release` 8, `review-ui` 4, `manage-project` 10, `next-step` 9, `run-plan` 2, `setup` 2, `run-evals` 1. Each has `prompt.md`, `case.yaml` (only to name `scaffold.sh`), a `scaffold.sh` that sources the fixture and sets up that case's state, and `graders/*.md`.
- `evals/cases/trigger/`: 44 trigger cases: six per skill (including `next-step` and `run-plan`), three prompts that should fire it and three near misses that belong to another skill, one more near miss for `next-step` (a prompt that belongs to `run-plan`), and seven for `review-ui` (four that should fire it, three near misses). They allow only `Skill` and need no shell. The four `review-ui` cases that name a file (1, 2, 3 and 7) have a scaffold (`ui_fixture`), so run them with `--scaffold`.
- The `release` and `review-ui` cases, and their trigger cases, load their domain plugin too (`plugins: [., plugins/<name>]` in the front matter).
- `evals/depends.json`: which files each skill's cases depend on (the skill's folder, the agents it calls, the review references it cites), which skill each near miss points at, and the hooks: `hook_files` lists, for a hook file, the skills whose behaviour cases it can reach (the skill, or one it hands work to, runs that hook or a tool that loads it, or the hook decides the case's result), and any other file under `hooks/` reaches every behaviour case. `tests/test_evals.py` checks it against what each `SKILL.md` cites.
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

Which cases to run: `python tools/eval_select.py select [--release]` lists the cases a change can reach since each one's last recorded pass, with the reason, and prints the `claude plugin eval` commands to run (one per `--case` glob). A change to a skill's body reruns its behaviour cases; a change to its `name` or `description` also reruns its trigger cases and the near misses that point at it; `--release` also lists every trigger case. A change to `hooks/session_start.py` or `hooks/devflow_store.py` reruns the behaviour cases of every skill but `review-ui`, a change to `hooks/guard.py` those of every skill but `review-ui` and `run-plan`, and a change to `hooks/hooks.json` or a new hook file all of them. After the run, in the frozen checkout, `python tools/eval_select.py record evals/results/<timestamp>/aggregate-result.json` stores the cases that passed (see below); commit `evals/passes.json` together with the Recorded runs row below.

When a failure counts: a behaviour case that fails one run is not yet failing. `record` prints `rerun <case>: <reason>` and the commands that run it twice more (`--runs 2`); run them in the same frozen checkout, then record the first result file and the new one together (`record <first> <new>`). If both reruns pass, the case is recorded with its two clean runs and the failed run is printed; with a second failed run it is `failing <case>: <reason>`, the one to report. A trigger case keeps one run: any score below 1 is `skipped <case>: <reason>`, as is a case with no runs, an error or a skipped paid grader.

Where to run them: evals run from a checkout frozen at one `develop` commit, never from the working folder where coding sessions commit: a skill edit during a run spoils it. (1) Make the frozen checkout at a commit already pushed to `develop`: `git worktree add --detach ../devflow-eval <commit>` (in WSL, a clone checked out to that commit does the same). (2) Run `select`, the `claude plugin eval` commands and `record` in that checkout; `record` stamps the tested commit, which is on `develop`. (3) In the frozen checkout, commit `evals/passes.json` and the README's Recorded runs row. (4) In the `develop` checkout, cherry-pick that commit (from a worktree `git cherry-pick <commit>`; from a WSL clone `git fetch <clone path> HEAD` then `git cherry-pick FETCH_HEAD`) and push `develop`; a conflict in `evals/passes.json` is resolved by keeping both sides' lines. (5) Move the frozen checkout on with `git -C ../devflow-eval checkout --detach <commit>`, or remove it with `git worktree remove ../devflow-eval`.

Who runs them: a coding session, from an eval step of the plan, through `/devflow:next-step`, which hands it to this repo's own `/run-evals` (`.claude/skills/run-evals/`, not shipped). The step carries two lines the project manager writes:

```
**Evals:** cases select | select --release | <case names>; runs <N>; model <default | Sonnet | Opus>; judge sonnet; jobs <J>
**Budget:** $<amount> for the eval runs, cases and judge (this session's own cost not counted); approved YYYY-MM-DD HH:MM by the maintainer
```

Its Who does what row is `coding session` | `` `/run-evals` ``. Until the maintainer's own words approve the Budget (a dated `approved` clause), `--next-step` stops with "has no approved Budget", and the plan runner stops before any step with a Budget line. `/run-evals` runs the listed cases one at a time from the frozen checkout (in WSL on Windows), each with `--max-cost-usd` set to what is left, starts the next only while what is left is at least the dearest case so far, runs only the reruns `record` asks for, records, writes the Recorded runs row, commits it after the maintainer's yes and cherry-picks it onto `develop`. It reports each failing case for the maintainer to rule on and never decides that a failure is flaky. The session's own cost is outside the Budget.

Run them from the frozen checkout's root:

```
claude plugin eval . --tag trigger --ablation none --runs 1 --scaffold --trust-plugin --no-publish -j 2
TMPDIR=$HOME/ev claude plugin eval . --tag behaviour --runs 1 --ablation none --scaffold --allow-tools Bash Write Edit --trust-plugin --no-publish -j 2 --judge-model sonnet --max-cost-usd 25
```

`--case "<glob>"` picks one case (`"release-*"` for a skill), and `--tag costly` the six that run real agent pipelines. `--ablation none` skips the no-plugin arm, which can't follow a `/devflow:*` prompt. `--judge-model sonnet` is worth the cost: the default Haiku judge disagrees with itself on rubrics of more than one clause. Results land in `evals/results/` (not committed): `aggregate-result.json` and `report.html`. The run exits 1 below the threshold. A full behaviour run costs about $11 to $14 and a subscription can hit its session limit partway: runs that hit it are reported as errors scoring 0, so rerun just those cases. The commands run two cases at a time (`-j 2`): the total cost is the same and `--max-cost-usd` is overrun by at most two runs, but usage builds faster than at `-j 1`, so the session limit comes sooner; lower `-j` to 1 if a run keeps hitting it, or raise it (up to 8) to go faster, since every run is a full `claude` child sharing your one rate limit.

To see how a run went, `python tools/eval_summary.py evals/results/<timestamp>/aggregate-result.json` prints one row per case and a total: runs, finished (runs with no error), passed (of all runs) and graders (the mean score of the finished runs, or `none finished`), as n of m and a percentage, then one line per error reason with its count, cut to its first clause so session-limit messages with different reset times count together. A run with an error counts as neither finished nor passed; a case with no runs shows `0 runs`; the first line says `partial` when the run stopped early. It reads only the result file, so it works after the workspaces are gone.

To see where a run's cost goes, `python tools/eval_cost.py evals/results/<timestamp>/aggregate-result.json` splits each run's recorded cost across the main session and each agent type (add `--root DIR` for workspaces moved elsewhere, such as `//wsl.localhost/Ubuntu-24.04/home/ubuntu/ev` from Windows). It reads the transcripts the runner keeps under the workspace's `config/projects`, so run it before the temporary workspaces are deleted. It does not use `out/trace.jsonl`, whose assistant lines carry partial output tokens. Measured on `add-feature-ui-change-covers-states-and-inputs` (devflow 0.2.1, before the design trim), a session total of $1.9969 plus $0.0087 for the judge:

| Part | Model | Cost | Share |
|---|---|---|---|
| main session | Opus | $0.7578 | 38.0% |
| designer | Opus | $0.8093 | 40.5% |
| reviewer | Opus | $0.3111 | 15.6% |
| implementer | Sonnet | $0.1186 | 5.9% |

The Opus main session and designer are about 80% of the run, the reviewer 16% and the Sonnet implementer 6%, so trimming should target the orchestrator's context and the designer's brief.

The area docs (step 29) are measured on the two pipeline cases that run the locator and designer, `add-feature-delegates-not-coding` and `fix-bug-failing-test-first`, two runs each, split with `eval_cost.py`. "Before" ran on `c04fab7`, before the fixture had a `CLAUDE.md` or `docs/architecture/tally.md`, on 2026-11-26 (Claude Code 2.1.329, WSL, `-j 1`, Sonnet judge; 4 of 4 runs passed, $4.16 in all). "After" runs the same commands on the step's commit, with the same Claude Code version, model and `-j`.

| Case | Agent | Before, run 1 | Before, run 2 | Before, mean | After, run 1 | After, run 2 | After, mean |
|---|---|---|---|---|---|---|---|
| `add-feature-delegates-not-coding` | designer | $0.1196 | $0.0980 | $0.1088 | $0.1818 | $0.1517 | $0.1668 |
| `add-feature-delegates-not-coding` | locator | not called | $0.0028 | $0.0028 (one call) | not called | $0.0032 | $0.0032 (one call) |
| `fix-bug-failing-test-first` | designer | $0.1499 | $0.1419 | $0.1459 | $0.1476 | $0.2003 | $0.1740 |
| `fix-bug-failing-test-first` | locator | $0.0035 | $0.0038 | $0.0037 | $0.0031 | $0.0033 | $0.0032 |

There was no saving. The designer cost more with the area docs on both cases (mean up 53% on `add-feature`, 19% on `fix-bug`), the locator's change was under a tenth of a cent, and the two cases together went from $4.16 to $4.81 (one `add-feature` run after also called the reviewer twice). With two runs per case and a two-file fixture, where a doc has little to save, this does not show what the docs do on a larger project.

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
| 2026-11-10 | trigger (31 cases, 3 runs each), Sonnet, WSL, Claude Code 2.1.308; step 39 | 23 of 31 pass. 0 of 3: `add-feature-1/2/3-fires` and `fix-bug-1-fires` (they pass on the default model, 1 run each: Sonnet answers without calling the skill) and `review-ui-1/2/3/7-fires` (they fail on the default model too: the skill's front matter did not parse, so it was not loaded; fixed in step 47). Every near miss passes, and all of `manage-project` and `release` | $5.10, plus $1.19 on default-model and Sonnet reruns |
| 2026-11-11 | trigger (37 cases, 1 run each), default model, WSL, Claude Code 2.1.308; step 12 release gate for 0.3.0 | 37 pass, including all of `manage-project` and `next-step` and `review-ui-1/2/3/7-fires` | $5.83 |
| 2026-11-15 | behaviour (45 cases, 1 run each, `-j 1`, Sonnet judge), default model, WSL, Claude Code 2.1.308; step 12 release gate for 0.3.0, on `bdc6db8` | 39 pass. 6 failed their first run and have no recorded pass: `add-feature-parts-run-in-order` (0.67, `part-1-sonnet`: Agent called 0x; the same score in all 4 runs), `add-feature-ui-change-covers-states-and-inputs` (0.75, `states-and-inputs`: judge FAIL x3, as on 11-12), `add-feature-new-ui-gets-build-and-motion` (0.75, `floor-in-report`: judge FAIL x3), `next-step-takes-the-next-step-and-claims-it` (0.83, `row-in-progress`: pattern not found), `release-never-signs` (0.83, `no-gate-yet`: Bash called 1x), `release-waits-for-the-version` (0.75, `no-commit`: Bash called 1x; failed 3 times on 3 graders). Runs from 11-11 and 11-12 that hit the session limit or ran while the working tree changed are not counted | $26.34 on the 14 invocations on `bdc6db8` (two on 11-12, twelve on 11-15); about $36 more on the earlier ones |
| 2026-11-15 | trigger, `review-ui-1/2/3/7-fires` (3 runs each), Sonnet, WSL, Claude Code 2.1.308; step 4 of the gate, step 47's reruns | 12 of 12 pass (3 of 3 each) | $2.10, plus $0.09 on a run the session limit cut |
| 2026-11-15 | model check and cost split of `add-feature-board-moves-one-agent` (1 run, `--keep-temp`, WSL) | 0 mismatches against the run project's board (designer Sonnet, implementer Sonnet, reviewer Opus); against the repo's own board the designer shows a mismatch, because the case moves it to Sonnet. The cost split: main 69.1%, reviewer 14.7%, implementer 10.1%, designer 6.1%. No case in the gate passes an implementer `model: "opus"`, so step 43's Sonnet-for-Opus mismatch is not re-measured | $0.77 |
| 2026-11-15 | behaviour, `next-step-takes-the-next-step-and-claims-it` (3 runs, Sonnet judge, `--keep-temp`), default model, WSL, Claude Code 2.1.308; step 51, on `eb350f5` | 3 of 3 pass, `row-in-progress` included (each run wrote `\| 2 Median \| in progress (2026-10-22 10:00) \|`). The failed run of 11-15 (`2026-11-15T03-44-43-776Z`, 0.83) cannot be explained: its workspace was deleted without `--keep-temp`, so no trace is left; grader and skill unchanged | $1.35 |
| 2026-11-18 | trigger (37 cases, 1 run each), default model, WSL, Claude Code 2.1.308; step 12 release gate for 0.3.0, on `d9c1207` | 37 pass, including all of `manage-project`, `next-step` and `review-ui` | $5.93 |
| 2026-11-22 | behaviour (48 cases, `-j 1`, Sonnet judge, `--keep-temp`), default model, WSL, Claude Code 2.1.329; step 12 release gate for 0.3.0, run one suite per command on `789f7e8` to `4228cde` (each case recorded on the HEAD it last ran on) | 45 of 48 pass: all of `fix-bug` (7), `release` (8), `next-step` (6) and `review-ui` (4), `add-feature` 12 of 13 and `manage-project` 8 of 10. **Known failures, accepted for 0.3.0:** `manage-project-diagnose-finds-a-skipped-review` (`report` judge fails: findings cite a bare line number or carry no confidence), `manage-project-vague-step-gets-a-cold-read` (`ranked-questions` judge fails: the questions come back unsorted) and `add-feature-ui-change-covers-states-and-inputs` (`states-and-inputs` judge fails: the design names an error state and the focus ring but not the other states or the inputs). Follow-ups: `release-later.md` steps 78, 79 and 81. Trigger stays at 37 of 37 (row above) | about $28 on the recorded runs, about $121 on the gate since 11-18 |
| 2026-11-26 | behaviour, `add-feature-delegates-not-coding` and `fix-bug-failing-test-first` (2 runs each, `-j 1`, Sonnet judge), default model, WSL, Claude Code 2.1.329; step 29's "before" runs, on `c04fab7` | 4 of 4 pass; the locator and designer costs are in the area-docs table above | $4.16 |
| 2026-11-26 | behaviour, the same two cases with the same settings; step 29's "after" runs, on `f1004c8` | 4 of 4 pass; the costs are in the area-docs table above | $4.81 |
| 2026-11-28 | behaviour (54 cases: `run-evals-*`, `add-feature-*`, `fix-bug-*`, `manage-project-*`, `next-step-*`, `release-*`, `run-plan-*`, `setup-*`; 1 run each, -j 1, sonnet judge), default model, WSL, Claude Code 2.1.329; step 91, on `24b6432` | 8 pass (`add-feature` board-moves-one-agent, claims-step-first, claims-step-first-local-plans, delegates-not-coding, keeps-to-files-line, model-line-moves-one-agent, new-ui-gets-build-and-motion, parts-run-in-order); skipped `add-feature-prompt-claims-the-runner-flag` (run 1 has an error: the 5-hour usage limit cut it); rerun not run: `run-evals-runs-within-the-budget` (run 1 scored 0.5); not run (usage limit): the other 44 cases | $9.81 |

## Where it came from

This is RYOS's `.claude/` setup with the RYOS-specific parts moved out into the profile. RYOS keeps its own copies (`add-ryos-feature`, `fix-ryos-bug`, `release-ryos`, `ryos-secretary`, the `ryos-*` agents and its hooks). Until RYOS moves over, keep devflow disabled in RYOS, or simply don't give RYOS a `.claude/devflow.json`.
