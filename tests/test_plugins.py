from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_RUNTIME = (
    "skills",
    "agents",
    "hooks",
    "templates",
    "tools/model_check.py",
    "tools/session_extract.py",
    "tools/devflow_checks.py",
)
PLUGIN_PATH = re.compile(r"(?<!\.claude/)(?<!\.claude\\)\bplugins[/\\]")
MOVED_SKILL = re.compile(r"\bskills[/\\]review-ui\b")


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _marketplace_entries(root: Path) -> list[dict]:
    data = _load_json(root / ".claude-plugin" / "marketplace.json")
    if not isinstance(data, dict) or not isinstance(data.get("plugins"), list):
        return []
    return [entry for entry in data["plugins"] if isinstance(entry, dict)]


def _layout_errors(root: Path) -> list[str]:
    errors: list[str] = []
    entries = _marketplace_entries(root)
    plugins = root / "plugins"
    folders = sorted(path for path in plugins.iterdir() if path.is_dir()) if plugins.is_dir() else []
    for folder in folders:
        name = folder.name
        label = f"plugins/{name}"
        manifest = _load_json(folder / ".claude-plugin" / "plugin.json")
        if not isinstance(manifest, dict):
            errors.append(f"{label}: no .claude-plugin/plugin.json")
        elif manifest.get("name") != name:
            errors.append(f"{label}: plugin.json name is {manifest.get('name')!r}, not the folder name")
        listed = [entry for entry in entries if entry.get("source") == f"./plugins/{name}"]
        if not listed:
            errors.append(f"{label}: not listed in .claude-plugin/marketplace.json")
        for entry in listed:
            if "version" in entry:
                errors.append(f"{label}: its marketplace entry carries a version")
            if entry.get("name") != name:
                errors.append(f"{label}: its marketplace entry name is {entry.get('name')!r}, not the folder name")
        if (folder / "hooks").exists():
            errors.append(f"{label}: holds hooks/")
    for entry in entries:
        source = entry.get("source")
        if isinstance(source, str) and source.startswith("./plugins/"):
            if not (root / source[2:]).is_dir():
                errors.append(f"{source}: listed but missing")
    return sorted(errors)


def _r1_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for item in BASE_RUNTIME:
        path = root / item
        if path.is_file():
            found.append(path)
        elif path.is_dir():
            found += sorted(
                child for child in path.rglob("*")
                if child.is_file() and "__pycache__" not in child.relative_to(root).parts
            )
    return found


def _r1_errors(root: Path) -> list[str]:
    errors: list[str] = []
    for path in _r1_files(root):
        data = path.read_bytes()
        if b"\0" in data:
            continue
        rel = path.relative_to(root).as_posix()
        for number, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
            if PLUGIN_PATH.search(line):
                errors.append(f"{rel}:{number}: names a path under plugins/")
            elif MOVED_SKILL.search(line):
                errors.append(f"{rel}:{number}: names skills/review-ui, which moved to devflow-ui")
    return sorted(errors)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _manifest(name: str) -> str:
    return json.dumps({"name": name})


def _marketplace(*entries: dict) -> str:
    base = {"name": "devflow", "source": "./", "version": "0.3.0"}
    return json.dumps({"name": "m", "plugins": [base, *entries]})


def _entry(name: str, **extra) -> dict:
    return {"name": name, "source": f"./plugins/{name}", **extra}


