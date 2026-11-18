from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Mapping, NamedTuple

POINTER = "devflow-store"
MANIFEST = "devflow-store.json"
HOME_ENV = "DEVFLOW_HOME"
CONFIG = Path(".claude") / "devflow.json"


class StoreError(ValueError):
    pass


class Found(NamedTuple):
    root: Path
    config: dict
    store: Path | None


def read_config(path: Path) -> dict | None:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return None
    if not isinstance(data, dict):
        raise ValueError(f"{path} must hold a JSON object")
    return data


def _first_line(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig")
    return text.splitlines()[0].strip() if text.splitlines() else ""


def _resolve(text: str, base: Path) -> Path:
    if text.startswith("/") or re.match(r"[A-Za-z]:", text):
        return Path(os.path.normpath(text))
    return Path(os.path.normpath(base / text))


def common_dir(project: Path) -> Path:
    project = Path(project)
    git = project / ".git"
    if not git.is_file():
        return git
    try:
        line = _first_line(git)
    except (OSError, UnicodeDecodeError) as error:
        raise StoreError(f"{git} cannot be read ({type(error).__name__})") from error
    if line.startswith("gitdir: "):
        line = line[len("gitdir: "):].strip()
    gitdir = _resolve(line, project)
    commondir = gitdir / "commondir"
    if commondir.is_file():
        try:
            line = _first_line(commondir)
        except (OSError, UnicodeDecodeError) as error:
            raise StoreError(f"{commondir} cannot be read ({type(error).__name__})") from error
        if line:
            return _resolve(line, gitdir)
    return gitdir


def pointer_file(project: Path) -> Path:
    return common_dir(project) / POINTER


def store_from_pointer(pointer: Path) -> Path:
    try:
        text = Path(pointer).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        raise StoreError(f"the pointer {pointer} cannot be read ({type(error).__name__})") from error
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise StoreError(f"the pointer {pointer} is empty")
    store = Path(lines[0])
    if not store.is_absolute():
        raise StoreError(f"the pointer {pointer} names {lines[0]}, which is not an absolute path")
    if not store.is_dir():
        raise StoreError(f"the pointer {pointer} names the store {store}, which is not a folder")
    return store


def find(project: Path) -> Found | None:
    project = Path(project)
    config = read_config(project / CONFIG)
    if config is not None:
        return Found(project, config, None)
    pointer = pointer_file(project)
    if not pointer.is_file():
        return None
    store = store_from_pointer(pointer)
    config = read_config(store / CONFIG)
    if config is None:
        raise StoreError(f"the store {store} has no .claude/devflow.json")
    return Found(store, config, store)


def home(env: Mapping[str, str]) -> Path:
    value = env.get(HOME_ENV)
    if value:
        return Path(value)
    return Path.home() / ".devflow"
