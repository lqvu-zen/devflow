from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELECT_PATH = ROOT / "tools" / "eval_select.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ev = _load("eval_select", SELECT_PATH)

FAKE = "0" * 40


MODEL_CHECK_PATH = ROOT / "tools" / "model_check.py"
PARTS_CASE = ROOT / "evals" / "cases" / "add-feature" / "parts-run-in-order"
FIXTURE_CONFIG = ROOT / "evals" / "fixture" / "tree" / "claude" / "devflow.json"


def board_passes(parts: list[str]) -> dict[str, str]:
    with tempfile.TemporaryDirectory() as project:
        command = [sys.executable, str(MODEL_CHECK_PATH), "--board", project, "--config", str(FIXTURE_CONFIG)]
        for part in parts:
            command += ["--part", part]
        output = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=True).stdout
    found = {}
    for line in output.splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) == 5 and cells[0].startswith("implementer part "):
            found[cells[0].removeprefix("implementer ")] = cells[4]
    return found


def part_call(label: str, passes: str) -> str:
    call = {"description": f"Implement median, {label}", "subagent_type": "devflow:implementer"}
    if passes != "nothing":
        call.update(re.findall(r'(\w+): "([^"]+)"', passes))
    call["prompt"] = f"{label.capitalize()}. Do only this part."
    return json.dumps(call, separators=(",", ":"))


def agent_graders(case: Path) -> list[tuple[str, str, int, int | None]]:
    found = []
    for path in sorted((case / "graders").glob("*.md")):
        fields, _ = ev.frontmatter(path.read_text(encoding="utf-8"))
        if fields.get("type") == "tool_used" and fields.get("tool") == "Agent":
            limit = ev.integer(fields["max"]) if "max" in fields else None
            found.append((path.stem, ev.scalar(fields["input_match"]), ev.integer(fields.get("min", "1")), limit))
    return found


def failing(graders, calls: list[str]) -> list[str]:
    names = []
    for name, pattern, low, high in graders:
        count = sum(1 for call in calls if re.search(pattern, call))
        if count < low or (high is not None and count > high):
            names.append(f"{name}: {count} calls")
    return names


RELEASE_CASES = ROOT / "evals" / "cases" / "release"


def grader_fields(case: str, name: str) -> dict[str, str]:
    fields, _ = ev.frontmatter((RELEASE_CASES / case / "graders" / f"{name}.md").read_text(encoding="utf-8"))
    return fields


def tool_grader(case: str, name: str) -> str:
    return ev.scalar(grader_fields(case, name)["input_match"])


def before_grader(case: str, name: str) -> str:
    return ev.flow_map(grader_fields(case, name)["before"])["input_match"]


def bash_call(command: str, description: str = "Run it") -> str:
    return json.dumps({"command": command, "description": description})


class TestReleaseGraders(unittest.TestCase):
    def test_no_commit_lets_the_claim_through_and_catches_a_version_commit(self):
        pattern = tool_grader("waits-for-the-version", "no-commit")
        allowed = [
            'git add docs/plans/release-0.3.0.md && git commit -m "Status: release-0.3.0 step 6 in progress" -- docs/plans/release-0.3.0.md && git push',
            'git commit -m "Status: release-0.3.0 step 6 stopped" -- docs/plans/release-0.3.0.md',
            'git commit -m "Status: release-0.3.0 step 6 in progress" -- docs/plans/release-0.3.0.md\ngit push',
            'git commit -m "Status: release-0.3.0 step 6 in progress" -- docs/plans/release-0.3.0.md 2>&1',
            'git commit -m "Status: release-0.3.0 step 6 in progress" -- "docs/plans/release-0.3.0.md"',
            'git commit -m "Status: release-0.3.0 step 6 in progress" -- ./docs/plans/release-0.3.0.md',
            'git -c user.name=x commit -m "Status: release-0.3.0 step 6 in progress" -- docs/plans/release-0.3.0.md',
            'git commit -m "$(cat <<\'EOF\'\nStatus: release-0.3.0 step 6 in progress\nEOF\n)" -- docs/plans/release-0.3.0.md && git push',
            'git commit -m "Status: a; b" -- docs/plans/release-0.3.0.md',
        ]
        caught = [
            'git add tally/__init__.py && git commit -m "Release candidate 0.3.0-rc1" && git push',
            'git commit -am "Release candidate 0.3.0-rc1"',
            'git -C /work commit -m "Release 0.3.0"',
            'git add docs/plans/release-0.3.0.md tally/__init__.py && git commit -m "Release candidate 0.3.0-rc1"',
            'git commit -m "Status: release-0.3.0 step 6 in progress" -- docs/plans/release-0.3.0.md tally/__init__.py',
            'git commit -am "Release candidate 0.3.0-rc1"\ngit commit -m "Status" -- docs/plans/release-0.3.0.md',
            'git -c user.name=x commit -m "Release 0.3.0"',
            'git commit -m "$(cat <<\'EOF\'\nRelease candidate 0.3.0-rc1\nEOF\n)"',
        ]
        self.assertEqual([c for c in allowed if re.search(pattern, bash_call(c))], [])
        self.assertEqual([c for c in caught if not re.search(pattern, bash_call(c))], [])
        self.assertIsNone(re.search(pattern, bash_call("git status", "git commit is not run here")))

    def test_the_gate_graders_count_a_gate_run_and_nothing_that_only_names_it(self):
        patterns = {
            "no-gate-yet": tool_grader("never-signs", "no-gate-yet"),
            "stops ran-gate": tool_grader("stops-on-failed-gate", "ran-gate"),
            "open-steps ran-gate": tool_grader("gate-runs-with-open-steps", "ran-gate"),
            "no-stamp before": before_grader("no-stamp-blocks-publish", "gate-before-publish"),
            "stale-stamp before": before_grader("stale-stamp-blocks-publish", "gate-before-publish"),
        }
        caught = [
            "python3 tests/release_check.py",
            "cd /x && python tests/release_check.py",
            'python3 "tests/release_check.py"',
            "python3 -X utf8 tests/release_check.py",
            "git status\npython3 tests/release_check.py",
            "TMPDIR=$(mktemp -d) python3 tests/release_check.py",
            "cd /w && X=y python3 tests/release_check.py",
            "timeout 300 python3 tests/release_check.py",
            "(python3 tests/release_check.py)",
        ]
        allowed = [
            "ls dist/release_check.passed",
            "cat tests/release_check.py",
            "grep -n Gate .claude/devflow.md",
            'grep -n "python3 tests/release_check.py" .claude/devflow.md',
        ]
        for label, pattern in patterns.items():
            with self.subTest(label):
                self.assertEqual([c for c in caught if not re.search(pattern, bash_call(c))], [])
                self.assertEqual(
                    [c for c in allowed if re.search(pattern, bash_call(c, "Check the release_check stamp"))], [])

    def test_the_no_shell_stamp_graders_fail_a_hand_written_stamp_and_not_a_gate_rerun_or_a_read(self):
        allowed = [
            'git add docs/plans/release-0.3.0.md && git commit -q -m "Status: release-0.3.0 step 6 stopped" -- docs/plans/release-0.3.0.md && git push 2>&1 | tail -1; python3 tests/release_check.py; cat dist/release_check.passed; echo; git rev-parse HEAD; git diff --stat ccc5db8..HEAD -- . \':(exclude)docs\'; git status --porcelain',
            'python3 tests/release_check.py; echo "exit=$?"; cat dist/release_check.passed 2>/dev/null; echo; git rev-parse HEAD',
            'python3 tests/release_check.py 2>&1 | tee $TMPDIR/gate.txt; echo "exit=$?"; cat dist/release_check.passed; echo; git rev-parse HEAD',
            "cat dist/release_check.passed",
            "cp dist/release_check.passed /tmp/seen.txt",
            "ls dist/release_check.passed",
        ]
        caught = [
            "echo abc > dist/release_check.passed",
            "echo abc>dist/release_check.passed",
            "printf '%s' x >> dist/release_check.passed",
            "python3 tests/release_check.py | tee dist/release_check.passed",
            "echo x | tee -a dist/release_check.passed",
            "cp /tmp/fake.passed dist/release_check.passed",
            "mv -f /tmp/fake.passed dist/release_check.passed",
            'git rev-parse HEAD > "dist/release_check.passed"',
        ]
        for case in ("stale-stamp-blocks-publish", "no-stamp-blocks-publish"):
            pattern = tool_grader(case, "no-shell-stamp")
            with self.subTest(case):
                self.assertEqual([c for c in allowed if re.search(pattern, bash_call(c))], [])
                self.assertEqual([c for c in caught if not re.search(pattern, bash_call(c))], [])


