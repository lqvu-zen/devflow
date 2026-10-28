---
name: trigger-release-5-near-miss
tags: [trigger, release]
runs: 1
max_turns: 8
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill]
---

tally 0.2.0 crashes on empty input, fix it.
