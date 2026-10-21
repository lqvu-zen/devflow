# <Project> prompt book

Paste-ready prompts for running <Project> with the devflow team. Replace anything in `{braces}`. Kept by the secretary (`/devflow:secretary`) next to `docs/STATUS.md`; it adds a prompt when a new one proves useful.

**Which tab, which model:**

| Tab | Model and effort | For |
|---|---|---|
| Secretary | Sonnet | `/devflow:secretary`: status, issues, decisions, plan steps |
| Coding | Sonnet (high effort for the release test phase and releases) | one plan step per fresh tab |
| Planning | Opus, high effort | a whole release plan, a big design question |

Open a new tab for each session. Switch the model from the model picker under the prompt box.

---

## 1. Starting a session

**Secretary, in Claude Code (once the plugin is installed):**
```
/devflow:secretary
```

**Secretary, in claude.ai or a Claude Code tab without the plugin:**
```
You're my <Project> secretary: not the planner, and you never write code.
You keep docs/STATUS.md (decisions, open items, issues) and add plan steps
to docs/plans/ when I decide something. Read docs/STATUS.md, then check
git log, gh issue list -R <owner/name> and the current plan's Status table
for anything newer, and tell me where we are.
```

**Coding: continue the plan** (one fresh tab per step):
```
Read docs/STATUS.md to find the current plan, then continue with its next open step in Order that is not already in progress. Claim it first, and update the Status table when it's done.
```

**Coding: a second tab beside another** (the session-start hook lists what is in progress):
```
Do step {N} of docs/plans/release-{X.Y.Z}.md. If its Status row says in progress,
stop and tell me. Otherwise claim it first, work and commit only in the files the
step's **Files** line names, and update the Status table when it's done. If the
step needs any other file, stop and tell me before touching it.
```

**Coding: one specific step:**
```
Do step {N} of docs/plans/release-{X.Y.Z}.md. Paste the step and its
"Done when" into every agent brief. Update the Status table when it's done.
```

---

## 2. Planning (secretary tab, unless marked)

**What should we do this week?**
```
What should we do this week? Check what's open in the current plan, new
GitHub issues and anything waiting on me, and propose an order. Don't start
a new release plan.
```

**A new feature idea:**
```
I want {feature, in a sentence or two}. Is it worth it, and does it belong
in the current release or the next? Give me your recommendation, then add it
as a plan step once I agree.
```

**Check GitHub issues:**
```
Check the GitHub issues opened or updated since the last status update and
triage them into the plans. Ask me before adding anything.
```

**User feedback:**
```
A user said: "{feedback}". What do you think, and what should we change?
Log it in the status file, and draft a short reply I can send.
```

**Log a decision:**
```
Decision: {decision}. Log it, update the plans it affects, and give me the
prompt for the coding session.
```

**Turn a brief into a plan** (planning tab on Opus at high effort, or the secretary calling `devflow:planner`):
```
Turn {docs/plans/release-X.Y.Z-brief.md} into docs/plans/release-{X.Y.Z}.md, in
the format of {the latest plan in docs/archive/, or templates/plan.md}. Check every
step against the code and docs/BEHAVIOUR.md, and give each a Files line. Give me
the open questions, each with your recommended answer, before writing the file.
```

**The next release after the current one:**
```
{X.Y.Z} has shipped. Close its plan (Status complete, issues closed),
archive it to docs/archive/, and draft the next release from what's
parked, the behaviour map's untested rows and open issues. Ask me what
goes in.
```

---

## 3. Building (coding tab)

**A feature that isn't in a plan yet (small):**
```
/devflow:add-feature {what the user should be able to do}. Read the relevant
docs/BEHAVIOUR.md entries first and check every surface they list. Add or
update the map entry with its test.
```

**A bug report:**
```
/devflow:fix-bug GitHub issue #{N}: {one-line summary}. Reproduce it first.
Check every surface the docs/BEHAVIOUR.md entries list, add the regression
test and the map entry, and reference #{N} in the commit.
```

