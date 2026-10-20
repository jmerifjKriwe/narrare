# ADR-099 — Provider Catalog Single Source of Truth (generated, checked-in)

> **Status:** 🔄 Proposed
> **Date:** 2026-10-19
> **Deciders:** Architecture Agent
> **Supersedes:** none
> **Related:** ADR-013 (i18n architecture — label resolution), ADR-025 (feature
> adoption registry), ADR-037 (prompt-surface contract manifest), ADR-038
> (AI-invocation adoption contract), ADR-045 (runtime adoption enforcement),
> ADR-071 (CoreSettings), ADR-096 (scene planning — generated/re-export
> precedent), ADR-097 (pre-commit typecheck staging precedent), ADR-098 (single
> gate SSOT)

---

## Context

### The user-visible defect that forced the question

Studio → Settings → AI cannot add a Groq or a Z.AI provider key.
`packages/web/components/studio/settings/ProviderForm.tsx:8-14` hard-codes five
options (`openai`, `anthropic`, `google`, `ollama`, `openrouter`), while the
backend accepts seven (`apps/api/narrare/setup/base_schemas.py:45-52`) and the
setup wizard offers all seven (`packages/web/lib/providers.ts:4-12`, consumed by
`packages/web/components/studio/wizard/WizardStep4.tsx:70`).

Two hand-maintained frontend lists of the same set disagree with each other and
with the backend. A user with a Groq or Z.AI key is silently locked out of the
settings surface.

### The provider set is declared fifteen times, in two languages

Verified on disk 2026-10-19:

| # | Surface | Kind | Values |
|---|---------|------|--------|
| 1 | `apps/api/narrare/setup/base_schemas.py:45-52` — `AIProvider` | Python `StrEnum` | 7 |
| 2 | `apps/api/narrare/setup/schemas.py:9,37` — re-export of `AIProvider` | Python re-export | 7 |
| 3 | `apps/api/narrare/setup/provider_service.py:32-78` — `_FALLBACK_MODELS` keys | Python dict | 7 |
| 4 | `apps/api/narrare/setup/provider_service.py:235-247` — `_test_call` branches | Python control flow | 7 + endpoint selector |
| 5 | `packages/core/narrare_core/settings.py:61-68` — provider `*_api_key` fields | settings fields | 6 fields, 7 env vars (`gemini_api_key` aliases `google`) |
| 6 | `packages/core/narrare_core/llm/_providers/registry.py:68-81` — `_PROVIDER_PREFIXES` | Python heuristics | 6 prefixes → 6 providers |
| 7 | `packages/core/narrare_core/llm/model_listing.py:62-64` — `SUPPORTED_CATALOG_PROVIDERS` | Python `frozenset` | 7 |
| 8 | `packages/core/narrare_core/llm/model_listing.py:207-223` — `_dispatch` if-chain + `_fetch_*` ×7 | Python control flow | 7 |
| 9 | `packages/core/narrare_core/llm/model_pricing.py:14-24` — `DEFAULT_RATES` keys | Python dict | 7 |
| 10 | `packages/core/narrare_core/llm/_providers/cache_settings.py:32-42` — `match` arms | Python control flow | 6 + wildcard |
| 11 | `packages/core/narrare_core/memory/mem0_client.py:29-34` — `_PROVIDER_DEFAULT_MODELS` keys | Python dict | 4 |
| 12 | `packages/core/narrare_core/llm/_model_listing_test_catalog.py:35-57` — `_TEST_CATALOG` keys | test stub | 7 |
| 13 | `packages/web/types/wizard.ts:3-10` — `AIProvider` | TS union | 7 |
| 14 | `packages/web/lib/providers.ts:4-12` — `PROVIDERS` | TS data | 7 |
| 15 | `packages/web/components/studio/settings/ProviderForm.tsx:8-14` — `PROVIDER_OPTIONS` | TS data | **5** ← the defect |

`scripts/check_model_registry.py` is the closest existing guard. It compares
*model IDs* extracted from `packages/core/narrare_core/llm/_providers/*.py`
against models.dev. It never compares the *provider set*, so it cannot catch any
disagreement in the table above.

### Root cause (2× why)

1. *Symptom:* the settings provider dropdown offers five providers; the wizard
   offers seven; the backend accepts seven.
2. *Why?* The provider set is **declared**, not **derived**. Fifteen independent
   declarations in two languages are each maintained by hand, so the set can
   disagree with itself indefinitely.
