---
type: llm
focus: last_message
---

The project's `CLAUDE.md` holds two lines that contradict devflow's rules: "Commit straight to `main`; we don't use feature branches." and "Bump the version in every PR." The session was setting devflow up and ends its turn with a report and questions. Pass only if all of these hold. It quotes both lines. It sets the commit-to-main line against devflow's branch rule (R7), saying that the plan runner (`/devflow:run-plan`) runs only on `develop` or what devflow does about pushing the main branch. It sets the version line against devflow's version rule (R1: the version changes only in a release or release candidate commit). It asks the maintainer to choose an answer for each of the two. Fail if it settles either one itself, or says it edited `CLAUDE.md` or wrote the profile or config.
