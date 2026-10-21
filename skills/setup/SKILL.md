---
name: setup
description: 'Adopt devflow in a project: read the codebase, draft the project profile (.claude/devflow.md) and guard config (.claude/devflow.json), start the behaviour map (docs/BEHAVIOUR.md), the status file and the plans folder, add the permission rules and the CI check, and confirm each with the maintainer before writing. Use when the user says "/devflow:setup", "set up devflow here", "use the RYOS workflow in this project", "adopt devflow", or when a devflow skill stopped because .claude/devflow.md is missing. Also use to refresh an out-of-date profile ("update the devflow profile"). Do NOT use it for feature, bug, release or status work once the profile exists.'
---

# Setting up devflow in a project

devflow's skills and agents know the method; this project's facts go in two files that you write here:

- **`.claude/devflow.md`**, the profile, read by every skill and agent. Its headings are fixed: **Project**, **Where things live**, **Architecture rules**, **Verify**, **Edit bounds**, **Escalate**, **See it working**, **Release**, **Try it**, **Standing rules**.
- **`.claude/devflow.json`**, the guard and CI config. The hooks act only in a project that has it.

Templates for everything are in the plugin's `templates/` folder, two folders up from this skill's base directory. Copy their structure; fill them with this project's facts.

**Write nothing until the maintainer has seen the drafts.** The profile becomes the contract every agent works to, so a wrong rule is worse than a missing one.

## 1. See what is already there

Check, and report in a few lines:

- `.claude/devflow.md`, `.claude/devflow.json`: if they exist, this is a refresh. Read them, and change only what the maintainer asks for or what is now wrong.
- `docs/BEHAVIOUR.md`, `docs/STATUS.md`, `docs/plans/`, `docs/archive/`: keep and reuse what exists.
- `.claude/skills/`, `.claude/agents/`, `.claude/hooks/`, `.claude/settings.json`: a project with its own workflow skills, agents or guard hooks (as RYOS has) would run both. Say which overlap, and ask whether devflow replaces them here or the project keeps its own and devflow stays off (the plugin can be disabled per project in `.claude/settings.json`: `"enabledPlugins": {"devflow@devflow": false}`).
- `CLAUDE.md`, `README.md`, `CONTRIBUTING.md`, architecture docs: read them; most of the profile comes from here.

## 2. Read the codebase, narrowly

Enough to fill the profile with evidence, not a full audit:

