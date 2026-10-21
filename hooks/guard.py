from __future__ import annotations

import json
import os
import posixpath
import re
import subprocess
import sys
from typing import Any, Callable, Mapping, NamedTuple


class Verdict(NamedTuple):
    kind: str
    reason: str = ""


ALLOW = Verdict("allow")


class Places(NamedTuple):
    real_data: tuple[str, ...]
    keys: tuple[str, ...]
    refs: dict[str, str]
    project: str = ""


class App(NamedTuple):
    commands: frozenset[str]
    modules: tuple[str, ...]
    harmless: tuple[tuple[str, ...], ...]
    isolate_env: tuple[str, ...]
    data_folder: str


class Rules(NamedTuple):
    name: str
    maintainer: str
    places: Places
    real_data_names: str
    secret_names: str
    key_word: re.Pattern
    key_path: re.Pattern
    key_end: re.Pattern
    secretary_paths: tuple[str, ...]
    secretary_names: str
    whole_tree: frozenset[str]
    self_guarding: tuple[str, ...]
    maintainer_only: tuple[tuple[str, tuple[str, ...]], ...]
    set_names: tuple[str, ...]
    app: App | None
    ask_release: bool


class Location:
    def __init__(self, project: str = "") -> None:
        self.project = project
        self.absolute: str | None = None
        self.relative: str | None = ""

    def change(self, target: str | None) -> None:
        if not target or target == "-" or target[0] in "$%":
            self.absolute = None
            self.relative = None
            return
        if _is_absolute(target):
            self.absolute = posixpath.normpath(target)
            self.relative = "" if self.project and self.absolute == self.project else None
            return
        if self.absolute is not None:
            self.absolute = posixpath.normpath(self.absolute + "/" + target)
        if self.relative is not None:
            joined = posixpath.normpath(posixpath.join(self.relative or ".", target))
            self.relative = None if joined.startswith("..") else ("" if joined == "." else joined)

    def resolve(self, word: str) -> str:
        if self.absolute is None or not _looks_relative(word):
            return word
        return posixpath.normpath(self.absolute + "/" + word.replace("\\", "/"))


class Segment(NamedTuple):
    text: str
    words: list[str]
    redirects: list[str]
    body: str
    shell: str
    piped: bool
    substitution: bool


READ_ONLY = frozenset(
    "ls dir cat head tail less more grep rg find stat wc file du sha256sum md5sum echo "
    "printf diff cmp sort get-content gc type get-childitem gci get-item gi test-path "
    "select-string sls get-filehash measure-object select-object where-object format-list "
    "format-table out-string sort-object write-output write-host".split()
)
START_SWITCHES = frozenset({
    "/b", "/wait", "/min", "/max", "/low", "/high", "/normal", "/realtime", "/abovenormal",
    "/belownormal", "/separate", "/shared", "/i", "/d",
})
COPIES = frozenset({"cp", "copy-item", "copy", "cpi", "xcopy", "robocopy"})
FIND_ACTIONS = frozenset({"-delete", "-exec", "-execdir", "-ok", "-okdir"})
INTERPRETERS = frozenset({"python", "python3", "py", "uv", "bash", "sh", "pwsh", "powershell", "node"})
PYTHONS = frozenset({"python", "python3", "py", "pythonw"})
CD_COMMANDS = frozenset({"cd", "set-location", "sl", "chdir", "pushd", "push-location"})
PATTERN_FIRST = frozenset({"grep", "egrep", "fgrep", "rg", "select-string", "sls", "findstr"})
FILE_COMMANDS = (READ_ONLY | COPIES | frozenset({
    "mv", "move", "move-item", "mi", "rm", "del", "erase", "remove-item", "ri", "set-content",
    "sc", "add-content", "ac", "out-file", "tee", "chmod", "icacls", "openssl", "ssh-keygen",
    "scp", "base64", "xxd", "od", "notepad", "code", "gpg", "certutil", "attrib", "ren",
    "rename-item", "new-item", "ni", "touch", "vim", "vi", "nano", "dd", "zip", "7z", "tar",
    "compress-archive", "get-acl", "set-acl", "findstr",
})) - frozenset({"echo", "printf", "write-output", "write-host"})
UV_VALUE_OPTIONS = frozenset({
    "--from",
    "--with", "--with-editable", "--with-requirements", "--extra", "--project",
    "--directory", "--python", "-p", "--group", "--env-file", "--index", "--package",
    "--only-group", "--no-group",
})
DEFAULT_HARMLESS = (("--version",), ("-v",), ("--help",), ("-h",))
DEFAULT_SECRET_EXTENSIONS = ("pem", "key", "p8")
ALWAYS_WHOLE_TREE = frozenset({".", "./", ":/", ":/.", "*"})
REF_NAMES = ("APPDATA", "LOCALAPPDATA", "USERPROFILE", "HOME", "XDG_DATA_HOME",
             "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME", "TMPDIR", "TEMP", "TMP")
WINDOWS_ALIASES = {"APPDATA": "AppData/Roaming", "LOCALAPPDATA": "AppData/Local"}
NEVER = re.compile(r"(?!x)x")

_DRIVE = re.compile(r"(?<![\w.:/~$-])/([a-z])(?=/|$|[\s\"'`;|&)])")
_REF = re.compile(r"%(\w+)%|\$\{env:(\w+)\}|\$env:(\w+)|\$\{(\w+)\}|\$(\w+)", re.IGNORECASE)
_TILDE = re.compile(r"(?<![\w/.~-])~(?=[/\\]|$|[\s\"'])")
_BASH_ASSIGN = re.compile(r"^([A-Za-z_]\w*)=(.*)$", re.DOTALL)
_PS_ASSIGN = re.compile(r"^\s*\$(?:env:)?(\w+)\s*=(?!=)\s*(.*)$", re.DOTALL | re.IGNORECASE)


