# Parallel-Work Optimizations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce merge-conflict cost for 2-3 parallel feature branches by (1) adding a merge driver for i18n/generated JSON, (2) splitting the shared `kernel/contracts/models.py` into per-domain modules, and (3) removing the last capability-specific edits from the shell.

**Architecture:** Three independent work packages. Phase 1 is tooling and requires an explicit approval under `CONSTRAINTS.md` §8 (new script + `.gitattributes` + setup step). Phase 2 is a mechanical refactor that keeps `models.py` as a thin aggregator for backward compatibility. Phase 3 removes two hardcoded shell mappings by deriving them from existing conventions/generated data.

**Tech Stack:** Python 3.14, FastAPI/SQLAlchemy, Vite/React/TanStack Router, Git merge drivers, existing `just generate`.

**Spec:** This plan implements the assessment in the 2026-11-07 conversation; no separate spec file exists. The standing rules in `docs/_shared/CONSTRAINTS.md` apply, including the §8 governance budget.

## Global Constraints

- No new standing rule, checker, hook, or required field without `NEEDS-APPROVAL` (CONSTRAINTS §8).
- Capability folders never import another capability; imports point `api → capabilities → kernel`.
- Generated files are regenerated with `just generate`, never hand-edited.
- English in code/tests/docs; user-visible text in en/de/fr.
- Every user-owned row carries `user_id`; data access through the scoped repository base.

## Review Focus

- The merge driver must fail loudly on conflicting keys instead of silently picking a side.
- The contracts split must not change SQLAlchemy metadata registration or any public import path.
- Shell changes must keep `IconRail` rendering identical for the four existing capabilities.
- Generated `workspaceRouteId` must match the route id TanStack Router assigns, or the workspace breakpoint silently breaks.
- A new capability added after Phase 3 must require no edit to `IconRail.tsx` or `TopBar.tsx`.

---

### Task 1: JSON merge driver script (approval-gated)

**Files:**
- Create: `scripts/merge_json.py`
- Create: `scripts/tests/test_merge_json.py` (or `app/kernel/tests/test_merge_json.py` if scripts tests are preferred)
- Modify: `CONTRIBUTING.md` (setup instructions)

**Interfaces:**
- Produces: `merge_json.py --base <O> --ours <A> --theirs <B>` exit codes: 0 merged, 1 conflict/manual required.

- [ ] **Step 1: Write failing tests for non-overlapping and conflicting merges**

```python
def test_merge_non_overlapping_keys(tmp_path):
    ...
    assert result == {"a": 1, "b": 2}

def test_merge_conflicting_key_exits_1(tmp_path):
    ...
    assert returncode == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest scripts/tests/test_merge_json.py -v`
Expected: FAIL (script missing)

- [ ] **Step 3: Implement `scripts/merge_json.py`**

Behavior:
- Parse all three JSON files.
- Deep-merge dicts; arrays are replaced, not concatenated.
- If a key exists in both ours and theirs with differing values, exit 1 and print the key path.
- On success, write merged JSON to `--ours` path with sorted keys and trailing newline.
- Invalid JSON exits 1.

- [ ] **Step 4: Run tests**

Run: `uv run pytest scripts/tests/test_merge_json.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/merge_json.py scripts/tests/test_merge_json.py CONTRIBUTING.md
git commit -m "feat(tooling): add merge driver for JSON catalogs"
```

---

### Task 2: `.gitattributes` and generated-file driver (approval-gated)

**Files:**
- Create: `.gitattributes`
- Modify: `scripts/merge_json.py` (add generated-file mode)
- Modify: `CONTRIBUTING.md`

**Interfaces:**
- Consumes: Task 1 script.
- Produces: merge attributes for `i18n/*.json`, `web/lib/generated/*`, `web/lib/api/openapi.json`, `web/lib/api/schema.d.ts`.

- [ ] **Step 1: Add generated-file handling to the script**

When invoked on a path under `web/lib/generated/` or `web/lib/api/`, ignore manual edits and regenerate by running `just generate` (or the relevant generator), writing the result to `--ours`. If generation fails, exit 1.

- [ ] **Step 2: Create `.gitattributes`**

```gitattributes
i18n/*.json merge=narrare-json
web/lib/generated/* merge=narrare-generated
web/lib/api/openapi.json merge=narrare-generated
web/lib/api/schema.d.ts merge=narrare-generated
```

- [ ] **Step 3: Document local setup**

Add to `CONTRIBUTING.md`:

