from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = ROOT / "hooks" / "guard.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


guard = _load("devflow_guard", GUARD_PATH)

ENV = {
    "APPDATA": r"C:\Users\Tester\AppData\Roaming",
    "LOCALAPPDATA": r"C:\Users\Tester\AppData\Local",
    "USERPROFILE": r"C:\Users\Tester",
}
SCRATCH = r"C:\Users\Tester\AppData\Local\Temp\claude\proj\session\scratchpad"

RYOS = {
    "name": "RYOS",
    "maintainer": "Vũ",
    "status_file": "docs/STATUS.md",
    "plans_dir": "docs/plans",
    "guard": {
        "real_data": ["%APPDATA%/RYOS", "%LOCALAPPDATA%/RYOS"],
        "secret_dirs": ["~/ryos-keys"],
        "secret_extensions": ["pem", "key", "p8"],
        "self_guarding_scripts": ["tests/real_data_smoke.py", "tests/release_check.py",
                                  "tests/launch_smoke.py", "tests/session_smoke.py"],
        "maintainer_only": [{"script": "tools/sign_release.py", "subcommands": ["sign", "new"]}],
        "app": {
            "commands": ["ryos", "ryos-cli", "run.bat"],
            "modules": ["ryos"],
            "harmless": [["--version"], ["-v"], ["--help"], ["-h"], ["verify", "*"]],
            "isolate_env": ["APPDATA"],
            "data_folder": "RYOS",
        },
    },
}

LINUX_ENV = {"HOME": "/home/tester"}
NOTES = {
    "name": "Notes",
    "maintainer": "Sam",
    "status_file": "STATUS.md",
    "plans_dir": "plans",
    "guard": {
        "real_data": ["~/.local/share/notes"],
        "secret_dirs": ["~/.notes-keys"],
        "secret_extensions": ["gpg"],
        "maintainer_only": [{"script": "scripts/publish.sh"}],
        "app": {"commands": ["notes"], "isolate_env": ["XDG_DATA_HOME"], "data_folder": "notes"},
        "ask_release": False,
    },
}


def clean() -> list[str]:
    return []


def dirty() -> list[str]:
    return ["docs/STATUS.md", "docs/plans/release-2.4.0.md"]


def verdict(command: str, tool: str = "Bash", secretary=clean, config=RYOS, env=ENV):
    return guard.decide(tool, {"command": command}, env, secretary, config)


def file_verdict(path: str, tool: str = "Write", config=RYOS, env=ENV):
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    return guard.decide(tool, {key: path, "content": "x"}, env, clean, config)