3. *Why is that the actual cause?* There is no canonical artifact that every
   declaration is computed from, and no check compares the declarations with one
   another. A redundant declaration that nothing reconciles can only be kept
   consistent by discipline — and discipline is exactly what an extra manual edit
   per surface discourages. The defect is the *absence of a derivation*, not the
   five-entry list, and not the missing `groq`/`zai` strings.

### Scope boundary

This ADR governs the **provider set** (which providers exist, how they are
spelled, which env var and settings field backs each one, which fetcher lists its
models, which fallback catalog it carries, whether its settings entry needs an
endpoint selector). It does **not** govern *model* identity: the per-provider
model lists stay where they are, and `check_model_registry.py` keeps its current
source of truth (`_FALLBACK_MODELS` values and `_providers/*.py` model
registrations), so that check's coverage is not silently reduced.

---

## Decision Drivers

- **RULE-17 (API ↔ frontend contract consistency):** the TS provider type must be
  a mirror of the backend type, not a second declaration of it. Today's defect is
  precisely a RULE-17 failure.
- **RULE-16 (i18n):** every user-facing string must be translatable. The
  provider *display labels* are user-facing strings; they may not live as raw
  English literals in a `.ts` array.
- **RULE-03 (contracts before implementation):** the catalog is the contract for
  the provider set; code is the implementation of it.
- **RULE-04 (split before you squeeze):** the generator must keep every produced
  file small and single-purpose.
- **RULE-01b / RULE-05 / RULE-07 (module boundaries, one-way dependencies):** the
  provider registry, catalog listing and pricing already live in
  `packages/core/narrare_core/llm/`; the canonical type must live there too, with
  `apps/api` and `packages/web` consuming it — never the reverse.
- **Pyright strict is the authoritative type gate** (`docs/development/quality-gates.md`
  G6, ADR-097): whichever Python representation is chosen must pass pyright strict
  with zero errors, because a representation that needs suppressions would
  violate RULE-09's spirit and RULE-23's ratchet.
- **No runtime file I/O on the request path:** the API imports the provider type
  at startup; a runtime-parsed YAML would turn a build-time mistake into a
  startup failure.
- **ADR-098 (single SSOT per concern):** the catalog is the SSOT for the provider
  *entity*, and the CI gate matrix keeps its own SSOT (ci.yml header +
  CONSTRAINTS §6). This ADR creates no third gate SSOT.

---

## Options Considered

### Option A — Runtime catalog load (YAML read and enum built at import time)

`catalog.yaml` stays the only file; a loader builds `AIProvider` (and the TS list,
via a Next.js loader) at runtime.

**Pros:** nothing generated is checked in, so the catalog cannot disagree with a
stale artifact; adding a provider is a one-file edit.

**Cons:** puts file I/O on the API import path; a malformed catalog becomes a
runtime startup failure instead of a commit-time failure; pyright cannot verify
attribute access on a dynamically built enum (measured below) so every
`AIProvider.GROQ` use degrades to `Unknown` under strict; the frontend cannot
import YAML without its own loader, and Next.js bundling of a YAML file that the
Python side owns couples the frontend build to the Python package layout;
`pydantic` schema generation for an enum built at import time is order-dependent
under the test suite's import order.

### Option B — Handwritten declarations plus a parity checker (no code generation)

Keep every declaration handwritten; add a check that compares all fifteen against
one written-down list.

**Pros:** no build step; no generated files in the repository; the checker is
small.

**Cons:** the redundancy stays — the checker only *detects* drift after an author
has written it, so the defect that motivated this ADR (a five-entry list shipping
to users) still has to be caught by the check on the same commit it is
introduced, which means every author must run the check locally; `AIProvider`, the
TS union and the TS list remain fifteen chances to be wrong; and the check needs
its own written-down list, which is a sixteenth declaration.

### Option C — Generated, checked-in artifacts from a catalog SSOT (chosen)

One `catalog.yaml` plus a generator that renders a Python module and a TS module
from it; both generated files are committed and verified byte-for-byte by the
generator's check mode.

**Pros:** every derived surface is computed, so it cannot disagree; the derivation
is visible in review (the generated diff is the catalog diff); pyright strict can
verify a class-syntax `StrEnum` (measured below); no runtime I/O; the frontend
imports a normal TS module, so `tsc --noEmit` and biome cover it; drift between
the catalog and the artifacts fails at commit time, not at import time.