def normalise(text: str) -> str:
    lowered = text.lower().replace("\\", "/")
    lowered = re.sub(r"/{2,}", "/", lowered)
    return _DRIVE.sub(r"\1:", lowered)


def flat(text: str) -> str:
    return normalise(re.sub(r"[\"'`]", "", text))


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple)):
        return [v for v in value if isinstance(v, str) and v]
    return []


def _ref_names(entries: list[str]) -> list[str]:
    names: list[str] = []
    for entry in entries:
        for match in _REF.finditer(entry):
            name = next(g for g in match.groups() if g).upper()
            if name not in names:
                names.append(name)
    return names


def refs_from_env(env: Mapping[str, str], extra: list[str]) -> dict[str, str]:
    refs: dict[str, str] = {}
    for name in list(REF_NAMES) + extra:
        value = env.get(name) or ""
        if value:
            refs[name.upper()] = value
    home = env.get("USERPROFILE") or env.get("HOME") or ""
    if home:
        refs["HOME"] = home
    return refs


def expand_refs(text: str, refs: Mapping[str, str], assigned: Mapping[str, str]) -> str:
    def replace(match: re.Match) -> str:
        name = next(g for g in match.groups() if g).upper()
        if name in assigned:
            return assigned[name]
        if refs.get(name):
            return refs[name]
        return match.group(0)

    expanded = _REF.sub(replace, text)
    home = refs.get("HOME") or refs.get("USERPROFILE")
    if home:
        expanded = _TILDE.sub(lambda _m: home, expanded)
    return expanded


def roots_from(entries: list[str], refs: Mapping[str, str]) -> tuple[str, ...]:
    variants: list[Mapping[str, str]] = [refs]
    profile = refs.get("USERPROFILE")
    if profile:
        variants.append({**refs, **{k: profile + "/" + v for k, v in WINDOWS_ALIASES.items()}})
    roots: list[str] = []
    for entry in entries:
        for variant in variants:
            expanded = expand_refs(entry, variant, {})
            if _REF.search(expanded) or expanded.startswith("~"):
                continue
            root = normalise(expanded).rstrip("/")
            if root:
                roots.append(root)
    return tuple(dict.fromkeys(roots))


def _relative_form(path: str) -> str:
    form = path.lower().replace("\\", "/").strip()
    while form.startswith("./"):
        form = form[2:]
    return form.rstrip("/")


def _app_from(config: Any) -> App | None:
    if not isinstance(config, Mapping):
        return None
    commands = frozenset(command_name(c) for c in _strings(config.get("commands")))
    modules = tuple(_strings(config.get("modules")))
    if not commands and not modules:
        return None
    harmless_config = config.get("harmless")
    if isinstance(harmless_config, list):
        harmless = tuple(tuple(_strings(p)) for p in harmless_config if _strings(p))
    else:
        harmless = DEFAULT_HARMLESS
    isolate = tuple(n.upper() for n in _strings(config.get("isolate_env")))
    folder = config.get("data_folder") if isinstance(config.get("data_folder"), str) else ""
    return App(commands, modules, harmless, isolate, folder)


def rules_from(config: Mapping[str, Any], env: Mapping[str, str]) -> Rules:
    guard_config = config.get("guard") if isinstance(config.get("guard"), Mapping) else {}
    real_entries = _strings(guard_config.get("real_data"))
    secret_dirs = _strings(guard_config.get("secret_dirs"))
    if "secret_extensions" in guard_config:
        extensions = [e.lstrip(".") for e in _strings(guard_config.get("secret_extensions"))]
    else:
        extensions = list(DEFAULT_SECRET_EXTENSIONS)
    app = _app_from(guard_config.get("app"))
    refs = refs_from_env(env, _ref_names(real_entries + secret_dirs)
                         + list(app.isolate_env if app else ()))
    project = normalise(env.get("CLAUDE_PROJECT_DIR") or "")
    places = Places(roots_from(real_entries, refs), roots_from(secret_dirs, refs), refs,
                    posixpath.normpath(project) if project else "")
    if extensions:
        alternatives = "|".join(re.escape(e) for e in extensions)
        key_word = re.compile(rf"^.*[\w-]\.({alternatives})$", re.IGNORECASE)
        key_path = re.compile(rf"[/\\~][\w.-]*[\w-]\.({alternatives})(?![\w(])", re.IGNORECASE)
        key_end = re.compile(rf"\.({alternatives})$", re.IGNORECASE)
    else:
        key_word = key_path = key_end = NEVER
    status_file = config.get("status_file") if isinstance(config.get("status_file"), str) \
        else "docs/STATUS.md"
    plans_dir = config.get("plans_dir") if isinstance(config.get("plans_dir"), str) \
        else "docs/plans"
    secretary = tuple(p for p in (_relative_form(status_file), _relative_form(plans_dir)) if p)
    whole_tree = set(ALWAYS_WHOLE_TREE)
    for path in secretary:
        if "/" in path:
            top = path.split("/", 1)[0]
            whole_tree.update({top, top + "/", "./" + top, "./" + top + "/"})
    maintainer_only: list[tuple[str, tuple[str, ...]]] = []
    for item in guard_config.get("maintainer_only") or []:
        if isinstance(item, Mapping) and _strings(item.get("script")):
            maintainer_only.append((_relative_form(_strings(item.get("script"))[0]),
                                    tuple(_strings(item.get("subcommands")))))
    set_names = tuple(dict.fromkeys(list(app.isolate_env if app else ())
                                    + _ref_names(real_entries)))
    return Rules(
        name=config.get("name") if isinstance(config.get("name"), str) else "the project",
        maintainer=config.get("maintainer") if isinstance(config.get("maintainer"), str)
        else "the maintainer",
        places=places,
        real_data_names=", ".join(real_entries),
        secret_names=", ".join(secret_dirs + ["*." + e for e in extensions]),
        key_word=key_word,
        key_path=key_path,
        key_end=key_end,
        secretary_paths=secretary,
        secretary_names=" and ".join(
            p for p in (status_file, plans_dir.rstrip("/\\") + "/" if plans_dir else "") if p),
        whole_tree=frozenset(whole_tree),
        self_guarding=tuple(_relative_form(s) for s in
                            _strings(guard_config.get("self_guarding_scripts"))),
        maintainer_only=tuple(maintainer_only),
        set_names=set_names,
        app=app,
        ask_release=guard_config.get("ask_release", True) is not False,
    )


