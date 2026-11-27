---
name: setup
description: 'Adopt devflow in a project: read the codebase, draft the project profile (.claude/devflow.md) and guard config (.claude/devflow.json), start the behaviour map (docs/BEHAVIOUR.md), the status file and the plans folder, add the permission rules and the CI check, and confirm each with the maintainer before writing. Use when the user says "/devflow:setup", "set up devflow here", "use the RYOS workflow in this project", "adopt devflow", or when a devflow skill stopped because .claude/devflow.md is missing. Also use to refresh an out-of-date profile ("update the devflow profile"). Do NOT use it for feature, bug, release or status work once the profile exists.'
---

# Setting up devflow in a project

devflow's skills and agents know the method; this project's facts go in two files that you write here:

- **`.claude/devflow.md`**, the profile, read by every skill and agent. Its headings are fixed: **Project**, **Where things live**, **Architecture rules**, **Verify**, **Edit bounds**, **Escalate**, **See it working**, **Design system**, **Release**, **Try it**, **Standing rules**.
- **`.claude/devflow.json`**, the guard and CI config. The hooks act only in a project that has it.

Templates for everything are in the plugin's `templates/` folder, two folders up from this skill's base directory. Copy their structure; fill them with this project's facts.

**Write nothing until the maintainer has seen the drafts.** The profile becomes the contract every agent works to, so a wrong rule is worse than a missing one.

## 1. See what is already there

