# Throughput T12c — the scaffolder's post-condition

- **Date:** 2026-10-20
- **Branch:** `brave-egret` (base `069cbbfd`)
- **Status:** `DONE_WITH_CONCERNS` — the post-condition is implemented and every
  test/gate is green, but the mandated live `--with-intent` probe exits 2: T12b's
  generated prompt body is not `check_prompt_structure`-compliant. The fix belongs
  in `scripts/scaffold_intent.py`, which this slice is forbidden to author. The
  post-condition names that surface and restores the tree — the behaviour T12c
  exists to enforce.
- **Files authored:** `scripts/scaffold_feature.py` (403 lines),
  `tests/unit/scripts/test_scaffold_feature.py` (260 lines), this report.

## 1. Implemented

`scaffold_feature()` now runs `_post_condition(root)` after `_write_all` and
before returning. Exit codes are unchanged: 0 written and gate-green, 1 id/surface
already exists, 2 post-condition (or input/write) failure.

1. **Parity gate, any root.** `find_disagreements(collect_facts(root))` from
   `scripts.check_intent_parity` runs for every scaffold. Disagreements, or a
   `RuntimeError` from an unreadable surface, exit 2 with each message printed.
   Because the oracle takes `root`, it works on a mirror tree.
2. **Four scoped checks, repository root only.** When `root.resolve() == _ROOT`
   (the running script's repo), each is run with `sys.executable`, the script
   resolved under `root`, `cwd=root`, output captured:
   `check_prompt_structure.py`, `check_prompt_surface_contract.py`,
   `check_locale_sync.py`, `check_feature_path_accuracy.py` (the real filename).
   A non-zero exit prints the surface name, its exit code and the last eight
   output lines, then exits 2.
3. **Restore on failure.** `_write_all` now returns `(written, snapshots)`;
   `_restore` reverts edited files and unlinks files this run created. A gate
   failure restores every touched file, prints the count and re-raises exit 2.

**Decision on scoped checks without `--with-intent`:** all four run anyway. The
probe output shows the relevant one is `check_prompt_structure`, not
feature-path accuracy: a fresh feature document is `status: planned` with no
`service`/`contract`/`router`/`prompt` fields, so `check_feature_path_accuracy`
is presently vacuous on it. It still runs because that frontmatter is exactly
what a future scaffold field could break.

## 2. Tests

`13 passed` in the file, `1479 passed` under `tests/unit/scripts/`.

- **Green path:** `test_with_intent_writes_all_eight_surfaces_and_parity_gate_is_green`
  scaffolds with intent into the mirror, returns normally (no `SystemExit`) and
  asserts `find_disagreements(collect_facts(root)) == []` — the in-call gate and
  the oracle agree.
- **Failing path:** `test_gate_failure_restores_the_mirror_to_its_pre_run_state`
  hashes every file, deletes the routed sibling's EN prompt template, scaffolds,
  then asserts `SystemExit` code 2, stderr naming the parity rejection and the
  missing template, and byte-identical hashes afterwards. RED on `069cbbfd`
  (`DID NOT RAISE SystemExit`); GREEN now.
  - Deviation from the brief's "missing manifest": a deleted manifest makes
    `plan_intent` exit 2 *before* writing, so it cannot exercise restore. A
    missing prompt template is a parity surface the scaffolder reads but never
    rewrites, so the gate is the first observer.
- **Invocation count:** `test_repository_root_runs_each_scoped_check_exactly_once`
  patches `_ROOT` to the mirror and `_run_check`; asserts the four script names,
  once each, in order, all with `root` as cwd.
- **Surface naming:** `test_scoped_check_failure_exits_2_naming_the_surface_and_restores`
  makes `check_locale_sync.py` return 1; asserts exit 2, the script name and its
  output tail, and restored hashes.
- The legacy bare-`tmp_path` tests now scaffold into `_mirror(tmp_path)`: the
  post-condition requires a repo-like tree, and those tests were asserting the
  artifacts, not an empty-root special case.

## 3. Evidence (raw)

```text
just test-file tests/unit/scripts/test_scaffold_feature.py ... 13 passed in 3.68s
just test-file tests/unit/scripts/ ........................... 1479 passed in 28.44s
just lint-check .............................................. LINT_EXIT=0
  All checks passed! / 3384 files already formatted
just check-architecture ...................................... ARCH_EXIT=0
  RESULT: No new frontmatter schema violations
  RESULT: Frontend file-size debt did not grow
just typecheck-file scripts/scaffold_feature.py .............. 0 errors, 0 warnings
```

## 4. Throwaway-worktree probes

`git worktree add --detach /tmp/opencode/scaffold-pc HEAD`, the new
`scripts/scaffold_feature.py` copied in, venv built by `uv`; worktree removed
afterwards (`git worktree remove --force`).

```text
just new-feature SCAFFOLD-006 api
  created tests/unit/api/test_scaffold_006.py
  created docs/superpowers/plans/reports/2026-10-20-scaffold_006.md
  created docs/features/SCAFFOLD-006.md
  PROBE_A_EXIT=0                      # all four scoped checks green

just new-feature SCAFFOLD-005 core --with-intent parity_probe3 --category kb --mode parity_mode3
  scaffold_feature: scripts/check_prompt_structure.py failed (exit 1) after scaffolding:
  NEW: kb/en/parity_mode3 | Missing required variable {{user_preferences}} for category 'kb'
  NEW: kb/fr/parity_mode3 | Missing 'Do NOT' section
  NEW: kb/fr/parity_mode3 | Missing 'Output Format' section
  NEW: kb/fr/parity_mode3 | Missing recommended variable {{world_context}} for category 'kb' (SHOULD)
  NEW: kb/fr/parity_mode3 | Missing recommended variable {{writing_language}} for category 'kb' (SHOULD)
  NEW: kb/fr/parity_mode3 | Missing required variable {{avoidance_patterns}} for category 'kb'
  NEW: kb/fr/parity_mode3 | Missing required variable {{user_preferences}} for category 'kb'
  RESULT: New prompt WARN(s) exceed baseline
  scaffold_feature: restored 15 file(s) after the post-condition failed
  PROBE_B_EXIT=2

# parity failure proof: KB_IMPROVE's manifest block removed, then restored
python scripts/check_intent_parity.py  → PARITY_EXIT=1
  30 intents, 24 routed, 1 disagreements
  KB_IMPROVE: missing block in prompt-surface-manifest.yaml for a routed intent
(after restore)                          → 0 disagreements, exit 0
```

Restore-on-failure is proven by the unit hash assertion and by the live
`restored 15 file(s)` followed by the manifest probe returning 0 disagreements.

## 5. Concerns

- **T12b defect, now loud:** `_prompt_text` emits only frontmatter and
  `## System Prompt`; `check_prompt_structure` requires `## Output Format` and
  `## Do NOT` and category variables (`{{user_preferences}}`,
  `{{avoidance_patterns}}`, …). Every generated intent fails the ratchet, so no
  `--with-intent` scaffold can be green until `scaffold_intent._prompt_text` is
  fixed. That file is outside this slice's authored set; the next slice should
  clone the sibling prompt body (or its section skeleton) rather than invent a
  sentence.
- The failing check mixes FAIL and WARN-ratchet: three of the reported lines are
  WARN, but a new prompt's warnings exceed the baseline and block. Exit 2 is
  therefore correct even where the message does not say FAIL.
- The four scoped checks are deliberately skipped for roots that are not this
  repository (mirrors); the parity gate still covers them.
- `subprocess.run` carries the project-standard `# noqa: S603  # nosec B603`
  with a fixed-argv justification, as every other script subprocess does.

## T12b4 — prompt template fix

- **Date:** 2026-10-20
- **Status:** `DONE` — `--with-intent` now scaffolds a prompt family that is green
  in the real tree, so the T12c post-condition can return 0.
- **Files:** `scripts/scaffold_intent.py`, `tests/unit/scripts/test_scaffold_feature.py`
  (one scenario retargeted, clone assertions added), this report.

### 1. Root cause and fix

`_prompt_text` invented a body from one sentence: frontmatter plus a
`## System Prompt` line. `check_prompt_structure.py` requires a structured
document, and the WARN ratchet turns any new file's warnings into a failure.
Re-deriving that structure in the scaffolder is a second source that drifts
whenever the checker changes.

The prompt structure is already encoded in every compliant bundled prompt, so
the scaffolder now clones the routed sibling's own `system.md`
(`{category}/en/{sibling mode}/system.md`, the sibling whose route shape it
already copies):

- **Copied:** frontmatter keys in their order, every section heading in its
  order (`##`/`###`/`####`), and every variable placeholder in the section that
  used it — including its XML wrapper (`<user_provided_text>{{entry_content}}</user_provided_text>`),
  which the governance check requires.
- **Derived:** frontmatter values (`prompt_type` = prompt category,
  `prompt_language` = target locale, `prompt_version` = `"0.1.0"`); the scope
  sentence per locale; four intent-agnostic `Do NOT` items (the quality gate
  requires at least four and the sibling's own prohibitions describe the
  sibling's job); and, when the sibling's output section holds a JSON example, a
  minimal `{intent, result, notes}` example of the new intent (the structured
  output gate requires one) — never the sibling's output contract.
- **Refused loudly:** a frontmatter key the scaffolder cannot derive exits 2 and
  names the key, instead of copying the sibling's value or silently dropping it.
- A section with neither prose nor placeholders keeps its heading and stays
  empty for the author.

The same body is written for `en`, `de` and `fr` (only the frontmatter language
and the localized scope sentence differ), so the new three-locale group stays
locale-synced.

### 2. Test change

The T12c restore scenario deleted `kb/en/improve/system.md` to make the parity
gate reject the scaffold *after* writing. That file is now the cloned template,
so deleting it fails during planning (also exit 2, before any write). The test
deletes `kb/en/extract/system.md` instead: KB_EXTRACT is a routed parity surface
the planner never reads, so planning succeeds and the gate remains the first
observer. The green-path test now also asserts the cloned headings, variables
and XML wrapper survive.

### 3. Evidence (raw)

```text
just test-file tests/unit/scripts/test_scaffold_feature.py ... 13 passed in 3.64s
just lint-check ............................................. All checks passed! / 3384 files already formatted (exit 0)
just check-architecture ..................................... ARCH_EXIT=0
just typecheck-file scripts/scaffold_intent.py ............... 0 errors, 0 warnings (exit 0)
```

Throwaway-worktree probe (`git worktree add --detach /tmp/opencode/scaffold-b4 HEAD`,
the three changed files copied in, `uv` venv built, removed with `--force`):

```text
just new-feature SCAFFOLD-007 core --with-intent parity_probe4 --category kb --mode parity_mode4
  created .../kb/{en,de,fr}/parity_mode4/system.md (+ the seven declaration surfaces)
  SCAFFOLD_EXIT=0            # includes the T12c post-condition's four scoped checks
python scripts/check_prompt_structure.py        STRUCTURE_EXIT=0
  Prompt warning ratchet: 8 current, 8 baseline, 0 new, 0 resolved
  RESULT: 8 WARN(s) (non-blocking)          # pre-existing analysis debt, all other files clean
python scripts/check_prompt_surface_contract.py CONTRACT_EXIT=0
  ✅ Prompt Surface Contract OK
python scripts/check_locale_sync.py             LOCALE_EXIT=0
  Groups checked: 51 / Synced: 51 / Drifted: 0
python scripts/check_intent_parity.py           PARITY_EXIT=0
  31 intents, 25 routed, 0 disagreements
```

### 4. Concern

The generated skeleton is intentionally thin: only `## System Prompt` carries
prose, `### Analysis Instructions` and `### Quality Rules` are headings without
bodies, and the JSON example is a placeholder. The file is marked
scaffolder-generated; the author fills the prose. This is the smallest invention
compatible with the structure gate, and it cannot drift from the checker.