class TestGuardRefuses(unittest.TestCase):
    def assertRefused(self, command: str, tool: str = "Bash", secretary=clean) -> str:
        result = verdict(command, tool, secretary)
        self.assertEqual(result.kind, "deny", f"{tool}: {command!r} was {result}")
        self.assertTrue(result.reason)
        return result.reason

    def test_writes_into_the_real_data_folder(self):
        self.assertRefused('echo x > "$APPDATA/RYOS/settings.json"')
        self.assertRefused(r"Remove-Item -Recurse $env:APPDATA\RYOS", "PowerShell")
        self.assertRefused("rm -rf /c/Users/Tester/AppData/Roaming/RYOS/logs")
        self.assertRefused('$p = "$env:APPDATA\\RYOS"; Remove-Item $p', "PowerShell")
        self.assertRefused(r'sqlite3 %APPDATA%\RYOS\scripts.db "delete from scripts"')
        self.assertRefused(r'sqlite3 %APPDATA%\RYOS\scripts.db "delete from scripts"', "PowerShell")
        self.assertRefused("cp x.db ~/AppData/Roaming/RYOS/")
        self.assertRefused(
            "uv run python -c \"open(r'C:\\Users\\Tester\\AppData\\Roaming\\RYOS\\x','w')\"")

    def test_the_local_data_folder_counts_as_real_data(self):
        self.assertRefused(r"Remove-Item -Recurse $env:LOCALAPPDATA\RYOS\updates", "PowerShell")
        self.assertRefused("rm -rf ~/AppData/Local/RYOS/updates")

    def test_a_read_feeding_a_write(self):
        self.assertRefused(r"Get-ChildItem $env:APPDATA\RYOS | Remove-Item", "PowerShell")
        self.assertRefused("ls /c/Users/Tester/AppData/Roaming/RYOS | xargs rm")

    def test_a_wrapped_write(self):
        self.assertRefused('powershell -Command "Remove-Item -Recurse $env:APPDATA\\RYOS"')
        self.assertRefused(r'cmd /c "del /q %APPDATA%\RYOS\scripts.db"')
        self.assertRefused('bash -c "rm -rf $APPDATA/RYOS"')
        self.assertRefused('echo $(rm -rf "$APPDATA/RYOS")')

    def test_a_heredoc_script_naming_the_real_folder(self):
        self.assertRefused("uv run python - <<'EOF'\n"
                           "open(r'C:\\Users\\Tester\\AppData\\Roaming\\RYOS\\x', 'w')\nEOF")

    def test_write_tools_into_the_real_folder(self):
        for tool in ("Write", "Edit", "MultiEdit"):
            result = file_verdict(r"C:\Users\Tester\AppData\Roaming\RYOS\settings.json", tool)
            self.assertEqual(result.kind, "deny", tool)
        self.assertEqual(file_verdict("/c/Users/Tester/AppData/Local/RYOS/x.ipynb",
                                      "NotebookEdit").kind, "deny")

    def test_starting_the_app_without_a_throwaway_data_folder(self):
        self.assertRefused("uv run ryos list")
        self.assertRefused("uv run --extra mcp ryos mcp")
        self.assertRefused("dist/cxfreeze/ryos-cli.exe run hello")
        self.assertRefused("uv run python -m ryos")
        self.assertRefused(r"& .\dist\cxfreeze\RYOS.exe", "PowerShell")
        self.assertRefused("timeout 30 uv run ryos")
        self.assertRefused('APPDATA="$APPDATA" uv run ryos list')
        self.assertRefused("start RYOS.exe")
        self.assertRefused("cmd //c start dist/cxfreeze/RYOS.exe")
        self.assertRefused('cmd /c start "" dist/cxfreeze/RYOS.exe')
        self.assertRefused("Invoke-Item dist/cxfreeze/RYOS.exe", "PowerShell")
        self.assertRefused("ii ./RYOS.exe", "PowerShell")
        self.assertRefused("uvx --from . ryos list")
        self.assertRefused("uv tool run ryos list")

    def test_mentioning_a_harness_does_not_exempt_a_write(self):
        self.assertRefused("rm -rf ~/AppData/Roaming/RYOS tests/launch_smoke.py")
        self.assertRefused("cp tests/session_smoke.py ~/AppData/Roaming/RYOS/")

    def test_a_relative_write_after_cd(self):
        self.assertRefused('cd "$APPDATA" && rm -rf RYOS')
        self.assertRefused("cd ~/AppData/Roaming/RYOS && rm -rf logs")
        self.assertRefused("Set-Location $env:LOCALAPPDATA; Remove-Item -Recurse RYOS", "PowerShell")
        self.assertRefused("cd ~/ryos-keys")

    def test_set_outside_cmd_sets_nothing(self):
        reason = self.assertRefused(r"set APPDATA=C:\tmp\x; uv run ryos list", "PowerShell")
        self.assertIn("In PowerShell this sets no environment variable", reason)
        self.assertIn("$env:APPDATA", reason)
        self.assertRefused(r"set APPDATA=C:\tmp\x")
        self.assertRefused(r"set LOCALAPPDATA=C:\tmp\x")

    def test_the_secrets(self):
        self.assertRefused("cat ~/ryos-keys/ryos-release.pem")
        self.assertRefused(r"Get-ChildItem $env:USERPROFILE\ryos-keys", "PowerShell")
        self.assertRefused("ls /c/Users/Tester/ryos-keys")
        self.assertRefused(r"type %USERPROFILE%\ryos-keys\notes.txt")
        self.assertRefused("cat x.pem")
        self.assertRefused("cat ./ryos-release.pem")
        self.assertRefused("cp ryos-release.pem /tmp/")
        self.assertRefused("echo x > signing.key")
        self.assertRefused(r"Get-Content .\ryos-release.pem", "PowerShell")
        self.assertEqual(file_verdict("x.pem").kind, "deny")
        self.assertEqual(file_verdict(r"C:\Users\Tester\ryos-keys\notes.txt", "Edit").kind, "deny")

    def test_maintainer_only_scripts(self):
        reason = self.assertRefused(
            "uv run --with cryptography python tools/sign_release.py sign k")
        self.assertIn("Vũ's to run", reason)
        self.assertRefused("uv run --with cryptography python tools/sign_release.py new")

    def test_reverting_secretary_files(self):
        self.assertRefused("git checkout -- docs/STATUS.md")
        self.assertRefused(r"git restore docs\plans\release-2.4.0.md")
        self.assertRefused("git -C D:/Projects/RYOS checkout HEAD -- docs/plans/")
        self.assertRefused('powershell -Command "git checkout -- docs/STATUS.md"')
        self.assertRefused("git status --short | awk '{print $2}' | xargs -r git checkout --")
        self.assertRefused("git checkout -- $(git diff --name-only)")
        self.assertRefused("git reset --hard")
        self.assertRefused("git reset HEAD~1 --hard")
        self.assertRefused("cd docs && git checkout -- STATUS.md")
        self.assertRefused("cd docs/plans; git restore release-2.4.0.md", "PowerShell")

    def test_whole_tree_discards_while_secretary_edits_wait(self):
        for command in ("git checkout -- .", "git checkout .", "git checkout -f main",
                        "git restore :/", "git stash", "git stash -u", "git stash push",
                        "git clean -fd", "git checkout -- docs", "git restore docs/*.md",
                        "git checkout -- '*.md'", "git checkout -- 'docs/*.md'",
                        "git checkout -- STATUS.md", "git restore STATUS.md",
                        "git switch -f main", "git switch --discard-changes main",
                        "cd /c/elsewhere && git restore x"):
            reason = self.assertRefused(command, secretary=dirty)
            self.assertIn("docs/STATUS.md", reason)


