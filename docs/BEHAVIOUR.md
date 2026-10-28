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
| **CK-01** A commit that changes a version file fails unless it is titled `Release candidate X.Y.Z-rcN` or `Release X.Y.Z`; a commit with either title fails unless every listed version file says that version (`X.Y.Z` in numbers-only files), whether or not the commit changed it. | CI | `tests/test_checks.py::TestVersionCheck` |
| **CK-02** New Python comment lines in the listed folders fail; moved comments pass. | CI | `tests/test_checks.py::TestCommentCheck` |

## 4. Process-escape review

| Behaviour | Surfaces | Guarded by |
| --- | --- | --- |
| **PE-01** `tools/session_extract.py` finds the project's session folder, takes the most recent sessions without the current one, and writes one text file each with thinking dropped. | SK | `tests/test_session_extract.py` |
| **PE-02** The secretary's review reports when it finds no sessions, and stops. | SK | `eval::secretary/session-review-finds-no-sessions` |

## 5. Workflow skills

| Behaviour | Surfaces | Guarded by |
| --- | --- | --- |
| **WF-01** `add-feature` delegates every phase to an agent and doesn't code itself. | SK | `eval::add-feature/delegates-not-coding` |
| **WF-02** A coding session claims its plan step first, and refuses a step another tab has claimed. | SK | `eval::add-feature/claims-step-first`, `eval::add-feature/refuses-claimed-step`, `eval::fix-bug/claims-step-first`, `eval::fix-bug/refuses-claimed-step` |
| **WF-03** A red CI run on HEAD comes first; a flaky run's fix becomes the next step. | SK | `eval::add-feature/red-ci-comes-first`, `eval::fix-bug/red-ci-triage`, `eval::fix-bug/flaky-rerun-then-next-step`, `eval::release/red-ci-stops-the-candidate`, `eval::secretary/flaky-fix-goes-first` |
| **WF-04** A step with a Files line edits only those files. | SK | `eval::add-feature/keeps-to-files-line` |
| **WF-05** A session stops at a `**Gate:**`, and at a design that conflicts with a check. | SK | `eval::add-feature/stops-at-gate`, `eval::add-feature/stops-on-conflicting-check` |
| **WF-06** After two fix rounds still red, the session stops and reports "Still red". | SK | **untested** |
| **WF-07** `fix-bug` writes a failing test first and records an escape when the bug got past a release. | SK | `eval::fix-bug/failing-test-first`, `eval::fix-bug/records-the-escape` |
| **WF-08** `release` waits for the maintainer's version, stops on a failed gate, never signs, and won't publish without a matching stamp. | SK | `eval::release/waits-for-the-version`, `eval::release/stops-on-failed-gate`, `eval::release/never-signs`, `eval::release/no-stamp-blocks-publish`, `eval::release/stale-stamp-blocks-publish` |
| **WF-09** The secretary never edits code, never pushes, never picks the version, never claims "done" without evidence, and gives every new step a Files line. | SK | `eval::secretary/never-edits-code`, `eval::secretary/never-pushes`, `eval::secretary/version-is-the-maintainers`, `eval::secretary/no-unbacked-done`, `eval::secretary/new-step-has-a-files-line` |
| **WF-10** Each workflow skill fires on its own prompts and not on the other three's. | SK | `eval::trigger/*` |

## 6. Setup and templates

| Behaviour | Surfaces | Guarded by |
| --- | --- | --- |
| **TP-01** `session_start.py` reads the Order and Status of a plan written from `templates/plan.md`. | TP SS | `tests/test_session_start.py::TestPlanReading` (inferred, please check it uses the template's shape) |
| **TP-02** Every heading a skill cites exists in `templates/devflow.md`. | TP SK | **untested** |
| **TP-03** `/devflow:setup` writes nothing before the maintainer has seen the drafts. | SK | **untested** |

## 7. UI review

| Behaviour | Surfaces | Guarded by |
| --- | --- | --- |
| **UI-01** `review-web-ui` measures the page in headless Chrome at phone and desktop width and returns one prioritized report; it never edits code. | SK | **untested** |
| **UI-02** Style choices listed in `.claude/ui-review.json` `allow` are not raised. | SK | **untested** |

## Escapes

Every bug found after a release gets one line here, in the fix's commit, and that commit adds the check named: "#NN (vX.Y.Z): should have been caught by <check>; added <test / map entry / release-gate case>".

- dc45cfd (v0.2.0): `.claude-plugin/marketplace.json` was left at 0.1.0. Should have been caught by CK-01 (`tools/devflow_checks.py version`); added the release cases in `tests/test_checks.py::TestVersionCheck` (a version file left behind, no version change, a missing file, a pattern that doesn't match).

## Harness escapes

A process rule broken by a session (not a bug in the product) gets one line here: what happened, and the hook case or permission rule that now stops it. A session that breaks a process rule adds, in the same change, the guard rule (`.claude/devflow.json`) or `deny` / `ask` rule that would have stopped it; a new `deny` or `ask` rule needs the maintainer's approval.

---

## Untested: backlog

- **WF-06** two fix rounds, then "Still red": needs a fixture that fails only during implementation (see `README.md`, Skill evals, Known gap).
- **TP-02** profile headings: a unit test that greps every `**<Heading>**` the skills cite against `templates/devflow.md`.
- **TP-03** setup writes nothing before approval: an eval case.
- **UI-01**, **UI-02** `review-web-ui`: no evals yet (planned in `docs/plans/ui.md` step 7).
