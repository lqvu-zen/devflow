# <Project>: project status

Kept by the project manager (`/devflow:manage-project`). **This file is the master.** Coding sessions **read** it but don't edit it: plan progress goes in each plan's own Status table. Last updated <YYYY-MM-DD HH:MM> (<UTC+N>).

## Roles

- **<Maintainer> (maintainer):** decides, merges, picks version numbers, uses each release candidate, runs the manual checks, reviews the behaviour map.
- **Coding sessions:** Claude Code running `/devflow:add-feature`, `/devflow:fix-bug` and `/devflow:release` with the `devflow:*` agents (locator, designer, implementer, reviewer, tester).
- **Project manager:** `/devflow:manage-project`. Keeps this file, the decision log and the open items; checks GitHub issues; writes plan steps when the maintainer decides something. Never writes code; commits only its own doc files and never pushes.
- **Planner:** the `devflow:planner` agent, called by the project manager for a whole plan or a big feature.

## Working practices

- **Coding sessions:** one fresh conversation per plan step, on Sonnet; the agents' models come from the board in `.claude/devflow.json` (the plugin's pins where it says `default`); `python <plugin>/tools/model_check.py --board` shows them. The prompt to continue, which names no plan file:
  > Read docs/STATUS.md to find the current plan, then continue with its next open step in Order that is not already in progress. Claim it first, and update the Status table when it's done.
- **The project manager:** run `/devflow:manage-project` at the start of each working day, so this file catches up with the plans' Status tables and the git log.
- **Prompts:** paste-ready prompts for every kind of session are in `docs/PROMPTS.md`.
- **Status and plan edits** (`docs/plans/*.md`, `docs/STATUS.md`) may arrive uncommitted. Coding sessions commit them with their next change and never revert them.

## Releases: only two plans

| Release | What | Plan |
|---|---|---|
| **<X.Y.Z>** (in progress) | <goals> | `docs/plans/release-X.Y.Z.md` |

## Where we are (<YYYY-MM-DD>)

- <latest release, what's on main, CI state>

## <Maintainer> to do

- <what waits on the maintainer>

## Open GitHub issues (checked <YYYY-MM-DD HH:MM>)

| # | Title | Where it is |
|---|---|---|

## Parked and dropped

- **Parked:** <ideas kept for later>
- **Dropped:** <ideas not coming back unless the maintainer says so>

## Decision log

- <YYYY-MM-DD HH:MM>: **Adopted devflow.** <one line on why>