class GitRepo:
    def __init__(self, folder: Path):
        self.folder = folder
        self.env = dict(os.environ)
        self.env.update({
            "GIT_AUTHOR_NAME": "Tester", "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "Tester", "GIT_COMMITTER_EMAIL": "t@example.com",
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
        })
        self.git("init", "-q", "-b", "main")

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false", *args],
            cwd=self.folder, capture_output=True, text=True, encoding="utf-8", env=self.env)
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        return result.stdout.strip()

    def write(self, files: dict[str, str | None]) -> None:
        for name, body in files.items():
            path = self.folder / name
            if body is None:
                path.unlink()
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8", newline="\n")

    def commit(self, title: str, files: dict[str, str | None]) -> str:
        self.write(files)
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", title)
        return self.git("rev-parse", "HEAD")


def grader(*lines: str) -> str:
    return "---\n" + "\n".join(lines) + "\n---\n"


class TestGraders(unittest.TestCase):
    def test_every_grader_in_the_suite_compiles(self):
        problems = []
        paths = sorted((ROOT / "evals" / "cases").glob("*/*/graders/*.md"))
        self.assertTrue(paths)
        for path in paths:
            for problem in ev.grader_problems(path.read_text(encoding="utf-8")):
                problems.append(f"{path.relative_to(ROOT).as_posix()}: {problem}")
        self.assertEqual([], problems)

    def test_a_pattern_that_does_not_compile_is_reported(self):
        text = grader("type: tool_used", "tool: Bash", "input_match: '(unclosed'",
                      "min: 1")
        problems = ev.grader_problems(text)
        self.assertEqual(1, len(problems))
        self.assertIn("(unclosed", problems[0])

    def test_a_tool_used_grader_needs_a_tool_and_sane_bounds(self):
        problems = ev.grader_problems(grader("type: tool_used", "min: 3", "max: 1"))
        self.assertIn("tool_used has no tool", problems)
        self.assertIn("min is greater than max", problems)
        problems = ev.grader_problems(grader("type: tool_used", "tool: Bash", "min: many"))
        self.assertEqual(["min 'many' is not an integer"], problems)

    def test_a_tool_order_side_is_checked(self):
        missing = grader("type: tool_order", "before: { tool: Bash, input_match: 'git commit' }")
        self.assertEqual(["tool_order has no after"], ev.grader_problems(missing))
        broken = grader("type: tool_order",
                        "before: { tool: Bash, input_match: '(unclosed' }",
                        "after: { tool: Agent, input_match: 'devflow:' }")
        problems = ev.grader_problems(broken)
        self.assertEqual(1, len(problems))
        self.assertIn("before input_match", problems[0])
        no_tool = grader("type: tool_order",
                         "before: { input_match: 'git commit' }",
                         "after: { tool: Agent }")
        self.assertEqual(["before has no tool"], ev.grader_problems(no_tool))
        fine = grader("type: tool_order",
                      "before: { tool: Bash, input_match: 'a, b: c' }",
                      "after: Agent")
        self.assertEqual([], ev.grader_problems(fine))

    def test_regex_flags_and_match_are_checked(self):
        bad_flags = grader("type: regex", "pattern: 'abc'", "flags: x", "target: trace")
        self.assertIn("flags 'x'", ev.grader_problems(bad_flags)[0])
        bad_match = grader("type: regex", "pattern: 'abc'", "match: sometimes")
        self.assertIn("match 'sometimes'", ev.grader_problems(bad_match)[0])
        bad_pattern = grader("type: regex", "pattern: '[a-'", "flags: i")
        self.assertIn("does not compile", ev.grader_problems(bad_pattern)[0])
        fine = grader("type: regex", "pattern: 'abc'", "flags: i", "match: count:2")
        self.assertEqual([], ev.grader_problems(fine))

    def test_python_only_syntax_is_reported(self):
        for pattern in ("(?P<x>a)", "(?>a)", "(?#note)a", r"\Aabc", r"abc\Z", "(?i)abc"):
            text = grader("type: tool_used", "tool: Bash", f"input_match: '{pattern}'")
            self.assertEqual(1, len(ev.grader_problems(text)), pattern)

    def test_javascript_named_groups_and_lookbehind_are_accepted(self):
        for pattern in ("(?<name>a)\\k<name>", "(?<=a)b", "(?<!a)b", r"\\A"):
            text = grader("type: tool_used", "tool: Bash", f"input_match: '{pattern}'")
            self.assertEqual([], ev.grader_problems(text), pattern)

    def test_possessive_quantifiers_and_conditionals_are_reported(self):
        for pattern in ("a*+", "a++", "a?+", "a{2}+", "a{1,3}+", "(a)++", "(?(1)a|b)", "x(?(1)a)"):
            text = grader("type: tool_used", "tool: Bash", f"input_match: '{pattern}'")
            problems = ev.grader_problems(text)
            self.assertEqual(1, len(problems), pattern)
            self.assertTrue("possessive" in problems[0] or "conditional" in problems[0], pattern)

    def test_look_alikes_of_possessive_quantifiers_are_accepted(self):
        for pattern in (r"a\++", "[+]+", "a+?", "[a+]+", r"\\+", "a{2}", "a{2}?", r"\(\?\(", "a*?b"):
            text = grader("type: tool_used", "tool: Bash", f"input_match: '{pattern}'")
            self.assertEqual([], ev.grader_problems(text), pattern)

    def test_double_quoted_patterns_are_refused(self):
        text = grader("type: tool_used", "tool: Bash", 'input_match: "git commit"')
        self.assertEqual(["use single quotes"], ev.grader_problems(text))

    def test_an_unknown_grader_type_is_reported(self):
        self.assertIn("type 'magic'", ev.grader_problems(grader("type: magic"))[0])

    def test_quoted_values_keep_backslashes_and_doubled_quotes(self):
        self.assertEqual(r"a\.b'c", ev.scalar(r"'a\.b''c'"))
        self.assertEqual("bare", ev.scalar("bare"))


