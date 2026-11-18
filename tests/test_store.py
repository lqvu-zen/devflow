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
STORE_PATH = ROOT / "hooks" / "devflow_store.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


devflow_store = _load("devflow_store_under_test", STORE_PATH)

GATE_TEST = 'if [ -f "$p/.claude/devflow.json" ] || [ -f "$g/devflow-store" ]; then'


def link(gitdir: Path, store: Path) -> Path:
    gitdir.mkdir(parents=True, exist_ok=True)
    pointer = gitdir / devflow_store.POINTER
    pointer.write_text(str(store) + "\n", encoding="utf-8")
    return pointer


def make_store(store: Path, config: dict | None) -> Path:
    store.mkdir(parents=True, exist_ok=True)
    if config is not None:
        (store / ".claude").mkdir(exist_ok=True)
        (store / ".claude" / "devflow.json").write_text(json.dumps(config), encoding="utf-8")
    (store / devflow_store.MANIFEST).write_text(
        json.dumps({"root_commit": "0" * 40, "origin": ""}), encoding="utf-8")
    return store


def worktree(main: Path, wt: Path) -> Path:
    admin = main / ".git" / "worktrees" / wt.name
    admin.mkdir(parents=True, exist_ok=True)
    (admin / "commondir").write_text("../..\n", encoding="utf-8")
    wt.mkdir(parents=True, exist_ok=True)
    (wt / ".git").write_text(f"gitdir: {admin.as_posix()}\n", encoding="utf-8")
    return wt


class StoreCase(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="devflow-store-"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.main = self.base / "main"
        (self.main / ".git").mkdir(parents=True)
        self.store = self.base / "home" / "projects" / "notes"


class TestCommonDir(StoreCase):
    def test_a_main_checkout_uses_its_git_folder(self):
        self.assertEqual(devflow_store.common_dir(self.main), self.main / ".git")
        self.assertEqual(devflow_store.pointer_file(self.main), self.main / ".git" / "devflow-store")

    def test_a_worktree_follows_gitdir_and_commondir(self):
        wt = worktree(self.main, self.base / "wt")
        self.assertEqual(devflow_store.common_dir(wt).resolve(), (self.main / ".git").resolve())

    def test_a_relative_gitdir_is_read_from_the_project(self):
        wt = self.base / "rel"
        admin = self.main / ".git" / "worktrees" / "rel"
        admin.mkdir(parents=True)
        (admin / "commondir").write_text("../..\n", encoding="utf-8")
        wt.mkdir()
        (wt / ".git").write_text("gitdir: ../main/.git/worktrees/rel\n", encoding="utf-8")
        self.assertEqual(devflow_store.common_dir(wt).resolve(), (self.main / ".git").resolve())

    def test_without_git_there_is_no_pointer(self):
        bare = self.base / "bare"
        bare.mkdir()
        self.assertFalse(devflow_store.pointer_file(bare).is_file())
        self.assertIsNone(devflow_store.find(bare))

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_a_real_worktree_matches_git(self):
        repo = self.base / "repo"
        repo.mkdir()
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run(git + ["init", "-q"], cwd=repo, check=True, capture_output=True)
        subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "x"], cwd=repo, check=True,
                       capture_output=True)
        wt = self.base / "real-wt"
        subprocess.run(git + ["worktree", "add", "-q", str(wt)], cwd=repo, check=True, capture_output=True)
        common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=wt,
                                check=True, capture_output=True, text=True).stdout.strip()
        self.assertEqual(devflow_store.common_dir(wt).resolve(), Path(common).resolve())
        self.assertEqual(devflow_store.common_dir(repo).resolve(), Path(common).resolve())


