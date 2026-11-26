# CI checks

`tools/devflow_checks.py` turns process rules into CI failures: the version changes only in a release commit, no new Python comments, no AI attribution where the project turned it off, every area-doc anchor names a real symbol, and a change to a documented area updates its doc or says why not. The same file runs in devflow's own CI and, copied by `setup`, in each consumer project's. Read this before adding a check or changing what one reads; adding one touches the tool, its config key, two CI files, setup and the wiring tests.

## Flow

1. **Arguments.** [`main`](../../tools/devflow_checks.py) takes the check's name, `--base`, `--head` and `--repo`, plus doc names for `anchors` only.
2. **Config.** Every check but `anchors` reads `.claude/devflow.json` with [`load_config`](../../tools/devflow_checks.py) and turns it into one [`Checks`](../../tools/devflow_checks.py) with [`checks_from`](../../tools/devflow_checks.py): `checks.version_files`, `checks.no_new_python_comments`, `checks.docs_routing`, `attribution` and `main_branch`. A key that is missing or of the wrong type turns its check off rather than failing it.
3. **The commit range.** [`commit_range`](../../tools/devflow_checks.py) turns `--base` into the commit to start after, falling back to the merge base with `origin/<main_branch>` when `--base` is empty, all zeros or unknown (a new branch's first push); [`commits_in`](../../tools/devflow_checks.py) lists the commits after it.
4. **The checks.**
   - [`version_problems_in`](../../tools/devflow_checks.py), per commit, with [`version_changes`](../../tools/devflow_checks.py) reading each configured file at the commit and its first parent;
   - [`comment_problems_in`](../../tools/devflow_checks.py), over the whole range, tokenizing old and new files with [`comment_tokens`](../../tools/devflow_checks.py) so a moved comment is not new;
   - [`attribution_problems_in`](../../tools/devflow_checks.py), per commit message;
   - [`docs_problems_in`](../../tools/devflow_checks.py), per commit: it reads the routing table at that commit with [`routes_in`](../../tools/devflow_checks.py) and the commit's paths with [`_changed_in`](../../tools/devflow_checks.py);
   - [`anchor_problems`](../../tools/devflow_checks.py), over the working tree's `docs/architecture/*.md`, with [`_symbol_problem`](../../tools/devflow_checks.py) for each code-span link and [`_line_anchor_problems`](../../tools/devflow_checks.py) for the rest of the line.
5. **Output.** One line per problem, each ending in a parenthesised rule reference (the file and section that states the rule), then exit 1; or `<check>: ok (…)` and exit 0. A git or config error prints `devflow_checks <check>: <error>` and exits 1.

## Invariants

- **Standard library only, one file.** `setup` copies this file alone into projects with no environment, and CI runs it as `uv run --no-project python tools/devflow_checks.py`.
- **Off by default.** A project that has not configured a check passes it. Only `anchors` runs without a config, and it passes when there is no `docs/architecture/`.
- **Per-commit checks judge each commit alone.** A version bump, an attribution line or a missing doc update in one commit is not excused by another commit in the same push; the message that answers for a change is that commit's own.
- **Every problem names its rule.** The message ends with where the rule is written, so the person who hits it in CI can read why.

## Recipe

Adding a check:

1. Add the name to `main`'s choices, a `*_problems_in` function, and, when it is configured, a field on [`Checks`](../../tools/devflow_checks.py) read in [`checks_from`](../../tools/devflow_checks.py) with a default that turns it off.
2. Add the key to `templates/devflow.json` and devflow's own `.claude/devflow.json` (`TestRealPins` in `tests/test_model_check.py` requires `models` to follow `checks` in both).
3. Add a step to `templates/ci-devflow.yml` and `.github/workflows/test.yml`, and to the job's name in both.
4. In `skills/setup/SKILL.md`, extend the CI condition in §4 when the new check can be the only reason to copy the tool.
5. Test it in `tests/test_checks.py` on real throwaway repositories (the `GitRepo` helper), and add a wiring test that both CI files run it and both configs set it, as `TestAttributionWiring` and `TestDocsWiring` do.
6. Add its row to the CK rows of `docs/BEHAVIOUR.md`, and name it in `CLAUDE.md` (Commands and Architecture) and in the profile's **Where things live** row for the CI check.

## Gotchas

- **`--base` is often useless in CI.** On a new branch's first push `github.event.before` is all zeros, and after a force push it is a commit that no longer exists; [`commit_range`](../../tools/devflow_checks.py) falls back to the merge base with the main branch in both cases (`TestNewBranchPush`, `TestBranchWiring`).
- **The config may start with a byte-order mark** on Windows; [`load_config`](../../tools/devflow_checks.py) reads it as `utf-8-sig` (`TestConfigWithAByteOrderMark`).
- **`anchors` needs `parse_intermixed_args`.** Doc names come before or after the options, so `main` parses them intermixed and rejects names given to any other check.

## Flagged / unverified

- None.