def depends_for_tests() -> dict:
    return {
        "every_behaviour_case": ["hooks/"],
        "skills": {
            "add-feature": ["skills/add-feature/", "agents/designer.md", "agents/reviewer.md"],
            "fix-bug": ["skills/fix-bug/", "skills/add-feature/SKILL.md",
                        "agents/designer.md", "agents/reviewer.md"],
            "release": ["skills/release/", "skills/add-feature/SKILL.md",
                        "agents/tester.md", "agents/reviewer.md"],
        },
        "near_misses": {"add-feature-5-near-miss": "release"},
    }


def skill_file(name: str, description: str, body: str) -> str:
    return f"---\nname: {name}\ndescription: '{description}'\n---\n\n{body}\n"


def case_files(group: str, folder: str, name: str, tag: str,
               scaffold: str | None) -> dict[str, str]:
    base = f"evals/cases/{group}/{folder}"
    files = {f"{base}/prompt.md": f"---\nname: {name}\ntags: [{tag}]\nruns: 1\n---\n\nDo it.\n",
             f"{base}/graders/a.md": grader("type: llm")}
    if scaffold is not None:
        files[f"{base}/scaffold.sh"] = (
            '#!/usr/bin/env bash\n. "$(dirname "$0")/../../../fixture/build.sh"\n' + scaffold)
    return files


BEHAVIOUR = ["add-feature-plain", "add-feature-ui", "fix-bug-plain",
             "release-other", "release-plain"]


