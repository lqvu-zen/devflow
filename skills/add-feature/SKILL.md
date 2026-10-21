---
name: add-feature
description: 'Add or improve a feature the devflow way, end to end: understand, locate the code with a Haiku agent, design with a fresh Opus agent, implement and test with a Sonnet agent, review with a fresh Opus agent, then commit and push, checked against the project''s behaviour map and architecture rules from .claude/devflow.md. Use whenever the user wants a NEW capability or an improvement to an existing one (a setting, a button, a command, a column, an endpoint, UX polish, edge-case handling, performance, a small refactor), even when they just describe the behaviour they want without saying "feature". Also use for a release-plan step that is not a bug. Do NOT use it to fix a reproducible bug or crash (use fix-bug), to cut a release (use release), or for status and planning (use secretary).'
---

# Adding or improving a feature

Adding a feature is not just "write the code". A change that ignores the project's architecture rules, its data and migration rules, or its dependency direction can look correct and still break the running product or a user's data. So this workflow front-loads understanding and ends with real verification, the product actually working and the tests actually passing, before anything is committed.

Work through the phases in order. Don't skip the test or review phase to save time; a feature that isn't verified isn't done.

## The project profile

Everything specific to this project is in **`.claude/devflow.md`**. Read it first. Its sections, by exact heading, are what the phases below paste into briefs:

- **Project**: what it is, the repo, the main branch, the maintainer.
- **Where things live**: the table the locator starts from.
- **Architecture rules**: the canonical list. Paste it **whole and verbatim** wherever a brief below says "the architecture rules"; a partial list is how a rule quietly gets dropped.
- **Verify**: the commands that must pass.
- **Edit bounds**: what the implementer may and may not edit, and what is never staged.
- **Escalate**: areas where the implementer runs on Opus.
- **See it working**: how to see a change working without touching real data or the maintainer's screen.

If `.claude/devflow.md` is missing, stop and tell the user to run `/devflow:setup` first.

**You are the orchestrator.** You own the conversation with the user, the delegation below, the verification of everything you delegate, and the commit decision. You do **not** design the feature, write the implementation, run the tests, or review the final diff yourself. Each of those goes to a fresh subagent with a pinned model, because an independent agent has no anchoring from this conversation and catches assumptions you've already absorbed. Your own job is steps 1 and 2 (gather context), then spawning, verifying and committing. Keep this separation even for small features.

## Who does each phase

| Phase | Runs as | Model (set in the agent file) | Why |
|---|---|---|---|
| 1. Understand | orchestrator (you) | session model: run from Sonnet | Owns the conversation; needs sound judgment, not peak reasoning. |
| 2. Locate code | `devflow:locator` | Haiku | Cheap, fast search; returns the code excerpts the design brief needs. |
| 3. Design | `devflow:designer` | Opus, high effort | Hardest reasoning: architecture fit, edge cases, the smallest correct change. |
| 4. Implement / test / fix | `devflow:implementer` | Sonnet (Opus, medium effort, when escalated) | Strong coder; fast and economical across the many tool calls in the fix loop. |
| 4b. Verify | orchestrator (you) | session model | Re-runs tests and walks the checklist; the real gate is the step-5 review. |
| 5. Review | `devflow:reviewer` | Opus, high effort | Fresh eyes: catches correctness and architecture-rule bugs the implementer missed. |
| 6. Commit & push | orchestrator (you) | session model | Mechanical. |
| 7. Report | orchestrator (you) | session model | Light summarization. |

Each agent file's frontmatter sets that role's model and effort, so don't pass `model` or `effort` in the calls below except to escalate. The orchestrator phases run on whatever model drives this session, so **run this skill from a Sonnet session**. Opus as orchestrator works too, but it is slower and costlier for no gain on the mechanical phases.

**Escalate the implementer** to Opus at medium effort when a mistake is expensive or the fix loop will be deep, which means any area **Escalate** names (data migrations, packaging, concurrency and security are the usual ones):

```
Agent({ description: "...", subagent_type: "devflow:implementer", model: "opus", effort: "medium", prompt: <brief> })
```

**If the `devflow:*` agent types aren't listed**, fall back to `subagent_type: "general-purpose"`. Pin the same model (`haiku`, `opus`, `sonnet`, `opus`), pass `effort: "high"` for the designer and reviewer, and paste that role's instructions from the plugin's `agents/<name>.md` (two folders up from this skill's base directory) at the top of the brief.

