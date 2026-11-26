# Store resolver

A project can keep its devflow files (config, profile, status file, plans) in the repo or, for a clone that must not carry them, in a store folder outside it that a pointer in git's common dir names. This doc covers how the hooks and the plan runner find that config, and the shell gate that decides whether a hook runs at all. Read it before changing where devflow looks for its files, or before adding a hook.

## Flow

1. **The shell gate** in [hooks.json](../../hooks/hooks.json) runs first, before any Python. With shell builtins only, it reads `$CLAUDE_PROJECT_DIR/.git`; when that is a file (a worktree or a linked clone), it follows its `gitdir:` line and then that folder's `commondir`. It starts the hook only when `.claude/devflow.json` exists in the project or a `devflow-store` file exists in the common dir. Otherwise the hook prints nothing and the call goes through.
2. **The Python resolver**, [`find`](../../hooks/devflow_store.py), repeats that decision with the same rules:
   - an in-repo config, read by [`read_config`](../../hooks/devflow_store.py), wins and returns a [`Found`](../../hooks/devflow_store.py) with `store` unset;
   - else [`pointer_file`](../../hooks/devflow_store.py) builds the pointer's path from [`common_dir`](../../hooks/devflow_store.py), and no pointer means `None` (not a devflow project);
   - else [`store_from_pointer`](../../hooks/devflow_store.py) reads the pointer's first line, which must be an absolute path to an existing folder, and the config must exist under that store's `.claude/`.
3. **The callers:**
   - the guard's [`main`](../../hooks/guard.py) returns exit 0 on `None`; on a store it skips the managed-files check, because the status file and plans are not in the working tree;
   - session start's [`main`](../../hooks/session_start.py) reads the profile, status file and plans under the store when there is one (its `report` takes `store`), and prints a `Store:` line;
   - the plan runner calls the same [`find`](../../hooks/devflow_store.py) through `session_start`, and uses [`common_dir`](../../hooks/devflow_store.py) for its waiver token folder.

## Invariants

- **No config, no hook.** Installing the plugin for a whole user account must change nothing in projects that never adopted devflow. Every hook added to `hooks.json` keeps the same gate, and the gate uses builtins only, because it runs before anything is known about the machine (no `uv`, no Python guaranteed).
- **The shell gate and `find` agree.** If the gate starts a hook that `find` then says has no config, the hook silently does nothing; if `find` would find a config the gate missed, the guard never runs. A change to how the pointer is located changes both, with a test in `tests/test_store.py` (`TestHookGateShell` runs the real gate) and the hook-command tests in `tests/test_guard.py` and `tests/test_session_start.py`.
- **A broken link asks, never allows.** A pointer that cannot be read, is empty, names a relative path or a missing folder, or a store without a config raises [`StoreError`](../../hooks/devflow_store.py). It is a `ValueError`, so the guard's exception handler turns it into an `ask`; session start prints a `Store:` line telling the maintainer to link the clone again.
- **An in-repo config wins over a pointer.** A clone that adopts devflow in the repo stops reading the store without anyone deleting the pointer.

## Recipe

Adding a hook:

1. Copy the gate from an existing command in [hooks.json](../../hooks/hooks.json) unchanged, and call the script with `uv run --no-project --quiet python`.
2. In the script, call [`find`](../../hooks/devflow_store.py) first and do nothing on `None`; catch [`StoreError`](../../hooks/devflow_store.py) and say what the maintainer should do.
3. Extend the gate tests to the new command: `TestHookGate` and `TestHookGateShell` in `tests/test_store.py` name the guard's and session start's commands one by one, so a third is not covered until it is added there.

## Gotchas

- **Paths in `.git` and `commondir` may be relative**, to the project and to the gitdir respectively, and may carry a trailing carriage return on Windows. Both the shell gate and [`_resolve`](../../hooks/devflow_store.py) / [`_first_line`](../../hooks/devflow_store.py) handle each case; a fix in one needs the same fix in the other.
- **The store's layout mirrors the repo's paths** (`.claude/devflow.json`, `.claude/devflow.md`, the status file and plans folder at their configured paths), so code that reads those files takes a root rather than building store-specific paths.

## Flagged / unverified

- No skill writes a store, a pointer or the `devflow-store.json` manifest yet; [`home`](../../hooks/devflow_store.py) (the `DEVFLOW_HOME` default) is read only by its tests. The layout above is what the readers expect, not what a writer has been checked to produce.