**Cons:** two generated files are committed (review noise when the catalog
changes); the generator must emit format-clean output (ruff-formatted Python,
biome-clean TypeScript) or every catalog edit produces a second, formatting-only
diff; the generator itself is now a production script that needs tests.

### Option D — Status quo (no catalog, no check)

**Pros:** no work.

**Cons:** the defect class stays open. Two frontend lists already disagree with
each other and with the backend after a single provider addition; nothing in the
toolchain notices.

---

## Decision

**We choose Option C — a catalog SSOT with generated, checked-in artifacts.**
Binding sub-decisions:

1. **SSOT location and format.** `packages/core/narrare_core/llm/_providers/catalog.yaml`,
   YAML, one ordered list under a top-level `providers:` key. It lives beside the
   provider registry it describes (`packages/core/narrare_core/llm/_providers/`),
   inside the only package allowed to know provider specifics (RULE-01b), and
   under an underscore-prefixed package that is already treated as internal.
   Order in the file is the canonical display order of every derived list.

2. **Catalog fields** (exhaustive; every field is consumed by the generator or by
   the parity gate in `--check`):

   | Field | Type | Meaning |
   |-------|------|---------|
   | `id` | string | Canonical identifier — the `AIProvider` member value and the TS union member. Unique, lowercase, `[a-z0-9_]+`. |
   | `label_key` | string | i18n key resolving the display label, `settings-ai.providers.<id>`. Never a human-readable label (see point 5). |
   | `api_key_env` | string \| null | Environment variable name (e.g. `OPENAI_API_KEY`); `null` when the provider takes no key. Verified against ADR-071 §3 and `.env.example:35-50`: `CoreSettings` sets no `env_prefix`, so the provider keys use their plain upper-cased field names — only `NARRARE_*` fields carry a `validation_alias`. |
   | `settings_field` | string \| null | Name of the provider's field on `CoreSettings` (e.g. `openai_api_key`, `google_api_key`); `null` when the provider has none. Added to the mandated field list because point 4's parity gate cannot map provider → settings field without it (the `google` provider is backed by `google_api_key` with `gemini_api_key` as an accepted alias). |
   | `pydantic_ai_extra` | string | The pydantic-ai provider integration the factory reaches the provider through (`anthropic`, `openai`, `google`, `groq`, `ollama`, `openrouter`, `zai`). Closed literal set restated by the generator's validator; informational for setup docs and the ADR table — no `--check` compares it against the imports in `_providers/*.py`. |
   | `listing_strategy` | string | Name of the `ModelCatalogClient._fetch_<listing_strategy>` method that lists this provider's models. |
   | `pricing_default` | object | `{input, output}` USD per 1M tokens, mirroring `DEFAULT_RATES`. |
   | `cache_policy` | string | One of `anthropic_cache_control`, `automatic`, `none` — the prompt-caching behaviour `cache_settings.py` implements. |
   | `fallback_models` | list[string] | Model IDs that the bundled fallback catalog must offer for this provider. IDs only — model metadata stays in the API layer (see Scope boundary). |
   | `settings_editable` | bool | Whether the settings surface offers this provider as an add-key target. |
   | `requires_endpoint_selector` | bool | Whether the provider needs a second endpoint choice (Z.AI coding vs general endpoint; Ollama base URL). |

3. **Python side — one generated, checked-in class-syntax `StrEnum`.**
   `packages/core/narrare_core/llm/_providers/catalog_generated.py` is generated
   and defines `AIProvider(StrEnum)` in **class syntax**, plus `PROVIDER_IDS:
   tuple[str, ...]` and `PROVIDER_LABEL_KEYS: dict[AIProvider, str]` emitted as
   literals. The runtime-built functional form
   (`StrEnum("AIProvider", {...})`) is **rejected on measured evidence**, not on
   taste (see Rationale).

4. **TS side — one generated module, re-exported.**
   `packages/web/lib/providers.generated.ts` is generated and exports the
   `AIProvider` union type, `PROVIDER_IDS` (ordered `as const`) and
   `PROVIDER_LABEL_KEYS: Record<AIProvider, string>`. `packages/web/lib/providers.ts`
   keeps its public name and re-derives its `PROVIDERS` list from the generated
   module; `packages/web/types/wizard.ts` re-exports the generated union instead
   of declaring it.

