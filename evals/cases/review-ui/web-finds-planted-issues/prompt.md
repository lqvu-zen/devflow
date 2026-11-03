---
name: review-ui-web-finds-planted-issues
tags: [review-ui, behaviour, costly]
runs: 2
max_turns: 60
timeout_seconds: 1500
allowed_tools: [Read, Glob, Grep, Skill, Bash]
append_system_prompt: "This is an automated test sandbox with no network and nobody to answer questions. When a skill tells you to ask the user, make your best inference and say so. The current time is 2026-10-22 10:00 UTC."
---

/devflow:review-ui Review the page in index.html at phone and desktop width.