class TestGuardAllows(unittest.TestCase):
    def assertAllowed(self, command: str, tool: str = "Bash", secretary=clean) -> None:
        result = verdict(command, tool, secretary)
        self.assertEqual(result.kind, "allow", f"{tool}: {command!r} was {result}")

    def test_the_app_with_a_throwaway_data_folder(self):
        self.assertAllowed('APPDATA="$S/a" LOCALAPPDATA="$S/a/local" uv run ryos list')
        self.assertAllowed(f"$env:APPDATA='{SCRATCH}\\a'; & .\\dist\\cxfreeze\\ryos-cli.exe list",
                           "PowerShell")
        self.assertAllowed(r'cmd /c "set APPDATA=C:\t&& ryos-cli list"')
        self.assertAllowed('export APPDATA="$T" RYOS_NO_TOASTS=1; uv run ryos list')

    def test_harmless_app_commands(self):
        self.assertAllowed("uv run ryos --version")
        self.assertAllowed("dist/cxfreeze/ryos-cli.exe --help")
        self.assertAllowed("uv run ryos verify dist/RYOS-windows.zip")

    def test_self_guarding_harnesses(self):
        self.assertAllowed("uv run python tests/real_data_smoke.py")
        self.assertAllowed(r"uv run python tests/real_data_smoke.py --db %APPDATA%\RYOS\backup.db")
        self.assertAllowed("uv run python tests/release_check.py 2>&1 | tail -40")
        self.assertAllowed("uv run python tests/launch_smoke.py --exe dist/cxfreeze/RYOS.exe")

    def test_reading_and_copying_out_of_the_real_folder(self):
        self.assertAllowed('tail -50 "$APPDATA/RYOS/logs/ryos.log"')
        self.assertAllowed('Get-Content "$env:APPDATA\\RYOS\\logs\\ryos.log" | Select-Object -Last 12',
                           "PowerShell")
        self.assertAllowed('cp /c/Users/Tester/AppData/Roaming/RYOS/scripts.db "$S/copy.db"')
        self.assertAllowed(r"Copy-Item $env:APPDATA\RYOS\scripts.db -Destination C:\tmp\copy.db",
                           "PowerShell")
        self.assertAllowed('ls ~/AppData/Roaming/RYOS | grep db')
        self.assertAllowed("cd ~/AppData/Roaming/RYOS && ls")
        self.assertAllowed('cd "$APPDATA/RYOS" && cp scripts.db "$S/copy.db"')
        self.assertAllowed('$log = "$env:APPDATA\\RYOS\\logs\\ryos.log"; '
                           "Select-String -Path $log -Pattern 'starting' | Select-Object -Last 12",
                           "PowerShell")

    def test_write_tools_elsewhere(self):
        self.assertEqual(file_verdict(SCRATCH + r"\appdata\RYOS\settings.json").kind, "allow")
        self.assertEqual(file_verdict(r"D:\Projects\RYOS\ryos\cli.py", "Edit").kind, "allow")

    def test_a_commit_message_naming_the_real_folder(self):
        self.assertAllowed(
            "cd D:/Projects/RYOS && git add ryos/ && git commit -m \"$(cat <<'EOF'\n"
            "fix: never write into %APPDATA%\\RYOS from a test\n\n"
            "Co-Authored-By: Claude <noreply@anthropic.com>\nEOF\n)\" && git push")

    def test_mentions_that_are_not_a_secret(self):
        self.assertAllowed('grep -n "\\.pem" .gitignore')
        self.assertAllowed("git log --oneline -- '*.pem'")
        self.assertAllowed("uv run python - <<'EOF'\n"
                           "from ryos import cardmenu\n"
                           "print([i.key for i in cardmenu.script_menu()])\nEOF")
        self.assertAllowed('uv run --no-project --with pytest pytest -q -k "f.key"')
        self.assertAllowed('grep -rn "event.key" ryos/')
        self.assertAllowed('Select-String -Pattern "item.key" -Path ryos\\qtui\\shell.py',
                           "PowerShell")
        self.assertAllowed('gh pr create --title x --body "uses item.key"')
        self.assertAllowed('git commit -m "fix: settings.key handling"')
        self.assertAllowed("uv run python -c \"print(self.key)\"")

    def test_reading_a_maintainer_only_script(self):
        self.assertAllowed("cat tools/sign_release.py")
        self.assertAllowed("grep -n sign tools/sign_release.py")
        self.assertAllowed("uv run python tools/sign_release.py check dist/SHA256SUMS.txt")

    def test_git_that_keeps_secretary_edits(self):
        self.assertAllowed("git checkout -- ryos/qtui/shell.py", secretary=dirty)
        self.assertAllowed("git checkout -- .")
        self.assertAllowed("git restore --staged ryos/x.py", secretary=dirty)
        self.assertAllowed("git stash list", secretary=dirty)
        self.assertAllowed("git checkout -b feature/x", secretary=dirty)
        self.assertAllowed("git checkout main", secretary=dirty)
        self.assertAllowed("git switch main", secretary=dirty)
        self.assertAllowed("git restore docs/*.md")
        self.assertAllowed("cd D:/Projects/RYOS && git checkout -- ryos/cli.py", secretary=dirty)
        self.assertAllowed("git mv docs/plans/release-2.4.0.md docs/archive/release-2.4.0.md")

    def test_the_secretary_check_runs_only_for_a_discard(self):
        calls = []

        def counting() -> list[str]:
            calls.append(1)
            return []

        verdict("git status --short && uv run --no-project --with pytest pytest -q",
                secretary=counting)
        self.assertEqual(calls, [])
        verdict("git stash", secretary=counting)
        self.assertEqual(calls, [1])


