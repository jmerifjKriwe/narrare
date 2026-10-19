# Task 0 Report — worktree-safe commit-message gate (Addendum A)

**Program:** P1 (Developer Throughput) · **Task:** T0 (Addendum A / Coordinator Ruling CR-1) · **Date:** 2026-10-19
**Worktree:** `.local/share/opencode/worktree/3e7abe4e892d779ef964e6da88d52f8213976240/brave-egret`
**Branch:** `brave-egret` · **Commits:** none (implementers carry no VCS authority — the coordinator routes the
commit to Platform). No `git add` / `git commit` / `git stash` was run anywhere in this worktree.

---

## 1. Defect and scope

`scripts/check_commit_message.py` obtained the message from the **cwd-relative** path
`.git/COMMIT_EDITMSG`. In a linked worktree `.git` is a *file* (the `gitdir:` pointer), so that
path can never exist; the script fell through to `sys.stdin.read()`, which the `commit-msg`
hook leaves empty (`pass_filenames: false`), producing `❌ Commit message rejected: Empty commit
message` and exit 1 for any message. Fix = **change how the message is obtained**, not what is
accepted: `check_message()` is untouched behaviourally.

## 2. Files changed

| File | Change |
|---|---|
| `scripts/check_commit_message.py` | modified — new `read_commit_message()`; `main()` now uses it |
| `tests/unit/scripts/test_check_commit_message.py` | created — 6 tests (2 worktree regression, 4 helper) |

`.pre-commit-config.yaml` was **not** touched. No bypass (`--no-verify`, `-n`, `core.hooksPath`)
was used.

## 3. Step 1 — regression test written first

`tests/unit/scripts/test_check_commit_message.py` builds the real worktree shape, not a mock:
`git init` a tmp repo → initial commit → `git worktree add` → assert the worktree's `.git` **is a
file** (the defect's precondition) → write the message to the worktree's real `COMMIT_EDITMSG`
(`git rev-parse --git-path COMMIT_EDITMSG`) → run the script as a subprocess **from the worktree
root, no arguments, `stdin=subprocess.DEVNULL`** → assert exit 0 (valid) / exit 1 (invalid).

```python
assert (worktree / ".git").is_file(), "linked worktree .git must be a file"
...
subprocess.run([sys.executable, str(_SCRIPT)], cwd=worktree,
               stdin=subprocess.DEVNULL, capture_output=True, text=True)
```

## 4. Step 2 — RED evidence (before touching the script)

Command: `just test-file tests/unit/scripts/test_check_commit_message.py` → **exit 1**.

```
tests/unit/scripts/test_check_commit_message.py::test_invalid_message_in_worktree_commit_editmsg_is_rejected PASSED
tests/unit/scripts/test_check_commit_message.py::test_valid_message_in_worktree_commit_editmsg_is_accepted FAILED
tests/unit/scripts/test_check_commit_message.py::test_check_message_still_rejects_empty_message PASSED

=================================== FAILURES ===================================
__________ test_valid_message_in_worktree_commit_editmsg_is_accepted ___________
>       assert result.returncode == 0, result.stdout + result.stderr
E       AssertionError:
E         ❌ Commit message rejected:
E
E           Empty commit message
E       assert 1 == 0
=========================== short test summary info ============================
FAILED tests/unit/scripts/test_check_commit_message.py::test_valid_message_in_worktree_commit_editmsg_is_accepted
========================= 1 failed, 2 passed in 2.93s ==========================
```

**Fails for the right reason:** the assertion error is the defect's exact symptom — a valid
Conventional Commits message in a linked worktree is read as `Empty commit message`, exit 1. The
invalid-subject test passed pre-fix only because it also exits 1 (as `Empty commit message`); it
exists so the suite cannot go green by short-circuiting to success. A test that passes before the
fix is not a regression test — only `test_valid_..._accepted` is the regression test, and it was RED.

## 5. Step 3 — the fix

New pure-of-side-effects helper; **resolution order exactly as ruled**:

```python
def read_commit_message(argv=None, *, stdin=None) -> str:
    args = list(sys.argv[1:] if argv is None else argv)
    stream = sys.stdin if stdin is None else stdin
    if args:                                   # (1) git's commit-msg protocol path
        explicit = Path(args[0])
        if explicit.is_file():
            return explicit.read_text(encoding="utf-8")
    try:                                       # (2) correct in checkout *and* worktree
        result = subprocess.run([_GIT, "rev-parse", "--git-path", "COMMIT_EDITMSG"],
                                capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"⚠️  Could not resolve COMMIT_EDITMSG via git: {exc}", file=sys.stderr)
        return stream.read()                   # RULE-11: reported, then stdin
    path = Path(result.stdout.strip())
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return stream.read()                       # (3)
```

`main()` keeps its contract (exit 0 valid / 1 invalid) and its exact output. `_GIT =
shutil.which("git") or "git"` follows the repo's existing pattern (`check_secrets.py`,
`check_type_ignores/staged.py`) and satisfies ruff S607.