- The build and dependency files (`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `CMakeLists.txt`, `*.csproj`, ...) for the stack, the entry points and the test, lint and type commands.
- The test folder and how tests are run in CI (`.github/workflows/*.yml` or the equivalent).
- The top-level source layout: one line per module or folder for **Where things live**.
- `git remote -v`, the default branch, `git tag -l` and `gh release list` for **Release**.
- Where the product keeps user data at run time (config folders, databases, `%APPDATA%`, `~/.local/share`, ...) and what turns off side effects in tests (env vars for notifications, telemetry, registry, network). These are the guard's **real_data** and the **See it working** rules.
- Secrets: key files, `.env`, signing tools. These are **secret_dirs**, **secret_extensions** and **maintainer_only**.

## 3. Ask what the code can't say

One `AskUserQuestion` call, at most four questions, only those whose answers you couldn't find. Usually:

- the maintainer's name and time zone (for the decision log);
- whether the project ships releases, and through what (GitHub releases, a package registry, a store);
- if it ships through GitHub releases: whether its release gate can write a pass stamp (a JSON file with the full HEAD SHA, the SHA-256 of the artifact checksum file and the case count, written only when every case passes and deleted when a run or build starts);
- where the real user data lives, if the code doesn't make it obvious;
- which areas are risky enough to escalate (migrations, packaging, concurrency, security, payments).

## 4. Draft, show, then write

Draft each file and show it to the maintainer before writing it. Keep the drafts honest: mark anything you inferred rather than read with "(inferred, please check)".

1. **`.claude/devflow.md`** from `templates/devflow.md`.
   - **Architecture rules**: only rules the code or docs actually show, each with its *why*. Five true rules beat fifteen guesses. Always include "don't touch the version" and the comment rule the project follows.
   - **Verify**: commands you ran and saw pass (run each once now). Say which ones you couldn't run.
   - Leave **Release** and **Try it** out if the project doesn't ship releases; the `release` skill stops when they are missing.
2. **`.claude/devflow.json`** from `templates/devflow.json`:
   - `name`, `maintainer`, `main_branch`, `status_file`, `plans_dir`;
   - `guard.real_data`: every place real user data lives, with env-var forms (`%APPDATA%/App`, `~/.local/share/app`);
   - `guard.secret_dirs`, `guard.secret_extensions`, `guard.maintainer_only` (scripts only the maintainer runs, with the subcommands that matter, e.g. `sign`);
   - `guard.app`: the commands and Python modules that start the product, the harmless arguments (`--version`, `--help`), `isolate_env` (the variables that must point at a scratch folder in the same command) and `data_folder` (the product's folder inside that variable). Leave `isolate_env` empty to refuse starting the product at all. Leave `app` out for a library;
   - `guard.self_guarding_scripts`: the project's own harnesses that protect real data themselves;
   - `guard.release_stamp` (`path`, `binds`, optional `gate`): only if the gate writes a stamp, or the maintainer wants it added to the gate now; the guard then refuses to publish a release without a stamp for the current HEAD and the current hash of `binds`. If the gate can't write one, leave the key out: publishing stays an ask. Record the choice in **Release** under **Stamp**;
   - `checks.version_files` (path and a regex whose group 1 is the version; `numbers_only` for files that take `X.Y.Z` only) and `checks.no_new_python_comments` (folders, Python only).
3. **`docs/BEHAVIOUR.md`** from `templates/BEHAVIOUR.md`. Start small and true: the surfaces the product really has, and the main areas with a few rows each, every row with the test that guards it today or **untested**. Tell the maintainer the map grows with every change from here on and that they should review it.
4. **`docs/STATUS.md`** from `templates/STATUS.md`, and an empty `docs/plans/` and `docs/archive/` (a `.gitkeep` each). Skip any that already exist.
   - **`docs/PROMPTS.md`** from `templates/PROMPTS.md`, the prompt book, with the project's name, repo and tab names filled in. Keep the `{braces}` as they are: they are filled in when a prompt is pasted. An existing `docs/PROMPTS.md` is kept as it is.
5. **`.claude/settings.json`**: merge `templates/settings.json`'s `ask` and `deny` lists into the existing file, keeping everything already there. Change `docs/STATUS.md` and `docs/plans` in the deny rules if `status_file` or `plans_dir` differ. New `ask` and `deny` rules need the maintainer's approval: list them and wait for a yes.
6. **CI**, if the project has GitHub Actions and `checks` has anything in it: copy the plugin's `tools/devflow_checks.py` to `tools/devflow_checks.py` in the project, and add the job in `templates/ci-devflow.yml` to the main workflow.
7. **`CLAUDE.md`**: add the section in `templates/CLAUDE-section.md` (create the file if there is none). Don't rewrite the rest of it.

## 5. Check it works

- Run the session-start hook by hand and show its output:
  `CLAUDE_PROJECT_DIR="$PWD" uv run --no-project python "<plugin>/hooks/session_start.py"`
- Feed the guard a command it must refuse and one it must allow, and show both results:
  `echo '{"tool_name":"Bash","tool_input":{"command":"git reset --hard"}}' | CLAUDE_PROJECT_DIR="$PWD" uv run --no-project python "<plugin>/hooks/guard.py"; echo "exit $?"`
  (exit 2 means refused). Also one that writes into a `real_data` folder, and one that starts the product without `isolate_env`, if configured.
- If `tools/devflow_checks.py` was added: `uv run --no-project python tools/devflow_checks.py version --head HEAD` passes.

## 6. Commit

Ask before committing. Stage only the files you wrote, by path, in one commit titled `Adopt devflow`, ending with the attribution lines your session's instructions give. Push only if the maintainer says so.

Then tell the maintainer, in a few lines: what was written, what you inferred and they should check, the rules that need their eye (the architecture rules, the real-data folders, the new `ask` and `deny` rules), and the next step: `/devflow:secretary` to start the first plan, or `/devflow:add-feature` / `/devflow:fix-bug` for the work at hand.
