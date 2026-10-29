# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`devflow` is a Claude Code plugin (and its own single-plugin marketplace, `.claude-plugin/marketplace.json`). It ships a working method: skills that orchestrate fresh subagents with pinned models, plus hooks and a CI tool that turn process rules into checks. The Python is standard library only; there is no build step and no dependencies. The one exception is the `review-ui` skill's web path, which ships Node scripts and needs Node 22+ and a Chrome-family browser.

## Commands

```
python -m unittest discover -s tests
python -m unittest tests.test_guard
python -m unittest tests.test_guard.<TestClass>.<test_name>
```

The hooks run in consumer projects as `uv run --no-project python …`. The CI check runs as `python tools/devflow_checks.py version|comments [--base SHA] [--head REF] [--repo PATH]`.

## Architecture

The plugin is mostly prompts and config; the only real code is three Python files.

- **Skills** (`skills/*/SKILL.md`): `setup`, `add-feature`, `fix-bug`, `release`, `secretary`, `review-ui`. The orchestrating session runs these and delegates every phase to an agent. `fix-bug` and `release` reuse the `add-feature` pipeline, so changes to shared rules (stop rules, claiming a plan step, gates, the briefs' verbatim-paste requirement) usually need to be mirrored across the skills. `review-ui` is standalone: it does not delegate to agents, reads **Design system** and **See it working** when the profile exists and works without it, and `skills/review-ui/vendor/` is third-party code to be updated only by re-copying from upstream.
- **Agents** (`agents/*.md`): `locator` (Haiku), `designer`, `reviewer`, `planner` (Opus, high effort), `implementer`, `tester` (Sonnet). Model and effort are pinned in each agent's frontmatter, so skills should not pass `model` or `effort` except to escalate.
- **Project profile contract**: skills never hardcode project facts. They read `.claude/devflow.md` in the consumer project by exact heading (Project, Where things live, Architecture rules, Verify, Edit bounds, Escalate, See it working, Design system, Release, Try it, Standing rules) and paste sections verbatim into agent briefs. Renaming a heading in `templates/devflow.md` breaks every skill that cites it.
- **Config contract**: `.claude/devflow.json` in the consumer project configures the guard and CI checks (schema example in `templates/devflow.json`). Without that file the hooks are no-ops: `hooks/hooks.json` gates each command on the file's existence.
- **`hooks/guard.py`** (PreToolUse on Bash, PowerShell, Write, Edit, MultiEdit, NotebookEdit, Read, Grep, Glob): parses shell commands across bash, PowerShell and cmd (splitting, quoting, heredocs, wrapper commands, `cd` tracking, env-var assignments) and returns allow, ask or deny. Exit 2 with a stderr reason is a deny; a JSON `permissionDecision: "ask"` on stdout is an ask. It denies writes to the project's real data (including globs and command substitutions that may reach it) and anything naming secrets, including the Read, Grep and Glob tools, refuses to start the app against real data unless the isolating env vars point at scratch, denies maintainer-only scripts, and denies git operations that would discard uncommitted secretary edits (status file and plans folder). It asks before `gh release` writes and forced pushes, and where `guard.release_stamp` is set it denies publishing (`gh release create`, `upload`, a publishing `edit`, `gh api` writes) unless the gate's pass stamp names the current HEAD and the bound file's current hash. An unexpected exception, a missing `uv` or a guard that cannot start produces an ask ("not checked") rather than letting the call through silently; the `hooks.json` command wraps the guard to do this.
- **`hooks/session_start.py`**: prints branch, uncommitted files, CI state on HEAD and the plan's next open step, skipping steps another tab has claimed. All subprocess calls share one deadline.
- **`tools/devflow_checks.py`**: CI check. `version` fails commits that change a configured version file unless the commit is titled `Release candidate X.Y.Z-rcN` or `Release X.Y.Z`, and fails a release-titled commit that leaves any listed version file at another version. `comments` fails new Python comment lines in configured folders, tokenizing old and new files so moved comments pass.
- **`templates/`**: files `/devflow:setup` copies into a consumer project (profile, config, behaviour map, status file, plan, CI workflow, `CLAUDE.md` section, settings).

## Testing notes

`tests/test_guard.py` loads `hooks/guard.py` by file path and runs it against an RYOS-shaped config, a Linux-style project and a minimal config. `tests/test_checks.py` builds real throwaway git repositories. Behaviour changes in the guard or checks need a matching test.

## Conventions

- Hook and tool Python files carry no comments; keep it that way (the CI comment check enforces this in consumer projects, and RYOS-derived code follows the same rule).
- The plugin version lives in `.claude-plugin/plugin.json` and is bumped only in a release commit.
- RYOS keeps its own copies of these skills, agents and hooks (`add-ryos-feature`, `ryos-*`); devflow is the generalized version with project specifics moved into the profile.

## How work is done here (devflow)

This project uses the devflow plugin. Its profile is `.claude/devflow.md` (architecture rules, verify commands, edit bounds, release); its guard config is `.claude/devflow.json`.

- New capability or improvement: `/devflow:add-feature`. Bug or red CI: `/devflow:fix-bug`. Shipping: by hand, as the plan's release step, with no candidate (Standing rules in the profile); not `/devflow:release`. Status, issues, plans and decisions: `/devflow:secretary`.
- What must keep working, on every surface, with the test guarding each: `docs/BEHAVIOUR.md`. Read an area's rows before changing it; a fix updates its entry and test, a new behaviour adds one.
- Project status: `docs/STATUS.md`, kept by the secretary. Plans: `docs/plans/`, one fresh coding session per step; claim the step first. Both are local and gitignored, as are `docs/archive/` and `docs/PROMPTS.md`.
- The version changes only in a `Release X.Y.Z` commit.
- **The escape rule.** Every bug found after a release gets one line in `docs/BEHAVIOUR.md` § Escapes, and its fix adds the check that would have caught it.
