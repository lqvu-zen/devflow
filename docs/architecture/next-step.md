# Next step

One decision, which plan step runs next, is made in one place and read by three: the session-start summary, `--next-step` (which the `next-step` skill runs), and the plan runner, which starts one headless session per step. This doc covers how a plan file is read, how the step is chosen, and how the runner judges a session afterwards. Read it before changing the plan format (`templates/plan.md`), what blocks a step, or what the runner stops on.

## Flow

1. **Finding the plans.** [`current_plan`](../../hooks/session_start.py) takes the plan the status file names as current, and [`next_plan`](../../hooks/session_start.py) the first other plan path in a status-file table row. [`archived_plans`](../../hooks/session_start.py) adds archived plans, which only answer another plan's `Needs`.
2. **Reading a plan.** [`read_plan`](../../hooks/session_start.py) builds a [`PlanView`](../../hooks/session_start.py) from the sections that [templates/plan.md](../../templates/plan.md) defines: [`step_order`](../../hooks/session_start.py) reads the numbers in the `Order` section, [`step_states`](../../hooks/session_start.py) the `Status` table, [`who_rows`](../../hooks/session_start.py) the `Who does what` table, and [`step_sections`](../../hooks/session_start.py) each `### N` step's body, from which [`step_field`](../../hooks/session_start.py) takes `**Gate:**`, `**Needs**` and `**Files:**`.
3. **Choosing.** [`choose_step`](../../hooks/session_start.py) walks the current plan's open, unclaimed steps in Order (a Status row not starting `done`, `✅` or `not needed` is open; one starting `started` or `in progress` is claimed). For each, [`blockers`](../../hooks/session_start.py) lists why it cannot start:
   - claimed by another tab;
   - a Gate that [`_open_gate`](../../hooks/session_start.py) finds uncleared, or a design-stop Gate that [`_held_gate`](../../hooks/session_start.py) finds stopped;
   - a `Who does what` row that [`runner`](../../hooks/session_start.py) does not map to `add-feature` or `fix-bug` for a coding session (by hand, the project manager, another plugin's skill, a moved skill);
   - a `Needs` step not done ([`needs`](../../hooks/session_start.py) reads own numbers, `plan-N` tokens and "every");
   - for a step of the next plan only, a `Files` line that [`overlaps`](../../hooks/session_start.py) a step in progress in either plan.

   Only the first candidate in Order can be taken, and only when nothing blocks it. When the first candidate is blocked but a later one is not, it does not skip ahead: it stops on the first, saying why. When none of the current plan can start, it takes the next plan's first ready step, marked `fallback`.
4. **Readers.**
   - [`plan_lines`](../../hooks/session_start.py) prints the summary's plan lines from the same [`Choice`](../../hooks/session_start.py);
   - [`next_step_lines`](../../hooks/session_start.py) prints `Plan:`, `Step:`, `Run:` or `Stop: … Next: …`, adding `Design:` when the Gate is cleared and the design file from [`design_file`](../../hooks/session_start.py) exists;
   - the runner's [`ask_next_step`](../../tools/plan_runner.py) runs `session_start.py --next-step` as a subprocess and parses those lines.
5. **The runner's loop.** [`run_plan`](../../tools/plan_runner.py) asks for the next step, starts one session for it, and then [`step_outcome`](../../tools/plan_runner.py) judges it: the usage limit, a timeout, the step's Status row read back with [`row_state`](../../tools/plan_runner.py) (missing, waiting for the maintainer's yes, or still open), changes beyond the status and plan files ([`foreign_changes`](../../tools/plan_runner.py)), the branch, and CI on the new HEAD ([`ci_conclusion`](../../tools/plan_runner.py)). Anything but `done` ends the run; a step offered twice ends it too. Permission asks the session could not answer stop nothing by themselves: [`denial_clause`](../../tools/plan_runner.py) adds them to the reason of any stop from the row check on, and a `done` step lists them under it ([`refusal_lines`](../../tools/plan_runner.py)) while the run goes on. Each step's start line carries the local time with its offset from [`started_stamp`](../../tools/plan_runner.py), and a usage-limit stop from [`limit_stop`](../../tools/plan_runner.py) ends with advice to resume the cut-off session or run the plan again.

## Invariants

- **One decision, three readers.** The summary, `--next-step` and the runner must never disagree about the next step, so none of them re-implements the choice: the summary and `--next-step` call [`choose_step`](../../hooks/session_start.py), and the runner reads `--next-step`'s output rather than the plan.
- **The runner never writes the plan, except one row.** The session it starts claims and updates its own row. The only write is [`mark_for_retake`](../../tools/plan_runner.py): when the usage limit cuts off a claimed step, and only while the row still reads exactly the claim the session left.
- **Only the Status table says done.** The runner trusts a step's Status row, not the session's own result, and then checks the tree, the branch and CI itself. A refused permission ask does not override a done row; those checks still apply.
- **The plan's headings are a contract.** `Order`, `Status`, `Who does what` and the `### N` step headings with their bold fields are read by exact name; renaming one in `templates/plan.md` silently makes every plan unreadable (`couldn't read the Order and Status`).

## Recipe

Adding a reason a step cannot start:

1. Add it to [`blockers`](../../hooks/session_start.py) with a reason phrase, and map that phrase to what the maintainer does next in [`next_action`](../../hooks/session_start.py).
2. Test it in `TestNextStep` (`tests/test_session_start.py`) for both plans, the current one and the fallback, and through `--next-step` in `TestMain`.
3. When the runner should stop on it differently, add a case to `TestStops` in `tests/test_plan_runner.py`, which drives a fake `claude`.

## Gotchas

- **Files overlap is checked only for the next plan's steps.** A current-plan step is never held back because a step in progress names the same files; only a fallback step from the next plan is, and a step there with no `Files` line is held back too.
- **The behaviour map, the changelog and the status and plan files are left out of the Files comparison** ([`step_files`](../../hooks/session_start.py)), because every step may touch them.
- **Gate wording matters.** A Gate is cleared only by a `Cleared YYYY-MM-DD` clause; a Gate saying "at the design stop" or "before implementation" lets the step start and stop itself at the design, and a row `stopped` there holds it until the maintainer answers.
- **The start line is read twice.** Its text up to `...` is read exactly by WF-27's tests, and its `(started …)` stamp by `run-plan`'s mid-run answer, which subtracts it from `date "+%Y-%m-%d %H:%M:%S %z"`; change the format in both or neither.

- **The output setting only drops summary lines.** [`output_mode`](../../hooks/session_start.py) chooses `full`, `short` or `off` for the session-start summary; it never changes which step is chosen, and `--next-step` ignores it, so the runner sees the same lines whatever the user set.
- **The runner's model can come from the user.** [`orchestrator_model`](../../tools/plan_runner.py) takes the board's `orchestrator`, else the user's `default_models` orchestrator; see [model-board.md](model-board.md).
- **A refused command did not run.** A `done` step with refusals relies on the session's own row plus the runner's tree, branch and CI checks; a refused push shows up as CI missing on HEAD.

## Flagged / unverified

- None.
