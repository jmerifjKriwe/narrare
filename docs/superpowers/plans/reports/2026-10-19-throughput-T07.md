# T07 — Wire the provider-catalog gate into commit, local and CI surfaces

**Task:** 7 (P1, final task) · **Depends on:** T6 · **Status:** implemented and verified, **not committed**

**Provenance:** this report was produced after **three interrupted dispatches**
(`subagent` aborted twice, then `shell` was denied mid-run). The three edits come
from the first interrupted run; every verification below was run afterwards by the
coordinator in the same worktree. The edits and the evidence therefore come from
different runs — stated here so a reader does not assume one continuous pass.

**Worktree:** `brave-egret` · **HEAD at verification:** `6ea06114` (T6d) · working
tree dirty with exactly the three T7 files.

---

## 1. The three insertions

### 1.1 `.pre-commit-config.yaml` — hook `provider-catalog-check`

Inserted between the `prompt-surface-contract` hook (ends at `stages: [pre-commit]`,
line 123 before the edit) and the `# Streaming Compliance — RULE-20 enforcement`
comment block.

```yaml
      # Provider catalog — ADR-099. Fails when catalog.yaml and either generated
      # artifact disagree, or when a handwritten surface (pricing, cache, mem0,
      # prefixes, settings, fallback catalog, test catalog, labels) drifts from it.
      # always_run: the gate must also fire when a handwritten surface changes
      # without the catalog changing, so a `files:` filter would miss the point.
      - id: provider-catalog-check
        name: Provider Catalog (ADR-099, generated + parity)
        entry: uv run --no-sync python scripts/generate_provider_catalog.py --check
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-commit]
```

Now at `.pre-commit-config.yaml:125-137` (id at 130). Indentation and every field
match the brief exactly.

### 1.2 `justfile` — `check-architecture`

One line, directly after the `check_prompt_surface_contract.py` line:

```make
    uv run --all-packages python scripts/generate_provider_catalog.py --check
```

Now `justfile:454`.

### 1.3 `.github/workflows/ci.yml` — `architecture` job

Directly after `Check prompt surface contract (ADR-037 + ADR-049 Phase D)`:

```yaml
      - name: Check provider catalog (ADR-099)
        run: uv run --no-sync python scripts/generate_provider_catalog.py --check
```

Now `ci.yml:552-553`. No gate-matrix row was added (this is a step of the
architecture job, exactly as the prompt-surface step is a step and not a row).

---

## 2. Registration evidence

`yaml.safe_load` over both files:

```
occurrences: 1
{'entry': 'uv run --no-sync python scripts/generate_provider_catalog.py --check',
 'language': 'system', 'pass_filenames': False, 'always_run': True,
 'stages': ['pre-commit']}
ci step: ['Check provider catalog (ADR-099)']
architecture jobs: 13
```

- The hook id appears **exactly once**.
- Every field equals the brief's value.
- The CI step is inside `jobs.architecture.steps` (the job list is still 13 jobs,
  so no job was accidentally nested or split).

---

## 3. Two-sided proof that the gate can fail

`pre-commit run provider-catalog-check` against the **repo** config is refused while
that config is unstaged, with:

```
[ERROR] Your pre-commit configuration is unstaged.
`git add .pre-commit-config.yaml` to fix this.
```

That is pre-commit's own guard, not a T7 defect — staging belongs to the commit
step. The hook was therefore exercised two ways, both recorded:

**(a) Through pre-commit, using a copy of the config** (`--config /tmp/opencode/pc-t7.yaml`, which stashes and restores unstaged work):

```
[WARNING] Unstaged files detected.
[INFO] Stashing unstaged files to /home/kiesow/.cache/pre-commit/patch1792437031-4081076.
Provider Catalog (ADR-099, generated + parity)...........................Passed
[INFO] Restored changes from /home/kiesow/.cache/pre-commit/patch1792437031-4081076.
exit=0
```

**(b) The entry itself, mutated then restored.** Mutation: `catalog.yaml`
`label_key: settings-ai.providers.groq` → `…groqx` (exactly one occurrence,
asserted before writing).

