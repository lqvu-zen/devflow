---
name: fix-bug-ui-bug-reviewer-gets-motion
tags: [fix-bug, behaviour, costly]
runs: 1
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Agent, Bash, Write, Edit, TodoWrite]
append_system_prompt: "This is an automated test sandbox with no network and nobody to answer questions. The gh command here is the script ./bin/gh in the project root: run it as ./bin/gh wherever a skill says gh. When a skill tells you to ask the maintainer or to stop, end your turn with your question or your report. The current time is 2026-10-22 10:00 UTC."
---

/devflow:fix-bug On the page in index.html, hovering the Get Tally button makes it grow over almost a second, far slower than the design system's motion allows, and it grows even when the system's reduce-motion setting is on. Keep the grow as hover feedback. Approve the design yourself and go ahead without asking.