def names_place(text: str, roots: tuple[str, ...] | list[str]) -> bool:
    for root in roots:
        if not root:
            continue
        for match in re.finditer(re.escape(root), text):
            end = match.end()
            if end == len(text) or not re.match(r"[\w.-]", text[end]):
                return True
    return False


def names_key_path(text: str, rules: Rules) -> bool:
    return bool(rules.key_path.search(text))


def _file_operands(words: list[str]) -> list[str]:
    name = command_name(words[0])
    args = words[1:]
    if name not in PATTERN_FIRST:
        return [w for w in args if not w.startswith("-")]
    operands: list[str] = []
    pattern_given = False
    index = 0
    while index < len(args):
        word = args[index]
        lowered = word.lower()
        if lowered in ("-e", "--regexp", "-pattern"):
            pattern_given = True
            index += 2
            continue
        if lowered in ("-f", "--file", "-path", "-literalpath"):
            if index + 1 < len(args):
                operands.append(args[index + 1])
            pattern_given = pattern_given or lowered in ("-f", "--file")
            index += 2
            continue
        if not word.startswith("-"):
            if pattern_given:
                operands.append(word)
            pattern_given = True
        index += 1
    return operands


def names_key_file(words: list[str], redirects: list[str], rules: Rules) -> bool:
    if any(rules.key_word.match(r) or names_key_path(r, rules) for r in redirects):
        return True
    if not words or command_name(words[0]) in ("git", "gh"):
        return False
    if any(names_key_path(w, rules) for w in words):
        return True
    if command_name(words[0]) not in FILE_COMMANDS:
        return False
    return any(rules.key_word.match(w) for w in _file_operands(words))


def _is_absolute(path: str) -> bool:
    return bool(re.match(r"^([a-z]:/|/|~)", path))


def _looks_relative(word: str) -> bool:
    return bool(word) and not re.match(r"^([a-zA-Z]:[/\\]|[/\\~$%-]|\w+://)", word)


def command_name(word: str) -> str:
    base = word.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return base[:-4] if base.endswith(".exe") else base


def _escape_char(shell: str) -> str:
    return {"bash": "\\", "powershell": "`", "cmd": "^"}[shell]


def parse_words(text: str, shell: str) -> tuple[list[str], list[str]]:
    words: list[str] = []
    redirects: list[str] = []
    cur: list[str] = []
    started = False
    quote = ""
    target_next = False
    esc = _escape_char(shell)
    quotes = "\"" if shell == "cmd" else "\"'"
    i, n = 0, len(text)

    def finish() -> None:
        nonlocal cur, started, target_next
        if started:
            word = "".join(cur)
            if target_next:
                redirects.append(word)
                target_next = False
            else:
                words.append(word)
        cur = []
        started = False

    while i < n:
        c = text[i]
        if quote:
            if c == quote:
                if shell == "powershell" and quote == "'" and i + 1 < n and text[i + 1] == "'":
                    cur.append("'")
                    i += 2
                    continue
                quote = ""
            elif quote == "\"" and shell == "bash" and c == "\\" and i + 1 < n and text[i + 1] in "\"\\$`":
                cur.append(text[i + 1])
                i += 2
                continue
            elif quote == "\"" and shell == "powershell" and c == "`" and i + 1 < n:
                cur.append(text[i + 1])
                i += 2
                continue
            else:
                cur.append(c)
            i += 1
            continue
        if c == esc and i + 1 < n:
            if text[i + 1] == "\n":
                i += 2
                continue
            cur.append(c)
            cur.append(text[i + 1])
            started = True
            i += 2
            continue
        if c in quotes:
            quote = c
            started = True
            i += 1
            continue
        if c.isspace():
            finish()
            i += 1
            continue
        if c == ">":
            prefix = "".join(cur)
            if started and prefix not in ("1", "2", "3", "&", "*"):
                finish()
            else:
                cur = []
                started = False
            while i < n and text[i] == ">":
                i += 1
            if i + 1 < n and text[i] == "&" and text[i + 1].isdigit():
                i += 2
                continue
            target_next = True
            continue
        if c == "<":
            finish()
            i += 1
            continue
        cur.append(c)
        started = True
        i += 1
    finish()
    return words, redirects


def _heredoc_delimiter(text: str, i: int) -> tuple[str, int] | None:
    j = i + 2
    if j < len(text) and text[j] == "<":
        return None
    if j < len(text) and text[j] == "-":
        j += 1
    while j < len(text) and text[j] in " \t":
        j += 1
    quote = text[j] if j < len(text) and text[j] in "'\"" else ""
    if quote:
        j += 1
    start = j
    while j < len(text) and (text[j].isalnum() or text[j] == "_"):
        j += 1
    if j == start:
        return None
    word = text[start:j]
    if quote and j < len(text) and text[j] == quote:
        j += 1
    return word, j


