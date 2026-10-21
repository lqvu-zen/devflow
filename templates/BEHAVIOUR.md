# <Project> behaviour map

`CLAUDE.md` and the architecture docs say how <Project> is built. This file says **what must keep working, and everywhere it shows up.** Most behaviours appear in several places at once. A change that reaches one place breaks the others unseen.

Each entry is one line the user would recognise, **every surface** it appears on, and the test that guards it, or **untested**.

## How to use it

- **Before you change an area, read its entries.** Check each surface listed, not only the one you are working on.
- **A fix adds or updates its entry and its test.** Put the issue number in the behaviour text, e.g. "(#27)".
- **A feature adds its entries** in the same change, with the surfaces it reaches.
- **Test names are exact.** Format: `<test file>::<Class>::<test>`. A bare class name means every test in that class applies. `<gate>::<case>` is a case of the release gate, which runs on built artifacts, not in CI.
- **A check usually covers one surface.** Where a test covers only some of the surfaces, the Guarded-by cell says which, e.g. "(W only)". The surfaces it does not name are unguarded, and the last section lists them.

## Surfaces

| Code | Surface |
| --- | --- |
| **W** | <the main window / web page> |
| **CLI** | <the command line> |
| **API** | <the public API> |

## 1. <Area>

| Behaviour | Surfaces | Guarded by |
| --- | --- | --- |
| **AR-01** <What the user sees or can do.> | W CLI | `<test>` |
| **AR-02** <...> | W | **untested** |

## Escapes

Every bug found after a release gets one line here, in the fix's commit, and that commit adds the check named: "#NN (vX.Y.Z): should have been caught by <check>; added <test / map entry / release-gate case>".

## Harness escapes

A process rule broken by a session (not a bug in the product) gets one line here: what happened, and the hook case or permission rule that now stops it. A session that breaks a process rule adds, in the same change, the guard rule (`.claude/devflow.json`) or `deny` / `ask` rule that would have stopped it; a new `deny` or `ask` rule needs the maintainer's approval.

---

## Untested: backlog

Entries marked **untested** above, then the entries guarded on some surfaces only.
