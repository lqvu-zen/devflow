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
MOVED_RELEASE = re.compile(r"\bdevflow:tester\b|\bskills[/\\]release(?![\w-])|\brelease[ -]mode\b", re.IGNORECASE)
OLD_NAME = re.compile(r"(?<![\w-])/?devflow:(?:release|review-ui|tester)(?![\w-])")
MOVED_NAME_SCAN = ("skills", "agents", "templates", "README.md", "CLAUDE.md")
README_ROW = re.compile(r"^\| (Skill|Agent) \| `([^`]+)` \|", re.MULTILINE)
README_TEMPLATE = re.compile(r"`([^`]+\.(?:md|json|yml))`")


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


def _r1_files(root: Path, items: tuple[str, ...] = BASE_RUNTIME) -> list[Path]:
    found: list[Path] = []
    for item in items:
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
            elif moved := MOVED_RELEASE.search(line):
                errors.append(f"{rel}:{number}: names {moved.group(0)}, which moved to devflow-release")
    return sorted(errors)


def _moved_name_errors(root: Path) -> list[str]:
    errors: list[str] = []
    for path in _r1_files(root, MOVED_NAME_SCAN):
        data = path.read_bytes()
        if b"\0" in data:
            continue
        rel = path.relative_to(root).as_posix()
        for number, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
            for moved in OLD_NAME.finditer(line):
                errors.append(f"{rel}:{number}: names {moved.group(0)}, the old name of a moved part")
    return sorted(errors)


def _folder_names(root: Path) -> dict[str, set[str]]:
    skills = {f"/devflow:{p.parent.name}" for p in (root / "skills").glob("*/SKILL.md")}
    agents = {f"devflow:{p.stem}" for p in (root / "agents").glob("*.md")}
    for plugin in sorted(p for p in (root / "plugins").glob("*") if p.is_dir()):
        skills |= {f"/{plugin.name}:{p.parent.name}" for p in plugin.glob("skills/*/SKILL.md")}
        agents |= {f"{plugin.name}:{p.stem}" for p in plugin.glob("agents/*.md")}
    templates = {p.name for p in (root / "templates").glob("*") if p.is_file()}
    return {"Skill": skills, "Agent": agents, "Template": templates}


def _readme_names(root: Path) -> dict[str, set[str]]:
    text = (root / "README.md").read_text(encoding="utf-8")
    found: dict[str, set[str]] = {"Skill": set(), "Agent": set(), "Template": set()}
    for kind, name in README_ROW.findall(text):
        found[kind].add(name)
    for line in text.splitlines():
        if line.startswith("| Templates |"):
            found["Template"] |= set(README_TEMPLATE.findall(line))
    return found


def _readme_list_errors(root: Path) -> list[str]:
    errors: list[str] = []
    folders = _folder_names(root)
    listed = _readme_names(root)
    for kind in ("Skill", "Agent", "Template"):
        for name in sorted(folders[kind] - listed[kind]):
            errors.append(f"README.md: no {kind} row for {name}")
        for name in sorted(listed[kind] - folders[kind]):
            errors.append(f"README.md: {kind} row {name} has no folder")
    return sorted(errors)


OPTION_REQUIRED = ("type", "title", "description")
OPTION_ALLOWED = (
    "type", "title", "description", "required", "default", "options", "multiple", "sensitive", "min", "max",
)
OPTION_TYPES = ("string", "number", "boolean", "directory", "file")
OPTION_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
BASE_OPTIONS = ("session_start_output", "maintainer_name", "maintainer_timezone", "default_models")


