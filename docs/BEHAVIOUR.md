# devflow behaviour map

`CLAUDE.md` and `.claude/devflow.md` say how devflow is built. This file says **what must keep working, and everywhere it shows up.** Most behaviours appear in several places at once. A change that reaches one place breaks the others unseen.

Each entry is one line the user would recognise, **every surface** it appears on, and the test that guards it, or **untested**.

## How to use it

- **Before you change an area, read its entries.** Check each surface listed, not only the one you are working on.
- **A fix adds or updates its entry and its test.** Put the issue number in the behaviour text, e.g. "(#27)".
- **A feature adds its entries** in the same change, with the surfaces it reaches.
- **Test names are exact.** Format: `<test file>::<Class>::<test>`. A bare class name means every test in that class applies. `eval::<folder>/<case>` is a case under `evals/cases/`, run with `claude plugin eval`, not in CI.
- **A check usually covers one surface.** Where a test covers only some of the surfaces, the Guarded-by cell says which, e.g. "(Bash only)". The surfaces it does not name are unguarded, and the last section lists them.

## Surfaces

| Code | Surface |
| --- | --- |
| **SH** | the shell tools (Bash, PowerShell, with cmd forms inside them) |
| **FT** | the file tools (Write, Edit, MultiEdit, NotebookEdit, Read, Grep, Glob) |
| **SS** | the session-start summary |
| **CI** | `tools/devflow_checks.py` in a project's CI |
| **SK** | a skill run in a session (`/devflow:*`) |
| **TP** | the templates `/devflow:setup` copies into a project |
| **EV** | the eval tools (`tools/eval_select.py`, `tools/eval_cost.py`, `tools/model_check.py`, `evals/depends.json`, `evals/passes.json`) |

## 1. Guard

| Behaviour | Surfaces | Guarded by |
| --- | --- | --- |
| **GD-01** Writes into the project's real data are refused, however the path is reached (variables, `~`, `cd`, wrappers, heredocs, globs, command substitutions). | SH FT | `tests/test_guard.py::TestGuardRefuses`, `tests/test_guard.py::TestAnotherProject::test_its_real_data` |
| **GD-02** Reading, copying out of and naming real data in a message are allowed. | SH FT | `tests/test_guard.py::TestGuardAllows` |
| **GD-03** Anything that touches or reads a secret folder or a secret extension is refused. | SH FT | `tests/test_guard.py::TestGuardRefuses::test_the_secrets`, `tests/test_guard.py::TestGuardRefuses::test_reading_a_secret_with_the_read_tools`, `tests/test_guard.py::TestGuardRefuses::test_a_glob_that_reaches_real_data_or_a_secret` |
| **GD-04** Starting the product is refused unless the isolating variables point at scratch in the same command; harmless arguments and self-guarding harnesses pass. | SH | `tests/test_guard.py::TestGuardRefuses::test_starting_the_app_without_a_throwaway_data_folder`, `tests/test_guard.py::TestGuardAllows::test_the_app_with_a_throwaway_data_folder`, `tests/test_guard.py::TestGuardAllows::test_harmless_app_commands`, `tests/test_guard.py::TestGuardAllows::test_self_guarding_harnesses` |
| **GD-05** Maintainer-only scripts are refused. | SH | `tests/test_guard.py::TestGuardRefuses::test_maintainer_only_scripts` |
| **GD-06** Git operations that would discard uncommitted secretary edits (status file, plans) are refused; other git work is allowed. | SH | `tests/test_guard.py::TestGuardRefuses::test_reverting_secretary_files`, `tests/test_guard.py::TestGuardRefuses::test_whole_tree_discards_while_secretary_edits_wait`, `tests/test_guard.py::TestGuardAllows::test_git_that_keeps_secretary_edits` |
| **GD-07** `gh release` writes and forced pushes ask the maintainer; release reads don't. | SH | `tests/test_guard.py::TestGuardAsks` |
| **GD-08** With `guard.release_stamp` set, publishing is refused unless the stamp names the current HEAD and the bound file's hash; without the key nothing changes. | SH FT | `tests/test_guard.py::TestReleaseStamp` |
| **GD-09** Every command a devflow skill tells a session to run is allowed. | SH | `tests/test_guard.py::TestGuardSkillCommands` |
| **GD-10** A project without `.claude/devflow.json` is left alone. | SH FT | `tests/test_guard.py::TestGuardHookCommand::test_a_project_without_a_config_is_left_alone` |
| **GD-11** A guard that crashes, can't read its config or can't start asks ("not checked") instead of passing silently; a refusal exits 2 with its reason. | SH FT | `tests/test_guard.py::TestGuardMain`, `tests/test_guard.py::TestGuardHookCommand` |
| **GD-12** A minimal config still keeps secrets and secretary edits. | SH FT | `tests/test_guard.py::TestMinimalConfig` |

