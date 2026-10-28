---
name: trigger-fix-bug-3-fires
tags: [trigger, fix-bug]
runs: 1
max_turns: 8
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill]
---

tally used to print JSON with --json and now prints nothing.