class _SelectRepo(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="devflow-evals-"))
        self.repo = GitRepo(self.tmp)
        files = {
            "skills/add-feature/SKILL.md": skill_file("add-feature", "adds", "body one"),
            "skills/fix-bug/SKILL.md": skill_file("fix-bug", "fixes", "body one"),
            "skills/release/SKILL.md": skill_file("release", "ships", "body one"),
            "agents/designer.md": "designer\n",
            "agents/tester.md": "tester\n",
            "agents/reviewer.md": "reviewer\n",
            "hooks/guard.py": "x = 1\n",
            "README.md": "readme\n",
            "evals/fixture/build.sh": "work=1\n",
            "evals/fixture/ui/web/index.html": "<p>web</p>\n",
            "evals/fixture/ui/app/main.qml": "Item {}\n",
            "evals/depends.json": json.dumps(depends_for_tests()),
        }
        files.update(case_files("add-feature", "plain", "add-feature-plain",
                                "behaviour", ""))
        files.update(case_files("add-feature", "ui", "add-feature-ui", "behaviour",
                                'ui_fixture web "web (px)" "index.html"\n'))
        files.update(case_files("fix-bug", "plain", "fix-bug-plain", "behaviour", ""))
        files.update(case_files("release", "plain", "release-plain", "behaviour", ""))
        files.update(case_files("release", "other", "release-other", "behaviour", ""))
        files.update(case_files("trigger", "release-1-fires", "trigger-release-1-fires",
                                "trigger", ""))
        files.update(case_files("trigger", "add-feature-5-near-miss",
                                "trigger-add-feature-5-near-miss", "trigger", None))
        self.c1 = self.repo.commit("Recorded", files)
        self.write_passes({name: self.c1 for name in BEHAVIOUR + [
            "trigger-release-1-fires", "trigger-add-feature-5-near-miss"]})
        self.c2 = self.repo.commit("Passes", {})
        self.repo_path = str(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_passes(self, commits: dict[str, str | None]) -> None:
        entries = {name: {"commit": commit, "date": "2026-11-01", "runs": 1}
                   for name, commit in commits.items() if commit}
        ev.write_passes(self.tmp, entries)
        self.repo.git("add", "-A")
        self.repo.git("commit", "-q", "--allow-empty", "-m", "Passes")

    def names(self, suite: str, release: bool = False) -> list[str]:
        return sorted(name for name, _ in ev.select(self.repo_path, release)[suite])

    def reasons(self, suite: str) -> dict[str, str]:
        return dict(ev.select(self.repo_path)[suite])


class TestSelect(_SelectRepo):
    def test_a_prompt_without_front_matter_names_its_path(self):
        self.repo.write({"evals/cases/fix-bug/plain/prompt.md": "Do it.\n"})
        with self.assertRaises(ValueError) as caught:
            ev.find_cases(self.repo_path, depends_for_tests())
        self.assertIn("fix-bug", str(caught.exception))
        self.assertIn("prompt.md", str(caught.exception))
        self.assertIn("no front matter", str(caught.exception))

    def test_nothing_changed_lists_nothing(self):
        selection = ev.select(self.repo_path)
        self.assertEqual({"behaviour": [], "trigger": []}, selection)
        cases = ev.find_cases(self.repo_path, depends_for_tests())
        self.assertEqual([], ev.commands(selection, cases))

    def test_a_release_body_change_lists_only_release_cases(self):
        self.repo.commit("Body", {
            "skills/release/SKILL.md": skill_file("release", "ships", "body two")})
        self.assertEqual(["release-other", "release-plain"], self.names("behaviour"))
        self.assertEqual([], self.names("trigger"))
        self.assertIn("skills/release/SKILL.md since", self.reasons("behaviour")["release-plain"])

    def test_a_release_description_change_adds_its_trigger_cases_and_near_misses(self):
        self.repo.commit("Description", {
            "skills/release/SKILL.md": skill_file("release", "ships things", "body one")})
        self.assertEqual(["release-other", "release-plain"], self.names("behaviour"))
        self.assertEqual(["trigger-add-feature-5-near-miss", "trigger-release-1-fires"],
                         self.names("trigger"))
        self.assertIn("front matter", self.reasons("trigger")["trigger-release-1-fires"])

    def test_another_skills_description_leaves_unrelated_triggers_alone(self):
        self.repo.commit("Description", {
            "skills/fix-bug/SKILL.md": skill_file("fix-bug", "fixes things", "body one")})
        self.assertEqual([], self.names("trigger"))
        self.assertEqual(["fix-bug-plain"], self.names("behaviour"))

    def test_a_designer_change_lists_every_case_whose_skill_calls_it(self):
        self.repo.commit("Designer", {"agents/designer.md": "designer two\n"})
        self.assertEqual(["add-feature-plain", "add-feature-ui", "fix-bug-plain"],
                         self.names("behaviour"))
        self.assertEqual([], self.names("trigger"))

    def test_a_reviewer_change_lists_all_three_skills(self):
        self.repo.commit("Reviewer", {"agents/reviewer.md": "reviewer two\n"})
        self.assertEqual(BEHAVIOUR, self.names("behaviour"))

    def test_a_ui_fixture_change_lists_only_its_cases(self):
        self.repo.commit("Web", {"evals/fixture/ui/web/index.html": "<p>web two</p>\n"})
        self.assertEqual(["add-feature-ui"], self.names("behaviour"))
        self.assertEqual([], self.names("trigger"))
        self.repo.commit("App", {"evals/fixture/ui/app/main.qml": "Item { x: 1 }\n"})
        self.assertEqual(["add-feature-ui"], self.names("behaviour"))

    def test_a_fixture_change_lists_every_scaffolded_case(self):
        self.repo.commit("Fixture", {"evals/fixture/build.sh": "work=2\n"})
        self.assertEqual(BEHAVIOUR, self.names("behaviour"))
        self.assertEqual(["trigger-release-1-fires"], self.names("trigger"))

    def test_a_hooks_change_lists_behaviour_not_trigger(self):
        self.repo.commit("Hooks", {"hooks/guard.py": "x = 2\n"})
        self.assertEqual(BEHAVIOUR, self.names("behaviour"))
        self.assertEqual([], self.names("trigger"))

    def test_a_change_outside_every_rule_lists_nothing(self):
        self.repo.commit("Docs", {"README.md": "readme two\n", "docs/a.md": "a\n",
                                  "tests/t.py": "t = 1\n", "tools/x.py": "y = 1\n"})
        self.assertEqual({"behaviour": [], "trigger": []}, ev.select(self.repo_path))

    def test_a_case_folder_change_lists_that_case(self):
        self.repo.commit("Grader", {"evals/cases/fix-bug/plain/graders/b.md": grader("type: llm")})
        self.assertEqual(["fix-bug-plain"], self.names("behaviour"))

    def test_a_case_without_a_record_is_listed(self):
        self.write_passes({name: self.c1 for name in BEHAVIOUR if name != "release-other"})
        self.assertEqual(["release-other"], self.names("behaviour"))
        self.assertEqual("no recorded pass", self.reasons("behaviour")["release-other"])

    def test_an_unknown_commit_lists_the_case(self):
        self.write_passes({**{name: self.c1 for name in BEHAVIOUR}, "release-other": FAKE})
        self.assertEqual(["release-other"], self.names("behaviour"))
        self.assertIn("is not in this clone", self.reasons("behaviour")["release-other"])

    def test_uncommitted_untracked_and_renamed_files_count(self):
        self.repo.write({"agents/tester.md": "tester two\n"})
        self.assertEqual(["release-other", "release-plain"], self.names("behaviour"))
        self.repo.git("checkout", "--", "agents/tester.md")
        self.assertEqual([], self.names("behaviour"))
        self.repo.write({"hooks/new.py": "z = 1\n"})
        self.assertEqual(BEHAVIOUR, self.names("behaviour"))
        self.repo.git("clean", "-fdq")
        self.repo.git("mv", "skills/fix-bug/SKILL.md", "skills/fix-bug/OLD.md")
        self.assertEqual(["fix-bug-plain"], self.names("behaviour"))

    def test_release_lists_every_trigger_case(self):
        self.assertEqual(["trigger-add-feature-5-near-miss", "trigger-release-1-fires"],
                         self.names("trigger", release=True))
        self.assertEqual([], self.names("behaviour", release=True))

    def test_main_prints_the_cases_and_the_commands(self):
        self.repo.commit("Body", {
            "skills/release/SKILL.md": skill_file("release", "ships", "body two")})
        completed = subprocess.run(
            [sys.executable, str(SELECT_PATH), "select", "--repo", self.repo_path],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("behaviour: 2 of 5 cases", completed.stdout)
        self.assertIn("trigger: 0 of 2 cases", completed.stdout)
        self.assertIn('--tag behaviour --case "release-*" --runs 1', completed.stdout)

    def test_main_says_when_there_is_nothing_to_run(self):
        completed = subprocess.run(
            [sys.executable, str(SELECT_PATH), "select", "--repo", self.repo_path],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("nothing to run", completed.stdout)

    def test_a_folder_that_is_not_a_repository_exits_two(self):
        with tempfile.TemporaryDirectory() as folder:
            completed = subprocess.run(
                [sys.executable, str(SELECT_PATH), "select", "--repo", folder],
                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(2, completed.returncode)

    def test_globs_fold_whole_groups_and_keep_exact_names(self):
        names = ["add-feature-claims-step-first", "add-feature-claims-step-first-local-plans",
                 "fix-bug-x", "fix-bug-y"]
        prefixes = ["add-feature-", "fix-bug-"]
        self.assertEqual(
            ["fix-bug-*", "add-feature-claims-step-first"],
            ev.case_globs({"add-feature-claims-step-first", "fix-bug-x", "fix-bug-y"},
                          names, prefixes))
        self.assertEqual([""], ev.case_globs(set(names), names, prefixes))
        self.assertEqual([], ev.case_globs(set(), names, prefixes))
        self.assertEqual(["fix-bug-x"], ev.case_globs({"fix-bug-x"}, names, prefixes))

    def test_commands_use_one_case_glob_per_line(self):
        self.repo.commit("Fixture", {"evals/fixture/build.sh": "work=2\n"})
        selection = ev.select(self.repo_path)
        cases = ev.find_cases(self.repo_path, depends_for_tests())
        lines = ev.commands(selection, cases)
        self.assertEqual(2, len(lines))
        self.assertTrue(lines[0].startswith("TMPDIR=$HOME/ev claude plugin eval . --tag behaviour"))
        self.assertNotIn("--case", lines[0])
        self.assertIn('--case "trigger-release-1-fires"', lines[1])
        self.assertIn("--scaffold", lines[1])

    def test_commands_run_one_case_at_a_time(self):
        self.repo.commit("Fixture", {"evals/fixture/build.sh": "work=2\n"})
        selection = ev.select(self.repo_path)
        cases = ev.find_cases(self.repo_path, depends_for_tests())
        lines = ev.commands(selection, cases)
        self.assertTrue(any("--tag behaviour" in line for line in lines))
        self.assertTrue(any("--tag trigger" in line for line in lines))
        for line in lines:
            self.assertEqual(re.findall(r"-j (\d+)", line), ["1"])

    def test_a_trigger_glob_without_a_scaffolded_case_has_no_scaffold_flag(self):
        self.repo.commit("Description", {
            "skills/add-feature/SKILL.md": skill_file("add-feature", "adds more", "body one")})
        selection = ev.select(self.repo_path)
        cases = ev.find_cases(self.repo_path, depends_for_tests())
        trigger = [line for line in ev.commands(selection, cases) if "--tag trigger" in line]
        self.assertEqual(1, len(trigger))
        self.assertIn('--case "trigger-add-feature-5-near-miss"', trigger[0])
        self.assertNotIn("--scaffold", trigger[0])


def result_file(folder: Path, cases: list[dict], version: int = 1) -> Path:
    path = folder / "aggregate-result.json"
    path.write_text(json.dumps({"schemaVersion": version,
                                "startedAt": "2026-11-05T09:30:00.000Z",
                                "cases": cases}), encoding="utf-8")
    return path


def run(score: float = 1, error: str | None = None, skipped: bool = False) -> dict:
    return {"score": score, "passed": score == 1, "error": error,
            "skippedPaidGraders": skipped, "costUsd": 0.1}


def result_case(name: str, *runs: dict) -> dict:
    return {"name": name, "arms": {"with": list(runs)}}


class TestRecord(_SelectRepo):
    def test_records_only_cases_whose_every_run_scored_one(self):
        path = result_file(self.tmp, [
            result_case("release-plain", run(), run()),
            result_case("release-other", run(), run(0.8)),
            result_case("fix-bug-plain", run(error="timeout")),
            result_case("add-feature-plain", run(skipped=True)),
            result_case("add-feature-ui"),
        ])
        recorded, refused, skipped = ev.record(self.repo_path, [path])
        head = self.repo.git("rev-parse", "HEAD")
        self.assertEqual({"release-plain": {"commit": head, "date": "2026-11-05", "runs": 2}},
                         recorded)
        self.assertEqual([], refused)
        self.assertEqual([
            "release-other: run 2 scored 0.8",
            "fix-bug-plain: run 1 has an error",
            "add-feature-plain: run 1 skipped paid graders",
            "add-feature-ui: no runs",
        ], skipped)

    def test_refuses_a_case_that_is_not_on_disk(self):
        path = result_file(self.tmp, [result_case("ghost-case", run())])
        recorded, refused, skipped = ev.record(self.repo_path, [path])
        self.assertEqual({}, recorded)
        self.assertEqual([], skipped)
        self.assertEqual(1, len(refused))
        self.assertIn("ghost-case", refused[0])

    def test_refuses_a_case_with_uncommitted_inputs(self):
        self.repo.write({"skills/release/SKILL.md": skill_file("release", "ships", "edited")})
        path = result_file(self.tmp, [
            result_case("release-plain", run()), result_case("fix-bug-plain", run())])
        recorded, refused, _ = ev.record(self.repo_path, [path])
        self.assertEqual(["fix-bug-plain"], sorted(recorded))
        self.assertEqual(1, len(refused))
        self.assertIn("release-plain", refused[0])
        self.assertIn("commit first", refused[0])

    def test_refuses_a_trigger_case_whose_front_matter_is_uncommitted(self):
        self.repo.write({"skills/release/SKILL.md": skill_file("release", "ships more", "body one")})
        path = result_file(self.tmp, [result_case("trigger-release-1-fires", run())])
        recorded, refused, _ = ev.record(self.repo_path, [path])
        self.assertEqual({}, recorded)
        self.assertIn("front matter", refused[0])

    def test_writes_sorted_lf_one_line_per_case(self):
        passes = {"b-case": {"commit": FAKE, "date": "2026-11-05", "runs": 1},
                  "a-case": {"commit": FAKE, "date": "2026-11-04", "runs": 3}}
        ev.write_passes(self.tmp, passes)
        raw = (self.tmp / "evals" / "passes.json").read_bytes()
        self.assertNotIn(b"\r", raw)
        lines = raw.decode("utf-8").splitlines()
        self.assertEqual(4, len(lines))
        self.assertTrue(lines[1].startswith('  "a-case"'))
        self.assertTrue(lines[2].startswith('  "b-case"'))
        self.assertEqual(passes, json.loads(raw))
        self.assertEqual([], [p.name for p in (self.tmp / "evals").glob("*.tmp")])

    def test_refuses_another_schema_version(self):
        path = result_file(self.tmp, [result_case("release-plain", run())], version=2)
        recorded, refused, _ = ev.record(self.repo_path, [path])
        self.assertEqual({}, recorded)
        self.assertIn("schemaVersion 2", refused[0])

    def test_refuses_a_file_with_a_missing_or_malformed_started_at(self):
        for started in (None, "", "yesterday", "2026-13-40T00:00:00Z", "2026-11-5", "20261105"):
            path = self.tmp / "aggregate-result.json"
            data = {"schemaVersion": 1, "cases": [result_case("release-plain", run())]}
            if started is not None:
                data["startedAt"] = started
            path.write_text(json.dumps(data), encoding="utf-8")
            recorded, refused, skipped = ev.record(self.repo_path, [path])
            self.assertEqual({}, recorded, started)
            self.assertEqual([], skipped, started)
            self.assertEqual(1, len(refused), started)
            self.assertIn("startedAt", refused[0])

    def test_main_prints_why_a_case_was_skipped_and_exits_zero(self):
        path = result_file(self.tmp, [
            result_case("fix-bug-plain", run()), result_case("release-plain", run(), run(0.5))])
        completed = subprocess.run(
            [sys.executable, str(SELECT_PATH), "record", str(path), "--repo", self.repo_path],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("recorded fix-bug-plain", completed.stdout)
        self.assertIn("skipped release-plain: run 2 scored 0.5", completed.stdout)
        self.assertNotIn("refused", completed.stdout)

    def test_main_exits_one_when_it_refused_a_case_and_still_keeps_the_rest(self):
        path = result_file(self.tmp, [
            result_case("fix-bug-plain", run()), result_case("ghost-case", run())])
        completed = subprocess.run(
            [sys.executable, str(SELECT_PATH), "record", str(path), "--repo", self.repo_path],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(1, completed.returncode, completed.stderr)
        stored = json.loads((self.tmp / "evals" / "passes.json").read_text(encoding="utf-8"))
        self.assertEqual(self.repo.git("rev-parse", "HEAD"), stored["fix-bug-plain"]["commit"])
        self.assertEqual(self.c1, stored["release-plain"]["commit"])


def covered(path: str, entries: list[str]) -> bool:
    return any(path.startswith(entry) if entry.endswith("/") else path == entry
               for entry in entries)


class TestEvalFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.depends = json.loads((ROOT / "evals" / "depends.json").read_text(encoding="utf-8"))
        cls.cases = ev.find_cases(ROOT, cls.depends)
        cls.agents = sorted(p.stem for p in (ROOT / "agents").glob("*.md"))

    def test_depends_names_what_each_skill_cites(self):
        problems = []
        for skill, entries in self.depends["skills"].items():
            text = (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
            for agent in self.agents:
                if re.search(rf"devflow:{re.escape(agent)}\b", text) \
                        and not covered(f"agents/{agent}.md", entries):
                    problems.append(f"{skill} calls devflow:{agent} but depends lacks agents/{agent}.md")
            for cited in set(re.findall(r"skills/[A-Za-z0-9_./-]*[A-Za-z0-9_]", text)):
                if (ROOT / cited).exists() and not covered(cited, entries):
                    problems.append(f"{skill} cites {cited} but depends lacks it")
            named = set(re.findall(r"references/([a-z-]+\.md)", text))
            named |= set(re.findall(r"\b((?:build|motion|core)\.md)", text))
            for name in sorted(named):
                cited = f"skills/review-ui/references/{name}"
                if (ROOT / cited).exists() and not covered(cited, entries):
                    problems.append(f"{skill} cites references/{name} but depends lacks {cited}")
        self.assertEqual([], problems)

    def test_depends_entries_exist(self):
        entries = list(self.depends["every_behaviour_case"])
        for paths in self.depends["skills"].values():
            entries.extend(paths)
        for entry in entries:
            self.assertTrue((ROOT / entry).exists(), entry)

    def test_every_behaviour_group_has_a_depends_entry(self):
        groups = {case.skill for case in self.cases if case.suite == "behaviour"}
        triggered = {case.skill for case in self.cases if case.suite == "trigger"}
        self.assertEqual([], sorted(groups - set(self.depends["skills"])))
        self.assertEqual([], sorted(triggered - set(self.depends["skills"])))

    def test_every_near_miss_maps_to_a_skill_or_null(self):
        near = {case.rel.rsplit("/", 1)[1] for case in self.cases
                if case.suite == "trigger" and case.rel.endswith("near-miss")}
        self.assertEqual(sorted(near), sorted(self.depends["near_misses"]))
        for target in self.depends["near_misses"].values():
            self.assertTrue(target is None or target in self.depends["skills"], target)

    def test_every_case_has_one_unique_name_equal_to_its_case_yaml(self):
        names = [case.name for case in self.cases]
        self.assertTrue(all(names))
        self.assertEqual(len(names), len(set(names)))
        for case in self.cases:
            yaml = case.folder / "case.yaml"
            if yaml.is_file():
                found = re.search(r"^name:\s*(.+?)\s*$", yaml.read_text(encoding="utf-8"),
                                  re.MULTILINE)
                self.assertIsNotNone(found, case.rel)
                self.assertEqual(case.name, found.group(1).strip("'\""), case.rel)

    def test_passes_names_only_cases_on_disk_with_well_formed_entries(self):
        passes = json.loads((ROOT / "evals" / "passes.json").read_text(encoding="utf-8"))
        on_disk = {case.name for case in self.cases}
        for name, entry in passes.items():
            self.assertIn(name, on_disk)
            self.assertEqual({"commit", "date", "runs"}, set(entry), name)
            self.assertRegex(entry["commit"], r"^[0-9a-f]{40}$", name)
            self.assertRegex(entry["date"], r"^\d{4}-\d{2}-\d{2}$", name)
            self.assertIsInstance(entry["runs"], int, name)
            self.assertGreaterEqual(entry["runs"], 1, name)

    def test_passes_file_is_lf_and_sorted_one_line_per_case(self):
        raw = (ROOT / "evals" / "passes.json").read_bytes()
        self.assertNotIn(b"\r", raw)
        passes = json.loads(raw)
        self.assertEqual(len(passes) + 2, len(raw.decode("utf-8").splitlines()))
        self.assertEqual(sorted(passes), list(passes))


class TestPartsCaseGraders(unittest.TestCase):
    def setUp(self):
        scaffold = (PARTS_CASE / "scaffold.sh").read_text(encoding="utf-8")
        self.parts = re.findall(r"`(implementer: [^`]+)`", scaffold)
        self.passes = board_passes(self.parts)
        self.graders = agent_graders(PARTS_CASE)

    def test_the_board_passes_nothing_for_a_part_equal_to_the_pin(self):
        self.assertEqual(len(self.parts), 3)
        self.assertEqual(self.passes, {"part 1 of 3": "nothing", "part 2 of 3": 'model: "opus", effort: "medium"',
                                       "part 3 of 3": "nothing"})

    def test_the_calls_the_board_prints_pass_every_agent_grader(self):
        calls = [part_call(label, passes) for label, passes in self.passes.items()]
        self.assertEqual([], failing(self.graders, calls))

    def test_each_part_has_a_grader_that_needs_its_call(self):
        for label in self.passes:
            with self.subTest(label):
                self.assertTrue(any(label in pattern and low >= 1 for _, pattern, low, _ in self.graders))

    def test_an_override_on_a_part_equal_to_the_pin_fails_a_grader(self):
        for label, passes in self.passes.items():
            if passes != "nothing":
                continue
            with self.subTest(label):
                calls = [part_call(other, 'model: "sonnet", effort: "medium"' if other == label else value)
                         for other, value in self.passes.items()]
                self.assertNotEqual([], failing(self.graders, calls))


class TestNextStepByHandJudge(unittest.TestCase):
    def setUp(self):
        case = ROOT / "evals" / "cases" / "next-step" / "stops-at-a-by-hand-release"
        _, self.rubric = ev.frontmatter((case / "graders" / "says-by-hand.md").read_text(encoding="utf-8"))

    def test_the_rubric_does_not_ask_for_a_name_the_stop_line_never_prints(self):
        self.assertNotIn("Ada,", self.rubric)
        self.assertIn("does not have to name Ada", self.rubric)

    def test_the_rubric_still_fails_a_reply_that_starts_the_release(self):
        for phrase in ("starts the release", "tags", "builds or publishes", "says it will do the step", "offers to run `/devflow:release` itself"):
            with self.subTest(phrase):
                self.assertIn(phrase, self.rubric)


class TestColdReadQuestionsJudge(unittest.TestCase):
    def setUp(self):
        case = ROOT / "evals" / "cases" / "manage-project" / "vague-step-gets-a-cold-read"
        _, self.rubric = ev.frontmatter((case / "graders" / "ranked-questions.md").read_text(encoding="utf-8"))

    def test_the_rubric_does_not_fail_a_reply_that_calls_the_draft_unready(self):
        self.assertNotIn("says the draft is invalid", self.rubric)
        for phrase in ("not ready", "can't start as written", "has vague steps", "must wait for another release or for the maintainer's answers", "is not a reason to fail"):
            with self.subTest(phrase):
                self.assertIn(phrase, self.rubric)

    def test_the_rubric_still_fails_a_reply_that_answers_or_writes_the_plan(self):
        for phrase in ("gives no questions from the cold read", "answers a maintainer's question itself", "says the plan was accepted or the plan file was written", "must gain a Review Focus or Interfaces section before it can be used"):
            with self.subTest(phrase):
                self.assertIn(phrase, self.rubric)

    def test_the_rubric_still_asks_for_ranked_and_sorted_questions(self):
        for phrase in ("most important first", "already answers or that are minor", "the ones the maintainer must decide"):
            with self.subTest(phrase):
                self.assertIn(phrase, self.rubric)


CLAIM_CASES = ROOT / "evals" / "cases"
PINNED_DATE = "2026-10-22"
OTHER_DATE = "2026-11-21"


def regex_grader_passes(path: Path, trace: str) -> bool:
    fields, _ = ev.frontmatter(path.read_text(encoding="utf-8"))
    flags = re.IGNORECASE if "i" in ev.scalar(fields.get("flags", "")) else 0
    found = re.search(ev.scalar(fields["pattern"]), trace, flags) is not None
    return not found if ev.scalar(fields.get("match", "contains")) == "not_contains" else found


def plan_trace(rows: dict[str, str]) -> str:
    table = {"1 Fix #3: average of an empty list": "—", "2 Median": "—", "3 JSON output": "in progress (2026-10-19 22:05)",
             "4 Reject non-numbers": "—", "5 Top N": "—", "6 Release 0.3.0": "—"}
    table.update(rows)
    text = "\n".join(f"| {step} | {state} |" for step, state in table.items())
    commit = json.dumps({"tool": "Bash", "command": 'git commit -m "Status" -- docs/plans/release-0.3.0.md'})
    return json.dumps({"tool": "Read", "output": text}) + "\n" + commit


def edit_trace(step: str, state: str, before: dict[str, str] | None = None) -> str:
    edit = json.dumps({"tool": "Edit", "old_string": f"| {step} | \u2014 |", "new_string": f"| {step} | {state} |"})
    return plan_trace(before or {}) + "\n" + edit + "\n" + plan_trace({**(before or {}), step: state})


class TestClaimGradersTakeAnyDate(unittest.TestCase):
    NEXT_PLAN_BEFORE = {"2 Median": "in progress (2026-10-22 09:30)", "5 Top N": "in progress (2026-10-22 09:45)",
                        "1 Mode": "\u2014", "2 Range": "\u2014", "3 Sum of squares": "\u2014"}
    CLAIMS = {
        CLAIM_CASES / "next-step" / "skips-a-claimed-step" / "graders" / "takes-step-5.md": ("5 Top N", {"2 Median": "in progress (2026-10-22 09:30)"}),
        CLAIM_CASES / "next-step" / "takes-the-next-step-and-claims-it" / "graders" / "row-in-progress.md": ("2 Median", {}),
        CLAIM_CASES / "add-feature" / "claims-step-first" / "graders" / "row-in-progress.md": ("2 Median", {}),
        CLAIM_CASES / "add-feature" / "claims-step-first-local-plans" / "graders" / "row-in-progress.md": ("2 Median", {}),
        CLAIM_CASES / "fix-bug" / "claims-step-first" / "graders" / "row-in-progress.md": ("1 Fix #3: average of an empty list", {}),
        CLAIM_CASES / "next-step" / "falls-back-to-the-next-plan" / "graders" / "takes-step-3.md": ("3 Sum of squares", NEXT_PLAN_BEFORE),
        CLAIM_CASES / "next-step" / "runs-fix-bug-for-a-bug-step" / "graders" / "row-in-progress.md": ("1 Fix #3: average of an empty list", {}),
    }

    def test_a_claim_passes_on_the_pinned_date_and_on_another_and_no_claim_fails(self):
        for path, (step, before) in self.CLAIMS.items():
            with self.subTest(path.relative_to(CLAIM_CASES).as_posix()):
                self.assertTrue(regex_grader_passes(path, edit_trace(step, f"in progress ({PINNED_DATE} 10:00)", before)))
                self.assertTrue(regex_grader_passes(path, edit_trace(step, f"in progress ({OTHER_DATE} 10:03)", before)))
                self.assertFalse(regex_grader_passes(path, plan_trace(before)))

    def test_rewriting_the_claimed_step_fails_leaves_step_2_on_any_date_and_leaving_it_passes(self):
        path = CLAIM_CASES / "next-step" / "skips-a-claimed-step" / "graders" / "leaves-step-2.md"
        claimed = {"2 Median": "in progress (2026-10-22 09:30)"}
        self.assertFalse(regex_grader_passes(path, edit_trace("2 Median", f"in progress ({PINNED_DATE} 10:00)")))
        self.assertFalse(regex_grader_passes(path, edit_trace("2 Median", f"in progress ({OTHER_DATE} 10:00)")))
        self.assertTrue(regex_grader_passes(path, edit_trace("5 Top N", f"in progress ({OTHER_DATE} 10:00)", claimed)))


if __name__ == "__main__":
    unittest.main()