```bash
git config merge.narrare-json.name "Narrare JSON merge"
git config merge.narrare-json.driver "python scripts/merge_json.py --base %O --ours %A --theirs %B"
git config merge.narrare-generated.name "Narrare generated merge"
git config merge.narrare-generated.driver "python scripts/merge_json.py --generated --base %O --ours %A --theirs %B"
```

- [ ] **Step 4: Verify with a manual conflict simulation**

Run: create two branches editing different i18n keys, merge, confirm auto-resolution; then conflicting key, confirm manual fallback.

- [ ] **Step 5: Commit**

```bash
git add .gitattributes scripts/merge_json.py CONTRIBUTING.md
git commit -m "feat(tooling): wire merge drivers for JSON and generated files"
```

---

### Task 3: Split `kernel/contracts/models.py`

**Files:**
- Create: `app/kernel/contracts/user.py`
- Create: `app/kernel/contracts/novel.py`
- Create: `app/kernel/contracts/knowledge.py`
- Modify: `app/kernel/contracts/models.py` (becomes aggregator/re-export)
- Test: existing migration and contract tests

**Interfaces:**
- Consumes: current `models.py` classes.
- Produces: same names from `app.kernel.contracts.models` (unchanged import path).

- [ ] **Step 1: Move `User` to `user.py`**

Keep imports minimal; ensure `Base`/`UserOwned` imports remain.

- [ ] **Step 2: Move `Novel`, `Chapter` to `novel.py`**

- [ ] **Step 3: Move `ENTITY_TYPES`, `Entity`, `EntityRelation`, `EntitySuggestion`, `ConsistencyFinding`, `Document`, `Chunk` to `knowledge.py`**

- [ ] **Step 4: Rewrite `models.py` as aggregator**

```python
from app.kernel.contracts.knowledge import (
    ENTITY_TYPES,
    Chunk,
    ConsistencyFinding,
    Document,
    Entity,
    EntityRelation,
    EntitySuggestion,
)
from app.kernel.contracts.novel import Chapter, Novel
from app.kernel.contracts.user import User

__all__ = [
    "ENTITY_TYPES",
    "Chapter",
    "Chunk",
    "ConsistencyFinding",
    "Document",
    "Entity",
    "EntityRelation",
    "EntitySuggestion",
    "Novel",
    "User",
]
```

The aggregator imports register all tables on `Base` for `register_models()`.

- [ ] **Step 5: Run typecheck and tests**

Run: `just typecheck && just test-file app/kernel/db/tests/test_migrations.py`
Expected: PASS

- [ ] **Step 6: Run full affected tests**

Run: `just test`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/kernel/contracts
git commit -m "refactor(kernel): split contracts models into per-domain modules"
```

---

### Task 4: Shell — derive area icon class from capability id

**Files:**
- Modify: `web/components/IconRail.tsx`
- Modify: `web/globals.css` (ensure fallback handling if needed)
- Test: `web/components/IconRail.test.ts`

**Interfaces:**
- Consumes: generated `nav` entries (`id`).
- Produces: `text-area-${entry.id}` class without `AREA_ICON` map.

- [ ] **Step 1: Update tests to cover a capability id not in a hardcoded map**

Add a test rendering with a nav entry whose id is not one of the four legacy names and assert the class `text-area-<id>` is applied.

- [ ] **Step 2: Run test to verify failure**

Run: `pnpm --dir web test IconRail`
Expected: FAIL

- [ ] **Step 3: Remove `AREA_ICON` and derive class**

Replace `AREA_ICON[area]` usage with `` `text-area-${entry.id}` ``. Keep the four existing CSS variables; document that a new capability must add its `--area-<id>` token and `@theme` mapping in `globals.css`.

- [ ] **Step 4: Run tests**

Run: `pnpm --dir web test IconRail`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/components/IconRail.tsx web/components/IconRail.test.ts
git commit -m "refactor(shell): derive area icon class from capability id"
```

---

### Task 5: Shell — generate `workspaceRouteId`

**Files:**
- Modify: `scripts/generate_capabilities.py`
- Modify: `web/lib/generated/routes.ts` (regenerated)
- Modify: `web/components/TopBar.tsx`
- Modify: `web/components/IconRail.tsx`
- Test: `web/routes/__root.test.tsx` (or a new shell test)

**Interfaces:**
- Consumes: capability that exports `workspaceRoute`.
- Produces: generated constant `workspaceRouteId: string` (the TanStack route id of the workspace route).

- [ ] **Step 1: Add generator support**

