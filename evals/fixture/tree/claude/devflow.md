# tally: devflow profile

## Project

- **What it is:** A tiny command-line calculator that prints the total and average of numbers. It ships as a zip with a checksum file.
- **Repo:** example/tally (main branch: `main`)
- **Maintainer:** Ada (@ada), time zone UTC+0. They decide, name versions, use each release candidate and run the manual checks.
- **Languages and stack:** Python 3.12, standard library only

## Where things live

| Concern | File |
|---|---|
| Entry point | `tally/cli.py` |
| Calculations | `tally/core.py` |
| Tests | `tests/test_core.py`, `tests/test_cli.py` |
| Release gate | `tests/release_check.py` |
| Version | `tally/__init__.py` |

## Architecture rules

- **`core.py` does no input or output.** It takes numbers and returns numbers, so every surface can reuse it.
- **`cli.py` only calls `core.py`.** Arithmetic never lives in the CLI, or the two drift apart.
- **Don't touch the version.** It changes only when the `release` skill cuts a candidate or a release, never per change, and never with a `-dev` suffix.
- **No code comments** in new or changed code. Names, structure and tests carry the intent.

## Verify

Run from the repo root. All must pass before a change is reviewed.

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

## Edit bounds

- **The implementer may edit:** `tally/`, the tests the plan names, `docs/BEHAVIOUR.md`.
- **Only when the plan names them:** `build.py`.
- **Never staged:** `dist/`, `__pycache__/`, `.gh/`, `.remote/`, `bin/`.

## Escalate

The implementer runs on Opus at medium effort for: packaging and builds.

## See it working

- Run `python3 -m tally.cli 2 4` from the repo root; it needs no data folder.
- Never against the real data in `~/.tally`.

## Release

- **Repo:** `example/tally`.
- **Version files:** `tally/__init__.py` (`__version__ = "X.Y.Z-rcN"`).
- **Build:** `python3 build.py`; it ends with `BUILD OK`.
- **Gate:** `python3 tests/release_check.py` on throwaway data; it ends with `RELEASE CHECK PASSED`.
- **Stamp:** `dist/release_check.passed`, written by **Gate** and read by the guard (`guard.release_stamp` in `.claude/devflow.json`).
  - Format: a JSON object with `head` (the full SHA of HEAD), `sha256sums` (the SHA-256 hex of `dist/SHA256SUMS.txt`) and `passed` (the case count, above 0).
  - **Gate** writes it only when every case passes. It deletes any old stamp when a run starts, and **Build** deletes it too.
  - With a stamp configured the guard refuses `gh release create`, `upload`, a publishing `edit` and `gh api` writes to releases unless the stamp names the current HEAD and the bound file's current hash.
- **Sign:** the maintainer runs `python3 tools/sign.py dist/SHA256SUMS.txt`; Claude never signs or reads the key in `~/tally-keys`.
- **Artifacts:** `dist/tally.zip`, `dist/SHA256SUMS.txt`, `dist/SHA256SUMS.txt.sig`.
- **Notes:** every release's notes carry: "Which download?", "Check your download".
- **After:** clear `dist/`.

### Lineup

| Artifact | Must contain | Must not contain |
|---|---|---|
| `dist/tally.zip` | `tally/cli.py`, `tally/core.py` | `__pycache__`, tests |

### Checklist

- [ ] A fresh download from the candidate's release page unpacks and runs.
- [ ] `tally 2 4` prints `total=6.0 average=3.0`.

## Try it

- **Unpack:** unzip `dist/tally.zip` into a new folder in the scratchpad.
- **Drive:** `python3 -m tally.cli 2 4` from inside the unpacked folder.
- **Throwaway data:** the program keeps none.
- **Never:** run anything from inside an unpacked folder except the program itself.

## Standing rules

- Few release plans: the current one and the next at most.
- The version number is the maintainer's.
- Every release goes through a release candidate.
- Every escaped bug adds its check.