## 2. Session start

| Behaviour | Surfaces | Guarded by |
| --- | --- | --- |
| **SS-01** Shows the current plan's next open step in Order, skipping steps another tab has claimed, and why a stopped step stopped. | SS | `tests/test_session_start.py::TestPlanReading` |
| **SS-02** Shows the branch, uncommitted files and CI on HEAD. | SS | `tests/test_session_start.py::TestGitAndCi` |
| **SS-03** All its subprocess calls share one deadline; it prints nothing in a project without the config. | SS | `tests/test_session_start.py::TestMain` |

## 3. CI check

| Behaviour | Surfaces | Guarded by |
| --- | --- | --- |
| **CK-01** A commit that changes a version file fails unless it is titled `Release candidate X.Y.Z-rcN` or `Release X.Y.Z`; a commit with either title fails unless every listed version file says that version (`X.Y.Z` in numbers-only files), whether or not the commit changed it; a git error reading a version file stops the check with git's message, not "has no". | CI | `tests/test_checks.py::TestVersionCheck` (git errors: `tests/test_checks.py::TestVersionCheck::test_a_git_failure_is_reported_with_its_cause`, root commit: `tests/test_checks.py::TestVersionCheck::test_the_root_commit_is_judged_without_a_parent`) |
| **CK-02** New Python comment lines in the listed folders fail; moved comments pass; a git error reading a changed file stops the check with git's message instead of skipping the file. | CI | `tests/test_checks.py::TestCommentCheck` (git errors: `tests/test_checks.py::TestCommentCheck::test_a_git_failure_is_reported_not_skipped`) |

## 4. Process-escape review

| Behaviour | Surfaces | Guarded by |
| --- | --- | --- |
| **PE-01** `tools/session_extract.py` finds the project's session folder, takes the most recent sessions without the current one, and writes one text file each with thinking dropped and each SessionStart hook's output kept as one `H` line (so the "CI on HEAD" line reaches the review); a session with no user or assistant turns gives no file. | SK | `tests/test_session_extract.py` (H line: `tests/test_session_extract.py::HookOutput`) |
| **PE-02** The secretary's review reports when it finds no sessions, and stops. | SK | `eval::secretary/session-review-finds-no-sessions` |

## 5. Workflow skills