class TestPluginLayout(unittest.TestCase):
    def _root(self, temp: str, *entries: dict, manifest: str | None = "x") -> Path:
        root = Path(temp)
        _write(root / ".claude-plugin" / "marketplace.json", _marketplace(*entries))
        if manifest is not None:
            _write(root / "plugins" / "x" / ".claude-plugin" / "plugin.json", _manifest(manifest))
        return root

    def test_the_repository_layout_holds(self):
        self.assertEqual(_layout_errors(ROOT), [])

    def test_a_good_plugin_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(temp, _entry("x"))
            self.assertEqual(_layout_errors(root), [])

    def test_an_unlisted_plugin_is_named(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(temp)
            found = _layout_errors(root)
        self.assertEqual(found, ["plugins/x: not listed in .claude-plugin/marketplace.json"])

    def test_a_listed_version_is_named(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(temp, _entry("x", version="1.0.0"))
            found = _layout_errors(root)
        self.assertEqual(found, ["plugins/x: its marketplace entry carries a version"])

    def test_a_plugin_with_hooks_is_named(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(temp, _entry("x"))
            _write(root / "plugins" / "x" / "hooks" / "hooks.json", "{}")
            found = _layout_errors(root)
        self.assertEqual(found, ["plugins/x: holds hooks/"])

    def test_a_missing_or_misnamed_manifest_is_named(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(temp, _entry("x"), manifest=None)
            (root / "plugins" / "x").mkdir(parents=True)
            missing = _layout_errors(root)
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(temp, _entry("x"), manifest="other")
            misnamed = _layout_errors(root)
        self.assertEqual(missing, ["plugins/x: no .claude-plugin/plugin.json"])
        self.assertEqual(misnamed, ["plugins/x: plugin.json name is 'other', not the folder name"])

    def test_a_listed_folder_that_is_missing_is_named(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(temp, _entry("gone"), manifest=None)
            found = _layout_errors(root)
        self.assertEqual(found, ["./plugins/gone: listed but missing"])

    def test_a_misnamed_marketplace_entry_is_named(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(temp, {"name": "other", "source": "./plugins/x"})
            found = _layout_errors(root)
        self.assertEqual(found, ["plugins/x: its marketplace entry name is 'other', not the folder name"])

    def test_an_unreadable_marketplace_counts_as_no_entries(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write(root / ".claude-plugin" / "marketplace.json", "{not json")
            _write(root / "plugins" / "x" / ".claude-plugin" / "plugin.json", _manifest("x"))
            found = _layout_errors(root)
        self.assertEqual(found, ["plugins/x: not listed in .claude-plugin/marketplace.json"])


class TestBaseOnly(unittest.TestCase):
    def test_no_base_runtime_file_names_a_plugin_path(self):
        self.assertEqual(_r1_errors(ROOT), [])

    def test_a_base_file_naming_a_plugin_path_is_named(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write(root / "skills" / "a" / "SKILL.md", "See plugins/devflow-ui/skills/review-ui/x.md\n")
            _write(root / "tools" / "model_check.py", 'PATH = "plugins/x"\n')
            _write(root / "hooks" / "guard.py", 'p = "${CLAUDE_PLUGIN_ROOT}\\plugins\\x"\n')
            _write(root / "hooks" / "x.py", 'p = "~/.claude/plugins/devflow/hooks"\nq = "myplugins/x"\n')
            _write(root / "tools" / "eval_select.py", 'PATH = "plugins/x"\n')
            _write(root / "evals" / "depends.json", '{"y": ["plugins/x/"]}\n')
            _write(root / "skills" / "a" / "__pycache__" / "c.pyc", "plugins/x\n")
            (root / "templates").mkdir()
            (root / "templates" / "bin.dat").write_bytes(b"plugins/x\0")
            found = _r1_errors(root)
        self.assertEqual(
            found,
            [
                "hooks/guard.py:1: names a path under plugins/",
                "skills/a/SKILL.md:1: names a path under plugins/",
                "tools/model_check.py:1: names a path under plugins/",
            ],
        )

    def test_a_base_file_naming_the_moved_skill_is_named(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write(root / "skills" / "a" / "SKILL.md", "Pass `skills/review-ui/references/core.md`.\n")
            _write(root / "agents" / "b.md", "Run skills\\review-ui\\inspect-site.mjs\n")
            _write(root / "templates" / "c.md", "Run /devflow-ui:review-ui and skills/review-uix.\n")
            _write(root / "evals" / "depends.json", '{"review-ui": ["skills/review-ui/"]}\n')
            found = _r1_errors(root)
        self.assertEqual(
            found,
            [
                "agents/b.md:1: names skills/review-ui, which moved to devflow-ui",
                "skills/a/SKILL.md:1: names skills/review-ui, which moved to devflow-ui",
            ],
        )


if __name__ == "__main__":
    unittest.main()
