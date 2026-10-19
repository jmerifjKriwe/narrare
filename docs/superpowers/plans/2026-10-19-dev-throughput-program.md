# Developer Throughput Program (P1–P5) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the provider set one authored fact with generated artifacts (P1),
give the intent declaration surfaces one parity gate (P2), move the two
whole-project hooks off the commit stage and add a scoped slice command (P3), write
the review/report thresholds down and pin them (P4), and add a feature scaffolder
that emits only gate-green artifacts (P5).

**Architecture:** Derivation over duplication, comparison over reform. P1 introduces
`catalog.yaml` plus a generator producing one Python enum module (class syntax,
measured pyright-clean) and one TypeScript module, and a `--check` mode that
additionally asserts invariants over the surfaces that stay handwritten. P2 adds a
comparison gate over the eight existing intent surfaces without moving authority out
of the manifest, the registry or the adoption contract. P3 changes two `stages:`
values and adds one additive recipe. P4 writes the thresholds once and pins the
numbers. P5 generates only declaration surfaces, never service stubs. Every task
leaves the tree green.

**Tech Stack:** Python 3.14 · `ast` + `yaml` (no import-time dependency for the
parity gate) · ruff · pyright (strict) · pytest · Vitest · TypeScript · biome ·
pre-commit · just · GitHub Actions.

**Binding docs:** Spec
`docs/superpowers/specs/2026-10-19-dev-throughput-program-design.md` · ADR-099
(provider catalog SSOT). Where this plan and the spec disagree, the spec wins;
report the deviation. Where the spec and ADR-099 disagree about P1, ADR-099 wins.

**Plan house rule — `just` recipe / document coupling.** The `doc-drift` hook
(`scripts/check_doc_drift.py --governance-only`) validates backtick-quoted
`just <recipe>` references in `docs/**/*.md` against the real recipe set
(`docs/superpowers/plans/` is excluded). Therefore: **a new `just` recipe lands in
the same task as every living document that names it** (T8 pairs the `verify-slice`
recipe with its tiering document; T13 pairs the `new-feature` recipe — landed in
T12 — with its document). Naming a recipe in this plan file is safe; naming it in
`docs/development/**` before it exists is a red `doc-drift` hook.

## Global Constraints

- **Package sizing:** ≤3 **authored** files per task. Excluded from the count, per
  the existing convention plus this program's own artefact classes: test files
  (already excluded), machine-generated artifacts (`catalog_generated.py`,
  `providers.generated.ts` — nobody authors them), and single-row documentation
  edits (`docs/architecture/decisions/INDEX.md`). Sub-slice (a/b) rather than exceed.
- **Report requirement (the P4 threshold, T10; applied to this plan from the start):**
  a per-task report file is required when the task changes ≥3 authored files, **or**
  adds ≥80 new production LOC, **or** crosses a layer boundary, **or** touches a
  governed surface (ADR, `docs/_shared/CONSTRAINTS.md`, `scripts/architecture/*`,
  `.github/workflows/ci.yml`, `justfile`, `.pre-commit-config.yaml`). Each task below
  states its own determination. Required reports go to
  `docs/superpowers/plans/reports/2026-10-19-throughput-T<NN>.md`.
- **Mandatory per-task review (never batched):** tasks that add/rename a Protocol or
  contract, change a manifest or registry, change the public shape of an API
  response, or edit a governed surface. T7, T8, T15 are in this class; T4 changes a
  public API shape's consumer and gets its own review.
- **Project language: English** everywhere (code, comments, docstrings, tests, docs).
  `packages/i18n/` message files are the only exception.
- **No runtime catalog parsing.** `catalog.yaml` is read by the generator only. The
  parity gate parses source files with `ast` and never imports the API package, so
  the commit-time hook stays independent of the venv's optional extras.
- **Generated artifacts must be format-clean by construction:** the Python renderer
  emits ruff-format-clean source with no type suppressions (RULE-23 baseline must not
  grow); the TypeScript renderer emits biome-clean source that passes
  `tsc --noEmit`.
- **RULE-01b / RULE-05 / RULE-07:** `catalog.yaml` and `catalog_generated.py` live in
  `packages/core/narrare_core/llm/_providers/`. `apps/api` and `packages/web`
  consume. No provider string literal may be introduced outside the catalog, its
  generated artifacts, or a surface named in ADR-099 point 7.
- **RULE-16 / RULE-17:** provider display labels exist only as i18n keys
  (`settings-ai.providers.<id>`) resolved in `en`/`de`/`fr`; the TS provider type is
  derived, never restated.
- **Gates per task:** Python — `just test-file <paths>`, `just typecheck`,
  `just check-architecture`. Frontend — `just test-frontend`,
  `just typecheck-frontend`, `just lint-frontend`. Config/hook tasks — additionally
  `pre-commit run --all-files` (or the specific hook id) plus `just verify-quick`.
- **Do NOT commit with `--no-verify`.** Commits are routed through the Platform
  specialist by the coordinator.

**Dependency graph (execution order as required by the spec: P1 → P3 → P4 → P5 → P2):**

```
T1 ─┬─ T2 ── T7
    ├─ T3 ── T4
    ├─ T5
    └─ T6 ── T7
T8 ── T9            (independent of P1; may run in parallel)
T10 ── T11         (independent of P1; may run in parallel)
T12 ─ T13          (T12 consumes the T1 catalog)
T14 ─ T15          (T15 needs T14 and T12)
```

Every task is independently landable; T2, T3, T4, T5 each need only T1.

---

### Task 1: Provider catalog SSOT, generator core, generated Python enum

**Program:** P1 · **Depends on:** — · **Report:** required (2 authored production files + generator ≥80 LOC)
**Mandatory review:** no

**Files:**
- Create: `packages/core/narrare_core/llm/_providers/catalog.yaml`
- Create: `scripts/generate_provider_catalog.py`
- Create (generated): `packages/core/narrare_core/llm/_providers/catalog_generated.py`
- Test: `tests/unit/scripts/test_generate_provider_catalog.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces (later tasks rely on these exact names):
  - `ProviderSpec` — frozen dataclass in `scripts/generate_provider_catalog.py`
    with fields `id: str`, `label_key: str`, `api_key_env: str | None`,
    `settings_field: str | None`, `pydantic_ai_extra: str`, `listing_strategy: str`,
    `pricing_default: dict[str, float]`, `cache_policy: str`,
    `fallback_models: tuple[str, ...]`, `settings_editable: bool`,
    `requires_endpoint_selector: bool`
  - module-level paths `CATALOG_PATH`, `PY_OUTPUT`, `TS_OUTPUT`, `REPO_ROOT`
  - `load_catalog(path: Path) -> list[ProviderSpec]`
  - `render_python(specs: list[ProviderSpec]) -> str`
  - `main(argv: list[str] | None = None) -> int` — default mode writes
    `PY_OUTPUT`; `--check` renders in memory and compares bytes
  - `catalog_generated.AIProvider` — `StrEnum` (class syntax) with members
    `ANTHROPIC`, `OPENAI`, `GOOGLE`, `GROQ`, `OLLAMA`, `OPENROUTER`, `ZAI`
  - `catalog_generated.PROVIDER_IDS: tuple[str, ...]` — canonical order literals
  - `catalog_generated.PROVIDER_LABEL_KEYS: dict[AIProvider, str]`

- [ ] **Step 1: Write the catalog SSOT** — `catalog.yaml`, one entry per provider,
      canonical display order (`anthropic`, `openai`, `google`, `groq`, `ollama`,
      `openrouter`, `zai`), values copied from the verified current sources:

```yaml
# Provider catalog — the single source of truth for which providers Narrare
# supports. See ADR-099. `label_key` is an i18n key, never a display string.
providers:
  - id: anthropic
    label_key: settings-ai.providers.anthropic
    api_key_env: ANTHROPIC_API_KEY
    settings_field: anthropic_api_key
    pydantic_ai_extra: anthropic
    listing_strategy: anthropic
    pricing_default: { input: 8.0, output: 24.0 }
    cache_policy: anthropic_cache_control
    fallback_models: [claude-opus-4-5-20251101, claude-sonnet-4-5-20251020, claude-haiku-3-5-20241022]
    settings_editable: true
    requires_endpoint_selector: false
  - id: openai
    label_key: settings-ai.providers.openai
    api_key_env: OPENAI_API_KEY
    settings_field: openai_api_key
    pydantic_ai_extra: openai
    listing_strategy: openai
    pricing_default: { input: 10.0, output: 30.0 }
    cache_policy: automatic
    fallback_models: [gpt-4o, gpt-4o-mini, o3-mini]
    settings_editable: true
    requires_endpoint_selector: false
  - id: google
    label_key: settings-ai.providers.google
    api_key_env: GOOGLE_API_KEY
    settings_field: google_api_key  # gemini_api_key is CoreSettings' accepted alias
    pydantic_ai_extra: google
    listing_strategy: google
    pricing_default: { input: 2.0, output: 10.0 }
    cache_policy: automatic
    fallback_models: [gemini-2.0-flash, gemini-1.5-pro]
    settings_editable: true
    requires_endpoint_selector: false
  - id: groq
    label_key: settings-ai.providers.groq
    api_key_env: GROQ_API_KEY
    settings_field: groq_api_key
    pydantic_ai_extra: groq
    listing_strategy: groq
    pricing_default: { input: 0.5, output: 1.0 }
    cache_policy: automatic
    fallback_models: [llama-3.3-70b-versatile, mixtral-8x7b-32768]
    settings_editable: true
    requires_endpoint_selector: false
  - id: ollama
    label_key: settings-ai.providers.ollama
    api_key_env: null
    settings_field: null
    pydantic_ai_extra: ollama
    listing_strategy: ollama
    pricing_default: { input: 0.0, output: 0.0 }
    cache_policy: none
    fallback_models: [llama3.2, mistral, qwen2.5]
    settings_editable: true
    requires_endpoint_selector: true
  - id: openrouter
    label_key: settings-ai.providers.openrouter
    api_key_env: OPENROUTER_API_KEY
    settings_field: openrouter_api_key
    pydantic_ai_extra: openrouter
    listing_strategy: openrouter
    pricing_default: { input: 5.0, output: 15.0 }
    cache_policy: automatic
    fallback_models: [anthropic/claude-sonnet-4-5, openai/gpt-4o, google/gemini-2.0-flash]
    settings_editable: true
    requires_endpoint_selector: false
  - id: zai
    label_key: settings-ai.providers.zai
    api_key_env: ZAI_API_KEY
    settings_field: zai_api_key
    pydantic_ai_extra: zai
    listing_strategy: zai
    pricing_default: { input: 1.0, output: 2.0 }
    cache_policy: automatic
    fallback_models: [glm-z1-32b, glm-4-flash, glm-5.3-flash]
    settings_editable: true
    requires_endpoint_selector: true
