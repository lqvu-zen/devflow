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
| Skill | `/devflow:review-web-ui` | One evidence-based UI/UX review of a web page: measures it in headless Chrome, reads phone and desktop screenshots, drives the interactive states, audits WCAG 2.2 AA, and returns a prioritized report with file:line fixes. Read-only. Needs Node 22+ and Chrome, Edge or Chromium. Bundles MIT-licensed code from taste-skill under `skills/review-web-ui/vendor/`. |
| Agent | `devflow:locator` | Haiku, read-only. Quotes the code and the behaviour-map rows. |
| Agent | `devflow:designer` | Opus, high effort. A plan or a root cause, never code. |
| Agent | `devflow:implementer` | Sonnet. Implements and verifies, with at most two fix rounds. Never commits. |
| Agent | `devflow:reviewer` | Opus, high effort. Diff review, or a release review before publishing. |
| Agent | `devflow:planner` | Opus, high effort, read-only. Drafts release plans for the secretary. |
| Agent | `devflow:tester` | Sonnet, read-only. Uses a candidate the way a user would. |
| Hook | guard (PreToolUse) | Refuses writes to the project's real data, anything touching or reading secrets (shell, file tools, Read, Grep, Glob), maintainer-only scripts, and reverting the secretary's uncommitted edits. Asks before `gh release` writes and forced pushes. |
| Hook | session start | Shows the branch, uncommitted files, CI on HEAD, and the plan's next open step (skipping steps another tab has claimed). |
| Tool | `tools/devflow_checks.py` | A CI check. It fails a commit that changes the version unless the commit is titled `Release candidate X.Y.Z-rcN` or `Release X.Y.Z`, and fails new Python comment lines in the listed folders. |

## How a project plugs in

Facts about each project live in that project, in two files that `/devflow:setup` writes:

- **`.claude/devflow.md`** is the profile that every skill and agent reads. It has fixed headings: Project, Where things live, Architecture rules, Verify, Edit bounds, Escalate, See it working, Release, Try it, Standing rules. Briefs paste these sections word for word, so the agents work to this project's rules. See `templates/devflow.md`.
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

## Reviewing a web UI

`/devflow:review-web-ui` works without `/devflow:setup`, the profile or the config files. It needs Node 22+ and Chrome, Edge or Chromium.

1. Start the app's dev server, or have a built `.html` file ready.
2. Run `/devflow:review-web-ui` and say what to review, for example `review the pricing page on mobile`. By default it reviews the whole page at 375 px and 1440 px.
3. It measures the page in headless Chrome, reads the screenshots, tries the interactive states, and answers in chat with a prioritized report (P0 to P3, file:line, fix, effort). It never edits code.

Optional: put `.claude/ui-review.json` in the project to set the server URL, pages, widths, output folder, and the style choices it should not flag (`allow`). The format is in `skills/review-web-ui/SKILL.md` under Config.

## Requirements

- `uv` on `PATH`. The hooks run as `uv run --no-project python …`, using only the standard library.
- Node 22+ and Chrome, Edge or Chromium, only for `/devflow:review-web-ui`.
- `git`. `gh`, logged in, for the CI line, issues and releases.
- The hooks are run by `bash`. On Windows, that's the Git Bash that Claude Code uses.

## Tests

```
python -m unittest discover -s tests
```

`tests/test_guard.py` runs the RYOS guard's test cases against an RYOS-shaped config to show the generic guard behaves the same, and adds a Linux-style project and a minimal config. `tests/test_session_start.py` and `tests/test_checks.py` cover the other hook and the CI check; the CI-check tests use real throwaway git repositories.

## Where it came from

This is RYOS's `.claude/` setup with the RYOS-specific parts moved out into the profile. RYOS keeps its own copies (`add-ryos-feature`, `fix-ryos-bug`, `release-ryos`, `ryos-secretary`, the `ryos-*` agents and its hooks). Until RYOS moves over, keep devflow disabled in RYOS, or simply don't give RYOS a `.claude/devflow.json`.