**When the work is a step from a release plan** (in the plans folder, `docs/plans/` unless `.claude/devflow.json` names another), paste the whole step section verbatim, from its `### N —` heading to the next heading, into the design, implement and review briefs. That includes its **Needs** and **Done when** lines and its `**Tried:**` line, if it has one. Tell the designer to read Tried and not repeat an approach it lists unless it says why this time is different. The reviewer checks every "Done when" item, and the step isn't finished until each one is met or marked "needs a human". Report the "needs a human" items to the user.

## The behaviour map (`docs/BEHAVIOUR.md`)

Most behaviours show up in several places: different layouts, list and detail views, the UI and the command line or API, one kind of item and another. A change that reaches one place and not the others is how "working on A breaks B" happens. `docs/BEHAVIOUR.md` lists, per area, each behaviour, **every surface** it appears on, and the test that guards it (or **untested**). Use it in every phase:

- **Locate (step 2):** the locator returns the map rows for the area(s) the change touches, verbatim, with their IDs.
- **Design (step 3):** paste those rows into the brief. The plan lists **every surface** the change touches, from the map, and says how each one is kept working.
- **Implement (step 4):** the implementer adds or updates the map entries (a new behaviour gets a new entry) and checks every surface listed.
- **Review (step 5):** the reviewer checks each listed surface, not only the one in the task, and that the map was updated. A surface left unchecked, or a missing entry, is a blocker.
- **Commit (step 6):** `docs/BEHAVIOUR.md` goes in the same commit as the change.

If the project has no map yet, say so in the report and suggest `/devflow:setup` to start one; don't block the feature on it.

## Before you start, and where you stop

**Claim your step before anything else.** When the work is a step of a release plan, read its Status row first. A row that says `in progress` or starts `started` is held by another tab: say so and stop, unless the maintainer says the claim is stale. Otherwise set the row to `in progress (YYYY-MM-DD HH:MM)`, commit that one line alone, by path (`git add <plan>`, then `git commit -m "Status: <release> step N in progress" -- <plan>`), and push it, before any other work. Keep the file's line endings (`git diff --stat` shows one changed line). A session that stops without finishing ("Still red", a `**Gate:**`, a second BLOCKERS) rewrites the row to say why it stopped and what is left, ending with "see Tried", so no claim goes stale; a finished step's row says `done` as usual. It also adds or extends a `**Tried:**` line under its step in the plan: one clause per approach, saying what it was and why it failed, with the path of any saved output. A later stop appends to the line and never rewrites earlier entries. The Tried line is committed with the row, by path, the same way as the claim (`git commit -m "Status: <release> step N stopped" -- <plan>`), and pushed.

**Check CI on HEAD first**, when the project has CI: `gh run list -L 3 --json conclusion,status,headSha,displayTitle` (compare `headSha` with `git rev-parse HEAD`). If the run on HEAD is red, the fix for it is the next step, ahead of the one you were asked for: say so, and carry on only when the maintainer agrees. A run still in progress is not a failure: wait for it (`gh run watch <id> --exit-status`) before you build on it. Triage a red run as in `fix-bug` ("When the bug is a red CI run") before treating it as a blocker; a flaky run is rerun once with `gh run rerun <id> --failed`, and if it goes green you carry on with your task and tell the maintainer that the flaky test's fix is the next step; the secretary adds it first in Order.

**Keep to the step's Files line.** When the plan step has a `**Files:**` line, the implementer edits, and you commit, only those files, and only within **Edit bounds**. If it needs a file the line doesn't list, it says so in its report and asks first; it doesn't edit the file quietly. Paste the Files line into the implement brief, and have the reviewer flag any changed file the line doesn't list as a blocker. A file marked "possibly" is allowed but is named in the report if it was touched. The behaviour map and the plan's own Status row are always allowed.

**Secretary edits.** Uncommitted changes to the status file or the plans folder belong to the secretary. Commit them with your next change; never revert them.

**Stop at a `**Gate:**` line.** When the plan step carries one, do the work up to the gate, then stop and tell the maintainer in plain words what they have to do (name the version, sign, install a build, tick a checklist, approve a list) before anything is committed, pushed or published past it. Never decide a gate's question yourself.

**Stop rules in the loop.** The implementer makes at most two fix rounds after its first run, then reports what is still red. If its report says "Still red", don't send it round again: report to the maintainer with the output. A reviewer's BLOCKERS get one more round (fix, re-review). If the second review still has blockers, stop and report them; don't start a third round.

## The workflow

### 1. Understand the request

Read what the user asked for and restate it to yourself in one sentence: what should the user be able to do after this ships that they can't do now? If a real ambiguity blocks the design, ask **one** focused question before anything else. Don't ask about things you can reasonably default.