class TestGuardAsks(unittest.TestCase):
    def assertAsks(self, command: str, tool: str = "Bash") -> None:
        result = verdict(command, tool)
        self.assertEqual(result.kind, "ask", f"{tool}: {command!r} was {result}")

    def test_release_and_forced_pushes(self):
        self.assertAsks("gh release create v2.4.0-rc1 dist/RYOS-windows.zip \\\n"
                        "  -R lqvu-zen/RYOS --prerelease --latest=false --title \"v2.4.0-rc1\"")
        self.assertAsks("cmd /c gh release delete v1")
        self.assertAsks("gh release upload v2.4.0 dist/SHA256SUMS.txt.sig", "PowerShell")
        self.assertAsks("gh -R lqvu-zen/RYOS release edit v2.4.0 --draft=false")
        self.assertAsks("git push --force-with-lease")
        self.assertAsks("git push origin +main")
        self.assertAsks("git push -f origin main")
        self.assertAsks("git push --mirror")
        self.assertAsks("gh api -X DELETE repos/lqvu-zen/RYOS/releases/1")
        self.assertAsks("gh api repos/lqvu-zen/RYOS/releases -f tag_name=v9")

    def test_the_reason_names_the_maintainer(self):
        self.assertIn("Vũ approves it", verdict("gh release delete v1").reason)

    def test_release_reads_are_not_asked(self):
        self.assertEqual(verdict("gh release list -R lqvu-zen/RYOS -L 5").kind, "allow")
        self.assertEqual(verdict("gh api repos/lqvu-zen/RYOS/releases/latest").kind, "allow")
        self.assertEqual(verdict("git push -u origin main").kind, "allow")