def _split(command: str, shell: str) -> list[tuple[str, str, bool]]:
    pieces: list[tuple[str, str, bool]] = []
    buf: list[str] = []
    bodies: list[str] = []
    pending: list[str] = []
    quote = ""
    piped = False
    esc = _escape_char(shell)
    quotes = "\"" if shell == "cmd" else "\"'"
    i, n = 0, len(command)

    def flush(next_piped: bool) -> None:
        nonlocal buf, bodies, piped
        text = "".join(buf).strip()
        if text:
            pieces.append((text, "\n".join(bodies), piped))
        buf = []
        bodies = []
        piped = next_piped

    def read_bodies(at: int) -> int:
        lines = command[at:].split("\n")
        consumed = 0
        index = 0
        while pending and index < len(lines):
            delimiter = pending[0]
            body: list[str] = []
            while index < len(lines):
                line = lines[index]
                consumed += len(line) + 1
                index += 1
                if line.strip() == delimiter:
                    break
                body.append(line)
            bodies.append("\n".join(body))
            pending.pop(0)
        return min(at + consumed, n)

    while i < n:
        c = command[i]
        if c == "\n" and pending:
            buf.append("\n")
            i = read_bodies(i + 1)
            if not quote:
                flush(False)
            continue
        if quote:
            if c == quote:
                quote = ""
            elif quote == "\"" and c == esc and shell != "cmd" and i + 1 < n:
                buf.append(command[i:i + 2])
                i += 2
                continue
            elif shell == "bash" and quote == "\"" and command.startswith("<<", i):
                found = _heredoc_delimiter(command, i)
                if found:
                    pending.append(found[0])
                    buf.append(command[i:found[1]])
                    i = found[1]
                    continue
            buf.append(c)
            i += 1
            continue
        if c == esc and i + 1 < n:
            if command[i + 1] == "\n":
                i += 2
                continue
            buf.append(command[i:i + 2])
            i += 2
            continue
        if c in quotes:
            quote = c
            buf.append(c)
            i += 1
            continue
        if shell == "bash" and command.startswith("<<", i):
            found = _heredoc_delimiter(command, i)
            if found:
                pending.append(found[0])
                buf.append(command[i:found[1]])
                i = found[1]
                continue
        if c in "\n;":
            flush(False)
            i += 1
            continue
        if command.startswith("&&", i) or command.startswith("||", i):
            flush(False)
            i += 2
            continue
        if c == "|":
            flush(True)
            i += 1
            continue
        if c == "&":
            before = command[i - 1] if i else ""
            after = command[i + 1] if i + 1 < n else ""
            if before in "<>" and before or after == ">" or shell == "powershell":
                buf.append(c)
                i += 1
                continue
            flush(False)
            i += 1
            continue
        buf.append(c)
        i += 1
    flush(False)
    return pieces


def _strip_wrappers(words: list[str]) -> list[str]:
    while words:
        name = command_name(words[0])
        if words[0] == "&":
            words = words[1:]
        elif name == "nohup":
            words = words[1:]
        elif name == "env":
            words = words[1:]
            while words and words[0].startswith("-"):
                words = words[2:] if words[0] in ("-u", "--unset") else words[1:]
        elif name == "timeout" and len(words) > 1:
            rest = words[1:]
            while rest and rest[0].startswith("-"):
                rest = rest[2:] if rest[0] in ("-k", "-s", "--signal", "--kill-after") else rest[1:]
            words = rest[1:] if rest else []
        elif name == "start-process":
            rest = []
            skip = False
            for word in words[1:]:
                lowered = word.lower()
                if skip:
                    skip = False
                    continue
                if lowered in ("-filepath", "-argumentlist", "-wait", "-nonewwindow", "-passthru"):
                    continue
                if lowered in ("-windowstyle", "-workingdirectory", "-redirectstandardoutput",
                               "-redirectstandarderror", "-redirectstandardinput", "-verb"):
                    skip = True
                    continue
                rest.append(word)
            words = rest
        elif name == "start":
            rest = words[1:]
            while rest and (rest[0] == "" or rest[0].lower() in START_SWITCHES):
                rest = rest[2:] if rest[0].lower() == "/d" else rest[1:]
            words = rest
        elif name in ("invoke-item", "ii"):
            words = [w for w in words[1:] if w.lower() not in ("-path", "-literalpath")]
            if not words:
                return words
        else:
            return words
    return words


def _inner_command(words: list[str]) -> tuple[str, str] | None:
    if not words:
        return None
    name = command_name(words[0])
    lowered = [w.lower() for w in words]
    if name == "cmd":
        for index, word in enumerate(lowered[1:], start=1):
            if word in ("/c", "/k", "//c", "//k"):
                return " ".join(words[index + 1:]), "cmd"
        return None
    if name in ("powershell", "pwsh"):
        for index, word in enumerate(lowered[1:], start=1):
            if word in ("-command", "-c", "/c", "-com", "-comm"):
                return " ".join(words[index + 1:]), "powershell"
        return None
    if name in ("bash", "sh"):
        for index, word in enumerate(lowered[1:], start=1):
            if word.startswith("-") and not word.startswith("--") and word.endswith("c"):
                if index + 1 < len(words):
                    return words[index + 1], "bash"
        return None
    return None