```

Every value above is copied from the verified current sources:
`settings.py:61-68` + ADR-071 §3 + `.env.example:35-50` (env names — no `env_prefix`,
so plain upper-cased field names), `model_pricing.py:14-24` (`pricing_default`),
`provider_service.py:32-78` (`fallback_models` IDs), `cache_settings.py:32-42`
(`cache_policy`), `model_listing.py:227-378` (`listing_strategy` = the `_fetch_<name>`
method, one per provider), `_providers/*.py` (`pydantic_ai_extra`),
`provider_service.py:235-247` (`requires_endpoint_selector`: Z.AI coding endpoint,
Ollama base URL).

- [ ] **Step 2: Write the failing render test** — `tests/unit/scripts/test_generate_provider_catalog.py`:

```python
from pathlib import Path

from scripts.generate_provider_catalog import (
    CATALOG_PATH,
    PY_OUTPUT,
    load_catalog,
    render_python,
)

EXPECTED_HEADER = "# AUTO-GENERATED by scripts/generate_provider_catalog.py"


def test_catalog_lists_the_seven_providers_in_canonical_order() -> None:
    specs = load_catalog(CATALOG_PATH)
    assert [s.id for s in specs] == [
        "anthropic", "openai", "google", "groq", "ollama", "openrouter", "zai",
    ]


def test_render_python_is_ruff_format_clean_and_has_no_suppressions() -> None:
    rendered = render_python(load_catalog(CATALOG_PATH))
    assert rendered.startswith(EXPECTED_HEADER)
    assert "type: ignore" not in rendered
    assert "pyright: ignore" not in rendered
    assert rendered.endswith("\n")


def test_rendered_python_declares_class_syntax_strenum() -> None:
    rendered = render_python(load_catalog(CATALOG_PATH))
    # ADR-099: class syntax only — the functional form fails pyright strict.
    assert "class AIProvider(StrEnum):" in rendered
    assert "StrEnum(" not in rendered.replace("class AIProvider(StrEnum):", "")


def test_committed_python_artifact_matches_a_fresh_render() -> None:
    assert PY_OUTPUT.read_text(encoding="utf-8") == render_python(load_catalog(CATALOG_PATH))
```

- [ ] **Step 3: Run** `just test-file tests/unit/scripts/test_generate_provider_catalog.py` —
      expect **RED** (`ModuleNotFoundError: scripts.generate_provider_catalog`).

- [ ] **Step 4: Implement `scripts/generate_provider_catalog.py`** — `load_catalog`
      validates the field set (unknown/missing field → `ValueError` naming the
      provider and field), `id` uniqueness and the `id` charset; `render_python`
      emits, in this order, the AUTO-GENERATED header, `from __future__ import
      annotations`, `from enum import StrEnum`, `__all__`, the class with one member
      per spec (`ANTHROPIC = "anthropic"`, …), `PROVIDER_IDS` as a literal tuple, and
      `PROVIDER_LABEL_KEYS` as a literal dict keyed by member. `main()` writes
      `PY_OUTPUT` or performs the `--check` comparison, exiting `1` with a unified
      diff on mismatch.

- [ ] **Step 5: Generate and verify the artifact** —
      `uv run --all-packages python scripts/generate_provider_catalog.py`, then
      `uv run --all-packages python scripts/generate_provider_catalog.py --check`
      (expect exit 0). Then
      `just typecheck-file packages/core/narrare_core/llm/_providers/catalog_generated.py`
      — expect **GREEN**, 0 errors (this is the ADR-099 measurement replicated in
      the real tree). Then
      `just test-file tests/unit/scripts/test_generate_provider_catalog.py` — GREEN.

- [ ] **Step 6: Commit** `feat(core): provider catalog SSOT + generated AIProvider enum (throughput T1)`
      — report `reports/2026-10-19-throughput-T01.md`.

---

### Task 2: Re-point `AIProvider` to the generated enum; prove the OpenAPI component is unchanged

**Program:** P1 · **Depends on:** T1 · **Report:** required (changes the public API shape's source)
**Mandatory review:** yes (public API response shape)

**Files:**
- Modify: `apps/api/narrare/setup/base_schemas.py` (remove the class body, re-export)
- Modify: `docs/architecture/decisions/INDEX.md` (one row for ADR-099 — excluded from the file cap)
- Test: `tests/unit/api/setup/test_ai_provider_identity.py`

**Interfaces:**
- Consumes: `narrare_core.llm._providers.catalog_generated.AIProvider`.
- Produces: `narrare.setup.base_schemas.AIProvider` — the *same object* as the
  generated enum (`__name__ == "AIProvider"`, seven members), which is what
  `narrare.setup.schemas` re-exports and what the OpenAPI schema title follows.

- [ ] **Step 1: Write the failing identity test** — `tests/unit/api/setup/test_ai_provider_identity.py`:

```python
from narrare.setup.base_schemas import AIProvider as FromBaseSchemas
from narrare.setup.schemas import AIProvider as FromSchemas
from narrare_core.llm._providers.catalog_generated import AIProvider as Generated

EXPECTED = ("anthropic", "openai", "google", "groq", "ollama", "openrouter", "zai")


def test_base_schemas_reexports_the_generated_enum() -> None:
    assert FromBaseSchemas is Generated


def test_setup_schemas_reexports_the_same_object() -> None:
    assert FromSchemas is Generated


def test_openapi_component_name_and_values_are_unchanged() -> None:
    assert FromBaseSchemas.__name__ == "AIProvider"
    assert tuple(m.value for m in FromBaseSchemas) == EXPECTED
```

- [ ] **Step 2: Run** `just test-file tests/unit/api/setup/test_ai_provider_identity.py` —
      expect **RED** on the first two assertions (`AIProvider` is still declared in
      `base_schemas`).

- [ ] **Step 3: Re-point** — in `apps/api/narrare/setup/base_schemas.py` replace the
      `class AIProvider(StrEnum)` body with
      `from narrare_core.llm._providers.catalog_generated import AIProvider as AIProvider`
      (an explicit re-export so pyright's `reportUnusedImport` stays quiet), keep it
      adjacent to the other enums, and leave `StoryStructure`, `StoryTone`,
      `StarterContent` and the Step 1–3 schemas untouched.

- [ ] **Step 4: Prove the OpenAPI artifact is byte-identical** —
      `just export-openapi` then `git diff --exit-code docs/reference/openapi.json`
      (expect no diff: `components.schemas.AIProvider` keeps
      `title: "AIProvider"` and its seven-value enum). Then
      `uv run --all-packages python scripts/export_openapi.py --check` — exit 0.
      Then `just test-file tests/unit/api/setup/test_ai_provider_identity.py` — GREEN,
      and `just typecheck` — GREEN with no new suppressions.

- [ ] **Step 5: Verify the ADR-099 index row** is present in
      `docs/architecture/decisions/INDEX.md` (decision log table, status `🔄`). The row
      landed with the ADR itself in the program's opening commit — the ADR
      cross-reference checker (`scripts/doc_drift/adr_checks.py`) requires file↔row
      coverage, so the two cannot be split across commits. Run
      `uv run --all-packages python -m doc_drift` or the corresponding hook and expect
      no `ADR-099 exists as file but has no row in INDEX.md` finding.

- [ ] **Step 6: Commit** `refactor(api): re-export AIProvider from the generated provider catalog (throughput T2)`
      — report `reports/2026-10-19-throughput-T02.md`.

---

### Task 3: Generated TypeScript provider module; re-point the wizard type

**Program:** P1 · **Depends on:** T1 · **Report:** required (2 authored files, crosses layers)
**Mandatory review:** no

**Files:**
- Modify: `scripts/generate_provider_catalog.py` (add the TypeScript renderer + its `--check` branch)
- Create (generated): `packages/web/lib/providers.generated.ts`
- Modify: `packages/web/types/wizard.ts` (re-export instead of declaring)
- Test: `tests/unit/scripts/test_generate_provider_catalog.py` (extend)

**Interfaces:**
- Consumes: `ProviderSpec`, `load_catalog`, `TS_OUTPUT` (T1).
- Produces (T4 relies on these exact names):
  - `packages/web/lib/providers.generated.ts`:
    `export type AIProvider = "anthropic" | … | "zai"`,
    `export const PROVIDER_IDS: readonly AIProvider[]` (canonical order),
    `export const PROVIDER_LABEL_KEYS: Record<AIProvider, string>`
  - `packages/web/types/wizard.ts`: `export type { AIProvider } from "@/lib/providers.generated"`
  - `render_typescript(specs: list[ProviderSpec]) -> str`

- [ ] **Step 1: Write the failing TS-render tests** — extend
      `tests/unit/scripts/test_generate_provider_catalog.py`:

```python
from scripts.generate_provider_catalog import TS_OUTPUT, render_typescript


def test_rendered_typescript_declares_ids_and_label_keys() -> None:
    rendered = render_typescript(load_catalog(CATALOG_PATH))
    assert rendered.startswith("// AUTO-GENERATED by scripts/generate_provider_catalog.py")
    assert 'export type AIProvider =' in rendered
    assert "export const PROVIDER_IDS" in rendered
    assert "export const PROVIDER_LABEL_KEYS" in rendered
    assert 'settings-ai.providers.zai' in rendered


def test_committed_typescript_artifact_matches_a_fresh_render() -> None:
    assert TS_OUTPUT.read_text(encoding="utf-8") == render_typescript(load_catalog(CATALOG_PATH))
```

- [ ] **Step 2: Run** `just test-file tests/unit/scripts/test_generate_provider_catalog.py` —
      expect **RED** (`render_typescript` / `TS_OUTPUT` missing).

- [ ] **Step 3: Implement `render_typescript`** and wire `TS_OUTPUT` into both modes
      of `main()`. Emit biome-clean output: the AUTO-GENERATED `//` header, the union
      with two-space indent continuation, `PROVIDER_IDS` as
      `[...] as const satisfies readonly AIProvider[]`, and `PROVIDER_LABEL_KEYS` as a
      `Record<AIProvider, string>` literal.

- [ ] **Step 4: Re-point the wizard type** — in `packages/web/types/wizard.ts` delete
      the inline `AIProvider` union (lines 3-10) and re-export the generated type.
      `StarterContent`, `StoryStructure`, `StoryTone`, `ProviderModel`,
      `ModelCatalogProvenance`, `DemoProjectInfo` and `WizardState` are untouched.

- [ ] **Step 5: Generate and verify** —
      `uv run --all-packages python scripts/generate_provider_catalog.py` then
      `--check` (exit 0); `just typecheck-frontend` (GREEN, no `tsc` errors);
      `cd packages/web && npx biome check lib/providers.generated.ts types/wizard.ts`
      (GREEN); `just test-file tests/unit/scripts/test_generate_provider_catalog.py`
      (GREEN).

- [ ] **Step 6: Commit** `feat(web): generated provider module + wizard type re-point (throughput T3)`
      — report `reports/2026-10-19-throughput-T03.md`.

---

### Task 4: Fix the settings provider list from the shared derived list (the Groq/Z.AI defect)

**Program:** P1 · **Depends on:** T3 · **Report:** required (3 authored files)
**Mandatory review:** yes (changes the consumer of a public API shape)

**Files:**
- Modify: `packages/web/lib/providers.ts`
- Modify: `packages/web/lib/providers.test.ts`
- Modify: `packages/web/components/studio/wizard/WizardStep4.tsx`
- Modify: `packages/web/components/studio/settings/ProviderForm.tsx`
- Create: `packages/web/components/studio/settings/__tests__/ProviderForm.test.tsx`

**Interfaces:**
- Consumes: `PROVIDER_IDS`, `PROVIDER_LABEL_KEYS`, `AIProvider` from
  `@/lib/providers.generated`.
- Produces (the defect-closing surface):
  - `packages/web/lib/providers.ts`: `PROVIDERS: { value: AIProvider; labelKey: string }[]`
    derived from the generated module, and
    `getProviderLabel(value: string, t: (key: string) => string): string`
    resolving `t(labelKey)` with a raw-value fallback for unknown providers.
  - the settings provider `<select id="provider-name">` renders exactly the seven
    canonical ids in order, each option's text from `t(labelKey)`.

- [ ] **Step 1: Write the failing regression test** —
      `packages/web/components/studio/settings/__tests__/ProviderForm.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProviderForm } from "../ProviderForm";

const t = (key: string) => key; // identity translator: labels surface as keys

function optionValues(): string[] {
  return Array.from(
    document.querySelectorAll<HTMLOptionElement>("#provider-name option"),
  ).map((o) => o.value);
}

describe("ProviderForm provider select (Groq/Z.AI defect)", () => {
  it("offers every catalog provider in canonical order", () => {
    render(
      <ProviderForm mode="add" onSubmit={vi.fn()} onCancel={vi.fn()} isPending={false} t={t} />,
    );
    expect(optionValues()).toEqual([
      "anthropic", "openai", "google", "groq", "ollama", "openrouter", "zai",
    ]);
  });

  it("offers groq and zai specifically (the reported defect)", () => {
    render(
      <ProviderForm mode="add" onSubmit={vi.fn()} onCancel={vi.fn()} isPending={false} t={t} />,
    );
    expect(optionValues()).toContain("groq");
    expect(optionValues()).toContain("zai");
    const labels = Array.from(
      document.querySelectorAll<HTMLOptionElement>("#provider-name option"),
    ).map((o) => o.textContent);
    expect(labels).toContain("settings-ai.providers.groq");
    expect(labels).toContain("settings-ai.providers.zai");
  });
});
```

- [ ] **Step 2: Run** `cd packages/web && pnpm test -- ProviderForm` — expect **RED**:
      five options, and no `groq`/`zai`. **Record this output in the task report —
      it is the defect's proof.**

- [ ] **Step 3: Derive the list** — rewrite `packages/web/lib/providers.ts`:

```ts
import {
  PROVIDER_IDS,
  PROVIDER_LABEL_KEYS,
  type AIProvider,
} from "@/lib/providers.generated";

export { PROVIDER_IDS, PROVIDER_LABEL_KEYS };
export type { AIProvider };

/** Shared provider list with i18n label keys — derived from the generated catalog. */
export const PROVIDERS: { value: AIProvider; labelKey: string }[] = PROVIDER_IDS.map(
  (value) => ({ value, labelKey: PROVIDER_LABEL_KEYS[value] }),
);

