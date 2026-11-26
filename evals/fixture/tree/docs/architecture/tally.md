# Tally

Tally reads numbers from the command line and prints one result line. The arithmetic lives in `tally/core.py` and the reading and printing in `tally/cli.py`. Open this doc before adding a statistic or changing what the result line shows.

## Flow

1. [`main`](../../tally/cli.py) takes the arguments (from `sys.argv` when none are passed, which is how the tests call it), turns each into a `float`, and passes the list to the calculations.
2. [`total`](../../tally/core.py) and [`average`](../../tally/core.py) each take that list and return a number.
3. [`main`](../../tally/cli.py) prints them on one line as `key=value` pairs separated by a space, in a fixed order, and returns 0.

[`top`](../../tally/core.py) is a calculation the CLI does not print yet.

## Invariants

- **The core returns, the CLI prints.** Nothing in `tally/core.py` reads input or prints, so every surface (the CLI today, anything else later) reuses the same functions and gets the same numbers.
- **The CLI does no arithmetic.** Every number on the result line comes from a function in `tally/core.py`; computing one inline in `main` is how the two drift apart.
- **The result line is a format users read.** Its keys and their order are part of the output: `tests/test_cli.py` pins the whole line, and the release checklist checks it by hand.

## Recipe

Adding a statistic:

1. Add a function to `tally/core.py` that takes the list of numbers and returns the value, next to [`total`](../../tally/core.py) and [`average`](../../tally/core.py).
2. Test it in `tests/test_core.py`, one test per function, as `TestCore` does.
3. If the CLI should print it, add a `key=value` pair to the line in [`main`](../../tally/cli.py), after the existing ones, calling the new function; then update the expected line in `tests/test_cli.py`.
4. Add or update the row in `docs/BEHAVIOUR.md` for each surface the statistic shows on.

## Gotchas

- **The CLI passes floats.** `main` converts every argument with `float`, so the printed values carry a decimal point (`6.0`, not `6`) even for whole numbers; the CLI test expects that form.

## Flagged / unverified

- None.
