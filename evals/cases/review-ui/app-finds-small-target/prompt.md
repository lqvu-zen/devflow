---
name: review-ui-app-finds-small-target
tags: [review-ui, behaviour, costly]
runs: 2
max_turns: 60
timeout_seconds: 1500
allowed_tools: [Read, Glob, Grep, Skill, Bash]
append_system_prompt: "This is an automated test sandbox with no network and nobody to answer questions. When a skill tells you to ask the user, make your best inference and say so. The current time is 2026-10-22 10:00 UTC."
---

/devflow:review-ui Is the settings screen any good? The source is app/SettingsPanel.qml and a screenshot is app/screens/settings.png.
