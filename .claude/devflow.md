# devflow: devflow profile

The devflow skills and agents read this file for everything specific to this project. Keep the headings exactly as they are: briefs paste these sections by name. Write each section as rules and facts, not history.

## Project

- **What it is:** a Claude Code plugin, and its own single-plugin marketplace. It ships a working method: skills that send each phase of a feature, bug fix or release to a fresh agent with a pinned model; a secretary that keeps the status file and plans; and hooks and a CI check that turn the process rules into checks. Maintainers of other projects install it from this repository and adopt it with `/devflow:setup`. RYOS keeps its own copies of these skills; devflow is the general version.
- **Repo:** lqvu-zen/devflow (main branch: `main`)
- **Maintainer:** Quang-Vu Le (lqvu-zen), time zone UTC+7. They decide, name versions, and run the manual checks.
- **Languages and stack:** Markdown (skills, agents, templates); Python 3.13, standard library only (hooks and tools); Node 22+ for `review-web-ui` only; bash for the hook commands and the eval scaffolds; GitHub Actions on Linux and Windows.

## Where things live

| Concern | File |
|---|---|
| Plugin manifest and version | `.claude-plugin/plugin.json` |
| Marketplace entry | `.claude-plugin/marketplace.json` |
| Workflow skills | `skills/{setup,add-feature,fix-bug,release,secretary}/SKILL.md` |
| UI review skill (standalone, Node) | `skills/review-web-ui/` (`vendor/` is third-party) |
| Agents, with pinned model and effort | `agents/*.md` |
| Hook registration | `hooks/hooks.json` |
| Guard (PreToolUse) | `hooks/guard.py` |
| Session-start summary | `hooks/session_start.py` |
| CI check (version, comments) | `tools/devflow_checks.py` |
| Session extract for the process-escape review | `tools/session_extract.py` |
| Files setup copies into a project | `templates/` |
| Unit tests | `tests/test_*.py` |
| Skill evals, fixture and scaffolds | `evals/cases/`, `evals/fixture/` |
| CI workflow | `.github/workflows/test.yml` |
| Changelog | `CHANGELOG.md` |
| Version | `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` |

## Architecture rules

The invariants that make this project work. Most "looked fine, broke in practice" bugs come from breaking one of them, so each rule says *why*. This is the canonical list: briefs paste it whole.

- **Python is standard library only, with no build step.** The hooks run in other people's projects as `uv run --no-project python …`, with no environment to install into. `review-web-ui` is the one exception (Node 22+ and a Chrome-family browser) and stays self-contained.
- **Skills never hardcode a project's facts.** They read `.claude/devflow.md` by exact heading and paste sections verbatim into agent briefs. Renaming or removing a heading in `templates/devflow.md` breaks every skill that cites it; adding one is safe. (inferred from CLAUDE.md, please check the "adding is safe" half)
- **A rule the skills share is written in the same words everywhere.** `fix-bug` and `release` reuse the `add-feature` pipeline, so a change to the stop rules, claiming a step, gates, the Files line, CI first or the verbatim-paste requirement is mirrored across `add-feature`, `fix-bug`, `release` and `secretary` in one change. A rule that drifts in one skill is a rule the agents get two ways.
- **Model and effort are pinned in each agent's frontmatter.** Skills don't pass `model` or `effort` except to escalate, so one edit to `agents/*.md` changes every caller.
- **The hooks do nothing without `.claude/devflow.json`.** `hooks/hooks.json` gates each command on that file, so installing the plugin for a user account is safe. Keep that gate in every hook added.
- **The guard never lets a call through unchecked.** An exception, a broken config, missing `uv` or a guard that can't start produces an `ask` ("not checked"), never a silent allow. A deny is exit 2 with a reason on stderr; an ask is a JSON `permissionDecision: "ask"` on stdout.
- **Every behaviour change in the guard or the checks has a matching test.** `tests/test_guard.py` runs it against an RYOS-shaped config, a Linux-style project and a minimal config; `tests/test_checks.py` uses real throwaway git repositories.
- **`skills/review-web-ui/vendor/` is third-party code.** Update it only by re-copying from upstream and recording the commit in `skills/review-web-ui/SKILL.md`; never edit it in place.
- **CRLF line endings throughout** (`.gitattributes`, `.editorconfig`, commit `d30f107`).
- **Don't touch the version.** It changes only in a release commit titled `Release X.Y.Z`, never per change, and never with a `-dev` suffix.
- **No code comments** in new or changed code: not in Python (the `comments` CI check enforces it for `hooks/`, `tools/` and `tests/`), not in shell scripts, not in JSON or YAML. Names, structure and tests carry the intent; the why goes in the commit message and the docs.

## Verify

Run from the repo root. All must pass before a change is reviewed.

```bash
python -m unittest discover -s tests
```