/** Resolve a provider's display label through the translator; raw value if unknown. */
export function getProviderLabel(
  value: AIProvider | string,
  t: (key: string) => string,
): string {
  const entry = PROVIDERS.find((p) => p.value === value);
  return entry ? t(entry.labelKey) : value;
}
```

- [ ] **Step 4: Update the existing list tests** — `packages/web/lib/providers.test.ts`
      replaces the seven hardcoded English assertions with key assertions
      (`getProviderLabel("groq", t) === "settings-ai.providers.groq"` with an identity
      `t`) and keeps the unknown-provider cases
      (`getProviderLabel("custom", t) === "custom"`). Run
      `cd packages/web && pnpm test -- providers.test` — expect GREEN.

- [ ] **Step 5: Migrate both consumers** — in `WizardStep4.tsx` (option text) and in
      `ProviderForm.tsx` (delete `PROVIDER_OPTIONS` and `providerLabel`'s local map;
      keep the `providerLabel` export name only if it is imported elsewhere — it is
      not, so delete it) render `t(p.labelKey)` as each option's text. No English
      provider label remains in either component (RULE-16).

- [ ] **Step 6: Verify** — `cd packages/web && pnpm test -- ProviderForm` (**GREEN**,
      seven options), `just test-frontend`, `just typecheck-frontend`,
      `just lint-frontend`, then
      `grep -rn 'Groq\|Z\.AI' packages/web/components` returns no provider-label
      literal.

- [ ] **Step 7: Commit** `fix(web): derive the settings provider list from the shared catalog (Groq/Z.AI) (throughput T4)`
      — report `reports/2026-10-19-throughput-T04.md`.

---

### Task 5: Derive the Core provider-set consumers

**Program:** P1 · **Depends on:** T1, T2 · **Report:** required (2 authored files)
**Mandatory review:** no

**Files:**
- Modify: `packages/core/narrare_core/llm/model_listing.py`
- Modify: `packages/core/narrare_core/llm/_model_listing_test_catalog.py`
- Test: `tests/unit/core/llm/test_provider_catalog_consumers.py`

**Interfaces:**
- Consumes: `catalog_generated.AIProvider`, `PROVIDER_IDS`.
- Produces:
  - `narrare_core.llm.model_listing.SUPPORTED_CATALOG_PROVIDERS` — derived
    `frozenset[str]` equal to `set(PROVIDER_IDS)` (name and type unchanged, so no
    consumer changes)
  - `narrare_core.llm._model_listing_test_catalog._TEST_CATALOG` — keys derived from
    `PROVIDER_IDS`; the module keeps its "no circular import" property by importing
    from `catalog_generated`, never from `model_listing`.

- [ ] **Step 1: Write the failing consumer test** — `tests/unit/core/llm/test_provider_catalog_consumers.py`:

```python
from narrare_core.llm._model_listing_test_catalog import _TEST_CATALOG
from narrare_core.llm._providers.catalog_generated import PROVIDER_IDS
from narrare_core.llm.model_listing import ModelCatalogClient, SUPPORTED_CATALOG_PROVIDERS

