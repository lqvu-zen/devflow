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
CHECKS_PATH = ROOT / "tools" / "devflow_checks.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


checks = _load("devflow_checks", CHECKS_PATH)

CONFIG = {
    "checks": {
        "version_files": [
            {"path": "app/__init__.py", "pattern": "^__version__ = \"([^\"]+)\""},
            {"path": "setup_freeze.py", "pattern": "^\\s*version=\"([^\"]+)\"",
             "numbers_only": True},
        ],
        "no_new_python_comments": ["app/"],
    }
}


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

    def commit(self, title: str, files: dict[str, str | None]) -> str:
        for name, body in files.items():
            path = self.folder / name
            if body is None:
                path.unlink()
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8", newline="\n")
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", title)
        return self.git("rev-parse", "HEAD")


def init_file(version: str) -> str:
    return f'"""App."""\n\n__version__ = "{version}"\n'


def setup_file(version: str) -> str:
    return f'setup(\n    name="App",\n        version="{version}",\n)\n'


class _RepoCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="devflow-checks-"))
        self.repo = GitRepo(self.tmp)
        self.root = self.repo.commit("Initial", {
            ".claude/devflow.json": json.dumps(CONFIG),
            "app/__init__.py": init_file("2.3.1"),
            "setup_freeze.py": setup_file("2.3.1"),
            "app/a.py": "def a():\n    return 1  # keeps one\n",
        })
        self.config = checks.checks_from(CONFIG)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestVersionCheck(_RepoCase):
    def problems(self, base: str | None = None, head: str = "HEAD") -> list[str]:
        repo = str(self.tmp)
        start = checks.commit_range(repo, base or self.root, head)
        return checks.version_problems_in(repo, checks.commits_in(repo, start, head),
                                          self.config.version_files)

    def test_the_release_titles_match(self):
        match = checks.RELEASE_TITLE.match
        self.assertEqual(match("Release candidate 2.3.1-rc1").group(1), "2.3.1-rc1")
        self.assertEqual(match("Release 2.3.1").group(2), "2.3.1")
        self.assertIsNone(match("Release 2.3.1 and a fix"))
        self.assertIsNone(match("feat: Release 2.3.1"))

    def test_a_feature_commit_bumping_the_version_fails(self):
        sha = self.repo.commit("feat: x", {"app/__init__.py": init_file("2.3.2")})
        problems = self.problems()
        self.assertEqual(len(problems), 1)
        self.assertIn(f'{sha[:7]} "feat: x" changes the version in app/__init__.py 2.3.1 -> 2.3.2',
                      problems[0])

    def test_a_title_that_does_not_match_the_version_fails(self):
        self.repo.commit("Release 2.4.0", {"app/__init__.py": init_file("2.4.1")})
        self.assertIn("sets the version in app/__init__.py to 2.4.1, not 2.4.0", self.problems()[0])

    def test_reverting_a_release_fails(self):
        self.repo.commit("Release 2.4.0", {"app/__init__.py": init_file("2.4.0")})
        self.repo.commit('Revert "Release 2.4.0"', {"app/__init__.py": init_file("2.3.1")})
        problems = self.problems()
        self.assertEqual(len(problems), 1)
        self.assertIn("Revert", problems[0])

    def test_clean_and_release_commits_pass(self):
        self.repo.commit("feat: clean", {"app/a.py": "def a():\n    return 2  # keeps one\n"})
        self.repo.commit("Release candidate 2.4.0-rc1", {
            "app/__init__.py": init_file("2.4.0-rc1"), "setup_freeze.py": setup_file("2.4.0")})
        self.repo.commit("Release 2.4.0", {"app/__init__.py": init_file("2.4.0")})
        self.assertEqual(self.problems(), [])

    def test_a_numbers_only_file_with_the_rc_fails(self):
        self.repo.commit("Release candidate 2.4.0-rc1", {
            "app/__init__.py": init_file("2.4.0-rc1"), "setup_freeze.py": setup_file("2.4.0-rc1")})
        self.assertIn("sets the version in setup_freeze.py to 2.4.0-rc1, not 2.4.0",
                      self.problems()[0])

    def test_without_version_files_nothing_is_checked(self):
        self.repo.commit("feat: x", {"app/__init__.py": init_file("2.3.2")})
        repo = str(self.tmp)
        self.assertEqual(checks.version_problems_in(repo, checks.commits_in(repo, self.root, "HEAD"),
                                                    ()), [])

    def test_main_reports_and_exits(self):
        self.repo.commit("feat: x", {"app/__init__.py": init_file("2.3.2")})
        result = subprocess.run([sys.executable, str(CHECKS_PATH), "version", "--base", self.root,
                                 "--head", "HEAD", "--repo", str(self.tmp)],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 1)
        self.assertIn("changes the version", result.stdout)
        result = subprocess.run([sys.executable, str(CHECKS_PATH), "comments", "--base", self.root,
                                 "--head", "HEAD", "--repo", str(self.tmp)],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "comments: ok (1 commits)"))


class TestCommentCheck(_RepoCase):
    def problems(self) -> list[str]:
        return checks.comment_problems_in(str(self.tmp), self.root, "HEAD",
                                          self.config.comment_dirs)

    def test_a_full_line_comment_fails(self):
        self.repo.commit("feat", {"app/a.py": "def a():\n    # why\n    return 1  # keeps one\n"})
        self.assertEqual(self.problems(), [
            'app/a.py:2: new comment "# why" (.claude/devflow.md, Architecture rules)'])

    def test_a_trailing_comment_fails(self):
        self.repo.commit("feat", {"app/a.py": "def a():\n    return 1  # keeps one\nb = 2  # two\n"})
        self.assertEqual(len(self.problems()), 1)
        self.assertIn("app/a.py:3", self.problems()[0])

    def test_a_new_file_with_a_comment_fails(self):
        self.repo.commit("feat", {"app/c.py": "x = 1\n# note\n"})
        self.assertIn('app/c.py:2: new comment "# note"', self.problems()[0])

    def test_what_is_not_a_new_comment_passes(self):
        self.repo.commit("feat", {
            "app/a.py": "def a():\n    return 1\n",
            "app/b.py": "def b():\n    return 1  # keeps one\n",
            "app/c.py": "#!/usr/bin/env python\n# -*- coding: utf-8 -*-\n"
                        'import os  # noqa: E402\nx = "# not a comment"\n'
                        'y = 1  # type: ignore[assignment]\n\n\ndef f():\n    """A docstring."""\n',
            "tests/x.py": "# a comment in tests\n",
        })
        self.assertEqual(self.problems(), [])

    def test_without_dirs_nothing_is_checked(self):
        self.repo.commit("feat", {"app/c.py": "x = 1\n# note\n"})
        self.assertEqual(checks.comment_problems_in(str(self.tmp), self.root, "HEAD", ()), [])


if __name__ == "__main__":
    unittest.main()
