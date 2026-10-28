---
name: fix-bug-red-ci-triage
tags: [fix-bug, behaviour]
runs: 2
max_turns: 60
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Agent, Bash, Write, Edit, TodoWrite]
append_system_prompt: "This is an automated test sandbox with no network and nobody to answer questions. The gh command here is the script ./bin/gh in the project root: run it as ./bin/gh wherever a skill says gh. When a skill tells you to ask the maintainer or to stop, end your turn with your question or your report. The current time is 2026-10-22 10:00 UTC."
---

/devflow:fix-bug The CI run on main is red. Fix it.
