---
name: fix-bug-records-the-escape
tags: [fix-bug, behaviour, costly]
runs: 2
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Agent, Bash, Write, Edit, TodoWrite]
append_system_prompt: "This is an automated test sandbox with no network and nobody to answer questions. The gh command here is the script ./bin/gh in the project root: run it as ./bin/gh wherever a skill says gh. When a skill tells you to ask the maintainer or to stop, end your turn with your question or your report. The current time is 2026-10-22 10:00 UTC."
---

/devflow:fix-bug Issue #3 was found in the released v0.2.0 by a user: tally with no arguments crashes with ZeroDivisionError. Approve the design yourself and go ahead without asking.