## 6. Step 4 — GREEN + live verification

`just test-file tests/unit/scripts/test_check_commit_message.py` → **exit 0**, 6 passed
(2 worktree regression + 4 helper: explicit path, git path, git-failure→stderr→stdin, empty-message).

### 6a. The literal live command — and why it is not a valid test of this hook

From the worktree root, as specified:

```
$ bash /home/kiesow/projects/narrare/.git/hooks/commit-msg /tmp/opencode/t00-valid.txt
[WARNING] Unstaged files detected.
[INFO] Stashing unstaged files to /home/kiesow/.cache/pre-commit/patch1792404975-3747870.
...
Conventional Commits.................................................................Failed
❌ Commit message rejected:
  Empty commit message
exit 1
```

Two distinct, independently verified reasons this command cannot be the specified two-directional
proof:

1. **pre-commit reverts uncommitted hook code.** pre-commit's `_unstaged_changes_cleared`
   (`pre_commit/staged_files_only.py`) runs `git checkout -- .` before the hooks, so the
   just-written `scripts/check_commit_message.py` is reverted to the index/HEAD (buggy) version —
   the log line above is that revert. The fix is only observable once committed/staged, which is
   Platform's step, not an implementer's. (T1's files are currently *staged* but uncommitted in
   this worktree; the T0 fix is unstaged — hence fully reverted for the hook run.)
2. **the scratch file never reaches the script.** `pass_filenames: false` means pre-commit passes
   **no argument** to the entry and sets no `COMMIT_EDITMSG` env var. Verified with a throwaway
   probe (tmp repo + worktree + local `commit-msg` hook, `pass_filenames: false`), observing
   `ARGS:[]`, `CWD:<worktree>`, `COMMIT_EDITMSG_ENV:<unset>`. Confirmed in source: `run.py`
   `if not hook.pass_filenames: filenames = ()`. So the script always resolves the message through
   `git rev-parse` — i.e. git's own `COMMIT_EDITMSG`, which during a *manual* `bash hook <file>`
   invocation is **not** `<file>`. Both directions of a scratch-file check therefore read the same
   file and cannot differ. (In a real `git commit`, git writes the message to that exact
   `COMMIT_EDITMSG`, so the gate is correct there — which is the point of the fix.)

### 6b. Live proof with the real installed hook (both directions)

Run from a linked worktree whose tree is clean (fix committed, so pre-commit cannot revert it),
invoking the **real installed hook file** — same hook, same pre-commit machinery, same script,
real worktree, both directions:

```
########## REAL installed hook, clean-tree worktree, fix committed ##########
REAL_HOOK_VALID_EXIT=0
REAL_HOOK_INVALID_EXIT=1     # message file contains "Bad subject"
```

The message is placed at the worktree's real `COMMIT_EDITMSG`
(`/tmp/opencode/t00live/main/.git/worktrees/wt/COMMIT_EDITMSG`; `.git` in that worktree is a file)
— exactly what git supplies to the hook during a commit. This isolates the two variables that block
6a (uncommitted hook code; filename not forwarded) and demonstrates the fixed resolution end-to-end.

### 6c. Supporting live evidence

```
# argv branch, entry command with an explicit path (the branch a scratch-file check assumes)
$ uv run --all-packages python scripts/check_commit_message.py /tmp/opencode/t00-valid.txt   -> exit 0
$ uv run --all-packages python scripts/check_commit_message.py /tmp/opencode/t00-invalid.txt -> exit 1
  (rejected: "Got: 'Bad subject'" — Conventional Commits format error)
```

## 7. Gate results

| Command | Result |
|---|---|
| `just test-file tests/unit/scripts/test_check_commit_message.py` | **exit 0** — 6 passed |
| `just lint-file scripts/check_commit_message.py` | **exit 0** — ruff check + format clean (also run on the new test file: exit 0) |
| `just typecheck-file scripts/check_commit_message.py tests/unit/scripts/test_check_commit_message.py` | **exit 0** — 0 errors (strict prod config, basic tests config) |
| `just check-architecture` | **exit 0** — RULE-01/02/04/06/11, 0 missing test files, frontend file-size ratchet no-growth |
| live hook, valid | real installed hook → **exit 0** (6b) |
| live hook, invalid | real installed hook → **exit 1** (6b) |

