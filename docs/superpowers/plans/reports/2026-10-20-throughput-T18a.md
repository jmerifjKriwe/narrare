# Throughput T18a — integrate `narrare/main` (claim gate) into the throughput branch

- **Date:** 2026-10-20
- **Branch:** `brave-egret`
- **Base commit:** `4bd088eb` (T17 wave)
- **Integrated commit:** `0e86b2eb` — #261, "require a User-visible claim for feat/fix"
- **Status:** merged, verified, committed as a two-parent merge commit
- **Ruling:** CR-11 — one merge, not a rebase (the same hunks in `ci.yml`,
  `quality-gates.md` and `justfile` are touched by 2–3 branch commits; a replay
  would resolve them repeatedly and could leave an inconsistent intermediate
  commit)

## 1. Why the conflict is real on both sides

The two changes overlap in the same functions and neither contains the other:

| Concern | `narrare/main` (#261) | This branch (T0/T8/T15/T17) |
|---|---|---|
| Message source | argv[1] > stdin > `.git/COMMIT_EDITMSG` | argv > non-empty stdin > `git rev-parse --git-path COMMIT_EDITMSG` |
| `.git` shape | assumes `.git` is a directory | correct in a linked worktree, where `.git` is a *file* |
| Claim gate | `feat`/`fix` require `User-visible:` | predates the gate |
| Hook input | `pass_filenames: true` | hook tiering (T8) |
| Gate tables | one new claim-gate row | four new rows + `ci-table-mirror` |

Main's `read_message` hardcodes `.git/COMMIT_EDITMSG`, which does not exist in a
worktree. This branch's `read_commit_message` has the git-path resolution but no
claim rule and no comment stripping. The union keeps both behaviours; no
semantic change was needed on either side.

## 2. Conflict set (6) and resolution

### 2.1 `scripts/check_commit_message.py` — union

From **main**: the docstring claim rule, `USER_VISIBLE_TYPES`,
`USER_VISIBLE_RE`, `PLACEHOLDERS`, `_check_user_visible`, the error-aggregation
path in `check_message`, `_strip_comments` (file-only `#` handling so a
Markdown heading in a PR body survives), and the argv/stdin/file chain.

From **this branch**: `_GIT` (resolved `git` executable), `shutil`/`subprocess`
imports, the `git rev-parse --git-path COMMIT_EDITMSG` lookup, the
`CalledProcessError`/`FileNotFoundError` warning on stderr (RULE-11), and the
empty-non-TTY-stdin fall-through that makes the lookup reachable under
pre-commit (`DEVNULL`) — **superseded by CR-12, see below**.

The docstring now states both: the resolution order (with git's path) *and* the
claim rule. `read_message` keeps main's `argv`-with-`argv[0]` convention (so
the hook's `argv[1]` works) plus an optional `stdin` seam for the tests.

### 2.2 `tests/unit/scripts/test_check_commit_message.py` — union, not split

All 17 claim-gate cases from main are kept. This branch's worktree regression
cases are ported:

- old `read_commit_message(argv)` → merged `read_message(argv)`;
- `argv[0]` is now the script name, so explicit-path tests pass
  `[str(_SCRIPT), str(path)]`;
- the worktree "valid" fixture message gained a `User-visible:` body line,
  because the merged gate now rejects a bare `feat` subject (that is the
  point of the feature; the test's subject is incidental);
- the module is imported statically (`import scripts.check_commit_message as
  checker`) so pyright strict sees typed members.

Size before the CR-12 fix: 382 lines — under the 600-line Python limit, so no
`test_check_commit_message_worktree.py` split was needed at that point (RULE-04).
Final size after the CR-12 fix forced the split: **188 + 269 = 457 lines**
(`test_check_commit_message.py` + `test_check_commit_message_input_resolution.py`).
The 382 figure is the superseded pre-split measurement, not a live number.

### 2.3 `justfile` — union

- main's `--hook-type commit-msg` in both `dev-setup` targets (auto-merged);
- main's `check-commit-msg` fix (`$$msg` → just-substituted argument), kept in
  this branch's stricter form `printf '%s\n' {{quote(msg)}}` (quotes/percent-safe
  and exactly one trailing newline, same stdin contract);
- this branch's `verify-slice` target and all tiering edits (auto-merged).

### 2.4 `.pre-commit-config.yaml` — union (auto-merged cleanly)

Main's `pass_filenames: true` on `conventional-commits` plus this branch's
stage tiering. `check_pre_commit_gate_tiers.py` passes: the hook still declares
exactly `stages: [commit-msg]` and appears once.

### 2.5 `.github/workflows/ci.yml` — union

Main's PR-title/body claim step (pull_request only, env-based, never
interpolated) and this branch's `check_pre_commit_gate_tiers.py` /
`check_review_policy_consistency.py` steps are both present (auto-merged). Only
the header table conflicted; it now carries the claim-gate row **and** both
branch rows. Every gate appears exactly once.

### 2.6 `docs/development/quality-gates.md` — union

Main's claim-gate row plus this branch's two rows, inserted at the position
`ci.yml` uses; the normative `§ Review & report policy` block is untouched.
`check_gate_drift.py` now reports **41 tool/check rows** on both sides.

## 3. Verification (raw)

```
$ git status --porcelain=v1   # after resolution, before commit
M  .github/dependabot.yml
M  .github/workflows/ci.yml
M  .pre-commit-config.yaml
M  CONTRIBUTING.md
M  docs/development/coding-standards.md
M  docs/development/quality-gates.md
M  justfile
M  scripts/check_commit_message.py
M  tests/unit/scripts/test_check_commit_message.py
```

The three `M` files without a task edit (`dependabot.yml`, `CONTRIBUTING.md`,
`coding-standards.md`) are git's clean automatic merge of #261's other files,
left alone per the task.

```
$ git log --oneline -3
<merge sha> chore(git): merge narrare/main into the throughput branch
4bd088eb docs(state): record the T17 wave and the measured extraPaths verdict
95a814dd fix(scripts): keep the gate tables identical, and check it (throughput T17b2)

$ git rev-list --count narrare/main..HEAD
37
$ git merge-base --is-ancestor narrare/main HEAD && echo has-main
has-main
```

Claim gate samples (stdin, `uv run --all-packages python scripts/check_commit_message.py`):

```
feat without claim                        -> exit 1, names 'User-visible'
feat with User-visible claim              -> exit 0
chore(git): merge ...                     -> exit 0
```

Worktree proof — `.git` is a file here:

```
$ ls -ld .git
-rw-rw-r-- 1 kiesow kiesow 65 Oct 19 08:07 .git
$ git rev-parse --git-path COMMIT_EDITMSG
/home/kiesow/projects/narrare/.git/worktrees/brave-egret/COMMIT_EDITMSG
$ test -e .git/COMMIT_EDITMSG || echo absent
absent
$ uv run --all-packages python scripts/check_commit_message.py </dev/null
exit=0    # pre-CR-12 measurement: empty stdin fell through to git's path (superseded — see CR-12)
```

Code path in the merged `read_message`, as shipped after CR-12: `len(argv) > 1` →
`argv[1]`; else a non-TTY stdin is authoritative **even when empty** and is returned
as-is (`""` when empty, which `check_message` rejects as "Empty commit message"); else
`subprocess.run([_GIT, "rev-parse", "--git-path", "COMMIT_EDITMSG"])` for the TTY/manual
case, the only worktree-safe way to find the file; a missing file and a failing git call
both yield `""`, the latter after printing `Could not resolve COMMIT_EDITMSG via git` to
stderr (RULE-11).

```
$ just test-file tests/unit/scripts/test_check_commit_message.py
26 passed in 2.58s
$ uv run --all-packages pyright tests/unit/scripts/test_check_commit_message.py scripts/check_commit_message.py
0 errors, 0 warnings, 0 informations
$ just check-architecture
exit=0 (45 services checked, 0 missing test files, 0 low coverage; frontend sizes green)
$ uv run --all-packages python scripts/check_gate_drift.py
Summary: 0 critical, 0 warnings
✅ ci-table-mirror: Both gate tables carry the same 41 tool/check rows
$ uv run --all-packages python scripts/check_intent_parity.py
30 intents, 24 routed, 0 disagreements
$ uv run --all-packages python scripts/check_pre_commit_gate_tiers.py
exit=0 (tiers match)
$ uv run --all-packages python scripts/check_review_policy_consistency.py
exit=0 (marker, block and pointers agree)
$ uv run --all-packages python scripts/check_doc_drift.py --governance-only
exit=0 (57 warnings, none governance-blocking)
$ pre-commit run --files <the six paths>
exit=0 — every hook passed
```

## 4. Concerns

- The merged `read_message` deliberately keeps main's comment stripping
  **file-only**. A stdin PR body containing `#` headings is preserved; a local
  `git commit` file has its `#` lines dropped. This is main's intent and the
  tests pin both directions.
- **Superseded by CR-12.** The empty-non-TTY-stdin fall-through is the one
  behavioural line not present verbatim in either parent. Without it the
  worktree lookup is unreachable under pre-commit (`DEVNULL` stdin), i.e. the
  branch's whole fix would be dead code. It does not change any non-empty stdin
  result. (CR-12 reverses this: the fall-through reintroduced a stale-message
  path, so a non-TTY stdin is authoritative even when empty.)
- The merge commit itself is `chore(...)`: it changes no user-visible product
  surface (scripts/CI/docs/tests only), which is exactly what the new claim
  rule asks for.

## CR-12 correction

The union above was wrong in one line. §2.1's "empty-non-TTY-stdin
fall-through" and §4's second bullet are **superseded**, as is the §3 sample
`</dev/null → exit=0`.

- **Defect:** with an empty non-TTY stdin the merged `read_message` fell through
  to `git rev-parse --git-path COMMIT_EDITMSG` and could return a stale file —
  exactly the path #261 removed ("`just check-commit-msg` silently validated a
  stale message"). Neither parent had this behaviour; the union introduced it.
- **Ruling CR-12:** main's precedence wins. A non-TTY stdin is authoritative
  **even when empty**; it yields `""`, which `check_message` rejects as
  "Empty commit message". Nothing is lost: the git hook passes the file in
  `argv[1]`, `just check-commit-msg` pipes a non-empty message, CI pipes
  `printf '%s\n\n%s\n' "$PR_TITLE" "$PR_BODY"`. Git's path still serves the
  manual/TTY case, where `.git` may be a file (the worktree fix).
- **Final precedence:** `argv[1]` → non-TTY stdin (authoritative, empty
  included) → `git rev-parse --git-path COMMIT_EDITMSG` (TTY only) → `""`.
- **Review follow-up (I1, M1):** §3's code-path paragraph now states that shipped
  precedence instead of the pre-CR-12 fall-through, and §2.2 reconciles the size
  figures (188 + 269 = 457 after the split; 382 marked as the pre-split
  measurement).

RED capture — the new regression test ran against the merged script before the
fix; the stale valid message in the worktree was accepted:

```
$ just test-file tests/unit/scripts/test_check_commit_message.py::test_empty_non_tty_stdin_is_not_the_stale_commit_editmsg
>       assert result.returncode == 1, result.stdout + result.stderr
E       AssertionError:
E       assert 0 == 1
tests/unit/scripts/test_check_commit_message.py:333: AssertionError
============================== 1 failed in 2.43s ===============================
```

After the fix (and after the RULE-04 split it forced — §2.2's "no split was
needed" is superseded; the TTY/worktree proofs moved to
`test_check_commit_message_input_resolution.py`, 188 + 269 lines):

```
$ just test-file tests/unit/scripts/test_check_commit_message.py \
    tests/unit/scripts/test_check_commit_message_input_resolution.py
27 passed in 3.44s
```

Worktree proof is unchanged and now explicit: the two end-to-end worktree cases
attach a real pseudo-terminal (the only case that reaches git's path) and
`test_read_message_skips_stdin_when_tty` pins it at the unit level.

```
$ printf 'feat(scripts): stale leftover message\n\nUser-visible: …\n' > "$(git rev-parse --git-path COMMIT_EDITMSG)"
$ uv run --all-packages python scripts/check_commit_message.py < /dev/null
❌ Commit message rejected:

  Empty commit message

exit=1    # stale file present, still rejected — the #261 bug class is gone
```