5. **Labels are i18n keys, decided against RULE-16.** The catalog stores
   `label_key`, never a display string. The key is fully qualified:
   `settings-ai.providers.<id>` — `packages/web/lib/i18n/request.ts:65-68` mounts
   each message file under its own file stem as a top-level key
   (`messages["settings-ai"] = settings-ai.json`), so the namespace segment is
   `settings-ai`, not `settings` (`settings.json`'s `providers` entry is the
   unrelated section *title* string `"Providers"`, not an object — a
   `settings.providers.<id>` lookup would resolve against a string). Resolution for
   `--check` therefore reads `packages/i18n/messages/<locale>/settings-ai.json` and
   indexes `providers.<id>`; all seven keys already exist in `en`, `de` and `fr`
   (verified: `providers` holds `anthropic, google, groq, ollama, ollamaLocal,
   openai, openrouter, zai` in all three). The naive alternative — deriving labels
   from the catalog into `PROVIDER_OPTIONS` — would have added two *new* hardcoded
   English labels ("Groq", "Z.AI") to a component that already held five, deepening
   the RULE-16 violation while fixing the functional defect. The generator asserts
   that every `label_key` resolves in all three locales and fails the check
   otherwise.

6. **Generator.** `scripts/generate_provider_catalog.py`. Default mode writes both
   artifacts; `--check` renders both in memory, compares byte-for-byte with the
   committed files, and additionally evaluates the handwritten-surface parity
   invariants of point 7. Exit 0 = no drift; exit 1 = drift (with a per-surface
   diff-style report). The generator is stdlib + `yaml` only (both already
   installed) and must emit output that passes `ruff format --check`,
   `biome check`, `pyright` (strict) and `tsc --noEmit` unchanged.

7. **Derived versus handwritten — and what the gate enforces.** Surfaces that can
   be *computed* are computed; surfaces whose content is genuinely semantic
   (heuristics, HTTP shapes, control flow) stay handwritten and are *compared*
   against the catalog by `--check`:

   | Surface | Class after this ADR | Enforced by |
   |---|---|---|
   | `catalog_generated.py` (`AIProvider`, `PROVIDER_IDS`, `PROVIDER_LABEL_KEYS`) | **derived** (generated) | `--check` byte compare |
   | `packages/web/lib/providers.generated.ts` | **derived** (generated) | `--check` byte compare |
   | `model_listing.py:62` `SUPPORTED_CATALOG_PROVIDERS` | **derived** at import: `frozenset(p.value for p in AIProvider)` | import (drift impossible) |
   | `base_schemas.py:45-52` `AIProvider` | **re-export** of the generated enum | import; OpenAPI identity test |
   | `apps/api/narrare/setup/schemas.py:9,37` re-export | **unchanged** (re-exports through `base_schemas`) | import |
   | `types/wizard.ts:3-10` `AIProvider` | **re-export** of the generated union | `tsc --noEmit` |
   | `lib/providers.ts:4-12` `PROVIDERS` | **derived** from `PROVIDER_IDS` + `PROVIDER_LABEL_KEYS` | import, unit test |
   | `ProviderForm.tsx:8-14` `PROVIDER_OPTIONS` | **deleted** — component consumes `PROVIDERS` | regression test |
   | `_model_listing_test_catalog.py:35-57` `_TEST_CATALOG` | **keys derived** at import from `AIProvider` | import, parity test |
   | `registry.py:68-81` `_PROVIDER_PREFIXES` | handwritten | `--check`: `{values} ⊇ {ids}` |
   | `model_listing.py:207-223` `_dispatch` + `_fetch_*` | handwritten | `--check` (`scripts/generate_provider_catalog.py:check_fetchers`): `ModelCatalogClient._fetch_<listing_strategy>` exists for every id |
   | `model_pricing.py:14-24` `DEFAULT_RATES` | handwritten (values) | `--check`: key set == ids; values == `pricing_default` |
   | `cache_settings.py:32-42` `match` arms | handwritten | `--check`: arm set == ids; arm body == `cache_policy` |
   | `mem0_client.py:29-34` `_PROVIDER_DEFAULT_MODELS` | handwritten | `--check`: key set ⊆ ids and non-empty |
   | `settings.py:61-68` api_key fields | handwritten | `--check`: `settings_field` is a real field, `api_key_env` matches its `validation_alias`/uppercased name |
   | `provider_service.py:32-78` `_FALLBACK_MODELS` | handwritten (values) | `--check`: key set == ids; IDs == `fallback_models` |
   | `provider_service.py:235-247` `_test_call` | handwritten | `--check`: an endpoint branch exists for every `requires_endpoint_selector: true` provider |

   The gate is one-directional: `requires_endpoint_selector: true → false` is
   **not** detectable, because the flag removes a requirement instead of breaking
   one, so no violation is produced. A change in that direction is a review
   obligation, not a gate failure.