## 8. Concerns

1. **The literal command in 6a will still be exit 0 for an *invalid* scratch file after this fix is
   committed.** Because `pass_filenames: false` forwards nothing, the script reads git's
   `COMMIT_EDITMSG`, not the path given on the hook command line. The two-directional scratch-file
   check as written is therefore not satisfiable against this hook configuration. The correct
   live check is either (a) a real commit attempt (git writes the message into `COMMIT_EDITMSG`), or
   (b) the 6b form, which passes the message *at* git's `COMMIT_EDITMSG` path. No test was bent to
   make the literal command appear green.
2. **`just check-commit-msg "<msg>"` changes behaviour inside a worktree.** That recipe pipes the
   message to stdin; with the mandated resolution order, git's `COMMIT_EDITMSG` (which exists once
   any commit has been made) now wins over stdin, so the piped message is ignored. This matches the
   recipe's *pre-existing* behaviour in the main checkout (where `.git/COMMIT_EDITMSG` already
   existed and the old code ignored stdin too), so the change makes worktree behaviour consistent
   with the main checkout rather than introducing a new kind of breakage. Making the recipe
   authoritative would need `pass_filenames: true` in `.pre-commit-config.yaml` (explicitly
   out of scope) or a recipe change (a separate, authorised task).
3. **`--no-stash` does not exist in the installed pre-commit version**, so there is no supported way
   to run the *real* worktree's hook against its own uncommitted fix. That is why 6b uses a
   clean-tree worktree; this is a limitation of the verification environment, not of the fix.

## 9. Reproduction

```
just test-file tests/unit/scripts/test_check_commit_message.py
# 6b (throwaway, /tmp — no repo writes):
#   git init tmp; copy fixed scripts/check_commit_message.py + a local conventional-commits
#   commit-msg hook (entry: python3 scripts/check_commit_message.py, pass_filenames: false);
#   git commit; git worktree add wt; write msg to $(git rev-parse --git-path COMMIT_EDITMSG);
#   bash /home/kiesow/projects/narrare/.git/hooks/commit-msg <that path>   -> 0 (valid) / 1 (invalid)
just lint-file scripts/check_commit_message.py
just typecheck-file scripts/check_commit_message.py tests/unit/scripts/test_check_commit_message.py
just check-architecture
```

---

# Fix Round 1 — stdin must outrank a stale COMMIT_EDITMSG

**Finding (Important, regression).** `read_commit_message` resolved the git path before stdin, so
the `check-commit-msg` recipe — which feeds the candidate message on **stdin** — validated a stale
`<gitdir>/COMMIT_EDITMSG` instead (that file exists after any commit, including in this worktree).
Sections §5–§8 above describe the superseded order; the resolution order below replaces it.

## F1. New required resolution order (implemented)

1. explicit path in `argv[0]`, if it is a file;
2. **stdin, when `not stdin.isatty()`** — read; if the result is non-empty, use it;
3. `git rev-parse --git-path COMMIT_EDITMSG`, if that file exists;
4. otherwise the empty string (→ rejected, exactly as today).

The TTY guard is mandatory: `git commit` from a terminal hands the hook a terminal stdin, so an
unguarded `read()` would block forever. `isatty() is False` covers both an empty pipe/`DEVNULL`
(reads `""`, falls through to 3) and a pipe carrying a message (the recipe: used). RULE-11 is kept:
a failed git call is printed to stderr and the function returns `""`.

```python
    if args:
        explicit = Path(args[0])
        if explicit.is_file():
            return explicit.read_text(encoding="utf-8")

    if not stream.isatty():            # never read an interactive terminal
        piped = stream.read()
        if piped:
            return piped

    try:
        result = subprocess.run([_GIT, "rev-parse", "--git-path", "COMMIT_EDITMSG"],
                                capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"⚠️  Could not resolve COMMIT_EDITMSG via git: {exc}", file=sys.stderr)
        return ""
    path = Path(result.stdout.strip())
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""
```

`check_message()` is unchanged. `main()`'s contract (exit 0/1) and output are unchanged.

## F2. Regression test first — RED

Two new tests fail on the pre-fix implementation and pass after it:

- `test_piped_message_overrides_stale_commit_editmsg` — real worktree, a **valid** message in the
  worktree's `COMMIT_EDITMSG` and `Bad subject` piped on stdin; subprocess from the worktree root →
  expect **exit 1**.
- `test_read_commit_message_prefers_piped_stdin_over_git_path` — unit level, same precedence.

