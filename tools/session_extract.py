from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator, NamedTuple

KEPT_TYPES = ("user", "assistant")
USER_LIMIT = 2000
ASSISTANT_LIMIT = 1500
SIDECHAIN_LIMIT = 400
RESULT_LIMIT = 300
CALL_LIMIT = 300
NOISE = re.compile(r"<(system-reminder|ide_[a-z_]+|command-[a-z]+|local-command-[a-z]+)>.*?</\1>",
                   re.DOTALL)
PATH_KEYS = ("file_path", "notebook_path", "path")


class Extract(NamedTuple):
    session_id: str
    branches: tuple[str, ...]
    first: str
    last: str
    lines: tuple[str, ...]


def folder_names(project: str) -> list[str]:
    narrow = re.sub(r"[:\\/]", "-", project.rstrip("\\/"))
    wide = re.sub(r"[^A-Za-z0-9]", "-", project.rstrip("\\/"))
    return [narrow] if narrow == wide else [narrow, wide]


def sessions_folder(source: str, projects_root: Path) -> Path | None:
    path = Path(source)
    if path.is_dir() and any(path.glob("*.jsonl")):
        return path
    if not projects_root.is_dir():
        return None
    existing = {child.name.casefold(): child for child in projects_root.iterdir() if child.is_dir()}
    for name in folder_names(source):
        if name.casefold() in existing:
            return existing[name.casefold()]
    return None


def recent_sessions(folder: Path, count: int, exclude: str = "") -> list[Path]:
    files = [f for f in folder.glob("*.jsonl") if f.stem != exclude]
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return files[:count]


def squash(text: str, limit: int) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[:limit - 1] + "…"


def clean_text(text: str) -> str:
    return NOISE.sub("", text)


def tool_summary(name: str, params: Any) -> str:
    if not isinstance(params, dict):
        return squash(name, CALL_LIMIT)
    if isinstance(params.get("command"), str):
        detail = params["command"]
    elif name == "Agent":
        detail = " | ".join(str(params[key]) for key in ("subagent_type", "model", "description")
                            if params.get(key))
    elif name == "Skill":
        detail = " ".join(str(params[key]) for key in ("skill", "args") if params.get(key))
    elif name in ("Grep", "Glob"):
        detail = " in ".join(str(params[key]) for key in ("pattern", "path") if params.get(key))
    else:
        detail = next((str(params[key]) for key in PATH_KEYS if params.get(key)), "")
        if not detail:
            detail = next((v for v in params.values() if isinstance(v, str)), "")
    return squash(f"{name}: {detail}" if detail else name, CALL_LIMIT)


def result_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(part.get("text", "") for part in content
                        if isinstance(part, dict) and part.get("type") == "text")
    return ""


def render_parts(kind: str, content: Any, sidechain: bool) -> Iterator[str]:
    limit = SIDECHAIN_LIMIT if sidechain else USER_LIMIT if kind == "user" else ASSISTANT_LIMIT
    tag = "U" if kind == "user" else "A"
    parts = [{"type": "text", "text": content}] if isinstance(content, str) else content
    if not isinstance(parts, list):
        return
    for part in parts:
        if not isinstance(part, dict):
            continue
        part_type = part.get("type")
        if part_type == "text" and isinstance(part.get("text"), str):
            text = squash(clean_text(part["text"]), limit)
            if text:
                yield f"{tag}: {text}"
        elif part_type == "tool_use" and isinstance(part.get("name"), str):
            yield f"T: {tool_summary(part['name'], part.get('input'))}"
        elif part_type == "tool_result":
            text = squash(result_text(part.get("content")), RESULT_LIMIT)
            marker = "R!" if part.get("is_error") else "R"
            yield f"{marker}: {text}" if text else f"{marker}:"


def read_records(path: Path) -> Iterator[dict]:
    with path.open(encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            try:
                record = json.loads(raw)
            except ValueError:
                continue
            if isinstance(record, dict):
                yield record


def extract_session(path: Path) -> Extract | None:
    lines: list[str] = []
    branches: list[str] = []
    stamps: list[str] = []
    session_id = path.stem
    for record in read_records(path):
        if record.get("type") not in KEPT_TYPES:
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        sidechain = bool(record.get("isSidechain"))
        prefix = "[sub] " if sidechain else ""
        lines.extend(prefix + line for line in
                     render_parts(record["type"], message.get("content"), sidechain))
        if isinstance(record.get("timestamp"), str):
            stamps.append(record["timestamp"])
        branch = record.get("gitBranch")
        if isinstance(branch, str) and branch and branch not in branches:
            branches.append(branch)
        if isinstance(record.get("sessionId"), str):
            session_id = record["sessionId"]
    if not lines:
        return None
    return Extract(session_id, tuple(branches), min(stamps, default=""), max(stamps, default=""),
                   tuple(lines))


def render(extract: Extract) -> str:
    header = [f"session: {extract.session_id}",
              f"branch: {', '.join(extract.branches) or 'unknown'}",
              f"time: {extract.first} to {extract.last}",
              "lines: U user, A assistant, T tool call, R tool result (R! an error), [sub] a subagent",
              ""]
    return "\n".join(header + list(extract.lines)) + "\n"


def write_extracts(files: list[Path], out: Path) -> list[tuple[Path, int]]:
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for path in files:
        extract = extract_session(path)
        if extract is None:
            continue
        target = out / f"{path.stem}.txt"
        target.write_text(render(extract), encoding="utf-8", newline="\n")
        written.append((target, target.stat().st_size))
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shrink recent Claude Code sessions to text.")
    parser.add_argument("source", help="a sessions folder, or the project path")
    parser.add_argument("--count", type=int, default=15)
    parser.add_argument("--out", required=True)
    parser.add_argument("--exclude", default="", help="session id to leave out (the current one)")
    parser.add_argument("--projects-root", default=str(Path.home() / ".claude" / "projects"))
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    folder = sessions_folder(args.source, Path(args.projects_root))
    if folder is None:
        print(f"session_extract: no sessions folder for {args.source}")
        return 1
    written = write_extracts(recent_sessions(folder, args.count, args.exclude), Path(args.out))
    for target, size in written:
        print(f"{target}  {size} bytes")
    print(f"wrote {len(written)} files from {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
