# Model board

Every agent call in the skills passes a model and effort worked out from five layers: the agent's pin, the user's `default_models` plugin setting, the project's `models` board in `.claude/devflow.json`, a plan step's Model line, and a design's parts. This doc covers how `tools/model_check.py` folds those layers into one row per role, how the skills and session start read it, and how a finished session is checked against it. Read it before adding a role or a phase, changing a floor, or changing what a skill passes on a call.

## Flow

1. **Pins.** [`load_pins`](../../tools/model_check.py) reads `model` and `effort` from each agent file's front matter in the base's `agents/`; [`load_all_pins`](../../tools/model_check.py) adds each `--extra-agents` folder (a domain plugin's), where the base wins a clash.
2. **Defaults.** [`board_defaults`](../../tools/model_check.py) gives each key in [`BOARD_KEYS`](../../tools/model_check.py) its default: an agent role takes its pin, a phase key (`designer.diagnosis`, `implementer.escalate`) takes its entry in [`PHASES`](../../tools/model_check.py), and a key with no agent (`orchestrator`, `manage-project.readers`) takes its entry in [`GENERAL`](../../tools/model_check.py).
3. **User defaults.** [`read_user_defaults`](../../tools/model_check.py) takes the raw `default_models` text from the plugin's option variable when it is set, else from `pluginConfigs` in the user settings file ([`default_user_settings`](../../tools/model_check.py)), and [`parse_user_defaults`](../../tools/model_check.py) splits it into entries and `ignored` texts. For a key the board gives no entry, [`board_rows`](../../tools/model_check.py) applies the user's value with source `user`.
4. **The board.** [`read_board`](../../tools/model_check.py) keeps the known keys, skips `default` (so the user's default shows through), and names everything else `ignored`. [`board_rows`](../../tools/model_check.py) parses each value with [`parse_board_value`](../../tools/model_check.py) (a model alone keeps the default's effort) and holds it at its floor through [`_floor_of`](../../tools/model_check.py). A user default goes through the same two functions.
5. **Model lines and parts.** In the same [`board_rows`](../../tools/model_check.py), each `--model` line, parsed by [`parse_model_line`](../../tools/model_check.py), goes over the board for every key of its role, unless [`refusal`](../../tools/model_check.py) or the diagnosis floor stops it (`not followed`). Each `--part` adds an `implementer part N of M` row.
6. **What a call passes.** [`pass_text`](../../tools/model_check.py) is `nothing` when the row equals the pin (the agent file already sets it), the session model for the orchestrator, and otherwise the `model:` and `effort:` to pass.
7. **Readers:**
   - `--board` prints the rows through [`format_board`](../../tools/model_check.py), which the skills run before their agent calls, with a `user defaults:` line saying where they were read;
   - session start prints a one-line [`board_summary`](../../tools/model_check.py), with [`orchestrator_note`](../../tools/model_check.py) when the session's model is not the board's or the user's orchestrator;
   - the plan runner's [`orchestrator_model`](../../tools/plan_runner.py) takes the orchestrator row, user default included;
   - check mode turns the rows into expectations with [`expectations_from`](../../tools/model_check.py) (`--escalated` and `--diagnosis` pick the phase rows), reads each agent call from the transcripts with [`agent_calls`](../../tools/model_check.py), and marks each one with [`judge`](../../tools/model_check.py).

## Invariants

- **The locator, reviewer and planner never go below their pins, and `fix-bug`'s diagnosis never below Opus, medium.** A board entry below is held at the floor and shown as `floor (board said …)`, a user default below it as `floor (your default said …)`; a Model line below is `not followed`. Only the roles in [`MAY_MOVE_DOWN`](../../tools/model_check.py) may go lower. This is the quality floor for the read-only judging roles.
- **No default is above Opus, medium.** Pins, phase defaults, general defaults and the diagnosis floor stay at or below it; a board entry, Model line or part may go higher. `TestRealPins.test_no_default_is_above_opus_medium` checks every default, and `tests/test_skills.py` checks the prose.
- **One edit moves every call.** The skills never write a model literally on an agent call; they pass what `--board` prints for the role. A literal would leave that call behind when the board or a pin changes.
- **A missing agent is `not installed`, never a mismatch.** A board role whose agent has no pin in any folder read (a domain plugin not installed) passes nothing, and its calls are judged `not installed` ([`missing_agents`](../../tools/model_check.py)).
- **The board has no effect on the guard.** `models` is read only by `model_check`; `TestBoardKey` in `tests/test_guard.py` shows a board changes no verdict.

## Recipe

Adding a board role or phase:

1. Add the key to [`BOARD_KEYS`](../../tools/model_check.py) in the order the board shows it, and to [`PHASES`](../../tools/model_check.py) or [`GENERAL`](../../tools/model_check.py) when it is not an agent's own role.
2. Add it, as `default`, to the `models` board in `templates/devflow.json` and devflow's own `.claude/devflow.json`; `TestRealPins.test_the_shipped_boards_are_all_default_and_parse_clean` requires both to list every key in order.
3. Name what the skill passes on that call by the row, not a literal, in every skill that makes the call, in the same words (`TestModelRules` in `tests/test_skills.py`).
4. Test the default, a board move, any floor and the check-mode verdict with the board fixtures in `tests/test_model_check.py`, and update the model rows of `docs/BEHAVIOUR.md`.

## Gotchas

- **Board values name the family, not the model id.** `opus`, `sonnet` or `haiku`; [`family`](../../tools/model_check.py) maps the ids found in transcripts onto those names, so a full id on the board is `ignored`.
- **The orchestrator takes a model only.** It runs on the session model set with `/model`, so a board value with an effort is ignored for it, and nothing can be passed for it on a call.
- **A part replaces an implementer Model line.** Giving both is refused, and a part for any role other than the implementer is refused.
- **The Bash tool gets no plugin option variables.** Hooks receive `CLAUDE_PLUGIN_OPTION_*`, but a `model_check` run from a skill does not, so it reads `pluginConfigs` in the user `settings.json`; where the variable is set, it wins over the file. A read failure gives a note on the `none set` label and no defaults, never an error.
- **A board entry blocks the user's default even when it cannot be parsed.** The key falls to its pin, and the board entry is named `ignored`.
- **Tests must not read the real user settings.** The test modules that reach this code point `CLAUDE_CONFIG_DIR` at an empty folder and remove the option variables for the whole module.

## Flagged / unverified

- The `pluginConfigs` key a real marketplace install or `--plugin-dir` writes (the code takes the keys starting `devflow@`, preferring one `enabledPlugins` marks `true`), and what an unset `${user_config.…}` renders as, are not checked against a real Claude Code.
