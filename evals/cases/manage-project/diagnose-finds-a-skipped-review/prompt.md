---
name: manage-project-diagnose-finds-a-skipped-review
tags: [manage-project, behaviour]
runs: 3
max_turns: 40
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Agent, Bash, Write, Edit, TodoWrite]
append_system_prompt: "This is an automated test sandbox with no network and nobody to answer questions. The gh command here is the script ./bin/gh in the project root: run it as ./bin/gh wherever a skill says gh. When a skill tells you to ask the maintainer or to stop, end your turn with your question or your report. The current time is 2026-10-22 10:00 UTC."
---

/devflow:manage-project Session d1a9c0de-0000-4000-8000-000000000002 did step 2 (Median) yesterday and marked it done, but median([]) crashes and nothing caught it. Why did that session go wrong?