def segments(command: str, shell: str, depth: int = 0) -> list[Segment]:
    result: list[Segment] = []
    for text, body, piped in _split(command, shell):
        words, redirects = parse_words(text, shell)
        words = _strip_wrappers(words)
        substitution = "$(" in text or (shell == "bash" and "`" in text)
        inner = _inner_command(words) if depth < 2 else None
        if inner is not None:
            inner_segments = segments(inner[0], inner[1], depth + 1)
            if inner_segments:
                first = inner_segments[0]
                inner_segments[0] = first._replace(piped=piped,
                                                   redirects=first.redirects + redirects)
                result.extend(inner_segments)
                continue
        result.append(Segment(text, words, redirects, body, shell, piped, substitution))
    return result


def _assignment_value(raw: str, refs: Mapping[str, str], assigned: Mapping[str, str]) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return expand_refs(value, refs, assigned)


def assignments(segment: Segment, refs: Mapping[str, str],
                assigned: dict[str, str]) -> tuple[list[str], bool]:
    words = list(segment.words)
    if segment.shell == "powershell" and words:
        match = _PS_ASSIGN.match(segment.text)
        if match and words[0].startswith("$"):
            name, rhs = match.group(1).upper(), match.group(2)
            rhs_words, _ = parse_words(rhs, "powershell")
            pure = len(rhs_words) <= 1 and (not rhs.strip() or rhs.strip()[0] in "\"'$0123456789@")
            assigned[name] = _assignment_value(rhs, refs, assigned)
            return ([] if pure else rhs_words), True
        return words, False
    if segment.shell == "cmd" and words and words[0].lower() == "set" and len(words) > 1:
        rest = " ".join(words[1:]).strip()
        if rest.startswith("/"):
            return words, False
        name, _, value = rest.partition("=")
        if name:
            assigned[name.strip().upper()] = _assignment_value(value, refs, assigned)
            return [], True
        return words, False
    if segment.shell == "bash" and words and words[0] in ("export", "declare", "local", "readonly"):
        words = words[1:]
        while words and words[0].startswith("-"):
            words = words[1:]
    found = False
    while words:
        match = _BASH_ASSIGN.match(words[0])
        if not match:
            break
        assigned[match.group(1).upper()] = _assignment_value(match.group(2), refs, assigned)
        words = words[1:]
        found = True
    return words, found


def set_outside_cmd(segment: Segment, names: tuple[str, ...]) -> str | None:
    words = segment.words
    if segment.shell == "cmd" or len(words) < 2 or words[0].lower() != "set" or not names:
        return None
    name = words[1].split("=", 1)[0].upper()
    return name if "=" in words[1] and name in names else None


def set_message(name: str, rules: Rules) -> str:
    return (f"guard.py refused: `set {name}=...` outside `cmd /c` sets no environment variable. "
            f"In PowerShell this sets no environment variable; use `$env:{name} = '...'`. In "
            f"Bash write `{name}=... command` in the same command, so nothing runs against "
            f"{rules.name}'s real data by mistake.")


def _after_xargs(words: list[str]) -> list[str]:
    rest = words[1:]
    while rest and rest[0].startswith("-"):
        option = rest[0]
        if option in ("-n", "-I", "-d", "-P", "-L", "-s", "-E", "-a"):
            rest = rest[2:]
        else:
            rest = rest[1:]
    return rest


def _copy_destination(name: str, args: list[str]) -> str | None:
    positional: list[str] = []
    index = 0
    while index < len(args):
        word = args[index]
        lowered = word.lower()
        if lowered in ("-t", "--target-directory"):
            return args[index + 1] if index + 1 < len(args) else None
        if lowered.startswith("--target-directory="):
            return word.split("=", 1)[1]
        if lowered.startswith("-dest"):
            return args[index + 1] if index + 1 < len(args) else None
        if lowered in ("-path", "-literalpath", "-filter", "-include", "-exclude"):
            index += 2
            continue
        if word.startswith("-") or (name in ("xcopy", "robocopy", "copy") and word.startswith("/")
                                    and len(word) <= 5 and ":" not in word):
            index += 1
            continue
        positional.append(word)
        index += 1
    if name == "robocopy":
        return positional[1] if len(positional) > 1 else None
    if not positional:
        return None
    if name in ("copy-item", "cpi") and any(a.lower() in ("-path", "-literalpath") for a in args):
        return positional[-1]
    return positional[-1] if len(positional) > 1 else None


def is_read_only(words: list[str], redirects: list[str], places: Places,
                 self_guarding: tuple[str, ...] = ()) -> bool:
    if any(names_place(flat(r), places.real_data) for r in redirects):
        return False
    if not words:
        return True
    script = script_of(words)
    if script is not None and self_guarding and flat(script).endswith(self_guarding):
        return True
    name = command_name(words[0])
    if name == "xargs":
        inner = _after_xargs(words)
        return bool(inner) and is_read_only(inner, [], places, self_guarding)
    if name in COPIES:
        destination = _copy_destination(name, words[1:])
        return destination is not None and not names_place(flat(destination), places.real_data)
    if name not in READ_ONLY:
        return False
    if name == "find" and any(w.lower() in FIND_ACTIONS for w in words):
        return False
    if name == "sort":
        for index, word in enumerate(words):
            if word in ("-o", "--output") and index + 1 < len(words):
                if names_place(flat(words[index + 1]), places.real_data):
                    return False
            if word.startswith("--output=") and names_place(flat(word), places.real_data):
                return False
    return True


def _python_script(args: list[str]) -> str | None:
    index = 0
    while index < len(args) and args[index].startswith("-"):
        if args[index].startswith(("-m", "-c")):
            return None
        index += 2 if args[index] in ("-X", "-W") else 1
    return args[index] if index < len(args) else None