When a change edits a skill's `description`, also run that skill's trigger cases (cheap; one run each):

```bash
claude plugin eval . --tag trigger --case "<skill>-*" --ablation none --runs 1 --trust-plugin --no-publish -j 4
```

Behaviour evals cost money (a full run is about $11 to $14). Run the changed skill's cases only when the plan step says so; the commands are in `README.md` under Skill evals. There is no lint or type check.

## Edit bounds

- **The implementer may edit:** `skills/` (except `skills/review-web-ui/vendor/`), `agents/`, `hooks/guard.py`, `hooks/session_start.py`, `tools/`, `templates/`, `tests/`, `evals/cases/`, `evals/fixture/`, `README.md`, the `Unreleased` section of `CHANGELOG.md`, `CLAUDE.md`, `docs/BEHAVIOUR.md`.
- **Only when the plan names them:** `hooks/hooks.json`, `.github/workflows/`, `.gitignore`, `.gitattributes`, `.editorconfig`, `skills/review-web-ui/vendor/` (re-copied from upstream), `.claude/`.
- **Never edited outside a release commit:** `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`.
- **Never staged:** `evals/results/`, `__pycache__/`, `docs/plans/`, `docs/STATUS.md`, `docs/archive/`, `docs/PROMPTS.md`, anything under `~/.claude/`.

## Escalate

The implementer runs on Opus at medium effort for: the guard (`hooks/guard.py`, `hooks/hooks.json`), the CI check (`tools/devflow_checks.py`), and any change to a rule the skills share (see Architecture rules), because a wrong word there changes what every agent does in every project.

## See it working

How to see a change working, safely:

- **The guard:** build a scratch project from the eval fixture (`cd <scratchpad>/p && bash D:/Projects/devflow/evals/fixture/build.sh`), then feed it calls: `echo '{"tool_name":"Bash","tool_input":{"command":"git reset --hard"}}' | CLAUDE_PROJECT_DIR="<scratchpad>/p" uv run --no-project python hooks/guard.py; echo "exit $?"`. Exit 2 is a deny.
- **The session-start hook:** `CLAUDE_PROJECT_DIR="<scratchpad>/p" uv run --no-project python hooks/session_start.py` on the same scratch project.
- **A skill or agent:** its eval cases (`claude plugin eval . --case "<glob>" …`, see `README.md`), or a session in the scratch project with `claude --plugin-dir D:/Projects/devflow`, which loads this checkout instead of the installed copy.
- **`review-web-ui`:** run it on a local `.html` file or the eval fixture's page, never on a live site the maintainer didn't name.
- Never against the maintainer's real setup: the installed plugin copies in `~/.claude/plugins`, `~/.claude/settings.json`, `~/.claude/CLAUDE.md`, or the session transcripts in `~/.claude/projects`. Never try a skill on a real project (RYOS or another) to see it work.

## Release

- **Repo:** `lqvu-zen/devflow`.
- **Version files:** `.claude-plugin/plugin.json` (`"version": "X.Y.Z"`); `.claude-plugin/marketplace.json` (the plugin entry's `"version": "X.Y.Z"`). Both numbers only: devflow has no release candidates (see Standing rules).
- **Build:** none. Users install from the repository at the tag.
- **Gate:** green CI on the release commit (Linux and Windows), plus the trigger evals, and the behaviour evals of every skill changed since the last release, each with its pass count recorded in `README.md`.
- **Stamp:** none. `gh release` writes ask the maintainer.
- **Sign:** none.
- **Artifacts:** none. The GitHub release carries notes only.
- **Notes:** the release's `CHANGELOG.md` section, plus "Updating: `/plugin marketplace update devflow`".
- **After:** start a new `## Unreleased` section in `CHANGELOG.md`; check that the README's skill, agent and template lists match the folders.

### Checklist

The maintainer's manual checks for every release:

- [ ] After `/plugin marketplace update devflow`, `/plugin` shows the new version.
- [ ] One real session with the updated plugin in a project that uses it starts cleanly (the session-start summary prints, the guard allows normal work).

## Standing rules

Rules from the decision log that every session keeps (the secretary adds to these):

- Few release plans: the current one and the next at most.
- The version number is the maintainer's.
- **devflow releases without a candidate** (2026-10-28): a `Release X.Y.Z` commit that changes both version files, a `vX.Y.Z` tag, and a GitHub release with notes, done by hand as the plan's release step. Don't run `/devflow:release` here: its runbook always cuts a candidate.
- **The status file, plans, archive and prompt book stay local** (2026-10-28): `docs/STATUS.md`, `docs/plans/`, `docs/archive/` and `docs/PROMPTS.md` are gitignored. The secretary saves them and commits nothing; coding sessions never stage them.
- Every escaped bug adds its check.
- Coding sessions: one fresh conversation per plan step.