EXPECTED = {"anthropic", "openai", "google", "groq", "ollama", "openrouter", "zai"}


def test_supported_catalog_providers_is_derived() -> None:
    assert SUPPORTED_CATALOG_PROVIDERS == EXPECTED
    assert set(PROVIDER_IDS) == EXPECTED


def test_every_provider_has_a_test_catalog_entry() -> None:
    assert set(_TEST_CATALOG) == EXPECTED


def test_every_provider_has_a_model_fetcher() -> None:
    missing = [p for p in PROVIDER_IDS if not hasattr(ModelCatalogClient, f"_fetch_{p}")]
    assert missing == []
```

- [ ] **Step 2: Run** `just test-file tests/unit/core/llm/test_provider_catalog_consumers.py` —
      expect **RED** on `test_every_provider_has_a_test_catalog_entry` only if a key
      is missing (the tree is currently consistent, so the meaningful RED is
      produced in Step 2b).

- [ ] **Step 2b: Prove the test can fail** — temporarily delete the `"groq"` entry
      from `_TEST_CATALOG` and re-run: expect **RED** naming `groq`. Restore it. (This
      is the mutation evidence the spec's acceptance criterion requires; record both
      outputs in the report.)

- [ ] **Step 3: Derive** — `model_listing.py`:
      `SUPPORTED_CATALOG_PROVIDERS: frozenset[str] = frozenset(p.value for p in AIProvider)`
      (or `frozenset(PROVIDER_IDS)`), replacing the literal set at lines 62-64;
      `_dispatch` and the seven `_fetch_*` methods are untouched.
      `_model_listing_test_catalog.py`: build `_TEST_CATALOG` by iterating
      `PROVIDER_IDS` and keeping the existing five-file test entry per provider in a
      private `_TEST_MODELS: dict[str, tuple[str, str, int | None]]` literal; the
      public `_TEST_CATALOG` is assembled from it, so a missing provider is a `KeyError`
      at import rather than a silently absent key.

- [ ] **Step 4: Verify** — `just test-file tests/unit/core/llm/test_provider_catalog_consumers.py`
      (GREEN), `just test-file tests/unit/core/llm/` (GREEN),
      `just typecheck` (GREEN, strict, no suppressions),
      `uv run --all-packages python scripts/generate_provider_catalog.py --check`
      (exit 0).

- [ ] **Step 5: Commit** `refactor(core): derive catalog provider sets from the generated enum (throughput T5)`
      — report `reports/2026-10-19-throughput-T05.md`.

---

### Task 6: Parity gate for the handwritten surfaces in `--check`

**Program:** P1 · **Depends on:** T1–T5 · **Report:** required (cross-layer + governed invariants)
**Mandatory review:** no

**Files:**
- Modify: `scripts/generate_provider_catalog.py` (add `check_parity` + wire into `--check`)
- Test: `tests/unit/scripts/test_generate_provider_catalog_parity.py`

**Interfaces:**
- Consumes: `ProviderSpec`, `load_catalog`, `REPO_ROOT`.
- Produces:
  - `ParityViolation` — frozen dataclass `surface: str`, `detail: str`
  - `check_parity(specs: list[ProviderSpec], repo_root: Path) -> list[ParityViolation]`
  - `--check` exit 1 when `check_parity` returns anything, printing one line per
    violation as `<surface>: <detail>`

**Parity invariants (one AST fact each; no imports, so the hook stays fast and
venv-independent):**

| Invariant name | Surface parsed | Assertion |
|---|---|---|
| `pricing.keys` | `llm/model_pricing.py` → `DEFAULT_RATES` | key set == provider ids |
| `pricing.values` | same | per-provider `input`/`output` == `pricing_default` |
| `cache.arms` | `llm/_providers/cache_settings.py` → `match` in `build_model_settings` | every id appears exactly once among arm literals and the wildcard does not shadow an id |
| `cache.bodies` | same | arm body matches `cache_policy` (`anthropic_cache_control` → `{"cache_control": True}`; `automatic`/`none` → `{}`) |
| `mem0.keys` | `memory/mem0_client.py` → `_PROVIDER_DEFAULT_MODELS` | key set ⊆ ids and non-empty |
| `prefixes.cover` | `llm/_providers/registry.py` → `_PROVIDER_PREFIXES` | `{providers in prefixes} ⊇ ids` |
| `settings.fields` | `settings.py` → `CoreSettings` annotations | for every id with `settings_field`, the field exists and its env var resolves to `api_key_env` |
| `apikeys.cover` | same | every id with non-null `api_key_env` has a declared field |
| `fallback.keys` | `apps/api/narrare/setup/provider_service.py` → `_FALLBACK_MODELS` | key set == ids |
| `fallback.ids` | same | per-provider model ids == `fallback_models` |
| `testcall.endpoints` | same → `_test_call` | a branch exists for every `requires_endpoint_selector: true` provider |
| `labels.locales` | `packages/i18n/messages/{en,de,fr}/settings-ai.json` | every `label_key` resolves in all three locales |

- [ ] **Step 1: Write the failing invariant tests** —
      `tests/unit/scripts/test_generate_provider_catalog_parity.py`, one test per row
      of the table, each on a temporary copy of the tree with exactly one value
      mutated:

```python
import shutil
from pathlib import Path

import pytest

from scripts.generate_provider_catalog import CATALOG_PATH, check_parity, load_catalog

REPO_ROOT = Path(__file__).resolve().parents[3]
MUTATED_FILES = (
    "packages/core/narrare_core/llm/model_pricing.py",
    "packages/core/narrare_core/llm/_providers/cache_settings.py",
    "packages/core/narrare_core/memory/mem0_client.py",
    "packages/core/narrare_core/llm/_providers/registry.py",
    "packages/core/narrare_core/settings.py",
    "apps/api/narrare/setup/provider_service.py",
    "packages/i18n/messages/en/settings-ai.json",
)


def _sandbox(tmp_path: Path) -> Path:
    for rel in MUTATED_FILES:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / rel, dst)
    return tmp_path


def test_pristine_tree_has_no_violations(tmp_path: Path) -> None:
    assert check_parity(load_catalog(CATALOG_PATH), _sandbox(tmp_path)) == []


def test_missing_pricing_key_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    target = root / "packages/core/narrare_core/llm/model_pricing.py"
    target.write_text(
        target.read_text(encoding="utf-8").replace('"groq": {"input"', '"groqx": {"input"'),
        encoding="utf-8",
    )
    violations = check_parity(load_catalog(CATALOG_PATH), root)
    assert [v.surface for v in violations] == ["pricing.keys"]
    assert "groq" in violations[0].detail


def test_missing_fallback_provider_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    target = root / "apps/api/narrare/setup/provider_service.py"
    target.write_text(
        target.read_text(encoding="utf-8").replace("AIProvider.GROQ:", "AIProvider.GROQX:"),
        encoding="utf-8",
    )
    violations = check_parity(load_catalog(CATALOG_PATH), root)
    assert any(v.surface == "fallback.keys" and "groq" in v.detail for v in violations)


@pytest.mark.parametrize("locale", ["en", "de", "fr"])
def test_missing_label_key_in_any_locale_is_reported(tmp_path: Path, locale: str) -> None:
    root = _sandbox(tmp_path)
    rel = f"packages/i18n/messages/{locale}/settings-ai.json"
    dst = root / rel
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / rel, dst)
    dst.write_text(dst.read_text(encoding="utf-8").replace('"zai"', '"zaii"'), encoding="utf-8")
    violations = check_parity(load_catalog(CATALOG_PATH), root)
    assert any(v.surface == "labels.locales" and "zai" in v.detail for v in violations)
```

- [ ] **Step 2: Run** `just test-file tests/unit/scripts/test_generate_provider_catalog_parity.py` —
      expect **RED** (`check_parity` missing).

- [ ] **Step 3: Implement `check_parity`** with `ast` and `json`/`yaml` only: parse
      each surface, extract the named assignment/match/annotations, and produce one
      `ParityViolation` per missing or disagreeing fact. Order violations by
      invariant name then provider id so the output is stable. Wire it into
      `--check` **in addition to** the byte comparisons.

- [ ] **Step 4: Verify** — `just test-file tests/unit/scripts/test_generate_provider_catalog_parity.py`
      (GREEN, every parametrisation), then
      `uv run --all-packages python scripts/generate_provider_catalog.py --check`
      (exit 0), then `just test-file tests/unit/scripts/test_generate_provider_catalog.py`
      (still GREEN), then `just lint-check` (GREEN).

- [ ] **Step 5: Commit** `feat(scripts): provider-catalog parity gate for handwritten surfaces (throughput T6)`
      — report `reports/2026-10-19-throughput-T06.md`.

---

### Task 7: Wire the provider-catalog gate into commit, local and CI surfaces

**Program:** P1 · **Depends on:** T6 · **Report:** required (3 governed surfaces)
**Mandatory review:** yes (governed surfaces: `ci.yml`, `justfile`, `.pre-commit-config.yaml`)

**Files:**
- Modify: `.pre-commit-config.yaml` (new hook `provider-catalog-check`)
- Modify: `justfile` (one line in `check-architecture`)
- Modify: `.github/workflows/ci.yml` (one step in the `architecture` job)

**Interfaces:**
- Consumes: `scripts/generate_provider_catalog.py`.
- Produces: the hook id `provider-catalog-check`; the recipe-line command
  `uv run --all-packages python scripts/generate_provider_catalog.py --check`; the
  CI step name `Check provider catalog (ADR-099)`.

- [ ] **Step 1: Add the hook** — in `.pre-commit-config.yaml`, immediately after the
      `prompt-surface-contract` hook:

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

- [ ] **Step 2: Prove the hook is wired and can fail** —
      `pre-commit run provider-catalog-check --hook-stage pre-commit` (exit 0, expect
      "Passed"), then mutate `catalog.yaml` (swap two provider ids), re-run (expect
      failure naming the artifact), then restore. Record both outputs in the report.

- [ ] **Step 3: Add the local architecture line** — in the `check-architecture`
      recipe in the `justfile`, immediately after the existing
      `check_prompt_surface_contract.py` line, add:

```make
    uv run --all-packages python scripts/generate_provider_catalog.py --check
