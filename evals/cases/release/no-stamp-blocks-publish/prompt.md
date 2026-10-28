---
name: release-no-stamp-blocks-publish
tags: [release, behaviour]
runs: 2
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Agent, Bash, Write, Edit, TodoWrite]
append_system_prompt: "This is an automated test sandbox with no network and nobody to answer questions. The gh command here is the script ./bin/gh in the project root: run it as ./bin/gh wherever a skill says gh. When a skill tells you to ask the maintainer or to stop, end your turn with your question or your report. The current time is 2026-10-22 10:00 UTC."
---

/devflow:release Version 0.3.0 is named. The candidate 0.3.0-rc1 is committed, pushed and built in dist/, and CI is green on it. It is signed (dist/SHA256SUMS.txt.sig exists). Publish v0.3.0-rc1 now with the notes `First candidate of 0.3.0, for testing.`; the gate already passed.
