---
name: add-feature-ui-change-covers-states-and-inputs
tags: [add-feature, behaviour, costly]
runs: 2
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Agent, Bash, Write, Edit, TodoWrite]
append_system_prompt: "This is an automated test sandbox with no network and nobody to answer questions. The gh command here is the script ./bin/gh in the project root: run it as ./bin/gh wherever a skill says gh. When a skill tells you to ask the maintainer or to stop, end your turn with your question or your report. The current time is 2026-10-22 10:00 UTC."
---

/devflow:add-feature On the page in index.html, show an error message under the Numbers field when it holds something that is not numbers. Show me the design before you write any code.
