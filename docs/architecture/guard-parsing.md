# Guard command parsing

The guard judges every Bash and PowerShell call before it runs, so it has to see a command the way the shell will: where one command ends and the next starts, which words are arguments and which are redirect targets, what a variable holds and which folder a relative path lands in. This doc covers that parsing and the order the rules are applied in. Read it before changing how a command is split or judged, or before adding a rule; the rules' own wording is in `hooks/guard.py` and their cases in `tests/test_guard.py`.

## Flow

1. [`main`](../../hooks/guard.py) reads the hook's JSON, finds the config through [`find`](../../hooks/devflow_store.py) (no config: exit 0, nothing judged), and calls [`decide`](../../hooks/guard.py). Any exception on the way becomes an `ask` ("not checked"), never an allow.
2. [`decide`](../../hooks/guard.py) builds the [`Rules`](../../hooks/guard.py) once with [`rules_from`](../../hooks/guard.py) and sends shell tools to [`command_verdict`](../../hooks/guard.py) (Bash as `bash`, PowerShell as `powershell`) and file tools to [`file_verdict`](../../hooks/guard.py) (Read, Grep and Glob with `reading=True`, which only checks secrets).
3. [`segments`](../../hooks/guard.py) cuts the command into [`Segment`](../../hooks/guard.py)s:
   - [`_split`](../../hooks/guard.py) walks the text once, tracking quotes and the shell's escape character ([`_escape_char`](../../hooks/guard.py)), and cuts at newlines, `;`, `&&`, `||`, `|` (marking the next piece `piped`) and a lone `&`. A bash heredoc's delimiter is found by [`_heredoc_delimiter`](../../hooks/guard.py); its body lines are consumed and kept as the segment's `body`, so they are never parsed as commands.
   - [`parse_words`](../../hooks/guard.py) turns a piece into words and redirect targets, removing quotes the way the shell would.
   - [`_strip_wrappers`](../../hooks/guard.py) drops launchers (`env`, `nohup`, `timeout`, `start`, `Start-Process`, `Invoke-Item`) so the real command is first.
   - [`_inner_command`](../../hooks/guard.py) finds `cmd /c`, `powershell -Command` and `bash -c`, and their text is split again in that shell, at most two levels deep.
4. [`command_verdict`](../../hooks/guard.py) judges the segments in order with one shared `assigned` map and one [`Location`](../../hooks/guard.py). The first deny wins at once; the first ask is kept and returned only if nothing denies.
5. [`_segment_verdict`](../../hooks/guard.py) applies the rules to one segment, in this order: `set` outside cmd, variable assignments ([`assignments`](../../hooks/guard.py)) and expansion ([`expand_refs`](../../hooks/guard.py)), secrets, `cd` (moves the [`Location`](../../hooks/guard.py)), maintainer-only scripts, command substitutions, real data, starting the app, reverting managed files ([`reverts_managed_files`](../../hooks/guard.py)), the release stamp ([`publishing`](../../hooks/guard.py), [`_stamp_refusal`](../../hooks/guard.py)) and finally the release ask ([`release_ask`](../../hooks/guard.py)).

## Invariants

- **Never a silent allow on failure.** The guard's whole value is that a call it could not judge is shown to a person. A new code path that can raise must stay inside `main`'s `try`, whose handler turns the exception into an `ask`.
- **Values are expanded with the map from before the segment.** `_segment_verdict` copies `assigned` into `before` and expands the segment's words with it, so `X=/real/data cmd $X` is judged with what `$X` held before this segment, as the shell does, while the assignment itself still reaches the next segment.
- **Taint flows only along a pipe.** A read-only command over real data marks its output tainted, and the next segment is judged as touching real data only when it is `piped`. A `;` or `&&` clears it.
- **The working folder is tracked, not guessed.** Relative paths are resolved against the absolute folder that an earlier `cd`, `Set-Location` or `pushd` segment named. Until then, and after a `cd` to `-` or to a variable, the absolute location is unknown and nothing is resolved, so the path checks use the words as written. The project-relative form (`Location.relative`) is tracked alongside and is what the managed-files rule reads.
- **`git` and `gh` are never judged as writing real data.** Their own rules (managed files, publishing, the release ask) cover them; naming a real-data path in a git command is not a write to it.

## Recipe

Adding a wrapper command, or a shell construct the splitter must see through:

1. Extend [`_strip_wrappers`](../../hooks/guard.py) for a launcher, [`_inner_command`](../../hooks/guard.py) for a nested shell, or [`_split`](../../hooks/guard.py) / [`parse_words`](../../hooks/guard.py) for syntax.
2. Add a refusal case to `TestGuardRefuses` that only the change makes pass (for example, writing real data through the new wrapper), and an allow case to `TestGuardAllows` that shows ordinary use still goes through.

Adding a rule:

1. Read its config in [`rules_from`](../../hooks/guard.py) and add the field to [`Rules`](../../hooks/guard.py), with a default that keeps a config without the key working (`TestMinimalConfig`).
2. Apply it in [`_segment_verdict`](../../hooks/guard.py) at the place in the order where its inputs are ready (after expansion and location for anything that reads paths), and in [`file_verdict`](../../hooks/guard.py) if file tools can break it too.
3. Test deny, ask and allow cases against the RYOS-shaped config, `TestAnotherProject` and `TestMinimalConfig`, and add its row to `docs/BEHAVIOUR.md`.

## Gotchas

- **cmd has one quote character and `^` for escapes; PowerShell uses a backtick and doubles a single quote inside single quotes.** A change to quoting in `_split` or `parse_words` has to keep all three shells; a test in one shell proves nothing about the others.
- **A lone `&` is a separator in bash and cmd but not in PowerShell**, where it is the call operator. `_split` keeps it in the text for PowerShell, and `_strip_wrappers` drops a leading `&` word.
- **A substitution (`$(...)` or a bash backtick) is not run by the guard.** It can only be judged by what it might name, which is why a substitution that may build a path into real data is denied unless the command is read-only.

## Flagged / unverified

- None.
