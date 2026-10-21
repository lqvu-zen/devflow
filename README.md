# devflow

A Claude Code plugin that brings the RYOS working method to any project. A maintainer decides. Fresh agents with pinned models do the work, and hooks turn the process rules into checks.

## What's in it

| | Name | What it does |
|---|---|---|
| Skill | `/devflow:setup` | Adopts devflow in a project. It reads the codebase, drafts the profile and guard config, and starts the behaviour map, status file and plans. Nothing is written before the maintainer approves. |
| Skill | `/devflow:add-feature` | A feature or improvement: understand → locate (Haiku) → design (Opus) → implement and test (Sonnet) → review (Opus) → commit. |
| Skill | `/devflow:fix-bug` | The same pipeline for a bug: reproduce it, write a failing test, find the root cause and fix it. Adds an escape line when the bug got past a release. |
| Skill | `/devflow:release` | Ships through a release candidate: version → build → gate → pre-release → tester → the maintainer's checklist → release review → promotion. |
| Skill | `/devflow:secretary` | Keeps the status file and the decision log, triages issues, and turns decisions into plan steps with paste-ready prompts. |
| Agent | `devflow:locator` | Haiku, read-only. Quotes the code and the behaviour-map rows. |
| Agent | `devflow:designer` | Opus, high effort. A plan or a root cause, never code. |
| Agent | `devflow:implementer` | Sonnet. Implements and verifies, with at most two fix rounds. Never commits. |
| Agent | `devflow:reviewer` | Opus, high effort. Diff review, or a release review before publishing. |
| Agent | `devflow:planner` | Opus, high effort, read-only. Drafts release plans for the secretary. |
| Agent | `devflow:tester` | Sonnet, read-only. Uses a candidate the way a user would. |
| Hook | guard (PreToolUse) | Refuses writes to the project's real data, anything touching secrets, maintainer-only scripts, and reverting the secretary's uncommitted edits. Asks before `gh release` writes and forced pushes. |
| Hook | session start | Shows the branch, uncommitted files, CI on HEAD, and the plan's next open step (skipping steps another tab has claimed). |
| Tool | `tools/devflow_checks.py` | A CI check. It fails a commit that changes the version unless the commit is titled `Release candidate X.Y.Z-rcN` or `Release X.Y.Z`, and fails new Python comment lines in the listed folders. |

## How a project plugs in

Facts about each project live in that project, in two files that `/devflow:setup` writes:

- **`.claude/devflow.md`** is the profile that every skill and agent reads. It has fixed headings: Project, Where things live, Architecture rules, Verify, Edit bounds, Escalate, See it working, Release, Try it, Standing rules. Briefs paste these sections word for word, so the agents work to this project's rules. See `templates/devflow.md`.
- **`.claude/devflow.json`** configures the guard and the CI check: real data folders, secrets, maintainer-only scripts, how the product starts and which environment variables must point at a scratch folder, and the version files. See `templates/devflow.json`. **The hooks do nothing in a project without this file**, so installing the plugin for your user account is safe.

The method also expects `docs/BEHAVIOUR.md` (the behaviour map), `docs/STATUS.md` (the status file), `docs/plans/` and `docs/archive/`. The status file and plans folder can be moved in `devflow.json`.

## Install

The repository is its own marketplace. From a local clone:

```
/plugin marketplace add D:/Projects/devflow
/plugin install devflow@devflow
```

Once the repo is on GitHub, add it by name instead: `/plugin marketplace add <owner>/devflow`. To turn it off in one project, add `"enabledPlugins": {"devflow@devflow": false}` to that project's `.claude/settings.json`.

Then, in a project: `/devflow:setup`.

## Requirements

- `uv` on `PATH`. The hooks run as `uv run --no-project python …`, using only the standard library.
- `git`. `gh`, logged in, for the CI line, issues and releases.
- The hooks are run by `bash`. On Windows, that's the Git Bash that Claude Code uses.

## Tests

```
python -m unittest discover -s tests
```

`tests/test_guard.py` runs the RYOS guard's test cases against an RYOS-shaped config to show the generic guard behaves the same, and adds a Linux-style project and a minimal config. `tests/test_session_start.py` and `tests/test_checks.py` cover the other hook and the CI check; the CI-check tests use real throwaway git repositories.

## Where it came from

This is RYOS's `.claude/` setup with the RYOS-specific parts moved out into the profile. RYOS keeps its own copies (`add-ryos-feature`, `fix-ryos-bug`, `release-ryos`, `ryos-secretary`, the `ryos-*` agents and its hooks). Until RYOS moves over, keep devflow disabled in RYOS, or simply don't give RYOS a `.claude/devflow.json`.