**Check for `uv` first.** Run `uv --version`. devflow's hooks run as `uv run --no-project python …`, so without `uv` the guard asks "not checked" on every guarded call and session start prints nothing. If the command is not found or fails, stop here, before reading the codebase or drafting anything, and give the maintainer the install command to run themselves (don't install it for them): on Windows `winget install astral-sh.uv`; on macOS and Linux `curl -LsSf https://astral.sh/uv/install.sh | sh` (other ways: https://docs.astral.sh/uv/getting-started/installation/). Then tell them to close Claude Code, open a new terminal so `PATH` picks up `uv`, start Claude Code there and run `/devflow:setup` again. There is no fallback to plain `python`.

Check, and report in a few lines:

- `.claude/devflow.md`, `.claude/devflow.json`: if they exist, this is a refresh. Read them, and change only what the maintainer asks for or what is now wrong. A refresh also runs the clash check in §3 on `CLAUDE.md` as it is now.
- `docs/BEHAVIOUR.md`, `docs/DESIGN.md`, `docs/STATUS.md`, `docs/plans/`, `docs/archive/`: keep and reuse what exists.
- `.claude/skills/`, `.claude/agents/`, `.claude/hooks/`, `.claude/settings.json`: a project with its own workflow skills, agents or guard hooks (as RYOS has) would run both. Say which overlap, and ask whether devflow replaces them here or the project keeps its own and devflow stays off (the plugin can be disabled per project in `.claude/settings.json`: `"enabledPlugins": {"devflow@devflow": false}`).
- `CLAUDE.md`, `README.md`, `CONTRIBUTING.md`, architecture docs: read them, and the files `CLAUDE.md` imports with `@path`; most of the profile comes from here. Skip the devflow section of `CLAUDE.md` itself.

## 2. Read the codebase, narrowly

Enough to fill the profile with evidence, not a full audit:

- The build and dependency files (`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `CMakeLists.txt`, `*.csproj`, ...) for the stack, the entry points and the test, lint and type commands.
- The test folder and how tests are run in CI (`.github/workflows/*.yml` or the equivalent).
- The top-level source layout: one line per module or folder for **Where things live**.
- `git remote -v`, the default branch, `git tag -l` and `gh release list` for **Release**.
- Where the product keeps user data at run time (config folders, databases, `%APPDATA%`, `~/.local/share`, ...) and what turns off side effects in tests (env vars for notifications, telemetry, registry, network). These are the guard's **real_data** and the **See it working** rules.
- Design tokens, if there is a user interface: CSS custom properties, a Tailwind config, a QML theme singleton, a Unity USS or theme asset; and which platforms it ships to (web, desktop, mobile, game).
- Secrets: key files, `.env`, signing tools. These are **secret_dirs**, **secret_extensions** and **maintainer_only**.

## 3. Ask what the code can't say

One `AskUserQuestion` call, at most four questions, only those whose answers you couldn't find. Usually:

- the maintainer's name and time zone (for the decision log), unless your plugin settings give them (name `${user_config.maintainer_name}`, time zone `${user_config.maintainer_timezone}`). Each is judged on its own: a value that is empty, or still shows its `user_config` placeholder, is not given, and is asked for as before. A given value is not asked for: it goes into the drafts (`maintainer` in `devflow.json`, **Maintainer** in **Project**) marked "(from your plugin settings)";
- whether the project ships releases, and through what (GitHub releases, a package registry, a store);
- if it ships through GitHub releases: whether its release gate can write a pass stamp (a JSON file with the full HEAD SHA, the SHA-256 of the artifact checksum file and the case count, written only when every case passes and deleted when a run or build starts);
- where the real user data lives, if the code doesn't make it obvious;
- which areas are risky enough to escalate (migrations, packaging, concurrency, security, payments);
- which two or three areas cause the most rework (for the area docs in §4.9).

**Rules that clash with devflow's.** List every line in the files §1 had you read (`CLAUDE.md` and its imports, `README.md`, `CONTRIBUTING.md`, the architecture docs) that contradicts one of the rules below. An adaptable rule can be changed by a profile or config entry; a fixed one is enforced by the skills' own text, which reads no setting for it.

- R1, version (adaptable): it changes only in a `Release candidate X.Y.Z-rcN` or `Release X.Y.Z` commit, never per change, never `-dev`, and the number is the maintainer's. If the project's rule wins, it replaces the template's "Don't touch the version" bullet, and `checks.version_files` is left out so CI doesn't fail every PR.
- R2, escapes (fixed): every bug found after a release gets one line in `docs/BEHAVIOUR.md` § Escapes, and its fix adds the check that would have caught it.
- R3, plan steps (fixed): the step is claimed first (its Status row before any other work), one fresh coding session per step, and the plan is edited one row at a time.
- R4, stop rules (fixed): at most two fix rounds, a second BLOCKERS stops, a `**Gate:**` line stops, and red CI on HEAD is fixed first.
- R5, Verify and review (partly adaptable): the Verify commands run on every change; they are the project's, and **Verify** may say which run for which kind of change. Fixed: the reviewer's `READY TO COMMIT` and the maintainer's yes come before the code commit.
- R6, comments (adaptable): no code comments in new or changed code, with the `comments` CI check where configured. If the project's rule wins, it replaces the template's comment bullet, and `checks.no_new_python_comments` is left out or narrowed.
- R7, branches and commits: `/devflow:run-plan` runs only on `develop`; the main branch is pushed only when the project's rules say so (otherwise the session asks); files are staged by path, never `git add -A`; forced pushes are asked; AI attribution follows `attribution`. So a rule to commit straight to the main branch is a clash. Adaptable: the push branch (an Architecture rules bullet, which also says `run-plan` won't run without `develop`) and attribution (settled by §4.2's question). Fixed: staging by path and asking before a forced push.

A line that only matches something devflow leaves open is not a clash: "no plan needed" (plans are optional), or anything already inside the project's own **Verify**. A rule already settled is not asked again: an Architecture rules bullet that quotes the line, or a line already edited to agree.

For each clash, give the quoted line with its file, the devflow rule it meets, and the answers on offer: devflow wins; the project's rule wins (only for an adaptable rule, with what it changes); or both stay, with a note on which applies when. Number the clashes and ask in the same turn as the other questions; they don't count toward the four, and the maintainer answers by number. With none found, say "no clashes" in the §1 report and ask nothing about them. Never settle one yourself.

## 4. Draft, show, then write

Draft each file and show it to the maintainer before writing it. Keep the drafts honest: mark anything you inferred rather than read with "(inferred, please check)".

1. **`.claude/devflow.md`** from `templates/devflow.md`.
   - **Architecture rules**: only rules the code or docs actually show, each with its *why*. Five true rules beat fifteen guesses. Always include "don't touch the version" and the comment rule the project follows.
     - Each clash settled as the project's rule wins, or both stay, gets one bullet here: the rule that applies, and for both, which applies when (for a fixed rule: outside devflow's skills, the project's line; inside `/devflow:add-feature`, `fix-bug` or `manage-project`, devflow's). End it `Settles CLAUDE.md: "<quoted line>".` (name the line's own file where it is another). Where it replaces the template's version or comment bullet, drop that bullet. The config change it needs goes into the `.claude/devflow.json` draft.
   - **Verify**: commands you ran and saw pass (run each once now). Say which ones you couldn't run.
   - Leave **Release** and **Try it** out if the project doesn't ship releases; the `release` skill stops when they are missing.
2. **`.claude/devflow.json`** from `templates/devflow.json`:
   - `name`, `maintainer`, `main_branch`, `status_file`, `plans_dir`;
   - `guard.real_data`: every place real user data lives, with env-var forms (`%APPDATA%/App`, `~/.local/share/app`);
   - `guard.secret_dirs`, `guard.secret_extensions`, `guard.maintainer_only` (scripts only the maintainer runs, with the subcommands that matter, e.g. `sign`);
   - `guard.app`: the commands and Python modules that start the product, the harmless arguments (`--version`, `--help`), `isolate_env` (the variables that must point at a scratch folder in the same command) and `data_folder` (the product's folder inside that variable). Leave `isolate_env` empty to refuse starting the product at all. Leave `app` out for a library;
   - `guard.self_guarding_scripts`: the project's own harnesses that protect real data themselves;
   - `guard.release_stamp` (`path`, `binds`, optional `gate`): only if the gate writes a stamp, or the maintainer wants it added to the gate now; the guard then refuses to publish a release without a stamp for the current HEAD and the current hash of `binds`. If the gate can't write one, leave the key out: publishing stays an ask. Record the choice in **Release** under **Stamp**;
   - `checks.version_files` (path and a regex whose group 1 is the version; `numbers_only` for files that take `X.Y.Z` only) and `checks.no_new_python_comments` (folders, Python only); leave out, or narrow, the one whose rule the project's own won (§3);
   - `checks.docs_routing`: keep the template's `"CLAUDE.md"` only when §4.9 writes area docs; with no area named, remove the key, so it alone never makes §4.7 add CI;
   - `attribution`: ask whether commits and PR descriptions carry AI attribution (Claude's `Co-Authored-By:` trailer, the "Generated with Claude Code" footer), recommending none; for none keep the template's `"attribution": "none"`, otherwise remove the key;
   - `models`: copy the template's board as it is (every entry `default`) and tell the maintainer this is where every agent's model and effort are set; `python <plugin>/tools/model_check.py --board` shows what each resolves to.
3. **`docs/BEHAVIOUR.md`** from `templates/BEHAVIOUR.md`. Start small and true: the surfaces the product really has, and the main areas with a few rows each, every row with the test that guards it today or **untested**. Tell the maintainer the map grows with every change from here on and that they should review it.
4. **`docs/DESIGN.md`** and the **Design system** heading of the profile, if the project has a user interface. Copy `templates/DESIGN.md`.
   - Where the code already has tokens (CSS custom properties, a Tailwind config, a QML theme singleton, a Unity USS or theme asset), fill the front matter and the sections from them, and mark every value you guessed with "(inferred, please check)".
   - Where it has none, leave the template as it is and say so; do not invent a palette.
   - Fill **Platforms the project ships to** and **UI surfaces** in the profile from what the code and the behaviour map show. A project with no user interface gets neither the heading nor the file. An existing `docs/DESIGN.md` is kept as it is.
5. **`docs/STATUS.md`** from `templates/STATUS.md`, and an empty `docs/plans/` and `docs/archive/` (a `.gitkeep` each). Skip any that already exist.
   - **`docs/PROMPTS.md`** from `templates/PROMPTS.md`, the prompt book, with the project's name, repo and tab names filled in. Keep the `{braces}` as they are: they are filled in when a prompt is pasted. An existing `docs/PROMPTS.md` is kept as it is.
6. **`.claude/settings.json`**: merge `templates/settings.json`'s `ask` and `deny` lists into the existing file, keeping everything already there. Change `docs/STATUS.md` and `docs/plans` in the deny rules if `status_file` or `plans_dir` differ. Where `attribution` is `none`, also add the template's `attribution` key (Claude Code's setting; empty `commit` and `pr` strings turn off its trailer and footer: https://code.claude.com/docs/en/settings-reference.md); otherwise leave it out. New `ask` and `deny` rules and the `attribution` setting need the maintainer's approval: list them and wait for a yes.
7. **CI**, if the project has GitHub Actions and `checks` has anything in it, `attribution` is `none`, or it has area docs: copy the plugin's `tools/devflow_checks.py` to `tools/devflow_checks.py` in the project, and add the job in `templates/ci-devflow.yml` to the main workflow.
   - **An existing `docs/architecture/`**, whether or not the maintainer named an area: before adding the job, run `uv run --no-project python "<plugin>/tools/devflow_checks.py" anchors --repo .` on it and show the maintainer what fails. Add the anchors step only with their agreement, or after the fixes they approve; otherwise leave that step out of the job and say so.
8. **`CLAUDE.md`**: add the section in `templates/CLAUDE-section.md` (create the file if there is none). For each clash settled as devflow wins, draft the edit to the quoted line (in the file it came from), show it old and new, and make it only on a yes. Don't rewrite the rest.
9. **Area docs**, for the areas the maintainer named in §3:
   - draft `docs/architecture/README.md` from `templates/architecture/README.md`, with one index row per doc;
   - draft one `docs/architecture/<area>.md` per named area from `templates/architecture/area.md`, only for an area that meets one of the README's triggers (a change there spans layers, adding one more instance of a pattern needs a recipe, or the mechanism takes more than one or two greps to find). Check each claim against the source as you write it, anchor by symbol, and put what you could not check under "Flagged / unverified";
   - replace the placeholder row of the "When to read an area's doc first" table in the `CLAUDE.md` section with one row per doc: its paths, its topics and the doc;
   - set `checks.docs_routing` in `.claude/devflow.json` to the instructions file that holds the table (`CLAUDE.md`).
   More areas get docs as changes touch them, never all at once. With no area named, write no docs, keep the template's placeholder row in the table, and leave `docs_routing` out of `.claude/devflow.json` (§4.2).

## 5. Check it works

- Run the session-start hook by hand and show its output:
  `CLAUDE_PROJECT_DIR="$PWD" uv run --no-project python "<plugin>/hooks/session_start.py"`
- Feed the guard a command it must refuse and one it must allow, and show both results:
  `echo '{"tool_name":"Bash","tool_input":{"command":"git reset --hard"}}' | CLAUDE_PROJECT_DIR="$PWD" uv run --no-project python "<plugin>/hooks/guard.py"; echo "exit $?"`
  (exit 2 means refused). Also one that writes into a `real_data` folder, and one that starts the product without `isolate_env`, if configured.
- If `tools/devflow_checks.py` was added: `uv run --no-project python tools/devflow_checks.py version --head HEAD` passes.
- If area docs were written: `uv run --no-project python tools/devflow_checks.py anchors` passes; show its output.

## 6. Commit

Ask before committing. Stage only the files you wrote, by path, in one commit titled `Adopt devflow`. Where `.claude/devflow.json` sets `"attribution": "none"`, no commit or PR description carries a `Co-Authored-By:` line naming Claude or a "Generated with Claude Code" line, whatever your session's instructions say; otherwise end it with the attribution lines they give, if any. Push only if the maintainer says so.

Then tell the maintainer, in a few lines: what was written, what you inferred and they should check, the rules that need their eye (the architecture rules, the real-data folders, the new `ask` and `deny` rules), and the next step: `/devflow:manage-project` to start the first plan, or `/devflow:add-feature` / `/devflow:fix-bug` for the work at hand.
