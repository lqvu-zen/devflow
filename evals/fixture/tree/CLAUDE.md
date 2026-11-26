# CLAUDE.md

### When to read an area's doc first

`docs/architecture/` holds one doc per area; its `README.md` has the writing rules. Read an area's doc before a change to its paths or topics when the change spans layers, adds one more instance of a pattern, or reaches a mechanism one or two greps won't find. Read only the sections you need (Flow, Invariants, Recipe, Gotchas). Skip it for a lookup or a one-file fix. A change to a row's paths updates its doc in the same commit, or the commit message carries `Docs-unaffected: <doc>.md - <why>`.

| Paths | Topics | Doc |
|---|---|---|
| `tally/` | the calculations and how the CLI prints them | `docs/architecture/tally.md` |
