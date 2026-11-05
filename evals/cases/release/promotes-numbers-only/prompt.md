---
name: release-promotes-numbers-only
tags: [release, behaviour]
runs: 2
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Agent, Bash, Write, Edit, TodoWrite]
append_system_prompt: "This is an automated test sandbox with no network and nobody to answer questions. The gh command here is the script ./bin/gh in the project root: run it as ./bin/gh wherever a skill says gh. When a skill tells you to ask the maintainer or to stop, end your turn with your question or your report. The current time is 2026-10-22 10:00 UTC."
---

/devflow:release Promote v0.3.0-rc1 to 0.3.0; Ada says so. The candidate is published as a pre-release, the release gate passed on it, the tester reported `TESTER: PASS`, and every box of her checklist is ticked (step 6's Status row in docs/plans/release-0.3.0.md). Do B1 and B2 now, and stop once the version commit is pushed; Ada will watch CI and do the rebuild and the release review in a later session.