This skill covers both **new capabilities** and **improvements to existing ones**. For an improvement, also pin down what's wrong with the current behaviour and what "good" looks like as a concrete, observable outcome. If the user is instead reporting something genuinely **broken**, a crash or wrong output they can reproduce, that's a bug: use `fix-bug`, which insists on a failing regression test first.

### 2. Locate the code

```
Agent({ description: "Locate code for <feature>", subagent_type: "devflow:locator", prompt: <brief> })
```

The brief gives the feature in one line plus the **Where things live** table, and asks the agent to identify the files and functions the change will touch, return the relevant code **excerpts verbatim** with `file:line` references, return the behaviour-map rows for the area, and report whether some or all of the capability **already exists**. End the brief with: *"Do not propose a design or edit anything; only locate and quote the relevant code."*

For a trivially small, obvious change you can skip the subagent and run one targeted Grep yourself. Either way, you finish step 2 holding the code excerpts, the map rows, and any "already exists" finding.

### 3. Design with a fresh Opus agent

You do not design inline.

```
Agent({ description: "Design <feature>", subagent_type: "devflow:designer", prompt: <self-contained brief> })
```

The brief must be self-contained; the designer can't see this conversation. Start it with **"Feature mode."** and paste, verbatim: the user's request (one paragraph); the **Where things live** table and the whole **Architecture rules** section; the excerpts, map rows and "already exists" findings from step 2; and: *"Design the smallest correct implementation. Do NOT write code; produce only a plan with the sections in your instructions. If something is ambiguous, list it as a question for the maintainer instead of guessing."*

Present the plan to the user and proceed once they're on board (a "go ahead" with no comment counts as approval). Use a task list so each concrete change is visible during implementation.

### 4. Implement, test and fix with a Sonnet agent

```
Agent({ description: "Implement <feature>", subagent_type: "devflow:implementer", prompt: <self-contained brief> })
```

The brief includes, verbatim: the **full approved plan**; the whole **Architecture rules** section; the **Verify**, **Edit bounds** and **See it working** sections; and: *"Read only the files in the plan plus the direct callers and callees you need. Edit only what Edit bounds allows. Implement the plan, then run every Verify command; if anything fails, fix and re-run, for at most two fix rounds after the first run; then stop and report what is still red. Do not commit or push. Report the files changed, the final test result, and a one-line smoke note."*

When the agent returns, **verify before moving on**; this is the gate, not a formality. Run `git diff` and the project's main test command yourself (cheap insurance against a green run that wasn't), then walk this checklist against the diff:

- [ ] Changes match the approved plan; nothing extra crept in.
- [ ] Every rule in **Architecture rules** holds in the changed code.
- [ ] Edits stay inside **Edit bounds**.
- [ ] `docs/BEHAVIOUR.md` has the new or updated entries, with their tests.
- [ ] The version is untouched.

If anything's off, fix it inline or send the implementer a follow-up via SendMessage. Mark each task complete only once verified.

### 5. Review with a fresh Opus agent

```
Agent({ description: "Review <feature>", subagent_type: "devflow:reviewer", prompt: <self-contained brief> })
```

The brief must include, verbatim: the original request; the approved plan; the full `git diff`; the whole **Architecture rules** section; the map rows; the plan step's Done when, if any; and: *"Diff mode. Review ONLY the diff and the files it modifies. Do NOT edit anything. Report BLOCKERS, SUGGESTIONS and OK. If there are no blockers, end with the line 'READY TO COMMIT'."*

If the reviewer reports BLOCKERS, fix them or delegate back to the implementer via SendMessage, then re-review: one more round only. Proceed only on `READY TO COMMIT`; if the second review still has blockers, stop and report them.

### 6. Commit and push

Match the existing commit style (`git log --oneline -5`). Stage only the relevant files, by path; never what **Edit bounds** says is never staged, and never `git add -A`. End the message with the attribution lines your session's instructions give, if any. Push to the main branch when the project's rules or the user's standing preferences say so; otherwise ask.

Then watch CI on the pushed commit: `gh run list -L 1 --json databaseId,headSha` to find its run, and `gh run watch <id> --exit-status`. A red run makes its fix the next step, ahead of anything else; say so in the report.

If this was a plan step, set its Status row to `done`, with the commit hash and one line on what landed, in the same commit or a `docs`-only one straight after.

### 7. Report back

Tell the user, briefly: what was added and where it shows, which files changed, the commit hash, whether CI on it went green, any `**Gate:**` line that still waits for the maintainer and what they have to do, the "needs a human" items, and any known limitation or follow-up worth doing next.