SKILL_COMMANDS = [
    "cd D:/Projects/RYOS && uv run --no-project --with pytest pytest -q",
    "cd D:/Projects/RYOS && uvx ruff check . && uvx mypy --platform linux",
    "uv run python tests/session_smoke.py",
    "git diff",
    "git log --oneline -5",
    "cd D:/Projects/RYOS && git add ryos/ tests/test_ryos.py && git commit -m \"$(cat <<'EOF'\n"
    "Fix the stop button\n\nCo-Authored-By: Claude <noreply@anthropic.com>\nEOF\n)\" && git push",
    "git add docs/plans/release-2.4.0.md && git commit -m \"Status: 2.4 step 12 in progress\" "
    "-- docs/plans/release-2.4.0.md && git push",
    "cd D:/Projects/RYOS && git status --porcelain && gh run list -L 3 --json "
    "conclusion,status,headSha,displayTitle \\\n"
    "  --jq '.[] | \"\\(.status)\\t\\(.conclusion // \"-\")\\t\\(.headSha[0:7])\\t\\(.displayTitle)\"'",
    "gh release list -R lqvu-zen/RYOS -L 5",
    'git tag -l "v2.4.0-rc*"',
    "gh run watch 123456 --exit-status",
    "cd D:/Projects/RYOS && git diff --stat v2.4.0-rc1..HEAD -- . ':(exclude)docs'",
    'cd D:/Projects/RYOS && git add ryos/__init__.py && git commit -m "Release 2.4.0" && git push',
    "cd D:/Projects/RYOS && rm -rf dist/* build",
    "cd D:/Projects/RYOS && plan=docs/plans/release-2.4.0.md\n"
    "awk -F'|' '/^## Status/{t=1} t && /^\\| [0-9]+ /{s=tolower($3); sub(/^ +/,\"\",s); "
    "if (s !~ /^(done|not needed)/) print \"OPEN: \" $2}' $plan\n"
    "grep -n -i '\\[ \\]\\|needs a human' $plan",
    "cd D:/Projects/RYOS && git mv docs/plans/release-2.4.0.md docs/archive/release-2.4.0.md",
    "uv run --no-project python tools/devflow_checks.py version --base 5c76e95 --head HEAD",
]


class TestGuardSkillCommands(unittest.TestCase):
    def test_every_skill_command_runs(self):
        for command in SKILL_COMMANDS:
            with self.subTest(command=command[:70]):
                result = verdict(command, secretary=dirty)
                self.assertEqual(result.kind, "allow", f"{command!r} was {result}")


class TestAnotherProject(unittest.TestCase):
    def check(self, command: str, tool: str = "Bash", secretary=clean):
        return verdict(command, tool, secretary, config=NOTES, env=LINUX_ENV)

    def test_its_real_data(self):
        self.assertEqual(self.check("rm -rf ~/.local/share/notes").kind, "deny")
        self.assertEqual(self.check("rm -rf $HOME/.local/share/notes/db").kind, "deny")
        self.assertEqual(self.check("cat ~/.local/share/notes/db").kind, "allow")
        self.assertIn("Notes's real data", self.check("rm -rf ~/.local/share/notes").reason)
        self.assertEqual(file_verdict("/home/tester/.local/share/notes/x", config=NOTES,
                                      env=LINUX_ENV).kind, "deny")

    def test_its_app_needs_its_own_data_folder(self):
        self.assertEqual(self.check("notes add hello").kind, "deny")
        self.assertEqual(self.check("XDG_DATA_HOME=~/.local/share notes add hello").kind, "deny")
        self.assertEqual(self.check("XDG_DATA_HOME=/tmp/x notes add hello").kind, "allow")
        self.assertEqual(self.check("notes --version").kind, "allow")
        self.assertIn("XDG_DATA_HOME", self.check("notes add hello").reason)

    def test_its_secrets(self):
        self.assertEqual(self.check("cat backup.gpg").kind, "deny")
        self.assertEqual(self.check("ls ~/.notes-keys").kind, "deny")
        self.assertEqual(self.check("cat x.pem").kind, "allow")

    def test_its_secretary_files(self):
        self.assertEqual(self.check("git checkout -- STATUS.md").kind, "deny")
        self.assertEqual(self.check("git restore plans/next.md").kind, "deny")
        reason = self.check("git stash", secretary=lambda: ["STATUS.md"]).reason
        self.assertIn("STATUS.md", reason)
        self.assertEqual(self.check("git checkout -- src/app.py").kind, "allow")

    def test_a_maintainer_only_script_without_subcommands(self):
        self.assertEqual(self.check("bash scripts/publish.sh").kind, "deny")
        self.assertEqual(self.check("./scripts/publish.sh --dry-run").kind, "deny")
        self.assertEqual(self.check("cat scripts/publish.sh").kind, "allow")

    def test_releases_are_not_asked_when_turned_off(self):
        self.assertEqual(self.check("gh release create v1").kind, "allow")