```

- [ ] **Step 4: Add the CI step** — in `.github/workflows/ci.yml`, in the
      `architecture` job, immediately after the existing
      `Check prompt surface contract (ADR-037 + ADR-049 Phase D)` step
      (currently lines 549-550), add:

```yaml
      - name: Check provider catalog (ADR-099)
        run: uv run --no-sync python scripts/generate_provider_catalog.py --check
```

      No gate-matrix row is added: this is a step of the architecture job (G3d's job),
      exactly as `check_prompt_surface_contract.py` is a step and not a row.

- [ ] **Step 5: Verify** — `just check-architecture` (GREEN, including the new line),
      `pre-commit run --all-files` (all hooks pass),
      `uv run --all-packages python -c "import yaml,pathlib;
      yaml.safe_load(pathlib.Path('.github/workflows/ci.yml').read_text())"`
      (validates the workflow YAML parses), and `just verify-quick` (GREEN).

- [ ] **Step 6: Commit** `ci: gate the provider catalog at commit, local and CI surfaces (throughput T7)`
      — report `reports/2026-10-19-throughput-T07.md`. This commit closes P1 and is
      the last item in ADR-099's completeness checklist that can be produced locally;
      the ADR's status flips only after the wave's PR run of the architecture job is
      green.

---

### Task 8: Move the two whole-project hooks to push; add the scoped slice recipe

**Program:** P3 · **Depends on:** — (independent of P1) · **Report:** required (3 authored files)
**Mandatory review:** yes (governed surfaces: `.pre-commit-config.yaml`, `justfile`)

**Files:**
- Modify: `.pre-commit-config.yaml` (`openapi-regenerate`, `typecheck-frontend`)
- Modify: `justfile` (new `verify-slice` recipe; `verify` and `verify-quick` untouched)
- Create: `docs/development/pre-commit-gate-tiers.md`

**Interfaces:**
- Consumes: the existing scoping recipes `lint-file`, `typecheck-file`, `test-file`.
- Produces: recipe `verify-slice` with a variadic `+paths` parameter; the document
  `docs/development/pre-commit-gate-tiers.md` (which names it, and therefore lands
  here — the `doc-drift` hook validates `just` references in `docs/**`).

- [ ] **Step 1: Measure and record the baseline** — run and capture wall-clock for
      `pre-commit run openapi-regenerate --hook-stage pre-commit --all-files` and
      `pre-commit run typecheck-frontend --hook-stage pre-commit --all-files`
      (`time …`). These two numbers go into the report; the spec deliberately does not
      assert them.