def script_of(words: list[str]) -> str | None:
    if not words:
        return None
    name = command_name(words[0])
    if name in PYTHONS:
        return _python_script(words[1:])
    if name == "uv" and len(words) > 1 and words[1] == "run":
        index = 2
        while index < len(words) and words[index].startswith("-"):
            index += 2 if words[index] in UV_VALUE_OPTIONS else 1
        if index >= len(words):
            return None
        if command_name(words[index]) in PYTHONS:
            return _python_script(words[index + 1:])
        return words[index]
    return None


def _module_matches(module: str, modules: tuple[str, ...]) -> bool:
    return any(module == m or module.startswith(m + ".") for m in modules)


def _python_module_args(args: list[str], modules: tuple[str, ...]) -> list[str] | None:
    if not modules:
        return None
    index = 0
    while index < len(args) and args[index].startswith("-"):
        option = args[index]
        if option == "-m":
            if index + 1 < len(args) and _module_matches(args[index + 1], modules):
                return args[index + 2:]
            return None
        if option.startswith("-m"):
            return args[index + 1:] if _module_matches(option[2:], modules) else None
        if option in ("-c",):
            return None
        index += 2 if option in ("-X", "-W") else 1
    return None


def app_arguments(words: list[str], app: App) -> list[str] | None:
    if not words:
        return None
    name = command_name(words[0])
    if name in app.commands:
        return words[1:]
    tool_run = name == "uv" and words[1:3] == ["tool", "run"]
    if name == "uvx" or tool_run:
        index = 3 if tool_run else 1
        while index < len(words) and words[index].startswith("-"):
            index += 2 if words[index] in UV_VALUE_OPTIONS else 1
        if index < len(words) and command_name(words[index]) in app.commands:
            return words[index + 1:]
        return None
    if name == "uv" and len(words) > 1 and words[1] == "run":
        index = 2
        while index < len(words) and words[index].startswith("-"):
            index += 2 if words[index] in UV_VALUE_OPTIONS else 1
        if index >= len(words):
            return None
        program = command_name(words[index])
        if program in app.commands:
            return words[index + 1:]
        if program in PYTHONS:
            return _python_module_args(words[index + 1:], app.modules)
        return None
    if name in PYTHONS:
        return _python_module_args(words[1:], app.modules)
    return None


def _is_harmless(args: list[str], app: App) -> bool:
    lowered = [a.lower() for a in args]
    for pattern in app.harmless:
        if len(pattern) == len(lowered) and all(
                p == "*" or p.lower() == a for p, a in zip(pattern, lowered)):
            return True
    return False


def starts_app(words: list[str], app: App) -> bool:
    args = app_arguments(words, app)
    return args is not None and not _is_harmless(args, app)


def _not_isolated(value: str | None, app: App, places: Places) -> bool:
    if not value:
        return True
    target = value + "/" + app.data_folder if app.data_folder else value
    return names_place(flat(target), places.real_data)


def app_message(rules: Rules) -> str:
    app = rules.app
    if app is None or not app.isolate_env:
        return (f"guard.py refused: this starts {rules.name}, which agents may not run here; "
                f"ask {rules.maintainer} to run it.")
    names = ", ".join(app.isolate_env)
    first = app.isolate_env[0]
    return (f"guard.py refused: this starts {rules.name} against its real data "
            f"({rules.real_data_names}). Point {names} at a scratch folder in the same command "
            f"(Bash: `{first}=\"$S/a\" <command>`; PowerShell: `$env:{first} = '...'; "
            f"<command>`), or ask {rules.maintainer} to run it.")


def _git(words: list[str]) -> tuple[str, list[str], str] | None:
    if not words or command_name(words[0]) != "git":
        return None
    index = 1
    directory = ""
    while index < len(words) and words[index].startswith("-"):
        if words[index] == "-C" and index + 1 < len(words):
            directory = posixpath.join(directory, words[index + 1].replace("\\", "/"))
        index += 2 if words[index] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") else 1
    if index >= len(words):
        return None
    return words[index].lower(), words[index + 1:], directory


def _path_form(word: str, prefix: str = "") -> str:
    form = word.lower().replace("\\", "/")
    if form.startswith(":/"):
        return posixpath.normpath(form[2:] or ".")
    if prefix and not _is_absolute(form):
        form = posixpath.join(prefix.lower(), form)
    while form.startswith("./"):
        form = form[2:]
    return posixpath.normpath(form) if form else form


def _pathspec(args: list[str]) -> tuple[list[str], list[str]]:
    paths: list[str] = []
    after: list[str] = []
    after_dashes = False
    skip = False
    takes_value = ("-s", "--source", "-b", "-B", "--orphan", "--conflict", "--pathspec-from-file")
    for word in args:
        if skip:
            skip = False
            continue
        if after_dashes:
            paths.append(word)
            after.append(word)
        elif word == "--":
            after_dashes = True
        elif word in takes_value:
            skip = True
        elif not word.startswith("-"):
            paths.append(word)
    return paths, after


def _dirty_reason(what: str, dirty: Callable[[], list[str]]) -> str | None:
    files = dirty()
    if not files:
        return None
    return (f"guard.py refused: {what} would discard uncommitted secretary edits "
            f"({', '.join(files)}). Commit them with your next change; never revert them.")


def _broad(path: str, form: str, whole_tree: frozenset[str]) -> bool:
    return form in whole_tree or any(c in path for c in "*?[")


def _bare_file(form: str) -> bool:
    return "/" not in form and bool(re.search(r"\.\w+$", form))