def _option_errors(options: object) -> list[str]:
    if not isinstance(options, dict) or not options:
        return ["userConfig: not a non-empty object"]
    errors: list[str] = []
    for name, option in options.items():
        if not OPTION_NAME.fullmatch(name):
            errors.append(f"{name}: not a valid option name")
        if not isinstance(option, dict):
            errors.append(f"{name}: not an object")
            continue
        errors += [f"{name}: no {key}" for key in OPTION_REQUIRED if not option.get(key)]
        errors += [f"{name}: unknown key {key}" for key in option if key not in OPTION_ALLOWED]
        if "type" in option and option["type"] not in OPTION_TYPES:
            errors.append(f"{name}: unknown type {option['type']}")
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

    def test_a_base_file_naming_the_release_parts_is_named(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write(root / "skills" / "a" / "SKILL.md", "Spawn devflow:tester.\nSpawn devflow-release:tester.\n")
            _write(root / "agents" / "b.md", "## Release mode\n**Release mode** is at the end.\n")
            _write(root / "templates" / "c.md", "Read skills/release/SKILL.md.\nRun /devflow-release:release.\n")
            _write(root / "hooks" / "d.py", 'p = "skills\\release"\nq = "skills/release-notes"\n')
            _write(root / "evals" / "depends.json", '{"release": ["skills/release/"]}\n')
            found = _r1_errors(root)
        self.assertEqual(
            found,
            [
                "agents/b.md:1: names Release mode, which moved to devflow-release",
                "agents/b.md:2: names Release mode, which moved to devflow-release",
                "hooks/d.py:1: names skills\\release, which moved to devflow-release",
                "skills/a/SKILL.md:1: names devflow:tester, which moved to devflow-release",
                "templates/c.md:1: names skills/release, which moved to devflow-release",
            ],
        )


class TestMovedNames(unittest.TestCase):
    def test_no_base_text_names_a_moved_part_by_its_old_name(self):
        self.assertEqual(_moved_name_errors(ROOT), [])

    def test_an_old_name_is_named(self):
        passing = (
            "Run /devflow-release:release and devflow-release:tester.\n"
            "Run /devflow-ui:review-ui, /devflow:review-web-ui and /devflow:release-notes.\n"
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _write(root / "skills" / "a" / "SKILL.md", passing + "Run `/devflow:release` now.\n")
            _write(root / "agents" / "b.md", passing + "Spawn devflow:tester.\n")
            _write(root / "templates" / "c.md", passing + "Run /devflow:review-ui.\n")
            _write(root / "README.md", passing + "| Skill | `/devflow:release` | x |\n")
            _write(root / "CLAUDE.md", passing + "Not `/devflow:review-ui`.\n")
            _write(root / "CHANGELOG.md", "/devflow:release\n")
            _write(root / "docs" / "BEHAVIOUR.md", "/devflow:release\n")
            _write(root / "evals" / "x", "/devflow:release\n")
            _write(root / "tests" / "x.py", "/devflow:release\n")
            _write(root / "hooks" / "session_start.py", "/devflow:release\n")
            found = _moved_name_errors(root)
        self.assertEqual(
            found,
            [
                "CLAUDE.md:3: names /devflow:review-ui, the old name of a moved part",
                "README.md:3: names /devflow:release, the old name of a moved part",
                "agents/b.md:3: names devflow:tester, the old name of a moved part",
                "skills/a/SKILL.md:3: names /devflow:release, the old name of a moved part",
                "templates/c.md:3: names /devflow:review-ui, the old name of a moved part",
            ],
        )

    def test_the_readme_gives_both_domain_installs(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for needle in (
            "/plugin install devflow-ui@devflow",
            "/plugin install devflow-release@devflow",
            '"devflow-ui@devflow"',
            '"devflow-release@devflow"',
            "two guards",
        ):
            self.assertIn(needle, text)

    def test_the_templates_and_manage_project_say_the_way_without_devflow_release(self):
        def read(rel: str) -> str:
            return (ROOT / rel).read_text(encoding="utf-8")

        section = read("templates/CLAUDE-section.md")
        self.assertIn("`/devflow-release:release` with the `devflow-release` plugin, else by hand as **Release**", section)
        plan = read("templates/plan.md")
        self.assertIn("(with `devflow-release`; without it, by hand as **Release** says)", plan)
        self.assertIn("Without the `devflow-release` plugin, the maintainer releases by hand as **Release**", plan)
        self.assertIn("through the candidate phase with `devflow-release`, else by hand.", plan)
        prompts = read("templates/PROMPTS.md")
        self.assertIn("(coding tab; needs the `devflow-release` plugin)", prompts)
        self.assertIn("These prompts need the `devflow-release` plugin", prompts)
        self.assertIn("The UI review prompts need the `devflow-ui` plugin", prompts)
        self.assertIn("where the `devflow-release` plugin is installed, `/devflow-release:release`", read("templates/STATUS.md"))
        self.assertIn("without it the maintainer releases by hand as **Release** says", read("skills/manage-project/SKILL.md"))


class TestUserConfig(unittest.TestCase):
    def _options(self) -> dict:
        return _load_json(ROOT / ".claude-plugin" / "plugin.json").get("userConfig")

    def test_each_option_has_the_required_keys_and_no_unknown_one(self):
        self.assertEqual(_option_errors(self._options()), [])

    def test_the_base_declares_these_options(self):
        self.assertEqual(tuple(self._options()), BASE_OPTIONS)

    def test_no_option_offers_a_pick_list_and_only_the_output_has_a_default(self):
        options = self._options()
        self.assertEqual([name for name, option in options.items() if "options" in option], [])
        self.assertEqual({name: option["default"] for name, option in options.items() if "default" in option},
                         {"session_start_output": "full"})

    def test_the_domain_plugins_declare_none(self):
        manifests = sorted(ROOT.glob("plugins/*/.claude-plugin/plugin.json"))
        self.assertTrue(manifests)
        for path in manifests:
            with self.subTest(path.parts[-3]):
                self.assertNotIn("userConfig", _load_json(path))

    def test_a_bad_option_is_named(self):
        found = _option_errors({
            "bad-name": {"type": "string", "title": "t", "description": "d"},
            "b": {"type": "text", "title": "t", "nope": 1},
            "c": "x",
        })
        self.assertEqual(found, [
            "b: no description",
            "b: unknown key nope",
            "b: unknown type text",
            "bad-name: not a valid option name",
            "c: not an object",
        ])


class TestReadmeLists(unittest.TestCase):
    def _root(self, temp: str, rows: str) -> Path:
        root = Path(temp)
        _write(root / "skills" / "a" / "SKILL.md", "x")
        _write(root / "skills" / "b" / "SKILL.md", "x")
        _write(root / "agents" / "m.md", "x")
        _write(root / "agents" / "n.md", "x")
        _write(root / "plugins" / "p" / "skills" / "c" / "SKILL.md", "x")
        _write(root / "plugins" / "p" / "agents" / "t.md", "x")
        _write(root / "templates" / "one.md", "x")
        _write(root / "templates" / "two.json", "x")
        _write(root / "README.md", rows)
        return root

    def test_the_readme_lists_match_the_folders(self):
        self.assertEqual(_readme_list_errors(ROOT), [])

    def test_matching_rows_pass(self):
        rows = (
            "| Skill | `/devflow:a` | x |\n| Skill | `/devflow:b` | x |\n| Skill | `/p:c` | x |\n"
            "| Agent | `devflow:m` | x |\n| Agent | `devflow:n` | x |\n| Agent | `p:t` | x |\n"
            "| Templates | `templates/` | `one.md` and `two.json`. |\n"
        )
        with tempfile.TemporaryDirectory() as temp:
            found = _readme_list_errors(self._root(temp, rows))
        self.assertEqual(found, [])

    def test_a_missing_or_extra_row_is_named(self):
        rows = (
            "| Skill | `/devflow:a` | x |\n| Skill | `/devflow:gone` | x |\n| Skill | `/p:c` | x |\n"
            "| Agent | `devflow:m` | x |\n| Agent | `devflow:extra` | x |\n| Agent | `p:t` | x |\n"
            "| Templates | `templates/` | `one.md` and `three.yml`. |\n"
        )
        with tempfile.TemporaryDirectory() as temp:
            found = _readme_list_errors(self._root(temp, rows))
        self.assertEqual(
            found,
            [
                "README.md: Agent row devflow:extra has no folder",
                "README.md: Skill row /devflow:gone has no folder",
                "README.md: Template row three.yml has no folder",
                "README.md: no Agent row for devflow:n",
                "README.md: no Skill row for /devflow:b",
                "README.md: no Template row for two.json",
            ],
        )


if __name__ == "__main__":
    unittest.main()
