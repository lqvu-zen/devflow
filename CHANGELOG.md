# Changelog

## Unreleased

- Evals: `tools/eval_select.py select` lists the eval cases a change can reach since each case's last recorded pass (`evals/depends.json`, `evals/passes.json`) and prints one `claude plugin eval` command per `--case` glob; `record` keeps a pass from a result file once its inputs are committed; `tests/test_evals.py` compiles every grader pattern before a paid run.
- Evals: `non-ui-change-gets-no-ui-section` is merged into `delegates-not-coding` (same prompt) and `ui-change-covers-states-and-inputs` now stops after the design, so it no longer runs the implementer; `tools/eval_select.py record` prints `skipped <case>: <reason>` for each case it did not keep and refuses a result file with a bad `startedAt`, `find_cases` names the `prompt.md` it cannot read, the grader check also reports possessive quantifiers and conditionals, and the depends check catches bare `build.md`, `motion.md` and `core.md` mentions (`fix-bug` now depends on `motion.md`). The release gate runs the cases `select --release` lists.
- Plans: a coding session changes a plan only in its own Status row and its step's Tried line, in place with the Edit tool, never by rewriting the file with Write, a script, `sed` or a regex. Where the plan is gitignored it saves the edit and commits nothing, and `release` B7 archives a finished plan with `mv` instead of committing it.
- CI check: a git error while reading a file (a missing or corrupt object, for example) now stops the check with git's message, instead of the version check reporting "has no <path>" or the comment check skipping the file.
- Release: when every version file is numbers-only, promotion commits `Release X.Y.Z` with `git commit --allow-empty` (the candidate already set the versions), B1 runs after the version commit (before, it could not see an uncommitted edit), and B1 and the release review accept the empty promotion diff; before, B2 failed with "nothing to commit".
- Release: open plan steps (those the release step's **Needs** line names whose Status row is not `done` or `not needed`) stop publishing the candidate (A5) and the release (B5), and the report names them; they no longer stop a phase the maintainer named, so "carry on from the release gate" runs the gate. Before, a session could stop on open steps without running the gate, or publish with steps still open. Evals: `release-gate-runs-with-open-steps`; `release-stale-stamp-blocks-publish` marks the plan steps done so it can still publish.
- UI changes: for new UI the add-feature implementer checks the finished UI against `build.md` §5 and reports each item met, not met or not checked; whenever the UI rules apply, the add-feature and fix-bug reviewers also get `motion.md` and apply its §5 when the diff moves something, a broken (M) rule a blocker and a (T) one a suggestion.

## 0.2.2

- Design system: the profile has a **Design system** heading and `/devflow:setup` copies `templates/DESIGN.md` (Google's DESIGN.md format plus Platforms, States, Inputs and Motion) to `docs/DESIGN.md`, filled from existing tokens where there are any.
- UI changes: for a change that touches UI, the designer adds a UI section (states, sizes, worst-case data, inputs, accessibility), the reviewer checks the diff against the design system, and the tester screenshots each state. New UI also follows `build.md` and `motion.md`.
- Review references are split into `core.md`, `web.md`, `app.md`, `game.md` and a dated `tells.md` of generated-look tells.
- Evals: a UI fixture, 4 `review-ui` and 2 `add-feature` behaviour cases and 7 `review-ui` trigger cases. `review-ui`'s description is now imperative, because it never fired before.
- UI review: `/devflow:review-web-ui` is now `/devflow:review-ui`, with no alias; a project skill that wraps it must use the new name. It also reviews desktop and mobile app screens and game UI from screenshots and source, picks its path from the profile's **Design system**, and reads **See it working**. Its bundled taste-skill inspector is updated from `c924fad` to `12af471`: page-frame checks, and an app-screen mode with `--app`.

## 0.2.1

- CI check: a release commit fails if it leaves any listed version file at another version (0.2.0 shipped with `marketplace.json` at 0.1.0).
- Marketplace: `marketplace.json` now carries the plugin's release version; 0.2.0 left it at 0.1.0.
- Evals: `release-stops-on-failed-gate` marks the plan steps done so it reaches the gate, and its report grader no longer requires an exact phrase.

## 0.2.0

- Guard: the Read, Grep and Glob tools can no longer open files in the configured secret folders or with a secret extension.
- Guard: globs that match a secret folder or the real data folder are refused (`cat ~/.secr*/token`, `rm $APPDATA/My*`).
- Guard: a write command whose command substitution may build a path into the real data folder is refused.
- Guard: when the guard fails (an exception, a broken `devflow.json`, `uv` missing, a guard that cannot start) the call now asks instead of passing silently.
- CI: the repository runs its own tests on Linux and Windows.
- README: states what the guard does and does not protect against.
- A flaky CI run that goes green on rerun makes the flaky test's fix the next plan step; the secretary puts it first in Order, and a release says so when it publishes on a rerun-green commit.
- Plans: each step has a Files line, and the plan template has a "Parallel lanes and merging" section; the coding skills keep to the Files line.
- Prompt book: `templates/PROMPTS.md` has a paste-ready prompt for every kind of session, and setup copies it to `docs/PROMPTS.md`.
- Guard: where `guard.release_stamp` is set, publishing a release is denied unless the stamp names the current HEAD and the current hash of the bound file.
- Secretary: reviews recent sessions for process rules the agents broke and proposes Harness escapes lines for the maintainer to approve.
- Evals: `evals/` holds behaviour and trigger evals for the four workflow skills, run with `claude plugin eval`.

## 0.1.0

- First release: the RYOS working method as a plugin.
