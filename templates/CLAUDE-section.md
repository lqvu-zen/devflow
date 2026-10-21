## How work is done here (devflow)

This project uses the devflow plugin. Its profile is `.claude/devflow.md` (architecture rules, verify commands, edit bounds, release); its guard config is `.claude/devflow.json`.

- New capability or improvement: `/devflow:add-feature`. Bug or red CI: `/devflow:fix-bug`. Shipping: `/devflow:release`. Status, issues, plans and decisions: `/devflow:secretary`.
- What must keep working, on every surface, with the test guarding each: `docs/BEHAVIOUR.md`. Read an area's rows before changing it; a fix updates its entry and test, a new behaviour adds one.
- Project status: `docs/STATUS.md`, kept by the secretary. Plans: `docs/plans/`, one fresh coding session per step; claim the step first.
- The version changes only in a `Release candidate X.Y.Z-rcN` or `Release X.Y.Z` commit.
- **The escape rule.** Every bug found after a release gets one line in `docs/BEHAVIOUR.md` § Escapes, and its fix adds the check that would have caught it.