```
--- packages/core/narrare_core/llm/_providers/catalog_generated.py (committed)
+++ packages/core/narrare_core/llm/_providers/catalog_generated.py (fresh render)
@@ -39,7 +39,7 @@
-    AIProvider.GROQ: "settings-ai.providers.groq",
+    AIProvider.GROQ: "settings-ai.providers.groqx",
provider catalog check FAILED: packages/core/narrare_core/llm/_providers/catalog_generated.py is stale — regenerate with `uv run --all-packages python scripts/generate_provider_catalog.py`

--- packages/web/lib/providers.generated.ts (committed)
+++ packages/web/lib/providers.generated.ts (fresh render)
@@ -25,7 +25,7 @@
-  groq: "settings-ai.providers.groq",
+  groq: "settings-ai.providers.groqx",
provider catalog check FAILED: packages/web/lib/providers.generated.ts is stale — regenerate with `uv run --all-packages python scripts/generate_provider_catalog.py`
labels.locales: groq: settings-ai.providers.groqx missing in packages/i18n/messages/de/settings-ai.json
labels.locales: groq: settings-ai.providers.groqx missing in packages/i18n/messages/en/settings-ai.json
labels.locales: groq: settings-ai.providers.groqx missing in packages/i18n/messages/fr/settings-ai.json
mutated_exit=1
```

Both halves fired: byte drift named **both** artifacts, and the parity gate named
the provider and all three locales. Restore:

```
=== restore ===
(empty diff above = restored)          # git diff --stat on catalog.yaml printed nothing
=== clean run ===
provider catalog check: …catalog_generated.py is up to date
provider catalog check: …providers.generated.ts is up to date
clean_exit=0
```

A registered-but-unrunnable hook is the failure this section exists to catch; it is
excluded here — the hook ran through pre-commit and passed, and the entry failed
then passed on the same tree.

---

## 4. The local gate actually executes the line

`just check-architecture` → **exit 0**, and the new line is visibly part of the
run rather than merely present in the recipe:

```
38:uv run --all-packages python scripts/generate_provider_catalog.py --check
39:provider catalog check: packages/core/narrare_core/llm/_providers/catalog_generated.py is up to date
40:provider catalog check: packages/web/lib/providers.generated.ts is up to date
```

---

## 5. Test suite (unit + frontend only)

`just verify-quick` (which is `test-unit test-frontend`, not the full `just verify`)
→ **exit 0**:

```
 Test Files  461 passed (461)
      Tests  3932 passed (3932)
   Duration  179.38s
```

(The 4xx/5xx lines in that log are the frontend tests' intentional error-path
fixtures, not failures.)

---

## 6. What did **not** complete

`pre-commit run --all-files` was attempted twice and **did not finish** — it stalls
over this repository's 40+ hooks and ~1,500 Python files, and the second attempt
was aborted by the harness (`Tool execution interrupted: shell`). No verdict from
that command is claimed.

Consequences, stated plainly:

- "All hooks pass repo-wide" is **not** established by this task.
- What *is* established: the new hook passes through pre-commit; the functional
  gates that completed (`just check-architecture`, `just verify-quick`) are green;
  and the commit that carries this change runs the full hook set on the staged
  files as part of `git commit`.
- If the repo-wide sweep is required later, run it in a session with a longer
  budget and expect minutes, not seconds.

---

## 7. Deviations and notes

1. **Hook proof mechanism.** The brief's Step 2 assumed
   `pre-commit run provider-catalog-check` would run directly. It cannot while
   `.pre-commit-config.yaml` is unstaged (pre-commit's own guard, quoted above).
   Both halves were proven instead: through pre-commit with a config copy, and the
   entry directly with a mutation. No `--no-verify` and no staging was used.
2. **`--all-files` incomplete** (section 6). Not silently skipped: it was run,
   stalled, and is recorded as unverified rather than as a pass.
3. **Report provenance.** Three dispatches were interrupted; the edits came from the
   first, the verification from a later run. Recorded at the top of this report.
4. **No gate-matrix row** — intentional, per the brief (step of the architecture
   job, like the prompt-surface step).

---

## 8. P1 close-out

With T7, ADR-099's locally producible completeness items are done:

- one authored provider fact (`catalog.yaml`), two generated, byte-compared artifacts;
- twelve parity invariants over the surfaces that stay handwritten;
- the gate wired into commit, local architecture check and CI.

ADR-099's status remains 🔄 until the wave's PR run of the architecture job is
green — that is the remaining step, and it needs a push.

## Commit

Committed as `d8a844c3` — `ci: gate the provider catalog at commit, local and CI surfaces`.

Status correction: the "not committed" line above describes the report at the time
it was written; this section records the commit that landed it.