| Behaviour | Surfaces | Guarded by |
| --- | --- | --- |
| **WF-01** `add-feature` delegates every phase to an agent and doesn't code itself, and no agent brief carries the UI-section markers (`core.md`, `UI change.`) for a change that is not UI. | SK | `eval::add-feature/delegates-not-coding` |
| **WF-02** A coding session claims its plan step first (committing the row alone, by path, where the plan is committed), and refuses a step another tab has claimed. | SK | `eval::add-feature/claims-step-first`, `eval::add-feature/refuses-claimed-step`, `eval::fix-bug/claims-step-first`, `eval::fix-bug/refuses-claimed-step` |
| **WF-03** A red CI run on HEAD comes first; a flaky run's fix becomes the next step. | SK | `eval::add-feature/red-ci-comes-first`, `eval::fix-bug/red-ci-triage`, `eval::fix-bug/flaky-rerun-then-next-step`, `eval::release/red-ci-stops-the-candidate`, `eval::secretary/flaky-fix-goes-first` |
| **WF-04** A step with a Files line edits only those files. | SK | `eval::add-feature/keeps-to-files-line` |
| **WF-05** A session stops at a `**Gate:**`, and at a design that conflicts with a check. | SK | `eval::add-feature/stops-at-gate`, `eval::add-feature/stops-on-conflicting-check` |
| **WF-06** After two fix rounds still red, the session stops and reports "Still red". | SK | **untested** |
| **WF-07** `fix-bug` writes a failing test first and records an escape when the bug got past a release. | SK | `eval::fix-bug/failing-test-first`, `eval::fix-bug/records-the-escape` |
| **WF-08** `release` waits for the maintainer's version, stops on a failed gate, runs a gate the maintainer named even while plan steps are open and then publishes nothing and names the open steps, never signs, won't publish without a matching stamp, and promotes a candidate whose version files are all numbers-only with an empty `Release X.Y.Z` commit (`--allow-empty`) instead of stopping. | SK | `eval::release/waits-for-the-version`, `eval::release/stops-on-failed-gate`, `eval::release/gate-runs-with-open-steps`, `eval::release/never-signs`, `eval::release/no-stamp-blocks-publish`, `eval::release/stale-stamp-blocks-publish`, `eval::release/promotes-numbers-only` |
| **WF-09** The secretary never edits code, never pushes, never picks the version, never claims "done" without evidence, and gives every new step a Files line. | SK | `eval::secretary/never-edits-code`, `eval::secretary/never-pushes`, `eval::secretary/version-is-the-maintainers`, `eval::secretary/no-unbacked-done`, `eval::secretary/new-step-has-a-files-line` |
| **WF-10** Each workflow skill fires on its own prompts and not on the other three's. | SK | `eval::trigger/*` |
| **WF-11** A coding session edits a plan only in its own Status row and its step's Tried line, in place with the Edit tool, never with Write, a script, `sed` or a regex; where the plan is gitignored it saves the edit and commits nothing (the 2026-11-03 plan wipe). | SK | `eval::add-feature/claims-step-first-local-plans` |
| **WF-12** Every skill's text after its front matter stays under 19,000 characters, so Claude Code's cut of a skill re-attached after compaction (at 20,000 characters, from the end) never reaches it; `add-feature` and `fix-bug` open with the stop rules (two fix rounds, one more round after BLOCKERS) as their first section, in the same words; `release` B4 stops after the same review-round limit, in the same words. | SK | `tests/test_skills.py::TestSkillSize`, `tests/test_skills.py::TestStopRules` (the wording and its place; whether a session stops is WF-06, untested), `tests/test_skills.py::TestStopRules::test_release_review_stops_after_the_same_round_limit` |
| **WF-13** Every skill has front matter whose `name` is its folder's name (lowercase words joined by hyphens) and a description of 200 to 1,536 characters; no Markdown file in a skill's folder outside `vendor/` holds a `$ARGUMENTS` or `$N` token Claude Code would replace, a `cd` into the plugin folder, or a development file (`test-*.md`, a creation log); every text file in a skill's folder outside `vendor/` has CRLF endings in the working tree (a local check: a CI checkout is always CRLF). | SK | `tests/test_skills.py::TestFrontMatter`, `tests/test_skills.py::TestSkillFiles` |
| **WF-14** A skill's quoted citation of another skill's heading (`x`'s "H", `skills/x/SKILL.md`, "H", `x` ("H")) names a heading that skill has; the secretary's shared-rules list cites every add-feature heading that holds a shared rule. | SK | `tests/test_skills.py::TestCrossSkillCitations`, `tests/test_skills.py::TestSharedRules` |
| **WF-15** `tools/model_check.py` reports, per agent call in a session, the role, what the call passed, the model each reply ran on, the effort where recorded, and what was expected (the pin, or a `--model` line), marking every mismatch and naming what it could not read (no transcript, effort not recorded, unfinished, a general-purpose call's role); it refuses a Model line that moves the locator, reviewer or planner below its pin; `add-feature` and `fix-bug` run it at the end and the secretary's review reads it. | SK EV | `tests/test_model_check.py`, `eval::add-feature/model-line-moves-one-agent` |
| **WF-16** A plan step's `**Model:** <role>: <Model>, <effort>; <why>` line moves that one role's call, and no other, overriding **Escalate** for that step; without it every agent runs on its pin; the designer's effort is medium in `add-feature` and high in `fix-bug`'s diagnosis. | SK TP | `tests/test_skills.py::TestModelRules`, `eval::add-feature/model-line-moves-one-agent`, `eval::add-feature/delegates-not-coding` |

## 6. Setup and templates

| Behaviour | Surfaces | Guarded by |
| --- | --- | --- |
| **TP-01** `session_start.py` reads the Order and Status of a plan written from `templates/plan.md`. | TP SS | `tests/test_session_start.py::TestPlanReading` (inferred, please check it uses the template's shape) |
| **TP-02** Every profile heading a skill cites (bold on a line about the profile, in the by-exact-heading list, or as a section or heading) exists in `templates/devflow.md`, and setup's fixed list is the template's headings in order; every template heading is cited by some skill, so a heading no skill cites fails too. | TP SK | `tests/test_skills.py::TestProfileHeadings` |
| **TP-03** `/devflow:setup` writes nothing before the maintainer has seen the drafts. | SK | **untested** |

## 7. UI review

| Behaviour | Surfaces | Guarded by |
| --- | --- | --- |
| **UI-01** `review-ui` on a web page measures it in headless Chrome at phone and desktop width and returns one prioritized report (P0-P3, file:line, fix, effort); it never edits code. | SK | `eval::review-ui/web-finds-planted-issues` (the report format and locations; phone and desktop width and "never edits" are untested) |
| **UI-02** Style choices listed in `.claude/ui-review.json` `allow` are not raised. | SK | **untested** |
| **UI-03** `review-ui` takes one path per platform: the user's words, else the Design system's platforms, else the project's files, else it asks; web goes to the web path, desktop and mobile to the app path, game to the game path. | SK | `eval::review-ui/app-finds-small-target`, `eval::review-ui/game-finds-hud-and-focus` (routing from the user's words only; the fallback order is untested) |
| **UI-04** The app and game paths judge screenshots of each state at each size plus the UI source, never run the inspector, take screenshots only as See it working says or use the user's, and return the same report format. | SK | `eval::review-ui/app-finds-small-target`, `eval::review-ui/game-finds-hud-and-focus` (no-inspector is graded on the app path only; screenshots taken as See it working says and the report format are untested) |
| **UI-05** With a profile, `review-ui` reads Design system and See it working and does not raise a tell the design system names; without one it works as before. | SK | `eval::review-ui/design-system-choice-not-reported` (the design-system waiver only; reading See it working and the no-profile case are untested) |
| **UI-06** The add-feature and fix-bug designer and reviewer briefs name `skills/review-ui/references/core.md`, and that file exists. | SK | `tests/test_skill_references.py::TestUiBriefReferences`, `eval::add-feature/ui-change-covers-states-and-inputs` (stops after the design: the designer gets `core.md` and the design system, the report names the error state, two other states and two inputs, and no implementer runs) |
| **UI-07** When a change adds new UI, the add-feature designer brief also names `build.md` and `motion.md` beside `core.md`, and both files exist; neither contradicts `core.md` or the precedence rule (that half is a review judgment, untested). | SK | `tests/test_skill_references.py::TestUiBriefReferences`, `eval::add-feature/new-ui-gets-build-and-motion` (the designer brief names `build.md` and `motion.md`) |
| **UI-08** For new UI, the add-feature implementer brief names `build.md` and the implementer reports each §5 item met, not met or not checked; whenever the UI rules apply, the add-feature and fix-bug reviewer briefs name `motion.md` in the same words and reviewer item 7 applies its §5 when the diff moves something, an (M) rule broken a blocker and a (T) one a suggestion. | SK | `tests/test_skill_references.py::TestUiBriefReferences` (the wording), `eval::add-feature/new-ui-gets-build-and-motion` (implementer brief names `build.md`, reviewer brief names `motion.md`, the final report lists the §5 floor items), `eval::fix-bug/ui-bug-reviewer-gets-motion` (whether the agents apply §5 correctly is untested) |

## 8. Evals

| Behaviour | Surfaces | Guarded by |
| --- | --- | --- |
| **EV-01** Every grader's `input_match` and `pattern` compiles, with the flags the runner allows and none of the Python-only syntax JavaScript lacks (named groups with `?P`, atomic groups, possessive quantifiers, conditionals, `\A`, `\Z`, inline flags), before a paid run. | EV | `tests/test_evals.py::TestGraders` |
| **EV-02** `select` lists exactly the cases a change can reach since each case's last pass, by `evals/depends.json`: a case with no record or an unknown commit is listed; uncommitted, untracked and renamed files count; trigger cases are listed only when their skill's (or their near-miss target's) front matter changed, and all of them with `--release`; one command is printed per `--case` glob. | EV | `tests/test_evals.py::TestSelect` |
| **EV-03** `record` keeps a pass only when every run scored 1 with no error and no skipped paid grader, and refuses a case with uncommitted inputs. It prints `skipped <case>: <reason>` (no runs, a run's error, a skipped paid grader or a score below 1) for each case it did not keep, which leaves the exit code at 0, and refuses a result file whose `startedAt` is missing or not `YYYY-MM-DD`. | EV | `tests/test_evals.py::TestRecord` |
| **EV-04** `evals/depends.json` names every agent and plugin file each skill cites and every near miss, whether a `SKILL.md` names a review reference by path or only by bare name (`build.md`, `motion.md`, `core.md`); `evals/passes.json` names only cases on disk. | EV | `tests/test_evals.py::TestEvalFiles` |
| **EV-05** `tools/eval_cost.py` splits a recorded eval run's cost by agent from the run's session transcripts (`config/projects`). It shares each model's recorded cost across the main session and each subagent type by weighted tokens, counting each message id once, so the rows add up to the run's total. It counts calls per agent type. A run whose files are gone, or that recorded no cost, is named rather than dropped. `--root` finds workspaces moved elsewhere. | EV | `tests/test_eval_cost.py` |

## Escapes

Every bug found after a release gets one line here, in the fix's commit, and that commit adds the check named: "#NN (vX.Y.Z): should have been caught by <check>; added <test / map entry / release-gate case>".

- dc45cfd (v0.2.0): `.claude-plugin/marketplace.json` was left at 0.1.0; should have been caught by CK-01 (`tools/devflow_checks.py version`); added the release cases in `tests/test_checks.py::TestVersionCheck` (a version file left behind, no version change, a missing file, a pattern that doesn't match).
- 7de4103 (v0.2.1): a git failure reading a version file was reported as "has no <path>", and one reading a changed Python file was skipped, because `_show` treated every git error as a missing path; should have been caught by CK-01 and CK-02 (`tools/devflow_checks.py`); added `tests/test_checks.py::TestVersionCheck::test_a_git_failure_is_reported_with_its_cause` and `tests/test_checks.py::TestCommentCheck::test_a_git_failure_is_reported_not_skipped`.
- dc45cfd (v0.2.0): `release` B2 ran `git add <version files> && git commit -m "Release X.Y.Z"` in a project whose version files are all numbers-only, where the candidate had already set them to X.Y.Z, so it failed with "nothing to commit", and B1 and the reviewer's release-mode item 8 rejected the empty promotion diff (still in v0.2.1 and v0.2.2); should have been caught by WF-08, whose release evals stopped before promotion; added `eval::release/promotes-numbers-only`.
- b10ec79 (v0.1.0, still in v0.2.2): `release` B7's open-steps check used awk `$2` and `$3`, which Claude Code can replace with skill arguments, so the check could not read the plan's Status table (whether the substitution happened in a real release session is unconfirmed); should have been caught by WF-13; added `tests/test_skills.py::TestSkillFiles`.

## Harness escapes

A process rule broken by a session (not a bug in the product) gets one line here: what happened, and the hook case, permission rule or skill wording that now stops it. A session that breaks a process rule adds, in the same change, the guard rule (`.claude/devflow.json`), `deny` / `ask` rule or skill wording that would have stopped it; a new `deny` or `ask` rule needs the maintainer's approval.

- 2026-11-03 (`ui.md` step 7): a coding session set one Status row with a whole-file Python `re.sub(..., flags=re.S)` on `docs/plans/ui.md` and deleted everything from "Who does what" row 7 to the end; plans are gitignored, so git could not restore it. Now stopped by wording, not a hook (D2): "**Edit the plan one row at a time.**" in `skills/add-feature/SKILL.md` under "Before you start, and where you stop", in the same words in `fix-bug` (same heading), `release` (under "A. Release candidate") and the secretary's shared-rules list ("Process escapes: review recent sessions"); map entry WF-11.
- 2026-11-05 (137546f): the stop rules moved into `add-feature`'s "Stop rules" section, but the secretary's shared-rules list still cited only "Before you start, and where you stop", so a secretary brief could leave them out. Now stopped by `tests/test_skills.py::TestSharedRules` (WF-14).
- e7d0d64, 6954c80: five `review-ui` files (`SKILL.md` and `references/app.md`, `build.md`, `game.md`, `motion.md`) were written with LF endings and stayed LF in the working tree, against the repository's CRLF rule. Now stopped locally by `tests/test_skills.py::TestSkillFiles::test_every_skill_file_has_crlf_endings` (WF-13).
- 2026-11-09 (step 1's session review): the review reported about 12 sessions as skipping the CI check first, but each had seen "CI on HEAD" in the SessionStart hook's output, which `tools/session_extract.py` dropped with every `attachment` record. Now stopped by the extract's `H` line and the secretary's "Process escapes: review recent sessions" wording that the SessionStart `H` line counts as the CI check on HEAD (PE-01, `tests/test_session_extract.py::HookOutput`).

---

## Untested: backlog

- **WF-06** two fix rounds, then "Still red": needs a fixture that fails only during implementation (see `README.md`, Skill evals, Known gap).
- **TP-03** setup writes nothing before approval: an eval case.
- **UI-02** `allow` list in `.claude/ui-review.json`: no eval or test yet.
- **UI-01, UI-03, UI-04, UI-05** `review-ui`: phone and desktop width, never editing code, the platform fallback order, the game path's no-inspector, screenshots taken per See it working, the shared report format on the app and game paths, and running without a profile have no eval.