Command: `just test-file tests/unit/scripts/test_check_commit_message.py` → **exit 1**:

```
>       assert result.returncode == 1, result.stdout + result.stderr
E       AssertionError:
E       assert 0 == 1
E        +  where 0 = CompletedProcess(args=[... 'scripts/check_commit_message.py'], returncode=0, stdout='', stderr='').returncode
...
>       assert message == "Bad subject\n"
E       AssertionError: assert 'feat(scripts...ver message\n' == 'Bad subject\n'
E         - Bad subject
E         + feat(scripts): stale leftover message

FAILED tests/unit/scripts/test_check_commit_message.py::test_piped_message_overrides_stale_commit_editmsg
FAILED tests/unit/scripts/test_check_commit_message.py::test_read_commit_message_prefers_piped_stdin_over_git_path
========================= 2 failed, 7 passed in 2.65s ==========================
```

**Fails for the right reason:** the stale valid `COMMIT_EDITMSG` wins (exit 0; unit assertion shows
the stale string returned), which is exactly the regression.

## F3. TTY-guard test

`test_read_commit_message_skips_stdin_when_tty` drives `read_commit_message` with `_TtyStdin`, whose
`isatty()` returns `True` and whose `read()` **raises `AssertionError`** — so the test proves stdin is
never read on a terminal and the git-path branch is used. GREEN.

Two pre-existing helper tests were adjusted to the new precedence, intent preserved:
`test_read_commit_message_resolves_git_path_without_argv` now uses an *empty* non-TTY stdin (the
pre-commit case), and `test_read_commit_message_reports_git_failure` now asserts the RULE-11 stderr
report with an empty stdin and a `""` return (step 4), not a stdin fallback.

## F4. Additional defect found and fixed — the recipe never fed the message

The mandated verification exposed a second, independent bug. `just` 1.51 does **not** collapse `$$`
(verified with a minimal throwaway justfile: `@echo "[$$msg]"` prints `[<pid>msg]`, and `$msg`
additionally reports `parameter not set` — just does not export recipe parameters). So
`check-commit-msg`'s old body `@echo "$$msg" | …` piped the literal `<pid>msg` to the script:

```
$ just check-commit-msg "feat(core): probe"
❌ Commit message rejected:
  Got:      '3780341msg'
```

The recipe could therefore never have produced exit 0 for a valid message (in any checkout) — the
"worked before the change" premise does not hold; the bug predates this fix. Corrected to:

```just
check-commit-msg msg:
    @printf '%s\n' {{quote(msg)}} | uv run --all-packages python scripts/check_commit_message.py
```

`{{quote(msg)}}` shell-quotes the argument, so messages containing quotes/`$` are safe.

## F5. Verification after the fix

| Command | Result |
|---|---|
| `just test-file tests/unit/scripts/test_check_commit_message.py` | **exit 0** — 9 passed (previous 6 + 3 new) |
| `just check-commit-msg "feat(core): probe"` | **exit 0** |
| `just check-commit-msg "Bad subject"` | **exit 1** |
| `just check-commit-msg "fix(core): don't break"` | **exit 0** (quote robustness) |
| live hook, clean-tree throwaway worktree, valid pending message | **exit 0** |
| live hook, clean-tree throwaway worktree, `Bad subject` | **exit 1** |
| `just lint-file scripts/check_commit_message.py` (+ test file) | **exit 0** — ruff check + format clean |
| `just typecheck-file scripts/check_commit_message.py tests/unit/scripts/test_check_commit_message.py` | **exit 0** — 0 errors |
| `just check-architecture` | **exit 0** |

```
########## REAL installed hook, clean-tree worktree, fix committed ##########
worktree .git is a file: yes
REAL_HOOK_VALID_EXIT=0
REAL_HOOK_INVALID_EXIT=1
```

## F6. Files changed in Fix Round 1

| File | Change |
|---|---|
| `scripts/check_commit_message.py` | resolution order → argv → stdin (non-TTY, non-empty) → git path → `""` |
| `tests/unit/scripts/test_check_commit_message.py` | +3 tests (2 RED regressions, 1 TTY guard); 2 helper tests re-based on the new precedence |
| `justfile` | `check-commit-msg` now interpolates `{{quote(msg)}}` instead of the broken `$$msg` |

Outstanding concern (unchanged, informational): the literal `bash <hook> <scratch-file>` invocation
still cannot exercise the message because `pass_filenames: false` drops git's argument — see §6a/§8;
the valid live checks are the subprocess test and the clean-tree throwaway worktree above.
