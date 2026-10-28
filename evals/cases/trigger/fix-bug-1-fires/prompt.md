---
name: trigger-fix-bug-1-fires
tags: [trigger, fix-bug]
runs: 1
max_turns: 8
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill]
---

tally average raises ZeroDivisionError on an empty list.
