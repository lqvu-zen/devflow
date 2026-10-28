# Changelog

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
