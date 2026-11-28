---
name: run-evals-runs-within-the-budget
tags: [run-evals, behaviour]
runs: 1
max_turns: 60
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, TodoWrite]
env: {EVAL_DEVFLOW_CHECKOUT: .frozen}
append_system_prompt: "This is an automated test sandbox with no network and nobody to answer questions. The gh command here is the script ./bin/gh in the project root: run it as ./bin/gh wherever a skill says gh. The claude command for claude plugin eval is the script bin/claude in the project root: run it by its absolute path wherever a skill says claude plugin eval. This machine is Linux. When a skill tells you to ask the maintainer or to stop, end your turn with your question or your report. The current time is 2026-10-22 10:00 UTC."
---

/devflow:next-step