def reverts_secretary_files(words: list[str], dirty: Callable[[], list[str]],
                            prefix: str | None, rules: Rules) -> str | None:
    names = rules.secretary_names
    if words and command_name(words[0]) == "xargs":
        inner = _git(_after_xargs(words))
        if inner and inner[0] in ("checkout", "restore"):
            return (f"guard.py refused: `git checkout` / `git restore` fed by xargs can revert "
                    f"{names} (secretary edits); name the paths yourself.")
        return None
    found = _git(words)
    if found is None:
        return None
    sub, args, directory = found
    if sub == "reset" and "--hard" in args:
        return "guard.py refused: `git reset --hard` discards uncommitted secretary edits; never run it."
    if sub in ("checkout", "restore"):
        base = posixpath.join(prefix or "", directory) if prefix is not None else directory
        paths, after = _pathspec(args)
        for path in paths:
            form = _path_form(path, base)
            if any(form.startswith(p) or "/" + p in form for p in rules.secretary_paths):
                return (f"guard.py refused: `git {sub}` on {path} reverts a secretary edit "
                        f"({names} are the secretary's; commit them, never revert).")
            if "$(" in path or "`" in path:
                return (f"guard.py refused: `git {sub}` fed by a command substitution can revert "
                        f"{names}; name the paths yourself.")
        if sub == "restore" and any(a in ("--staged", "-S") for a in args) and not any(
                a in ("--worktree", "-W") for a in args):
            return None
        files = paths if sub == "restore" else after
        unknown_place = prefix is None or bool(directory)
        risky = any(_broad(p, _path_form(p), rules.whole_tree) for p in paths) or any(
            _bare_file(_path_form(p)) or (unknown_place and "/" not in _path_form(p))
            for p in files)
        forced = sub == "checkout" and any(a in ("-f", "--force") for a in args)
        if risky or forced:
            return _dirty_reason(f"`git {sub} {' '.join(args)}`", dirty)
        return None
    if sub == "switch":
        if any(a in ("-f", "--force", "--discard-changes") for a in args):
            return _dirty_reason(f"`git switch {' '.join(args)}`", dirty)
        return None
    if sub == "stash":
        if not args or args[0] in ("push", "save") or args[0].startswith("-"):
            return _dirty_reason("`git stash`", dirty)
        return None
    if sub == "clean":
        if any(a == "--force" or (a.startswith("-") and not a.startswith("--") and "f" in a) for a in args):
            return _dirty_reason("`git clean -f`", dirty)
    return None


def release_ask(words: list[str], maintainer: str) -> str | None:
    if not words:
        return None
    name = command_name(words[0])
    if name == "gh":
        index = 1
        while index < len(words) and words[index].startswith("-"):
            index += 2 if words[index] in ("-R", "--repo") else 1
        rest = words[index:]
        if len(rest) > 1 and rest[0] == "release" and rest[1] in (
                "create", "edit", "delete", "delete-asset", "upload"):
            return f"`gh release {rest[1]}` changes a published release; {maintainer} approves it."
        if rest and rest[0] == "api" and any("releases" in w for w in rest):
            method = "GET"
            fields = False
            for i, word in enumerate(rest):
                if word in ("-X", "--method") and i + 1 < len(rest):
                    method = rest[i + 1].upper()
                elif word.startswith("-X") and len(word) > 2:
                    method = word[2:].upper()
                elif word.startswith("--method="):
                    method = word.split("=", 1)[1].upper()
                elif word in ("-f", "-F", "--field", "--raw-field", "--input"):
                    fields = True
            explicit = any(w in ("-X", "--method") or w.startswith(("-X", "--method=")) for w in rest)
            if method != "GET" or (fields and not explicit):
                return (f"`gh api` writing to releases changes a published release; "
                        f"{maintainer} approves it.")
        return None
    found = _git(words)
    if found and found[0] == "push":
        for word in found[1]:
            if (word.startswith("--force") or word == "--mirror" or word.startswith("+")
                    or (word.startswith("-") and not word.startswith("--") and "f" in word)):
                return (f"A forced or mirroring `git push` rewrites history on the remote; "
                        f"{maintainer} approves it.")
    return None


def maintainer_only(words: list[str], rules: Rules) -> str | None:
    if not words:
        return None
    runner = command_name(words[0]) in INTERPRETERS | {"uvx", "source", "."}
    for index, word in enumerate(words):
        if index and not runner:
            break
        form = flat(word)
        for script, subcommands in rules.maintainer_only:
            if not form.endswith(script):
                continue
            if not subcommands:
                return script
            following = words[index + 1] if index + 1 < len(words) else ""
            if following in subcommands:
                return f"{script} {following}"
    return None


def _cd_target(words: list[str]) -> str | None:
    args = [w for w in words[1:] if w.lower() not in ("-path", "-literalpath", "/d", "-l", "-p")]
    return args[0] if args else None