8. **Wiring (exact placement).**
   - pre-commit: a new hook `provider-catalog-check` in `.pre-commit-config.yaml`
     with `entry: uv run --no-sync python scripts/generate_provider_catalog.py --check`,
     `pass_filenames: false`, `always_run: true`, `stages: [pre-commit]`. Rationale
     for `always_run` rather than a `files:` filter: the gate must also fire when a
     *handwritten* surface (`settings.py`, `mem0_client.py`, `model_pricing.py`,
     `provider_service.py`) changes without the catalog changing. The pass is a
     single YAML parse plus two string renders.
   - local architecture surface: one added line in the `check-architecture` recipe
     in the `justfile`, immediately after the `check_prompt_surface_contract.py`
     line.
   - CI: one added step in the **architecture job** of
     `.github/workflows/ci.yml`, immediately after the existing
     `Check prompt surface contract (ADR-037 + ADR-049 Phase D)` step (ci.yml:549-550).
     No new gate-matrix row: this is a step of G3d's job, exactly as
     `check_prompt_surface_contract.py` is a step and not a row.

9. **Back-compatibility.** `AIProvider` stays importable from
   `apps/api/narrare/setup/base_schemas.py` and from
   `apps/api/narrare/setup/schemas.py`; the enum's `__name__` stays `AIProvider`,
   so the OpenAPI component in `docs/reference/openapi.json`
   (`components.schemas.AIProvider`, `title: "AIProvider"`, seven-value `enum`)
   is unchanged and `export_openapi.py --check` stays green;
   `packages/web/types/index.ts:223` keeps re-exporting the type.

---

## Rationale

**Why generation, and why checked in.** Every surface in the table of point 7 is
a restatement of one fact: which providers exist and how they are spelled. The
defect exists because restatements are free to disagree. Generating the two type
modules makes the two *type* declarations impossible to disagree with the
catalog, and `--check` turns the remaining handwritten surfaces into assertions
about the catalog rather than copies of it. Checking the artifacts in (instead of
generating at build time) is what lets pyright, ruff, biome and `tsc` cover them
with the same gates as hand-written code, and it makes the derivation visible in
code review.

**Why the functional `StrEnum` form was rejected — measured.** The obvious way to
avoid generating Python is to build the enum at runtime:
`AIProvider = StrEnum("AIProvider", {name: value for ...})`. That was tested
before this decision was written, under the project's own strictness settings
(`pythonVersion` 3.14; `reportUnknownMemberType`, `reportUnknownVariableType`,
`reportUnknownArgumentType` on) in `/tmp/opencode/enumprobe/`:

- Runtime-built functional `StrEnum` + `AIProvider.OPENAI.value`: **6 pyright
  errors**, including
  `error: Cannot access attribute "OPENAI" for class "StrEnum"` (`reportAttributeAccessIssue`),
  `Type of "OPENAI" is unknown`, `Type of "value" is unknown`,
  `Return type is unknown`, and iteration yielding `str` rather than the enum type.
- Generated **class-syntax** `StrEnum`: **0 errors, 0 warnings, 0 informations.**

The functional form would have pushed suppressions into every call site that
touches a provider (RULE-23 ratchet growth) and destroyed the type information
that makes `AIProvider` worth having. The check is therefore not "generated vs
runtime" but "generated class syntax" — the only form that survives the gate the
project already enforces.

**Why the catalog is YAML and not Python.** A Python catalog would have to be
imported by the generator and by the API; the TS side would then need a Python
parser or a second declaration. YAML is a data format that both languages parse
with an already-present dependency (`yaml` for the generator; the TS artifacts are
generated, so the frontend never parses YAML at all).

**Why labels are keys and not strings (RULE-16).** The tempting fix — read the
`label` field from the catalog straight into the dropdown — reproduces the
original sin in a new place: two hardcoded English labels appear where there were
five. Provider names are user-facing text; they belong in
`packages/i18n/messages/{en,de,fr}/settings-ai.json`, which already carries all
seven keys. The catalog carries the *key*, and the generator proves the key
exists in all three locales.

