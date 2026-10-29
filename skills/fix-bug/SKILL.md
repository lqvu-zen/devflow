---
name: fix-bug
description: 'Diagnose and fix a bug the devflow way: reproduce it, prove it with a failing test, find the root cause with a fresh Opus agent, fix it with a Sonnet agent, review with a fresh Opus agent, commit and push, and record the escape when the bug got past a release. Uses the project''s behaviour map and architecture rules from .claude/devflow.md. Use whenever the user reports the product misbehaves: a crash, traceback, freeze or hang, wrong output, a setting that doesn''t stick, a broken migration, "X used to work and now doesn''t", or a red CI run, even when they just describe the broken behaviour without saying "bug". Do NOT use it to add capabilities (use add-feature), to cut a release (use release), or for status and planning (use secretary).'
---

# Fixing a bug

The trap with bug-fixing is fixing the *symptom* instead of the *cause*, or "fixing" something you never reproduced. Most bugs trace back to a structural cause: a broken architecture rule, an unguarded migration, a state refreshed the wrong way, a setting that never round-trips. So this workflow insists on two things before any code changes: reproduce the bug, and capture it in a **failing test** (where the logic is testable) so the fix is provable and can't silently regress.

Work through the phases in order. A "fix" you didn't reproduce and can't show passing is not a fix.

## The project profile

Everything specific to this project is in **`.claude/devflow.md`**: **Project**, **Where things live**, **Architecture rules**, **Verify**, **Edit bounds**, **Escalate**, **See it working** and **Design system**. Read it first. Paste **Architecture rules** whole and verbatim wherever a brief below asks for it. If the file is missing, stop and tell the user to run `/devflow:setup` first.

**You are the orchestrator.** You own the conversation, the delegation, the verification of everything you delegate, and the commit decision. You do **not** diagnose the root cause, write the fix, run the tests or review the final diff yourself; each goes to a fresh subagent, because an independent agent has no anchoring from this conversation. Your own job is steps 1 and 2 (reproduce, gather context), then spawning, verifying and committing. Keep the separation even for a one-line fix.

## Who does each phase

| Phase | Runs as | Model (set in the agent file) | Why |
|---|---|---|---|
| 1. Reproduce & scope | orchestrator (you) | session model: run from Sonnet | Owns the conversation; pins down the repro and expected vs. actual. |
| 2. Locate code | `devflow:locator` | Haiku | Cheap, fast search; returns the suspect code for diagnosis. |
| 3. Diagnose + failing test | `devflow:designer` (bug mode) | Opus, high effort | Hardest reasoning: root cause and the minimal correct fix. |
| 4. Fix / verify | `devflow:implementer` | Sonnet (Opus, medium effort, when escalated) | Strong coder; fast across the fix-and-re-run loop. |
| 4b. Verify | orchestrator (you) | session model | Re-runs tests and walks the checklist; the real gate is the review. |
| 5. Review | `devflow:reviewer` | Opus, high effort | Confirms the fix addresses the cause, not the symptom, with no new regressions. |
| 6. Commit & push | orchestrator (you) | session model | Mechanical. |
| 7. Report | orchestrator (you) | session model | Light summarization. |

Don't pass `model` or `effort` in the calls below except to escalate. **Run this skill from a Sonnet session.** **Escalate the implementer** to Opus at medium effort for any area **Escalate** names:

```
Agent({ description: "...", subagent_type: "devflow:implementer", model: "opus", effort: "medium", prompt: <brief> })
```