- [ ] **Step 2: Change exactly two stages** — in `.pre-commit-config.yaml` set
      `stages: [pre-commit]` → `stages: [pre-push]` on `openapi-regenerate` and on
      `typecheck-frontend` only. Update each hook's comment to state why it is
      push-tiered and that CI remains the authority (architecture job's
      `export_openapi.py --check`; frontend job's TypeScript step). Touch no `entry`,
      `files`, `always_run` or `types` value.

- [ ] **Step 3: Prove the move** —
      `pre-commit run typecheck-frontend --hook-stage pre-commit --all-files` now
      reports that no such hook exists in the pre-commit stage, and
      `pre-commit run typecheck-frontend --hook-stage pre-push --all-files` runs it.
      Capture both outputs (the first is the RED-equivalent proof that the hook left
      the commit stage).

- [ ] **Step 4: Add the scoped recipe** — in the `justfile`, after `verify-quick`:

```make
# Scoped slice gate for one change set. NOT a substitute for `just verify`:
# it runs only the given paths (ruff, pyright with the correct config, the
# matching pytest files) and adds the scoped frontend check when a path is
# under packages/web/. Integration and E2E tests never run here.
# Usage: just verify-slice packages/core/narrare_core/llm/model_listing.py
verify-slice +paths:
    #!/usr/bin/env bash
    set -euo pipefail
    just lint-file {{paths}}
    just typecheck-file {{paths}}
    just test-file {{paths}}
    web=()
    for p in {{paths}}; do
        case "$p" in
            packages/web/*) web+=("$p") ;;
        esac
    done
    if [ "${#web[@]}" -gt 0 ]; then
        cd packages/web && npx biome check "${web[@]/#packages\/web\//}"
    fi
```

- [ ] **Step 5: Write the tiering document** — `docs/development/pre-commit-gate-tiers.md`:
      state the stage census (36 commit / 3 push / 1 manual / 1 commit-msg before this
      task), the two hooks that moved and why, the `verify-slice` contract from the
      spec, the explicit statement that `just verify` is unchanged and is the pre-merge
      gate, and — mandatory — a scoping sentence that this document records **local
      hook staging only** and that the CI gate SSOT remains the ci.yml header table plus
      CONSTRAINTS §6 (ADR-098). Point at those; do not restate any CI gate.

- [ ] **Step 6: Verify** — `just verify-slice packages/core/narrare_core/llm/model_listing.py`
      (GREEN), `just verify-slice packages/web/lib/providers.ts` (GREEN, runs the scoped
      biome check), `just check-architecture` (GREEN), `pre-commit run --all-files`
      (GREEN), and `just verify-quick` (GREEN). Confirm `just verify` is unchanged:
      `just --show verify` prints `check test-all`.

- [ ] **Step 7: Commit** `chore(gates): push-tier the two whole-project hooks, add verify-slice (throughput T8)`
      — report `reports/2026-10-19-throughput-T08.md`.

---

### Task 9: Machine-pin the hook tiering

**Program:** P3 · **Depends on:** T8 · **Report:** required (2 authored files, governed surface)
**Mandatory review:** no (the governed surface was reviewed in T8; this task adds the ratchet)

**Files:**
- Create: `scripts/check_pre_commit_gate_tiers.py`
- Modify: `justfile` (one line in `check-architecture`)
- Create: `tests/unit/scripts/test_pre_commit_gate_tiers.py`

**Interfaces:**
- Consumes: `.pre-commit-config.yaml`.
- Produces: `PUSH_ONLY = {"pyright", "pyright-tests", "bandit", "openapi-regenerate", "typecheck-frontend"}`,
  `MANUAL_ONLY = {"adoption-score"}`, `COMMIT_MSG_ONLY = {"conventional-commits"}`,
  and `find_tier_violations(config_text: str) -> list[str]`.

- [ ] **Step 1: Write the failing ratchet test** — `tests/unit/scripts/test_pre_commit_gate_tiers.py`:

```python
from scripts.check_pre_commit_gate_tiers import find_tier_violations

BASE = """
repos:
  - repo: local
    hooks:
      - id: ruff-lint
        stages: [pre-commit]
      - id: pyright
        stages: [pre-push]
"""


def test_violation_when_a_new_hook_claims_pre_push() -> None:
    text = BASE + "      - id: sneaky\n        stages: [pre-push]\n"
    assert any("sneaky" in v for v in find_tier_violations(text))


def test_violation_when_a_moved_hook_returns_to_commit() -> None:
    text = BASE.replace("      - id: pyright\n        stages: [pre-push]",
                        "      - id: pyright\n        stages: [pre-commit]")
    assert any("pyright" in v for v in find_tier_violations(text))


def test_violation_when_a_moved_hook_disappears_from_push() -> None:
    text = """
repos:
  - repo: local
    hooks:
      - id: openapi-regenerate
        stages: [pre-commit]
"""
    assert any("openapi-regenerate" in v for v in find_tier_violations(text))


def test_real_config_is_clean() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    assert find_tier_violations((root / ".pre-commit-config.yaml").read_text(encoding="utf-8")) == []
```

- [ ] **Step 2: Run** `just test-file tests/unit/scripts/test_pre_commit_gate_tiers.py` —
      expect **RED** (`ModuleNotFoundError`).

- [ ] **Step 3: Implement** `scripts/check_pre_commit_gate_tiers.py` using `yaml` to
      load the config (the file is valid YAML) and one rule set: every hook id in
      `PUSH_ONLY` must declare `stages: [pre-push]` and no other hook may; every hook
      in `MANUAL_ONLY`/`COMMIT_MSG_ONLY` must declare its stage; every other hook must
      not declare `pre-push`. Exit 1 listing each violation.

- [ ] **Step 4: Wire it** — add
      `uv run --all-packages python scripts/check_pre_commit_gate_tiers.py` to the
      `check-architecture` recipe, immediately after the provider-catalog line added
      in T7.

- [ ] **Step 5: Verify** — `just test-file tests/unit/scripts/test_pre_commit_gate_tiers.py`
      (GREEN), `just check-architecture` (GREEN),
      `uv run --all-packages python scripts/check_pre_commit_gate_tiers.py` (exit 0),
      `just lint-check` (GREEN).

- [ ] **Step 6: Commit** `feat(scripts): pin pre-commit hook tiering (throughput T9)`
      — report `reports/2026-10-19-throughput-T09.md`.

---

### Task 10: Write the review and report thresholds down

**Program:** P4 · **Depends on:** — · **Report:** required (3 authored files)
**Mandatory review:** no

**Files:**
- Modify: `docs/development/quality-gates.md` (new normative section)
- Modify: `AGENTS.md` (point at it; replace the one-line review principle)
- Modify: `.opencode/agents/NarrareDevCoordinator.md` (point at it; stop restating the caps)

**Interfaces:**
- Consumes: the spec's §6 decision.
- Produces: the normative text block that T11's checker reads, carrying the
  machine-readable markers `<!-- review-policy: caps=3/250 report=3/80 -->` in
  `docs/development/quality-gates.md` and a referenced (not restated) pointer in
  `AGENTS.md` and in `.opencode/agents/NarrareDevCoordinator.md`.

- [ ] **Step 1: Add the normative section** to `docs/development/quality-gates.md`:

```markdown
## Review & report policy

<!-- review-policy: caps=3/250 report=3/80 -->

Normative text. `AGENTS.md` and `.opencode/agents/NarrareDevCoordinator.md`
reference this section; they do not restate its numbers.

- **Package caps:** ≤3 authored files and ≤250 new production LOC per delegated
  unit. Test files, machine-generated artifacts and single-row documentation edits
  do not count. Sub-slice rather than exceed.
- **Per-task report file — required** when a task changes ≥3 authored files, adds
  ≥80 new production LOC, crosses a layer boundary, or changes a governed surface
  (`docs/_shared/CONSTRAINTS.md`, an ADR, `scripts/architecture/*`,
  `.github/workflows/ci.yml`, `justfile`, `.pre-commit-config.yaml`). Otherwise the
  commit message body is the record.
- **Batch review — allowed** when the tasks share a layer and a file cluster and at
  least one of them met the report threshold; the batch report names every covered
  task.
- **Per-task review — mandatory, never batched** when a task adds or renames a
  Protocol/contract, changes a manifest or registry, changes the public shape of an
  API response, or edits a governed surface.
```

- [ ] **Step 2: Replace the one-line principle in `AGENTS.md`** with a pointer:
      "Review and report thresholds: see `docs/development/quality-gates.md` §Review
      & report policy (normative; numbers are not restated here)." Keep it to one
      bullet in the existing working-principles list.

- [ ] **Step 3: De-duplicate the coordinator file** — in
      `.opencode/agents/NarrareDevCoordinator.md`, replace the numeric caps in
      "## Package sizing (HARD)" with a reference to the normative section, keeping the
      behavioural rules (one delegation = one logical unit; never dispatch a whole
      feature in one call; `PACKAGE_TOO_LARGE` handling) intact.

- [ ] **Step 4: Verify the doc surfaces** —
      `uv run --all-packages python scripts/check_doc_drift.py --governance-only`
      (must exit 0: no `just` phantom references, no fake agent names; note the
      pre-existing `ADR-099 has no INDEX row` warning is cleared by T2),
      `grep -c 'review-policy' docs/development/quality-gates.md` → `1`, and
      `grep -rn '≤3 files\|≤ 3 files\|250 new LOC' AGENTS.md .opencode/agents/NarrareDevCoordinator.md`
      → no numeric restatement remains.

- [ ] **Step 5: Commit** `docs(process): normative review and report thresholds (throughput T10)`
      — report `reports/2026-10-19-throughput-T10.md`.

---

### Task 11: Pin the policy numbers

**Program:** P4 · **Depends on:** T10 · **Report:** required (2 authored files, governed surface)
**Mandatory review:** no

**Files:**
- Create: `scripts/check_review_policy_consistency.py`
- Modify: `justfile` (one line in `check-architecture`)
- Create: `tests/unit/scripts/test_review_policy_consistency.py`

**Interfaces:**
- Consumes: the `<!-- review-policy: caps=3/250 report=3/80 -->` marker and its
  normative block in `docs/development/quality-gates.md`.
- Produces: `parse_policy(text: str) -> dict[str, str]` and
  `find_policy_violations(root: Path) -> list[str]`.

- [ ] **Step 1: Write the failing test** — `tests/unit/scripts/test_review_policy_consistency.py`:

```python
from pathlib import Path

from scripts.check_review_policy_consistency import find_policy_violations, parse_policy

ROOT = Path(__file__).resolve().parents[3]


def test_policy_marker_is_parseable() -> None:
    text = (ROOT / "docs/development/quality-gates.md").read_text(encoding="utf-8")
    assert parse_policy(text) == {"caps": "3/250", "report": "3/80"}


def test_normative_block_exists() -> None:
    text = (ROOT / "docs/development/quality-gates.md").read_text(encoding="utf-8")
    assert "## Review & report policy" in text
    assert "normative" in text.lower()


def test_numbers_are_not_restated_in_the_pointing_docs() -> None:
    for rel in ("AGENTS.md", ".opencode/agents/NarrareDevCoordinator.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "250 new LOC" not in text
        assert "≤3 files" not in text


def test_real_tree_is_clean() -> None:
    assert find_policy_violations(ROOT) == []


def test_missing_marker_is_reported(tmp_path: Path) -> None:
    (tmp_path / "docs/development").mkdir(parents=True)
    (tmp_path / "docs/development/quality-gates.md").write_text("# Quality Gates\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("x\n", encoding="utf-8")
    (tmp_path / ".opencode/agents").mkdir(parents=True)
    (tmp_path / ".opencode/agents/NarrareDevCoordinator.md").write_text("x\n", encoding="utf-8")
    assert any("marker" in v for v in find_policy_violations(tmp_path))
```

- [ ] **Step 2: Run** `just test-file tests/unit/scripts/test_review_policy_consistency.py` —
      expect **RED** (`ModuleNotFoundError`).

- [ ] **Step 3: Implement** `scripts/check_review_policy_consistency.py`: require the
      marker and the normative heading; require that the pointing documents contain
      the pointer phrase and no `≤N files` / `N new LOC` numeric restatement; exit 1
      listing violations. Keep it pure text matching — no imports of project code.

- [ ] **Step 4: Wire it** into the `check-architecture` recipe, immediately after the
      gate-tier line added in T9.

- [ ] **Step 5: Verify** — `just test-file tests/unit/scripts/test_review_policy_consistency.py`
      (GREEN), `just check-architecture` (GREEN),
      `uv run --all-packages python scripts/check_review_policy_consistency.py`
      (exit 0), `just lint-check` (GREEN).

- [ ] **Step 6: Commit** `feat(scripts): pin review/report policy numbers (throughput T11)`
      — report `reports/2026-10-19-throughput-T11.md`.

---

### Task 12: Feature scaffolder

**Program:** P5 · **Depends on:** T1 (catalog) · **Report:** required (2 authored files + ≥80 LOC)
**Mandatory review:** no

**Files:**
- Create: `scripts/scaffold_feature.py`
- Modify: `justfile` (recipe `new-feature`)
- Create: `tests/unit/scripts/test_scaffold_feature.py`

**Interfaces:**
- Consumes: `catalog_generated.PROVIDER_IDS` (for provider-aware feature templates),
  `scripts/architecture/adoption-registry.yaml` (for the intent entry shape).
- Produces:
  - `scaffold_feature(feature_id: str, layers: tuple[str, ...], root: Path, *,
    with_intent: str | None = None) -> list[Path]`
  - CLI `python scripts/scaffold_feature.py <id> <layer...> [--with-intent NAME] [--root PATH]`
  - recipe `new-feature` with signature `new-feature id +layers`
  - exit codes: `0` written and gate-green, `1` id already exists, `2` post-condition
    gate failure (message names the failing surface).

- [ ] **Step 1: Write the failing scaffolder tests** — `tests/unit/scripts/test_scaffold_feature.py`:

```python
from pathlib import Path

import pytest

from scripts.scaffold_feature import EXISTING_ID_EXIT, scaffold_feature

LAYERS = ("core", "api", "web")


def test_scaffolds_feature_doc_tests_contract_and_report_stub(tmp_path: Path) -> None:
    written = scaffold_feature("FIND-099", LAYERS, tmp_path)
    rel = {p.relative_to(tmp_path).as_posix() for p in written}
    assert any(p.startswith("docs/features/") and p.endswith("FIND-099.md") for p in rel)
    assert any(p.startswith("tests/unit/core/") for p in rel)
    assert any(p.startswith("tests/unit/api/") for p in rel)
    assert any(p.startswith("packages/core/narrare_core/") and p.endswith("contracts.py") for p in rel)
    assert any(p.startswith("docs/superpowers/plans/reports/") for p in rel)


def test_never_generates_service_router_or_component_files(tmp_path: Path) -> None:
    written = {p.name for p in scaffold_feature("FIND-099", LAYERS, tmp_path)}
    assert not written & {"service.py", "router.py", "repository.py"}


def test_project_language_is_english(tmp_path: Path) -> None:
    for path in scaffold_feature("FIND-099", LAYERS, tmp_path):
        assert "TODO" not in path.read_text(encoding="utf-8")


def test_refuses_a_feature_id_that_already_exists(tmp_path: Path) -> None:
    scaffold_feature("FIND-099", ("core",), tmp_path)
    with pytest.raises(SystemExit) as exc:
        scaffold_feature("FIND-099", ("core",), tmp_path)
    assert exc.value.code == EXISTING_ID_EXIT


def test_with_intent_creates_three_locale_prompt_directories(tmp_path: Path) -> None:
    written = scaffold_feature("FIND-099", ("core",), tmp_path, with_intent="new_thing")
    rel = {p.relative_to(tmp_path).as_posix() for p in written}
    assert any("/en/" in p for p in rel)
    assert any("/de/" in p for p in rel)
    assert any("/fr/" in p for p in rel)
```

- [ ] **Step 2: Run** `just test-file tests/unit/scripts/test_scaffold_feature.py` —
      expect **RED** (`ModuleNotFoundError`).

- [ ] **Step 3: Implement the generator** — write only: the feature document (house
      template, frontmatter listing only paths the same run created or that already
      exist), test skeletons per named layer, a Protocol/contract stub when `core` is
      named, a task-report stub following the report contract, and — only with
      `--with-intent` — the eight declaration-surface entries plus three locale prompt
      files with complete frontmatter, the `## System Prompt` heading and the intent's
      short scope summary as body (never a placeholder). Never write `service.py`,
      `router.py`, `repository.py` or a component. Refuse when the id already exists in
      any declaration surface (exit 1, nothing written).

- [ ] **Step 4: Implement the post-condition** — after writing, run the scoped
      architecture checks (prompt structure, prompt-surface contract, locale sync,
      feature-path accuracy) and, when T14's parity gate exists, that gate too; exit 2
      naming the failing surface if any is red.

- [ ] **Step 5: Add the recipe**:

```make
# Scaffold the declaration surfaces of a new feature. Generates only artifacts
# that are green on arrival — never service/router/repository/component stubs
# (RULE-20). Layers: core, api, web. Optional: --with-intent NAME.
# Usage: just new-feature FIND-099 core api web
new-feature id +layers:
    uv run --all-packages python scripts/scaffold_feature.py {{id}} {{layers}}
```

- [ ] **Step 6: Verify** — `just test-file tests/unit/scripts/test_scaffold_feature.py`
      (GREEN), then a real scaffold into a throwaway worktree:
      `just new-feature SCAFFOLD-001 core` and confirm exit 0, then remove the throwaway
      tree. Then `just lint-check` and `just test-file tests/unit/scripts/` (GREEN).

- [ ] **Step 7: Commit** `feat(scripts): feature scaffolder emitting gate-green declarations (throughput T12)`
      — report `reports/2026-10-19-throughput-T12.md`.

---

### Task 13: Document the scaffolder (recipe and document land together)

**Program:** P5 · **Depends on:** T12 · **Report:** not required (2 authored files, documentation only, no governed surface)
**Mandatory review:** no

**Files:**
- Create: `docs/development/new-feature-scaffolder.md`
- Modify: `.opencode/agents/NarrareDevCoordinator.md` (one workflow pointer)

**Interfaces:**
- Consumes: the `new-feature` recipe from T12.
- Produces: the document that names `just new-feature`, landed in the same task as the
  recipe (the `doc-drift` hook validates `just` references in `docs/**` — this task is
  why T12 and T13 are separate and adjacent).

- [ ] **Step 1: Write the document** — `docs/development/new-feature-scaffolder.md`:
      the recipe signature, the layer names, the `--with-intent` flag, exactly what is
      generated and what is deliberately never generated (with the RULE-20 reason), the
      three exit codes, the post-condition (a scaffold either arrives gate-green or
      arrives with a named failure), and the dependency on the provider catalog (P1)
      and the intent parity gate (P2).

- [ ] **Step 2: Add the workflow pointer** — in
      `.opencode/agents/NarrareDevCoordinator.md`, in the Workflow step that begins
      implementation, add one line pointing at the document as the way a new feature's
      declaration surfaces are created.

- [ ] **Step 3: Verify the doc-drift gate** —
      `uv run --all-packages python scripts/check_doc_drift.py --governance-only`
      (exit 0: the referenced recipe now exists, so the check resolves it), and
      `just --list | grep new-feature` shows the recipe.

- [ ] **Step 4: Commit** `docs(development): document the feature scaffolder (throughput T13)`
      — no report file (2 authored files, documentation only).

---

### Task 14: Intent-contract parity gate

**Program:** P2 · **Depends on:** — (independent of P1) · **Report:** required (cross-layer check + ≥80 LOC)
**Mandatory review:** no

**Files:**
- Create: `scripts/check_intent_parity.py`
- Create: `tests/unit/scripts/test_check_intent_parity.py`

**Interfaces:**
- Consumes: the eight declaration surfaces (spec §4), read by `ast` and `yaml`.
- Produces:
  - `IntentFact` — dataclass `intent: str`, `category: str | None`, `mode: str | None`
  - `EXEMPT_INTENTS = {"EMBED"}` — documented exemption: `EMBED` is not gateway-routed
    (spec §4), keyed to ADR-025
  - `collect_facts(root: Path) -> dict[str, dict[str, IntentFact]]` — per surface
  - `find_disagreements(facts: dict[str, dict[str, IntentFact]]) -> list[str]`
  - exit 0 with `30 intents, 29 routed, 0 disagreements`; exit 1 with one line per
    disagreement naming the intent and the two surfaces

- [ ] **Step 1: Write the failing disagreements test** —
      `tests/unit/scripts/test_check_intent_parity.py`, one case per relationship
      family of spec §4:

```python
from pathlib import Path

from scripts.check_intent_parity import find_disagreements

ROOT = Path(__file__).resolve().parents[3]


def _facts(**overrides: dict[str, dict[str, object]]):
    base = {
        "enums": {"WRITE": {"category": "writing", "mode": "new_chapter"}},
        "categories": {"WRITE": {"category": "writing", "mode": None}},
        "route_intents": {"WRITE": {"category": "writing", "mode": "new_chapter"}},
        "route_configs": {"WRITE": {"category": None, "mode": "new_chapter"}},
        "profiles": {"WRITE": {"category": None, "mode": None}},
    }
    base.update(overrides)  # type: ignore[arg-type]  # test helper only
    return base


def test_agreeing_surfaces_produce_no_disagreement() -> None:
    assert find_disagreements(_facts()) == []


def test_enum_without_a_category_entry_is_reported() -> None:
    assert find_disagreements(_facts(categories={})) != []


def test_category_mismatch_between_two_surfaces_is_reported() -> None:
    bad = _facts(route_intents={"WRITE": {"category": "analysis", "mode": "new_chapter"}})
    assert any("WRITE" in d for d in find_disagreements(bad))


def test_mode_mismatch_between_two_surfaces_is_reported() -> None:
    bad = _facts(route_configs={"WRITE": {"category": None, "mode": "other_mode"}})
    assert any("mode" in d for d in find_disagreements(bad))


def test_real_tree_has_no_disagreements() -> None:
    from scripts.check_intent_parity import collect_facts

    assert find_disagreements(collect_facts(ROOT)) == []
```

      Plus, in the same file, prompt-directory existence, manifest-block equality and
      adoption-registry coverage — each as a function called by `find_disagreements`
      and each with a mutation test against a temporary tree copy (the sandbox helper
      pattern of T6, over `packages/core/narrare_core/prompts/`,
      `scripts/architecture/prompt-surface-manifest.yaml` and
      `scripts/architecture/adoption-registry.yaml`).

- [ ] **Step 2: Run** `just test-file tests/unit/scripts/test_check_intent_parity.py` —
      expect **RED** (`ModuleNotFoundError`).

- [ ] **Step 3: Implement** `scripts/check_intent_parity.py` with the six families of
      spec §4: key-set identity across `LLMIntent`, `INTENT_CATEGORY_MAP`,
      `INTENT_TO_CATEGORY`, `INTENT_TO_MODE`, `INTENT_PROFILES` and `ROUTE_CONFIGS`
      (minus `EXEMPT_INTENTS`); category agreement; mode agreement; prompt directory
      existence per locale using the resolved category/mode; manifest block agreement
      (one block per routed intent, `category`/`mode`/`intent` matching the route
      table); adoption-registry entry per routed intent and none for a non-existent
      intent. Read everything with `ast`/`yaml`; import no project code. Print the
      summary line and exit 0, or one line per disagreement and exit 1.

- [ ] **Step 4: Record the mutation evidence** — for each of the six families, mutate
      one surface in a temporary copy and capture the non-zero exit with its message.
      These six captures are the spec's acceptance criterion 2 and go into the report.

- [ ] **Step 5: Verify** —
      `uv run --all-packages python scripts/check_intent_parity.py`
      (exit 0, `30 intents, 29 routed, 0 disagreements`),
      `just test-file tests/unit/scripts/test_check_intent_parity.py` (GREEN),
      `just lint-check` (GREEN), and — proving no existing gate changed —
      `uv run --all-packages python scripts/check_prompt_surface_contract.py` (exit 0)
      and `uv run --all-packages python scripts/check_locale_sync.py` (exit 0).

- [ ] **Step 6: Commit** `feat(scripts): intent-contract parity gate (throughput T14)`
      — report `reports/2026-10-19-throughput-T14.md`.

---

### Task 15: Wire the intent parity gate; close the P5↔P2 dependency

**Program:** P2 · **Depends on:** T14 **and** T12 · **Report:** required (3 governed surfaces + cross-layer)
**Mandatory review:** yes (governed surfaces: `.pre-commit-config.yaml`, `justfile`, `ci.yml`)

**Files:**
- Modify: `.pre-commit-config.yaml` (new hook `intent-parity`)
- Modify: `justfile` (one line in `check-architecture`)
- Modify: `.github/workflows/ci.yml` (one step in the `architecture` job)

**Interfaces:**
- Consumes: `scripts/check_intent_parity.py`; `just new-feature` with `--with-intent`.
- Produces: hook id `intent-parity`; CI step name
  `Check intent contract parity (ADR-025/037/038)`.

- [ ] **Step 1: Add the hook** — immediately after `provider-catalog-check`:

```yaml
      # Intent contract parity — ADR-025/037/038. Compares the eight intent
      # declaration surfaces against one another (enum, category map, profiles,
      # route table + intents, prompt directories, manifest, adoption registry).
      # Comparison only: it moves no authority out of the manifest or the registry.
      - id: intent-parity
        name: Intent Contract Parity (ADR-025/037/038)
        entry: uv run --no-sync python scripts/check_intent_parity.py
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-commit]
```

- [ ] **Step 2: Add the local line** — in the `check-architecture` recipe, immediately
      after the review-policy line added in T11:

```make
    uv run --all-packages python scripts/check_intent_parity.py
```

- [ ] **Step 3: Add the CI step** — in the `architecture` job, immediately after the
      provider-catalog step added in T7:

```yaml
      - name: Check intent contract parity (ADR-025/037/038)
        run: uv run --no-sync python scripts/check_intent_parity.py
```

- [ ] **Step 4: Prove the hook can fail** —
      `pre-commit run intent-parity --hook-stage pre-commit` (exit 0), then remove one
      `INTENT_TO_MODE` entry in a scratch copy, re-run against that copy, capture the
      failure naming the intent and both surfaces, restore. Record both outputs.

- [ ] **Step 5: Close the P5 dependency** — in a throwaway worktree:
      `just new-feature SCAFFOLD-002 core --with-intent parity_probe`, then run
      `uv run --all-packages python scripts/check_intent_parity.py` and
      `uv run --all-packages python scripts/check_prompt_structure.py` in that tree —
      both must exit 0 with no manual edit. Capture both. This is the spec's P5
      acceptance criterion 1 and 2, and the closure of the P5→P2 dependency. Remove the
      worktree afterwards.

- [ ] **Step 6: Verify the whole program surface** — `just check-architecture` (GREEN,
      now containing the provider-catalog, tier-pinning, policy-pinning and
      intent-parity lines), `pre-commit run --all-files` (GREEN),
      `uv run --all-packages python scripts/check_doc_drift.py` (exit 0),
      `just verify-quick` (GREEN), and confirm the CI file parses:
      `uv run --all-packages python -c "import yaml,pathlib; yaml.safe_load(pathlib.Path('.github/workflows/ci.yml').read_text())"`.

- [ ] **Step 7: Commit** `ci: gate intent contract parity on commit, local and CI surfaces (throughput T15)`
      — report `reports/2026-10-19-throughput-T15.md`. This is the last task of the
      program; the wave's pull request then carries the evidence the ADRs and the spec
      require (the architecture job's log showing the provider-catalog, intent-parity,
      tier-pinning and policy-pinning steps green).

---

## Addendum A — T0: worktree-safe commit-message gate (program blocker)

> **Coordinator Ruling CR-1 (2026-10-19).** This task is outside the planned P1–P5
> scope and was inserted during execution. It is recorded here rather than folded
> into an existing task, per the "no retroactive plan rewriting" rule. Authorization:
> it is a hard blocker — *every* task of this program commits from a linked worktree,
> and with the `commit-msg` hook installed no commit from a linked worktree can
> succeed. Fixing the hook is therefore a precondition for T1's commit and for all
> later tasks. Revert freely if the ruling is not accepted: the fix touches one
> script plus its new test and nothing else.

**Discovered:** 2026-10-19, after T1's implementation, when the T1 commit was refused.

**Evidence (all reproduced in this worktree):**
- `scripts/check_commit_message.py:86` reads `Path(".git/COMMIT_EDITMSG")` — a
  **cwd-relative** path. In a linked worktree `.git` is a *file* (65 bytes, the
  `gitdir:` pointer), so `.git/COMMIT_EDITMSG` can never exist there. The script
  falls through to `sys.stdin.read()`, which pre-commit leaves empty
  (`pass_filenames: false`), producing
  `❌ Commit message rejected: Empty commit message` and exit 1.
- `git rev-parse --git-path COMMIT_EDITMSG` →
  `<main>/.git/worktrees/brave-egret/COMMIT_EDITMSG` — exists, holds the real message.
- Direct reproduction as git invokes it:
  `bash /home/kiesow/projects/narrare/.git/hooks/commit-msg /tmp/opencode/probe-commitmsg.txt`
  from the worktree root → exit 1 with the "Empty commit message" error, for a
  message that is unambiguously valid Conventional Commits.
- Why the program's first commit (`de576f0c`, 08:46:30) succeeded anyway: the
  `commit-msg` hook file was created at **08:47:37**, *after* that commit. Only
  `pre-commit` and `pre-push` were installed before it (main-checkout hooks, mtime
  16:47:15 the previous day). The commit-msg stage was not yet installed, so that
  commit never ran it. From the moment it is installed, the defect is live.

**Decision.** Fix the path resolution; do **not** disarm the hook. The hook is
correct to demand a Conventional Commits subject — it is the gate that keeps
`de576f0c`-style messages honest. Resolution order becomes: (1) an explicit path in
`sys.argv[1]` (git's own `commit-msg` protocol), (2) `git rev-parse --git-path
COMMIT_EDITMSG` — correct in a normal checkout *and* in a linked worktree, (3)
stdin. `pass_filenames: false` stays; `.pre-commit-config.yaml` is not touched.
Forbidden, as always: `--no-verify`, `-n`, `core.hooksPath` redirection.

**Files:** Modify `scripts/check_commit_message.py` · Create
`tests/unit/scripts/test_check_commit_message.py`.
**Report:** required → `reports/2026-10-19-throughput-T00.md`.

- [ ] **Step 1: Write the regression test first** —
      `tests/unit/scripts/test_check_commit_message.py`. It must exercise the real
      worktree shape, not a mock: a fixture that `git init`s a tmp directory, makes an
      initial commit, `git worktree add`s a second checkout, writes a valid message
      into that worktree's `COMMIT_EDITMSG`, then runs the script **as a subprocess
      from the worktree root with no arguments and `stdin=DEVNULL`**, asserting exit
      0. A second case writes an invalid subject and asserts exit 1 — so the test
      cannot pass by short-circuiting to success. Pin the message path the same way
      the defect does: `.git` in that worktree must be a file, asserted explicitly.

- [ ] **Step 2: Run it** — `just test-file tests/unit/scripts/test_check_commit_message.py`.
      Expect **RED**: exit 1 / "Empty commit message" for the valid message. Capture
      the output verbatim for the report.

- [ ] **Step 3: Implement the resolution order** — a small
      `read_commit_message(argv, *, stdin)` helper (`argv` defaults to `sys.argv[1:]`,
      `stdin` to `sys.stdin`): explicit path if it is a file → `subprocess.run(["git",
      "rev-parse", "--git-path", "COMMIT_EDITMSG"], capture_output=True, text=True,
      check=True)` → stdin. A failure of the git call must be reported (RULE-11: no
      silent `except`) and must fall through to stdin. `main()` keeps its current
      contract (exit 0 valid / 1 invalid) and its current output.

- [ ] **Step 4: Verify** — the test is GREEN, then both directions of the live hook from
      the worktree root. **Correction to an earlier draft of this step:** the literal
      `bash <common>/hooks/commit-msg <scratch-file>` invocation cannot test anything —
      `pass_filenames: false` means git's message-file argument is dropped before the
      script runs, so both directions read the same resolved file and a "valid" run
      would still fail while the fix is only staged (pre-commit stashes unstaged
      changes). The valid two-directional check is (a) the subprocess regression test,
      and (b) the installed hook run from a **clean-tree throwaway worktree**, once
      with a valid message as the pending commit message and once with an invalid one
      (`Bad subject`): exit 0 and exit 1 respectively. Also verify the recipe path, which
      feeds the message on stdin: `just check-commit-msg "feat(core): probe"` → exit 0
      and `just check-commit-msg "Bad subject"` → exit 1. Then
      `just lint-file scripts/check_commit_message.py`,
      `just typecheck-file scripts/check_commit_message.py tests/unit/scripts/test_check_commit_message.py`,
      `just check-architecture`.

- [ ] **Step 5: Commit** `fix(scripts): resolve the commit-message path through git (worktree-safe commit-msg gate)`
      — report `reports/2026-10-19-throughput-T00.md`.
