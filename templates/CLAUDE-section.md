## How work is done here (devflow)

This project uses the devflow plugin. Its profile is `.claude/devflow.md` (architecture rules, verify commands, edit bounds, release); its guard config is `.claude/devflow.json`.

- New capability or improvement: `/devflow:add-feature`. Bug or red CI: `/devflow:fix-bug`. Shipping: `/devflow-release:release` with the `devflow-release` plugin, else by hand as **Release** in the profile says. Status, issues, plans and decisions: `/devflow:manage-project`. Continue the plan: `/devflow:next-step`.
- What must keep working, on every surface, with the test guarding each: `docs/BEHAVIOUR.md`. Read an area's rows before changing it; a fix updates its entry and test, a new behaviour adds one.
- Project status: `docs/STATUS.md`, kept by the project manager. Plans: `docs/plans/`, one fresh coding session per step; claim the step first.
- The version changes only in a `Release candidate X.Y.Z-rcN` or `Release X.Y.Z` commit.
- **The escape rule.** Every bug found after a release gets one line in `docs/BEHAVIOUR.md` § Escapes, and its fix adds the check that would have caught it.

### When to read an area's doc first

`docs/architecture/` holds one doc per area; its `README.md` has the writing rules. Read an area's doc before a change to its paths or topics when the change spans layers, adds one more instance of a pattern, or reaches a mechanism one or two greps won't find. Read only the sections you need (Flow, Invariants, Recipe, Gotchas). Skip it for a lookup or a one-file fix. A change to a row's paths updates its doc in the same commit, or the commit message carries `Docs-unaffected: <doc>.md - <why>`.

| Paths | Topics | Doc |
|---|---|---|
| `<folder>/`, `<path/file.ext>`, `<glob/*.ext>` | <what the area is about> | `docs/architecture/<area>.md` |