class TestFind(StoreCase):
    def test_an_in_repo_config_is_in_repo_mode(self):
        (self.main / ".claude").mkdir()
        (self.main / ".claude" / "devflow.json").write_text('{"name": "Notes"}', encoding="utf-8")
        found = devflow_store.find(self.main)
        self.assertEqual(found, devflow_store.Found(self.main, {"name": "Notes"}, None))

    def test_an_in_repo_config_wins_over_a_pointer(self):
        (self.main / ".claude").mkdir()
        (self.main / ".claude" / "devflow.json").write_text('{"name": "here"}', encoding="utf-8")
        make_store(self.store, {"name": "there"})
        link(self.main / ".git", self.store)
        found = devflow_store.find(self.main)
        self.assertEqual((found.config, found.store), ({"name": "here"}, None))

    def test_a_pointer_reads_the_store_config(self):
        make_store(self.store, {"name": "there"})
        link(self.main / ".git", self.store)
        self.assertEqual(devflow_store.find(self.main),
                         devflow_store.Found(self.store, {"name": "there"}, self.store))
        wt = worktree(self.main, self.base / "wt")
        self.assertEqual(devflow_store.find(wt),
                         devflow_store.Found(self.store, {"name": "there"}, self.store))

    def test_a_pointer_with_crlf_and_a_byte_order_mark(self):
        make_store(self.store, {"name": "there"})
        (self.main / ".git" / "devflow-store").write_bytes(
            b"\xef\xbb\xbf\r\n" + str(self.store).encode("utf-8") + b"\r\n")
        self.assertEqual(devflow_store.find(self.main).store, self.store)

    def test_neither_is_none(self):
        self.assertIsNone(devflow_store.find(self.main))

    def test_a_missing_store_raises(self):
        link(self.main / ".git", self.store)
        with self.assertRaises(devflow_store.StoreError) as caught:
            devflow_store.find(self.main)
        self.assertIn(str(self.store), str(caught.exception))

    def test_an_empty_or_relative_pointer_raises(self):
        make_store(self.store, {"name": "there"})
        pointer = self.main / ".git" / "devflow-store"
        for text in ("", "\n  \n", "projects/notes\n", "~/.devflow/projects/notes\n"):
            pointer.write_text(text, encoding="utf-8")
            with self.assertRaises(devflow_store.StoreError):
                devflow_store.find(self.main)
        pointer.write_bytes(b"\xff\xfe\x00bad")
        with self.assertRaises(devflow_store.StoreError):
            devflow_store.find(self.main)

    def test_a_store_without_a_config_raises(self):
        make_store(self.store, None)
        link(self.main / ".git", self.store)
        with self.assertRaises(devflow_store.StoreError) as caught:
            devflow_store.find(self.main)
        self.assertIn("has no .claude/devflow.json", str(caught.exception))

    def test_an_undecodable_git_file_raises(self):
        wt = self.base / "wt"
        wt.mkdir()
        (wt / ".git").write_bytes(b"gitdir: \xff\xfe\x80\n")
        with self.assertRaises(devflow_store.StoreError):
            devflow_store.find(wt)


class TestHome(unittest.TestCase):
    def test_devflow_home_overrides_the_root(self):
        self.assertEqual(devflow_store.home({"DEVFLOW_HOME": "/tmp/devflow-home"}), Path("/tmp/devflow-home"))

    def test_the_default_is_under_the_user_home(self):
        self.assertEqual(devflow_store.home({}), Path.home() / ".devflow")


class TestHookGate(unittest.TestCase):
    def test_both_hooks_share_one_gate(self):
        hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
        guard = hooks["PreToolUse"][0]["hooks"][0]["command"]
        start = hooks["SessionStart"][0]["hooks"][0]["command"]
        self.assertIn(GATE_TEST, guard)
        self.assertIn(GATE_TEST, start)
        self.assertEqual(guard.split(GATE_TEST)[0], start.split(GATE_TEST)[0])
        self.assertNotIn("git ", guard.split(GATE_TEST)[0])
        self.assertNotIn("$(", guard.split(GATE_TEST)[0])


if __name__ == "__main__":
    unittest.main()