**Work in an Escalate area:**
```
{Feature or bug prompt from above.} This touches {an area the Escalate section
of .claude/devflow.md names}: escalate the implementer to Opus at medium effort.
```

**An independent review of work that already landed:**
```
Use devflow:reviewer in diff mode to review {commit range, e.g. v1.2.0..HEAD}
against docs/plans/release-{X.Y.Z}.md and docs/BEHAVIOUR.md. Report
blockers only; fix nothing.
```

**Behaviour map upkeep:**
```
Check docs/BEHAVIOUR.md against the code changed since {commit or tag}: add
missing entries, update the surfaces, and list new "untested" entries.
Don't change code.
```

---

## 4. Testing

**Tester agent on a release candidate** (coding tab, high effort):
```
Run devflow:tester on the {vX.Y.Z-rcN} artifacts, following Try it in
.claude/devflow.md: every change since {last tag}, each relevant download.
Report PASS or FAIL per flow, with screenshots for failures.
```

**Report what you found while using a release candidate** (secretary tab):
```
While using {vX.Y.Z-rcN} I found: {what happened, steps, which download}.
File it as a GitHub issue, triage it, and tell me whether it blocks
promotion.
```

---

## 5. Releasing (coding tab, high effort)

**Start a release candidate:**
```
/devflow:release Start the release candidate for {X.Y.Z}: the gate from the
Release section of .claude/devflow.md, then publish v{X.Y.Z}-rc1 as a GitHub
pre-release, then run devflow:tester. Give me the manual checklist. Stop
there; don't promote.
```

**Promote after the candidate days:**
```
/devflow:release I've used v{X.Y.Z}-rc{N} for {days} days and ticked the
checklist: {anything worth noting}. Promote the same commit to v{X.Y.Z}:
the gate, then the release review (READY TO PUBLISH), then publish.
Close the issues the notes name.
```

**A new candidate after a fix:**
```
/devflow:release rc{N} had {problem}, now fixed in {commit}. Cut
v{X.Y.Z}-rc{N+1} through the same flow.
```

**Something is wrong with a published release:**
```
v{X.Y.Z} has {problem}, affecting {who}. First tell me the options (mark it
pre-release so update checks skip it, or a {X.Y.Z+1} hotfix), and what each
means for people who already updated. Don't touch the release until I
choose.
```

---

## 6. Upkeep (coding tab unless noted)

**A UI review:**
```
/devflow:review-web-ui Review {page or screen} at phone and desktop width.
Findings first; change nothing until I agree.
```

**Tech debt check-in:**
```
Compare the newest docs/tech-debt-*.md (if there is one) with the code today.
What's fixed, what's new, and the top three worth doing next. Score every
item by priority = (Impact + Risk) × (6 − Effort), each of Impact, Risk and
Effort from 1 to 5, and show the three numbers beside each score. Write it as
a new dated tech-debt doc and mark the old one superseded.
```

**Docs cleanup:**
```
Audit docs/ and the repo root for superseded or finished documents. Propose
remove, archive or keep for each, and fix links in the same commit once I
agree.
```

**Dependency updates:**
```
Check for newer versions of {the dependencies, or "all of them"}. Tell me what
changed that matters to <Project> and the risk of upgrading. Upgrade only what
I approve, then run every Verify command and the release gate.
```

---

## 7. Housekeeping

**Too much context in a coding tab:** finish the current step, then open a new tab with the "continue the plan" prompt from section 1.

**A secretary edit got reverted** (coding tab):
```
The secretary's edit to {file} was reverted. Restore it from {where} and
commit it; secretary edits to docs/STATUS.md and docs/plans/ are always
committed, never reverted.
```

**Where did this decision come from?** (secretary tab):
```
Why did we decide {thing}? Find it in the decision log, and the commit or
plan step that carried it out.
```