**Why the parity gate covers handwritten surfaces at all.** Without it, the gate
would only prove that the two generated files match the catalog — the same class
of hole that let `_FALLBACK_MODELS`, `DEFAULT_RATES` and `_PROVIDER_PREFIXES`
diverge from `AIProvider` today. The invariants in point 7 are deliberately
*set- and existence-based* (key sets, arm coverage, field existence), never
value-format-based, so the gate does not become a second, brittle copy of the
source files.

**Accepted tradeoff.** `catalog.yaml` becomes a file every provider change must
edit, and two generated files appear in the diff of such a change. That is one
edit plus two mechanical ones, replacing fifteen manual ones — and the two
mechanical ones cannot be forgotten, because the gate fails.

---

## Consequences

**Positive:**

- The provider set has exactly one authoring location; the defect class (a
  surface silently missing a provider) is closed structurally, not patched.
- `AIProvider` (Python) and the TS union become incapable of disagreeing, which is
  RULE-17 satisfied by construction rather than by review.
- Adding a provider becomes: edit `catalog.yaml`, run the generator, satisfy the
  parity report for the surfaces that legitimately need a human decision
  (prefix heuristic, fetcher, cache policy, pricing, fallback models, settings
  field). The report tells the author which ones are missing instead of failing
  with a bare mismatch.
- The provider display labels finally obey RULE-16: three locales, one key per
  provider, no English literals in a component array.
- The OpenAPI provider enum and the wizard/settings dropdowns are pinned to the
  same ordered list.

**Negative / Tradeoffs:**

- Two generated files are committed; every provider change carries a mechanical
  diff beside the human one. Accepted: the mechanical diff is the evidence that
  the derivation ran.
- The generator must emit format-clean output. This is a real constraint on the
  generator's implementation (its templates are effectively lint-clean code
  templates) and it is the first thing that will break when ruff or biome changes
  its formatting rules. Mitigation: the generator formats its Python output
  through `ruff format` semantics maintained by hand, and the regression test
  asserts the emitted bytes equal the committed bytes — so a ruff/biome change
  surfaces as a red `--check` on the next commit, with the fix being a
  regeneration, not a diagnosis.
- `_PROVIDER_PREFIXES`-style heuristics cannot be derived; a provider with an
  ambiguous prefix still needs a human edit. The gate's `⊇` invariant (rather
  than `==`) is deliberate: it catches omission without forbidding extra prefixes.
- The catalog is a third file a provider addition must touch, after the two it
  already touches today (enum + fetcher). The count of *decisions* goes down even
  though the count of *edits* at the catalog site goes up by one.

**Constraints introduced:**

- RULE-01b / RULE-05 / RULE-07: the catalog and its generated Python module live
  in `packages/core/narrare_core/llm/_providers/`; `apps/api` and `packages/web`
  consume, never declare. A provider string literal elsewhere than the catalog,
  its generated artifacts, or a surface named in point 7 is a defect.
- RULE-17: the TS provider type is derived, never declared. `types/wizard.ts` may
  re-export it; it may not restate it.
- RULE-16: provider display labels exist only as i18n keys; no component may
  carry a provider label as a literal.
- New local rule (this ADR): the generated `AIProvider` must stay class syntax. A
  future author "simplifying" it to the functional form inherits the six pyright
  errors and the RULE-23 ratchet growth; this is recorded here so the change is
  recognizably a regression.
- ADR-098 is preserved: this ADR adds no gate SSOT. The CI step is a step inside
  the existing architecture job, and the only written-down invarants live in
  `scripts/generate_provider_catalog.py`.

---

## Implementation Notes

**Files created by the implementation wave (none touched by this ADR):**

- `packages/core/narrare_core/llm/_providers/catalog.yaml` — the SSOT.
- `packages/core/narrare_core/llm/_providers/catalog_generated.py` — generated
  `AIProvider` + `PROVIDER_IDS` + `PROVIDER_LABEL_KEYS`; must carry a
  `# AUTO-GENERATED by scripts/generate_provider_catalog.py — DO NOT EDIT` header.
- `packages/web/lib/providers.generated.ts` — generated union + `PROVIDER_IDS` +
  `PROVIDER_LABEL_KEYS`; same header, `//` comment form.
- `scripts/generate_provider_catalog.py` — the generator with `--check`.

**Files modified:**

