# Architecture docs

These docs record what the code does not show: how an area's pieces connect across files, what must stay true, how to add one more instance of a pattern, and the traps. The routing table in `CLAUDE.md` ("When to read an area's doc first") says which doc to read before changing which paths.

## Docs

| Doc | Area |
|---|---|
| [tally.md](tally.md) | The calculations in `tally/core.py` and how the CLI prints them |

## When an area gets a doc

Write one when any of these holds:

- A change there spans layers (server and client, generated and hand-written, code and data).
- Adding one more instance of a pattern (a command, a check, a screen) needs a recipe someone had to rediscover.
- The mechanism cannot be found in one or two greps.

Not for a lookup, a one-file fix, or anything whose whole effect is visible in the code. Add areas as changes touch them, never all at once. Merge or delete a doc whose area is gone: a stale doc misleads more than a missing one.

## Writing rules

- **Why, not what.** Explain flows, invariants and gotchas. Leave out anything a reader gets by opening the file.
- **Anchor by symbol, never by line.** Cite source as a link whose text is one code span naming the symbol and whose target is the file that defines it, relative to this folder:

  ```markdown
  [`total`](../../tally/core.py)
  ```

  Never a file name followed by a colon and a line number, a line fragment, or a line range. If the spot is inside a function, anchor the function and describe the spot in words.
- **No incidental counts or mirrored lists.** Name a set instead of counting or copying it. Write a number only when it is the fact itself (a limit, a size, a measurement).
- **State the constraint, not the deliberation.** Rejected alternatives go in the commit message.
- **Mark what you could not verify.** Every doc ends with a "Flagged / unverified" section for claims not checked against the source.

## Keeping them current

- A change to a routed path updates its doc in the same commit, or the commit message carries `Docs-unaffected: <doc>.md - <why>`.
- A doc found wrong is corrected, or flagged in its "Flagged / unverified" section when the fix is not small.
- When a wrong or missing doc contributed to a bug, the fix carries the correction.
