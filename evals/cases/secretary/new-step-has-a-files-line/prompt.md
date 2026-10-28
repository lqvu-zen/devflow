---
name: secretary-new-step-has-a-files-line
tags: [secretary, behaviour]
runs: 3
max_turns: 50
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Agent, Bash, Write, Edit, TodoWrite]
append_system_prompt: "This is an automated test sandbox with no network and nobody to answer questions. The gh command here is the script ./bin/gh in the project root: run it as ./bin/gh wherever a skill says gh. When a skill tells you to ask the maintainer or to stop, end your turn with your question or your report. The current time is 2026-10-22 10:00 UTC."
---

/devflow:secretary Add a plan step: tally should take a --precision N option for the number of decimals printed. Yes, add it, no need to ask. Commit it.