def _segment_verdict(segment: Segment, rules: Rules, assigned: dict[str, str],
                     dirty: Callable[[], list[str]], tainted_in: bool,
                     location: Location) -> tuple[Verdict, bool]:
    places = rules.places
    set_name = set_outside_cmd(segment, rules.set_names)
    if set_name:
        return Verdict("deny", set_message(set_name, rules)), False
    before = dict(assigned)
    words, _assigned_here = assignments(segment, places.refs, assigned)
    expanded = [expand_refs(w, places.refs, before) for w in words]
    redirects = [expand_refs(r, places.refs, before) for r in segment.redirects]
    values = [assigned[k] for k in assigned if before.get(k) != assigned[k]]
    text = flat(" ".join(expanded + redirects))
    name = command_name(expanded[0]) if expanded else ""
    body = flat(expand_refs(segment.body, places.refs, before)) if name in INTERPRETERS else ""
    if names_place(text, places.keys) or names_place(body, places.keys) \
            or names_key_file(expanded, redirects, rules) or names_key_path(body, rules):
        return Verdict("deny", f"guard.py refused: this names a secret ({rules.secret_names}). "
                               f"{rules.maintainer} keeps it; Claude never reads, copies or uses "
                               "it."), False
    if name in CD_COMMANDS:
        target = _cd_target(expanded)
        location.change(flat(target) if target is not None else None)
        if location.absolute is not None and names_place(location.absolute, places.keys):
            return Verdict("deny", "guard.py refused: this enters a secrets folder. "
                                   f"{rules.maintainer} keeps it; Claude never reads, copies or "
                                   "uses it."), False
        return ALLOW, False
    reserved = maintainer_only(expanded, rules)
    if reserved:
        return Verdict("deny", f"guard.py refused: `{reserved}` is {rules.maintainer}'s to run, "
                               "never Claude's."), False
    if not expanded and segment.substitution and any(
            names_place(flat(v), places.real_data) for v in values):
        return Verdict("deny", f"guard.py refused: a command substitution touching "
                               f"{rules.name}'s real data; read it with a read-only command "
                               "instead."), False
    located = expanded[:1] + [location.resolve(flat(w)) for w in expanded[1:]]
    located_redirects = [location.resolve(flat(r)) for r in redirects]
    names_real = (names_place(text, places.real_data) or names_place(body, places.real_data)
                  or names_place(flat(" ".join(located + located_redirects)), places.real_data)
                  or (location.absolute is not None
                      and names_place(location.absolute, places.real_data)))
    tainted_out = False
    if expanded and (names_real or tainted_in):
        if name in ("git", "gh"):
            pass
        elif not body and not (segment.substitution and names_real) and is_read_only(
                located, located_redirects, places, rules.self_guarding):
            tainted_out = True
        else:
            return Verdict("deny", f"guard.py refused: this writes to, or runs something on, "
                                   f"{rules.name}'s real data ({rules.real_data_names}). Only "
                                   "reads and copies out of it are allowed; work on a copy in a "
                                   "scratch folder."), False
    if rules.app is not None and starts_app(expanded, rules.app):
        app = rules.app
        if not app.isolate_env or any(_not_isolated(assigned.get(v), app, places)
                                      for v in app.isolate_env):
            return Verdict("deny", app_message(rules)), False
    reason = reverts_secretary_files(expanded, dirty, location.relative, rules)
    if reason:
        return Verdict("deny", reason), False
    ask = release_ask(expanded, rules.maintainer) if rules.ask_release else None
    if ask:
        return Verdict("ask", ask), tainted_out
    return ALLOW, tainted_out


def command_verdict(command: str, shell: str, rules: Rules,
                    secretary_dirty: Callable[[], list[str]]) -> Verdict:
    assigned: dict[str, str] = {}
    location = Location(rules.places.project)
    tainted = False
    asked: Verdict | None = None
    for segment in segments(command, shell):
        verdict, tainted_out = _segment_verdict(segment, rules, assigned, secretary_dirty,
                                                tainted and segment.piped, location)
        if verdict.kind == "deny":
            return verdict
        if verdict.kind == "ask" and asked is None:
            asked = verdict
        tainted = tainted_out
    return asked or ALLOW


def file_verdict(path: str, rules: Rules) -> Verdict:
    places = rules.places
    form = flat(expand_refs(path, places.refs, {}))
    if names_place(form, places.keys) or rules.key_end.search(form):
        return Verdict("deny", f"guard.py refused: this file is (or is beside) a secret "
                               f"({rules.secret_names}). {rules.maintainer} keeps it; Claude "
                               "never reads or writes it.")
    if names_place(form, places.real_data):
        return Verdict("deny", f"guard.py refused: this file is in {rules.name}'s real data "
                               f"({rules.real_data_names}). Work on a copy in a scratch folder.")
    return ALLOW


def decide(tool_name: str, tool_input: Mapping, env: Mapping[str, str],
           secretary_dirty: Callable[[], list[str]], config: Mapping[str, Any]) -> Verdict:
    rules = rules_from(config, env)
    if tool_name in ("Bash", "PowerShell"):
        command = tool_input.get("command") or ""
        shell = "bash" if tool_name == "Bash" else "powershell"
        return command_verdict(command, shell, rules, secretary_dirty)
    if tool_name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        return file_verdict(path, rules)
    return ALLOW


def secretary_files(config: Mapping[str, Any]) -> list[str]:
    status_file = config.get("status_file") if isinstance(config.get("status_file"), str) \
        else "docs/STATUS.md"
    plans_dir = config.get("plans_dir") if isinstance(config.get("plans_dir"), str) \
        else "docs/plans"
    return [p for p in (status_file, plans_dir) if p]


def secretary_changes(project_dir: str, paths: list[str]) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--", *paths],
            cwd=project_dir or None, capture_output=True, text=True, encoding="utf-8", timeout=5)
    except (OSError, subprocess.SubprocessError):
        return []
    return [line[3:].strip() for line in result.stdout.splitlines() if line.strip()]


def load_config(project_dir: str) -> dict | None:
    path = os.path.join(project_dir or ".", ".claude", "devflow.json")
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return None
    if not isinstance(data, dict):
        raise ValueError(f"{path} must hold a JSON object")
    return data


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
        project = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or ""
        config = load_config(project)
        if config is None:
            return 0
        verdict = decide(data.get("tool_name", ""), data.get("tool_input") or {}, os.environ,
                         lambda: secretary_changes(project, secretary_files(config)), config)
    except Exception as error:
        print(f"guard.py failed: {type(error).__name__}: {error} -- not checked", file=sys.stderr)
        return 1
    if verdict.kind == "deny":
        print(verdict.reason, file=sys.stderr)
        return 2
    if verdict.kind == "ask":
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": verdict.reason,
        }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
