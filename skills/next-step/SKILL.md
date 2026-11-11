---
name: next-step
description: 'Continue the project''s plan: find the next step the way the session-start summary does (the current plan''s next open step in Order that no other tab has claimed, else the next plan''s first ready step), then run it through the skill its Who does what row names, /devflow:add-feature or /devflow:fix-bug, which claims it and updates its Status row. Stops, editing nothing, at an uncleared Gate, a project-manager step, a step done by hand or by another skill, or when no step can start. Use when the user says "continue the plan", "next step", "what''s next, do it", or pastes the continue prompt. Do NOT use when the user names a step or describes a feature or bug (use add-feature or fix-bug), or asks where things stand or what is left (use manage-project).'
---

# Continuing the plan

The next step is chosen by code, not by reading the plan again, so this skill and the session-start summary always agree. You find the step, then hand it to the skill that does it. You never do a step yourself.

## The project profile

If `.claude/devflow.md` is missing, stop and tell the user to run `/devflow:setup` first.

## 1. Find the step

Run, from the project root:

```
python <plugin>/hooks/session_start.py --next-step
```

`hooks/` is two folders up from this skill's base directory. The output is a few labelled lines:

- `Plan:` the plan the step is in, ending "(the next plan)" when no step of the current plan can start.
- `Why:` and `Skipped:` (only on the next plan): why no step of the current plan can start, and the next plan's steps passed over.
- `Step:` the step's number and title, and `Last state:` its row's note, if any.
- `Gate:` the text of an uncleared Gate line.
- Then either `Run: /devflow:add-feature` or `Run: /devflow:fix-bug`, or `Stop: <reason>. Next: <what happens next>.`

Take what it prints as it is. Never pick another step, and never re-read the plan to second-guess it. If the command fails or prints neither a `Run:` nor a `Stop:` line, show the user its output and stop.

## 2. On a Stop line

Tell the user, in plain words: the plan, the step (when one is named), the reason, the Gate's text when there is one, and what happens next, from the `Next:` part. Then end your turn.

Edit nothing, claim nothing, commit nothing, and start no skill and no agent. A Gate is the maintainer's to clear; a by-hand step is the maintainer's to do; a project-manager step goes to `/devflow:manage-project`.

## 3. On a Run line

1. Say which step you are taking and from which plan. When the plan is the next plan, give the `Why:` and `Skipped:` lines, and say that the step ships with the current release and that the project manager moves it into the current plan when it lands.
2. Call the Skill tool with the skill the `Run:` line names (`add-feature` or `fix-bug`) and the arguments `Do step N of <plan>.`, with N and the plan path from the `Step:` and `Plan:` lines. When the step comes from the next plan, add `Taken from the next plan: <the Why line>.`
3. Follow that skill to its end. It claims the step (as in `add-feature`'s "Before you start, and where you stop") and updates its Status row when the step is done or stopped. You never edit the plan or the status file yourself.

## Rules

- Never do a step by hand: no edits, agents or commits outside the skill you run.
- One step per run. When it is done, report and stop; the next step is a fresh session.
- A step the user names ("do step 4 of the plan") is not this skill's: that goes straight to `add-feature` or `fix-bug`.