class TestMinimalConfig(unittest.TestCase):
    def test_an_empty_config_still_keeps_secrets_and_secretary_edits(self):
        self.assertEqual(verdict("cat x.pem", config={}).kind, "deny")
        self.assertEqual(verdict("git checkout -- docs/STATUS.md", config={}).kind, "deny")
        self.assertEqual(verdict("rm -rf build", config={}).kind, "allow")
        self.assertEqual(verdict("uv run ryos list", config={}).kind, "allow")
        self.assertEqual(verdict("gh release create v1", config={}).kind, "ask")

    def test_an_app_with_nothing_to_isolate_is_never_started(self):
        config = {"guard": {"app": {"commands": ["tool"]}}}
        self.assertEqual(verdict("tool run", config=config).kind, "deny")
        self.assertEqual(verdict("tool --help", config=config).kind, "allow")


class TestGuardMain(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp(prefix="devflow-guard-"))
        (self.project / ".claude").mkdir()
        (self.project / ".claude" / "devflow.json").write_text(json.dumps(RYOS), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.project, ignore_errors=True)

    def run_hook(self, payload: dict, project: Path | None = None,
                 stdin: str | None = None) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.update(ENV)
        env["CLAUDE_PROJECT_DIR"] = str(project or self.project)
        return subprocess.run([sys.executable, str(GUARD_PATH)],
                              input=stdin if stdin is not None else json.dumps(payload),
                              capture_output=True, text=True, encoding="utf-8", env=env,
                              timeout=30)

    def test_refused_exits_2_with_the_reason(self):
        result = self.run_hook({"tool_name": "Bash", "tool_input": {"command": "uv run ryos list"}})
        self.assertEqual(result.returncode, 2)
        self.assertIn("APPDATA", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_refused_file_write(self):
        result = self.run_hook({"tool_name": "Write", "tool_input": {
            "file_path": r"C:\Users\Tester\AppData\Roaming\RYOS\settings.json", "content": "{}"}})
        self.assertEqual(result.returncode, 2)
        self.assertIn("real data", result.stderr)

    def test_allowed_is_silent(self):
        result = self.run_hook({"tool_name": "Bash", "tool_input": {
            "command": 'APPDATA="$S/a" LOCALAPPDATA="$S/l" uv run ryos list'}})
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_ask_prints_the_decision(self):
        result = self.run_hook({"tool_name": "PowerShell", "tool_input": {
            "command": "gh release delete v1 -R lqvu-zen/RYOS"}})
        self.assertEqual(result.returncode, 0)
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "PreToolUse")
        self.assertEqual(output["permissionDecision"], "ask")
        self.assertIn("gh release delete", output["permissionDecisionReason"])

    def test_a_project_without_a_config_is_left_alone(self):
        bare = Path(tempfile.mkdtemp(prefix="devflow-bare-"))
        try:
            result = self.run_hook({"tool_name": "Bash", "tool_input": {
                "command": "git reset --hard && cat x.pem"}}, project=bare)
        finally:
            shutil.rmtree(bare, ignore_errors=True)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_a_crash_fails_open_visibly(self):
        result = self.run_hook({}, stdin="not json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("guard.py failed", result.stderr)
        self.assertIn("not checked", result.stderr)

    def test_a_broken_config_fails_open_visibly(self):
        (self.project / ".claude" / "devflow.json").write_text("{ nope", encoding="utf-8")
        result = self.run_hook({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        self.assertEqual(result.returncode, 1)
        self.assertIn("not checked", result.stderr)


if __name__ == "__main__":
    unittest.main()
