# <Project>: devflow profile

The devflow skills and agents read this file for everything specific to this project. Keep the headings exactly as they are: briefs paste these sections by name. Write each section as rules and facts, not history.

## Project

- **What it is:** <one paragraph: what the product does, who uses it, how it ships>
- **Repo:** <owner/name> (main branch: `main`)
- **Maintainer:** <name> (<GitHub handle>), time zone <UTC+N>. They decide, name versions, use each release candidate and run the manual checks.
- **Languages and stack:** <e.g. Python 3.12 + PySide6; TypeScript + React + Node 22>

## Where things live

| Concern | File |
|---|---|
| <entry point> | `<path>` |
| <data / storage> | `<path>` |
| <settings / config> | `<path>` |
| <UI> | `<path>` |
| <tests> | `<path>` |
| Version | `<path>` |

## Architecture rules

The invariants that make this project work. Most "looked fine, broke in practice" bugs come from breaking one of them, so each rule says *why*. This is the canonical list: briefs paste it whole.

- **<Rule>.** <What it means and why it exists.>
- **Data changes go through migrations.** <Where migrations live, how they are keyed, that each is safe to run twice.>
- **Don't touch the version.** It changes only when the `release` skill cuts a candidate or a release, never per change, and never with a `-dev` suffix.
- **No code comments** in new or changed code, unless this project's style says otherwise. Names, structure and tests carry the intent.

## Verify

Run from the repo root. All must pass before a change is reviewed.

```bash
<unit tests>
<lint>
<type check>
<smoke check>
```

## Edit bounds

- **The implementer may edit:** `<source dirs>`, the tests the plan names, `docs/BEHAVIOUR.md`.
- **Only when the plan names them:** `<build files, lock files, packaging>`.
- **Never staged:** `<build output, local databases, .env, caches>`.

## Escalate

The implementer runs on Opus at medium effort for: <data migrations, packaging and builds, concurrency, security, payments>.

## See it working

How to see a change working, safely:

- <how to run it on throwaway data, e.g. `APPDATA="$S/a" uv run app`>
- <how to take screenshots without opening a window on the maintainer's main screen>
- <environment variables that turn off notifications, telemetry, registry writes>
- Never against the real data in <path>.

## Design system

Leave this section out if the project has no user interface.

- **File:** `docs/DESIGN.md`, in Google's DESIGN.md format (tokens in the front matter, then the sections, then Platforms, States, Inputs and Motion).
- **Platforms the project ships to:** <web | desktop | mobile | game, one or more; for each, the framework: e.g. desktop (Qt/QML), game (Unity)>.
- **UI surfaces:** <the behaviour-map surfaces and folders that are user interface>.

## Release

Leave this section out if the project doesn't ship releases.

- **Repo:** `<owner/name>`.
- **Version files:** `<path>` (`__version__ = "X.Y.Z-rcN"`); `<path>` (numbers only: `X.Y.Z`).
- **Build:** `<command>`; it ends with `<success line>`.
- **Gate:** `<command>` on throwaway data; it ends with `<success line>`.
- **Stamp:** <none | `<dist/gate.passed>`, written by **Gate** and read by the guard (`guard.release_stamp` in `.claude/devflow.json`)>.
  - Format: a JSON object with `head` (the full SHA of HEAD), `sha256sums` (the SHA-256 hex of the file the stamp binds, e.g. `dist/SHA256SUMS.txt`) and `passed` (the case count, above 0). Extra fields such as `skipped` and `python` are allowed and ignored.
  - **Gate** writes it only when every case passes and neither HEAD nor the bound file changed during the run. It deletes any old stamp when a run starts, and **Build** deletes it too, so a failed or interrupted run leaves none.
  - With a stamp configured the guard refuses `gh release create`, `upload`, a publishing `edit` and `gh api` writes to releases unless the stamp names the current HEAD and the bound file's current hash. Without one, those commands only ask the maintainer.
- **Sign:** <none | the maintainer runs `<command>`; Claude never signs or reads the key>.
- **Artifacts:** `<dist/app-windows.zip>`, `<dist/SHA256SUMS.txt>`.
- **Notes:** every release's notes carry: <"Which download?", "Check your download", "Updating">.
- **After:** <clear `dist/`; add a fixture when the schema changed>.

### Lineup

| Artifact | Must contain | Must not contain |
|---|---|---|
| `<app.zip>` | `<app.exe>` | caches, local databases, settings files |

### Checklist

The maintainer's manual checks for every candidate:

- [ ] A fresh download from the candidate's release page installs and starts.
- [ ] The maintainer's real data looks right after the upgrade.
- [ ] <anything only a person can check>

## Try it

How the tester agent uses a built candidate the way a user would:

- **Unpack:** <unzip into a new folder in the scratchpad>.
- **Drive:** <the CLI commands, API calls or off-screen UI driver to use>.
- **Throwaway data:** <the environment that keeps every process off real data>.
- **Never:** <launch a window on the main screen; run anything from inside an unpacked folder except the program itself>.

## Standing rules

Rules from the decision log that every session keeps (the secretary adds to these):

- Few release plans: the current one and the next at most.
- The version number is the maintainer's.
- Every release goes through a release candidate.
- Every escaped bug adds its check.