In `generate_capabilities.py`, when a capability exports `workspaceRoute`, emit its route id. Because the generator cannot execute route creation, instead conventionally set `workspaceRouteId = "/novels/$id"`? No — derive from the capability's declared workspace path. Better: have the capability's `routes.tsx` export a string constant `workspaceRouteId` alongside `workspaceRoute`, and the generator copies it into `web/lib/generated/routes.ts`.

Adjust generator to collect `workspaceRouteId` exports.

- [ ] **Step 2: Export `workspaceRouteId` from writing capability**

In `app/capabilities/writing/web/routes.tsx`, add:

```ts
export const workspaceRouteId = "/novels/$id";
```

- [ ] **Step 3: Regenerate**

Run: `just generate`
Expected: `web/lib/generated/routes.ts` exports `workspaceRouteId`.

- [ ] **Step 4: Use generated constant in shell**

Replace hardcoded `"/novels/$id"` in `TopBar.tsx` and `IconRail.tsx` with imported `workspaceRouteId`.

- [ ] **Step 5: Run tests**

Run: `pnpm --dir web test && just typecheck`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_capabilities.py app/capabilities/writing/web/routes.tsx web/lib/generated/routes.ts web/components/TopBar.tsx web/components/IconRail.tsx
git commit -m "refactor(shell): use generated workspace route id"
```

---

### Task 6: Final verification

- [ ] **Step 1: Run fast gate**

Run: `just check`
Expected: PASS

- [ ] **Step 2: Run full gate**

Run: `just verify`
Expected: PASS

- [ ] **Step 3: Run E2E for touched capabilities**

Run: `just test-e2e writing knowledge settings setup chat prompts`
Expected: PASS

- [ ] **Step 4: Confirm no cross-capability imports introduced**

Run: `python3 - <<'PY'\n...\nPY`
Expected: 0 violations.

---

**Plan complete and saved to `docs/superpowers/plans/2026-11-07-parallel-work-optimizations.md`. Please review the plan. Which execution approach would you prefer?**

- **Subagent-driven** - A fresh subagent implements each task and a fresh reviewer checks it before the next one starts, then a whole-branch review at the end. Most thorough; costs a fresh context per task and per review.
- **Native** - I implement every task myself in this session, the way this harness runs work, then one fresh reviewer on the most capable model checks the whole branch. Cheapest and fastest; no independent review until the end.

For this plan I recommend **subagent-driven**, because the phases are independent and a shipped mistake in the merge driver or contracts split would affect every future change. Does the plan capture what you want, and which approach should we use?
## Deviations from the plan as written

- **Merge-driver tests live in `app/kernel/tests/test_merge_json.py`.** The plan allowed this alternative. `pyproject.toml` sets `testpaths = ["app"]`, so a test under `scripts/tests/` would never run in a gate.
- **`--generated` runs before any JSON parsing and writes `%A`.** The plan's first draft parsed all three inputs first and never wrote the regenerated file back to `--ours`. The driver now takes `--path %P`, regenerates, reads the regenerated working-tree file, and writes those bytes to `%A`; `.gitattributes`/`CONTRIBUTING.md` carry the `%P` argument.
- **JSON merge preserves existing key order.** Sorted keys rewrote every catalog line on every merge. The driver keeps the branch's order and appends keys only the other side added; `ensure_ascii=False` keeps de/fr text as text.
- **Delete-vs-modify is a conflict.** A key deleted on one side and changed on the other now exits 1 instead of silently resurrecting the edit.
- **The area hue is an inline CSS variable, not a dynamic Tailwind class.** Tailwind's scanner cannot see `text-area-${id}`, so the four existing hues collapsed in the browser. `IconRail` exports `areaStyle(area)` returning `var(--area-<id>, var(--foreground))`; a new capability adds its `--area-<id>` token in `globals.css`, and the fallback is the foreground ink.
- **The generator fails loudly when `workspaceRouteId` is missing.** Falling back to the path literal is only accidentally equal to the TanStack route id; a nested workspace route would silently break the breakpoint.
- **The workspace id moved to `web/lib/generated/workspace.ts`.** Keeping it in `routes.ts` made the shell chrome import the route table, which closed a cycle back through the capability routes. The leaf module removes the cycle; `app/capabilities/writing/web/routes.test.ts` asserts the generated id names a route the shell router mounts.
- **Generated regeneration is in-process.** The driver calls `scripts.export_openapi` / `scripts.generate_capabilities` directly instead of spawning `just`; `schema.d.ts` is refused because its Node step has no in-process equivalent and stays a manual `just generate`.