**If the `devflow:*` agent types aren't listed**, fall back to `subagent_type: "general-purpose"` with the same model, `effort: "high"` for the designer and reviewer, and paste the plugin's `agents/<name>.md` (two folders up from this skill's base directory) at the top of the brief.

**When the work is a step from a release plan**, paste the whole step section verbatim, from its `### N —` heading to the next heading, into the diagnosis, fix and review briefs. That includes its **Needs** and **Done when** lines and its `**Tried:**` line, if it has one. Tell the designer to read Tried and not repeat an approach it lists unless it says why this time is different. Report the step's "needs a human" items.

## The behaviour map (`docs/BEHAVIOUR.md`)

The map lists each behaviour, **every surface** it appears on, and the test that guards it. A bug on one surface is often on its neighbours too.

- **Locate:** the locator returns the map rows for the area, verbatim, with their IDs.
- **Diagnose:** the designer says whether the bug or the fix reaches the other surfaces, and names the entry to update with its regression test.
- **Fix:** the implementer updates the entry and names its regression test; a behaviour that had no entry gets one. Put the issue number in the behaviour text, e.g. "(#27)".
- **Review:** each listed surface is checked; a missing entry is a blocker.
- **Commit:** `docs/BEHAVIOUR.md` goes in the same commit as the fix.

## UI bugs

A bug is a UI bug when it shows on a UI surface that **Design system** lists under UI surfaces. Without a **Design system** section, or when the bug is not on a UI surface, none of this applies and the phases run exactly as written. When it applies, each brief below also carries:

- **Designer (step 3):** the whole **Design system** section and the whole design-system file, verbatim, and the path of the core checklist (`skills/review-ui/references/core.md` in the plugin, beside this skill's folder; pass it as an absolute path), and: *"UI bug. Add the UI item from your instructions: the states, sizes and inputs the bug shows in and the ones the fix must not break."*
- **Implementer (step 4):** the plan's UI item, the **Design system** section and the design-system file, verbatim, and: *"Use the design system's tokens; no hard-coded colour, size, spacing, radius or duration that a token covers. Follow See it working to take a screenshot of the broken state before the fix and of each state the plan names after it, and report any you could not reach, with the reason. Keep screenshots in your scratchpad, never in the repo."*
- **Reviewer (step 5):** the plan's UI item, the **Design system** section, the design-system file, and the path of the core checklist (`skills/review-ui/references/core.md` in the plugin, beside this skill's folder; pass it as an absolute path), and: *"UI bug. Check the diff against the design system and the core checklist as your instructions say."*

The states the implementer could not reach go in the report to the user as "needs a human".

## The escape rule

A bug found **after a release** (in a released version, or by a user) is an escape: some check should have caught it. The fix's commit adds one line to `docs/BEHAVIOUR.md` § **Escapes**:

> #NN (vX.Y.Z): should have been caught by <check>; added <test / map entry / release-gate case>

and adds that check in the same commit. The designer names the missing check in its diagnosis.

## Before you start, and where you stop

**Claim your step**, **check CI on HEAD first**, **commit secretary edits, never revert them**, **stop at a `**Gate:**` line**, **keep to the step's Files line**, and the **stop rules in the loop** work exactly as in `add-feature` (in this plugin, `skills/add-feature/SKILL.md`, "Before you start, and where you stop"). Read that section and follow it. In short: claim the plan row and push that alone before any work; a red CI on HEAD comes first; a step with a Files line edits and commits only those files and asks before touching another; at most two fix rounds after the first run, and one re-review after BLOCKERS, then stop and report; a session that stops without finishing rewrites its row to end with "see Tried" and adds or extends the step's `**Tried:**` line.

## The workflow

### 1. Reproduce and scope the bug

You can't fix what you can't see fail. Pin down, from the user, the exact steps, the expected behaviour, and the actual behaviour (and the full traceback if there is one; ask for it rather than guessing). Then reproduce it:

- If it's logic, reproduce with a quick scratch script outside the repo, or by reading the failing path. That's the cheapest repro.
- If it's runtime or UI behaviour, follow **See it working**: drive the product on throwaway data and capture the broken state. Never against real data, never on the maintainer's main screen.

If you genuinely cannot reproduce it, say so and ask the user for more detail (OS, version, exact input, settings) instead of speculating a fix. State the confirmed repro in one sentence before moving on.

#### When the bug is a red CI run

The failed run is the repro; the log is the traceback, so don't ask the user for either. Triage it with `gh` before anything else, in this order. Each answer goes into the diagnosis brief.

1. **The line that set the exit code.** Read the failed steps' log:

   ```bash
   gh run view <id> --log-failed
   ```

   Find the `exit code` line that ends the failing step, then read upward to the command that returned it. Name that command and its output. A warning or an error that the step went on past is not the failure.

2. **Flaky or not.** Judge the failed *job*, not the workflow: a workflow can be red for one job while the others are steady. List recent runs, then look up that job in each:

   ```bash
   gh run list --workflow <file> --branch <main branch> --limit 20 --json databaseId,headSha,conclusion
   gh run view <run id> --json headSha,jobs --jq '.headSha[0:7] as $sha | .jobs[] | select(.name == "<job>") | "\($sha)\t\(.conclusion)\t\(.databaseId)"'
   ```

   Report the job's pass rate over those runs and its last pass. A job that passes and fails across runs with no commit dividing them is flaky. If it is flaky, rerun the failed jobs once:

   ```bash
   gh run rerun <id> --failed
   gh run watch <id> --exit-status
   ```

   If the rerun goes green, carry on with your task and tell the maintainer that the flaky test's fix is the next step; the secretary adds it first in Order. If the red run was the whole task, stop and report instead. If the rerun is red again, it is not flaky: go on to step 3.

3. **The breaking commit.** From the same listing, take the last run where the job passed and the first where it failed, then list what lies between:

   ```bash
   git log --oneline <passing sha>..<failing sha>
   ```

   Confirm it both ways: every run of the job before that commit passes, and every run from it on fails. When the range holds more than one commit, or CI skipped some, run the failing command from step 1 at each one in a throwaway worktree (`git worktree add <scratch dir> <sha>`) until one commit turns it. Give the commit and its diff to the diagnosis. If you cannot confirm it both ways, say so; don't name a commit on a guess.

4. **Already being fixed.** Look for an open PR and a plan step on the same failure:

   ```bash
   gh pr list --state open --search "<job name or failing test>"
   ```

   Then read the plan's Status rows. If a PR or a step covers it, say which and stop; don't start a second fix.

Then the run is a bug like any other: the line from step 1 is the repro, the commit from step 3 is where the locator starts, and the phases below run as written.

### 2. Locate the code

```
Agent({ description: "Locate code for <bug>", subagent_type: "devflow:locator", prompt: <brief> })
```

The brief gives the bug and its repro in a line or two plus the **Where things live** table, and asks the agent to find the files and functions on the failing path, quote them **verbatim** with `file:line`, return the map rows, and flag anything near the failure that looks like a broken architecture rule. End with: *"Do not propose a fix or edit anything; only locate and quote the relevant code."*

### 3. Diagnose the root cause and write a failing test

```
Agent({ description: "Diagnose <bug>", subagent_type: "devflow:designer", prompt: <self-contained brief> })
```

Start the brief with **"Bug mode."** and paste, verbatim: the confirmed repro and expected/actual behaviour; any traceback; the **Where things live** table and the whole **Architecture rules** section; the excerpts and map rows from step 2; whether the bug escaped a release (and which); and: *"Find the ROOT CAUSE, not the symptom. Write a test that FAILS on the current code and will PASS once fixed. Do NOT write the fix. Produce the sections in your instructions, and if this is an escape, name the check that should have caught it."*

Present the diagnosis and fix plan to the user; proceed once they're on board. Use a task list for the concrete changes.

### 4. Fix and verify

```
Agent({ description: "Fix <bug>", subagent_type: "devflow:implementer", prompt: <self-contained brief> })
```

The brief includes, verbatim: the root cause and fix plan; the failing test to add; the whole **Architecture rules** section (the fix must not trade one violation for another); the **Verify**, **Edit bounds** and **See it working** sections; the escape line and its check, if any; and: *"Apply the fix and add the failing test, then run every Verify command and the repro; at most two fix rounds after the first run, then stop and report what is still red. Do not commit or push. Report files changed, the regression test going red to green, the final suite result, and a one-line repro-gone note."*

When the agent returns, **verify before moving on**. Run `git diff` and the main test command yourself, then check:

- [ ] The regression test actually fails on the old code and passes on the fix (not a test written to trivially pass).
- [ ] The fix addresses the root cause from step 3, not just the symptom.
- [ ] Every rule in **Architecture rules** holds in the changed code.
- [ ] Edits stay inside **Edit bounds**.
- [ ] The map entry is updated; an escape has its § Escapes line and its check.
- [ ] For a UI bug, the broken state and each state the plan names have a screenshot, or the report says why not.

### 5. Review before commit

```
Agent({ description: "Review fix for <bug>", subagent_type: "devflow:reviewer", prompt: <self-contained brief> })
```

The brief includes, verbatim: the bug and repro; the root cause and plan; the full `git diff`; the whole **Architecture rules** section; the map rows; and: *"Diff mode. Review ONLY the diff and the files it modifies. Confirm the change fixes the stated root cause, that the regression test genuinely covers the bug, and that no architecture rule is broken or new regression introduced. Do NOT edit anything. Report BLOCKERS, SUGGESTIONS and OK. If there are no blockers, end with 'READY TO COMMIT'."*

BLOCKERS get one more round, then stop and report.

### 6. Commit and push

As in `add-feature` step 6: match the commit style, stage by path, attribution lines from your session's instructions, push per the project's rules, watch CI on the pushed commit, and set the plan step's Status row to `done` with the hash.

### 7. Report back

Tell the user, briefly: what was broken and the root cause, the fix and which files changed, the regression test added, the escape line if any, the commit hash, whether CI went green, any `**Gate:**` still waiting and what the maintainer has to do, and anything to watch for.
