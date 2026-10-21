# Changelog

## Unreleased

- Guard: the Read, Grep and Glob tools can no longer open files in the configured secret folders or with a secret extension.
- Guard: globs that match a secret folder or the real data folder are refused (`cat ~/.secr*/token`, `rm $APPDATA/My*`).
- Guard: a write command whose command substitution may build a path into the real data folder is refused.
- Guard: when the guard fails (an exception, a broken `devflow.json`, `uv` missing, a guard that cannot start) the call now asks instead of passing silently.
- CI: the repository runs its own tests on Linux and Windows.
- README: states what the guard does and does not protect against.

## 0.1.0

- First release: the RYOS working method as a plugin.