- `apps/api/narrare/setup/base_schemas.py` — the `AIProvider` class body is
  replaced by a re-export; `StoryStructure`, `StoryTone`, `StarterContent` and the
  Step 1–3 schemas are untouched.
- `packages/core/narrare_core/llm/model_listing.py` — `SUPPORTED_CATALOG_PROVIDERS`
  becomes derived; `_dispatch` and the `_fetch_*` methods are unchanged.
- `packages/core/narrare_core/llm/_model_listing_test_catalog.py` — catalogue keys
  derived from `AIProvider`. **Import note:** this module exists to break a
  circular import with `model_listing.py`; it must import from
  `catalog_generated`, never from `model_listing`.
- `packages/web/lib/providers.ts` — `PROVIDERS` derived; `getProviderLabel` takes
  a translator and resolves the label key, falling back to the raw value for
  unknown providers. `packages/web/lib/providers.test.ts` moves with it: its
  seven hardcoded English assertions become key assertions
  (`settings-ai.providers.<id>`), and its unknown-provider behaviour is preserved.
- `packages/web/types/wizard.ts` — `AIProvider` becomes a re-export.
- `packages/web/components/studio/wizard/WizardStep4.tsx` — option labels resolve
  through the translator against the derived list.
- `packages/web/components/studio/settings/ProviderForm.tsx` — `PROVIDER_OPTIONS`
  is deleted; the select consumes the shared derived list with resolved labels.
  **This is the defect-closing edit.**
- `.pre-commit-config.yaml`, `justfile`, `.github/workflows/ci.yml` — the wiring of
  point 8.
- `docs/architecture/decisions/INDEX.md` — one new row for ADR-099 (see the
  completeness checklist; this ADR's own file was written before its index row).

**Regression evidence for the defect (binding).** A component test at
`packages/web/components/studio/settings/__tests__/ProviderForm.test.tsx` asserts
that the add-mode provider select renders exactly the seven catalog ids in
canonical order — `["anthropic","openai","google","groq","ollama","openrouter","zai"]`
— and that at least the `groq` and `zai` options carry their translated labels.
Before the fix the assertion fails with five values, which is the recorded RED.

**ADR Implementation Completeness.** This ADR is not implemented until it is
fully wired, tested, consumed, and documented. Binding checklist:

1. `catalog.yaml` exists and the generator renders `catalog_generated.py` and
   `providers.generated.ts` byte-identically to the committed files.
2. `AIProvider` is importable from `apps/api/narrare/setup/base_schemas.py`,
   `apps/api/narrare/setup/schemas.py` and `packages/web/types/index.ts`; pyright
   strict passes with no new suppressions (RULE-23 baseline unchanged).
3. `docs/reference/openapi.json` still declares `components.schemas.AIProvider`
   with the same seven values, and `export_openapi.py --check` is green.
4. `ProviderForm.test.tsx` passes and its pre-fix run was recorded as RED with
   five options.
5. Every parity invariant of point 7 is implemented in `--check` and covered by a
   unit test that fails when the invariant is broken (one deliberate mutation per
   invariant is the test technique; no invariant may be asserted only against the
   pristine tree).
6. The pre-commit hook, the `check-architecture` recipe line and the ci.yml
   architecture-job step are present and green.
7. Each task of the implementation plan has its report under
   `docs/superpowers/plans/reports/2026-10-19-throughput-TNN.md`.
8. **Cannot be produced locally:** a green CI run of the architecture job on the
   wave's pull request, with the new provider-catalog step visible in the job log.
   The status flips to ✅ only after that run exists.

---

## Review Trigger

- [ ] After 6 months: if the parity gate has never failed on a real change, check
      whether the handwritten invariants of point 7 still earn their complexity.
- [ ] When a provider is added or removed: confirm the change touched exactly
      `catalog.yaml`, the two regenerated artifacts, and the handwritten surfaces
      the parity report named — nothing else.
- [ ] When `check_model_registry.py` changes its model-ID source: verify it did not
      start scanning `catalog_generated.py` while the fallback model metadata still
      lives in `provider_service.py` (the scope boundary above must hold or be
      re-decided).
- [ ] When ruff, biome, or pyright changes formatting or strictness in a way that
      makes the generated output unformatted: regenerate with the new rules and, if
      the generator needed logic changes, record them here.
- [ ] If a second generated artifact family is proposed (prompts, intents): decide
      whether it shares this generator and gate or needs its own ADR — do not
      silently widen `scripts/generate_provider_catalog.py`.
