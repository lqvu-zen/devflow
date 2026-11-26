# Architecture docs

These docs record what the code does not show: how an area's pieces connect across files, what must stay true, how to add one more instance of a pattern, and the traps. The routing table in `CLAUDE.md` ("When to read an area's doc first") says which doc to read before changing which paths.

## Docs

| Doc | Area |
|---|---|
| [guard-parsing.md](guard-parsing.md) | How the guard cuts a shell command into segments and judges each one |
| [store.md](store.md) | How the hooks find a devflow config: in the repo, or in a linked store outside the clone |
| [model-board.md](model-board.md) | How each agent call's model and effort are worked out from pins, the board, Model lines and parts |
| [next-step.md](next-step.md) | How the next plan step is chosen, and how session start, `--next-step` and the plan runner share that choice |
| [checks.md](checks.md) | The CI checks in `tools/devflow_checks.py`, and how to add one more |

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
  [`load_config`](../../src/config.py)
  ```

  Never a file name followed by a colon and a line number, a line fragment, or a line range. If the spot is inside a function, anchor the function and describe the spot in words. The anchor check, `python tools/devflow_checks.py anchors [<doc>.md ...]`, fails on a missing file, a symbol its file lacks, and any line anchor; it skips fenced examples like the one above.
- **No incidental counts or mirrored lists.** Name a set instead of counting or copying it. Write a number only when it is the fact itself (a limit, a size, a measurement).
- **State the constraint, not the deliberation.** Rejected alternatives go in the commit message.
- **Mark what you could not verify.** Every doc ends with a "Flagged / unverified" section for claims not checked against the source. Evidence written against an old commit is a lead, not proof: confirm it in the current code before citing it.

## Keeping them current

- A change to a routed path updates its doc in the same commit, or the commit message carries `Docs-unaffected: <doc>.md - <why>`. The `docs` check fails a commit that does neither.
- A doc found wrong is corrected, or flagged in its "Flagged / unverified" section when the fix is not small.
- When a wrong or missing doc contributed to a bug, the fix carries the correction.
- Each release, the docs audit in `docs/PROMPTS.md` runs the anchor check over every doc, looks for areas added since the last audit, and spot-checks the docs whose anchored files changed most.
