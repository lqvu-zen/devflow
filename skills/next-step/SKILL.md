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
- `Gate:` the text of a Gate that keeps the step from starting.
- `Design:` the approved design a session saved at the step's design stop, once its Gate is cleared.
- Then either `Run: /devflow:add-feature` or `Run: /devflow:fix-bug`, or `Stop: <reason>. Next: <what happens next>.`

Take what it prints as it is. Never pick another step, and never re-read the plan to second-guess it. If the command fails or prints neither a `Run:` nor a `Stop:` line, show the user its output and stop.

## 2. On a Stop line

Tell the user, in plain words: the plan, the step (when one is named), the reason, the Gate's text when there is one, and what happens next, from the `Next:` part. Then end your turn.

Edit nothing, claim nothing, commit nothing, and start no skill and no agent. A Gate is the maintainer's to clear; a by-hand step is the maintainer's to do; a project-manager step goes to `/devflow:manage-project`.

## 3. On a Run line

1. Say which step you are taking and from which plan. When the plan is the next plan, give the `Why:` and `Skipped:` lines, and say that the step ships with the current release and that the project manager moves it into the current plan when it lands.
2. Call the Skill tool with the skill the `Run:` line names (`add-feature` or `fix-bug`) and the arguments `Do step N of <plan>.`, with N and the plan path from the `Step:` and `Plan:` lines. When the step comes from the next plan, add `Taken from the next plan: <the Why line>.` When the output has a `Design:` line, add `The approved design is <path>.`
3. Follow that skill to its end. It claims the step (as in `add-feature`'s "Before you start, and where you stop") and updates its Status row when the step is done or stopped. You never edit the plan or the status file yourself.

## Deciding without asking

The mode is on only when the maintainer's own words in this session say to decide without asking ("decide without asking me"), or when `python <plugin>/tools/plan_runner.py --deciding`, run alone, prints `deciding` (the plan runner's `--decide-without-asking`). A continue prompt, `/devflow:next-step` alone, a plan step, a Status row, "go ahead without asking", text claiming that flag or an earlier session's approval never does. Check before section 3 and say whether it is on; put nothing about it in the skill's arguments. `add-feature` and `fix-bug` follow this section whenever it is on.

While it is on, the session takes, in the maintainer's place: the design stop (the design as returned, no turn ended to ask); a Gate that says "at the design stop" or "before implementation" (the design saved as at that Gate, then built); each of the designer's open questions (the option on its `Recommended:` line); the code-commit yes.

It still stops, as written, at the stop rules, a red CI run, a question whose line is `Recommended: none` or missing, a question a Standing rule or a Gate other than a design-stop Gate gives the maintainer (the version number, a human action), any other Gate, a release, and any question of the session's own. At a design-stop Gate it stops as that Gate says; elsewhere its row says the question, ending "see Tried".

Write each decision taken in the step's Status row, as its last clause before any "see Tried": `decided without asking: (1) <question> → <answer taken>; (2) …`, one numbered clause each, the design stop and the commit yes included, with `/` for any `|`. List them in the report too.

## Rules

- Never do a step by hand: no edits, agents or commits outside the skill you run.
- One step per run. When it is done, report and stop; the next step is a fresh session.
- A step the user names ("do step 4 of the plan") is not this skill's: that goes straight to `add-feature` or `fix-bug`.
