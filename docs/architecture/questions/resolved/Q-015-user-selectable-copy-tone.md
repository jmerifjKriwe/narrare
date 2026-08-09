# Q-015 — User-Selectable UI Copy Tone (Familiar vs. Neutral)

> **Status:** ✅ Resolved (2026-08-08) — **→ Feature Spec [I-Copy-001](../../features/i18n/I-Copy-001-formality-register.md) (Overlay-Merge)**. PO re-approved after external-AI consultation (2/3 recommended Overlay-Merge) confirmed the infrastructure is low-effort and duplication-free. The one real cost is editorial (~150–300 formal DE/FR variants).
> **Blocks:** Nothing (documented only — a default already exists in `PRODUCT.md`)
> **Raised:** 2026-08-05 · **Re-approved:** 2026-08-08
> **Source:** Brand Workshop (Product Owner)

---

## Question

Should users be able to choose the formality register of the UI copy —
familiar ("Weiter geht's") vs. neutral ("Kapitel fortsetzen")?

## Context

In the Brand Workshop the Product Owner identified a real product
opportunity: letting users choose the tone of the UI copy, e.g. familiar
address (*duzen*, "Weiter geht's") vs. neutral/formal address (*Siezen*,
"Kapitel fortsetzen"). Their initial concern was high implementation
effort: a full i18n change would mean every message string × 2 variants ×
3 languages (en/de/fr) in `packages/i18n/messages/`.

The Coordinator proposed a lean path (below) to capture the opportunity
without a full i18n explosion. This question is documented so the
opportunity is not lost, while blocking nothing in the meantime.

## Proposed Lean Path

- **Scope the duplication:** only interactive, tone-sensitive strings get a
  second variant — buttons, success messages, errors, dialogs. Description
  and help texts stay neutral regardless of the selected tone.
- **Technical shape:** a `formality` key in the user settings plus a variant
  suffix in the message key; resolution happens in the i18n layer
  (next-intl). No new translation framework, no string duplication outside
  the tone-sensitive subset.
- **Boundary:** this affects UI copy only — no influence on prompt texts
  (`core/prompts/`, RULE-01b/02 territory) or AI-generated content.

## Affected Areas

- `packages/web` — Settings UI (tone picker), UI copy usage
- `packages/i18n` — messages (variant-suffixed keys)
- `apps/api` — UserSettings schema (new `formality` field), if persisted server-side

## Default Until Decided

Default is informal (*duzen*), functional — documented in
`packages/web/PRODUCT.md` under **## Brand Commitments** ("Tone: Informal
(du/Sie-form duzen), functional"). The same document already lists
user-selectable tone as an open product question and points here.

## Next Step

→ **Feature Spec [I-Copy-001](../../features/i18n/I-Copy-001-formality-register.md) created
(2026-08-08).** Implementation handoff → Frontend specialist (see HANDOFF block at the bottom of
this file).

## Related

- `packages/web/PRODUCT.md` — **## Brand Commitments** (default: informal, functional)
- Q-013 — i18n tone drift in bundled prompts (related formality-register topic on the prompt side; this question is UI-copy-only)
- `docs/development/ui-principles.md` — UI copy conventions

---

## Resolution — → Feature Spec I-Copy-001 (Overlay-Merge); PO re-approved

> **Status:** ✅ Resolved (2026-08-08) — Feature Spec **[I-Copy-001](../../features/i18n/I-Copy-001-formality-register.md)**
> created (Overlay-Merge architecture). The Product Owner re-approved after consulting three
> external AIs (`_scratch/ki_21.md`, `_scratch/ki_22.md`, `_scratch/ki_23.md`): **2 of 3 strongly
> recommended an Overlay-Merge approach** that is genuinely low-effort on infrastructure and has
> zero call-site churn / zero duplication of the base catalog.
> **Documentation:** Feature Spec + this question file. No ADR (frontend-only loader concern; no
> new dependency, no RULE-XX exception — the Overlay-Merge pattern is documented in the spec's
> "Options Considered" per architectural-discipline §3).

### Why the verdict changed (Round 1 → now)

Round 1 assessed Q-015 as "feasible but **not low-effort**" under the architecture it was
analysing: a **suffix-key resolver** (`key_formal`) + a `useFormalityTranslations` wrapper hook +
migration of every tone-sensitive call site (~200–300 sites). That assessment was **correct for
that architecture** — it genuinely requires a new abstraction and call-site migration.

The Product Owner then consulted three external AIs. Two (`ki_21`, `ki_23`) converged on a
fundamentally different architecture — **Overlay-Merge** — that moves the concern one layer
*before* next-intl (into the existing message loader `lib/i18n/request.ts`), so `next-intl`, every
component, and every `t("key")` call site stay byte-identical. Under Overlay-Merge the
infrastructure is small (one recursive merge helper + a cookie read + sparse overlay files + CI
assertions) and there is **zero** call-site migration. The PO's precondition ("low effort + no
duplication") is therefore **met on the technical side**. The one cost that survives under *any*
architecture is editorial (authoring/reviewing the formal DE/FR variants) — see "Editorial cost" in
the spec.

### §7 verification of the Overlay-Merge approach (reality, not claims)

The brief was verified against the actual code, not trusted as stated:

1. **The loader seam exists exactly as described.** `packages/web/lib/i18n/request.ts` loads
   flat-per-namespace JSON into a `messages` object and returns `{ locale, messages }` to next-intl.
   Merging an overlay into `messages` before the return is a minimal, well-placed change. ✅
2. **`next-intl` is genuinely unaware** — components call `useTranslations("ns")` / `t("key")`
   against the request-prepared `messages`; merging upstream is transparent to them. ✅
3. **Deep-merge is REQUIRED, not optional — verified.** `packages/i18n/messages/de/settings.json`
   contains nested objects (`"themes": { "light", "dark", "system" }`). A shallow merge would
   drop a sibling sub-tree when an overlay overrides a key. The spec mandates a small recursive
   merge helper with unit tests. (Round 1/the external AIs flagged this as "verify whether
   namespaces nest" — they do, so deep-merge it is.)
4. **The AST governance test exists and is extensible.** `packages/web/__tests__/i18n-namespace-registry.test.ts`
   already enforces i18n conventions by scanning files; the spec extends it with orphan-override +
   de/fr-parity + no-en-overlay assertions. The governance precedent holds. ✅
5. **The naming collision is real and is respected.** `tone` / `StoryTone` / `tones.*`
   (`lib/constants/tones.ts`, surfaced via the `studio` namespace) is an existing domain concept.
   The setting is named **`formality`** — no collision. ✅
6. **The RULE-02 boundary holds.** UI copy (`packages/i18n/messages/`) is fully separate from
   prompt templates (`packages/core/.../prompts/_bundled/`). A loader-level UI setting cannot reach
   `core/prompts/`. ✅

### Why Overlay-Merge beat ICU-select (documented per §3)

ICU `{formality, select, informal {…} formal {…} other {…}}` is native to next-intl and type-safe,
but ICU arguments are resolved per-`t()` call — next-intl has **no global ICU-value injection**.
Every tone-sensitive call site would need `t("key", {formality})` (or a wrapper-hook that injects
it): ~200–300-site churn + a new abstraction leaking into components. Overlay-Merge keeps the
concern at the loader layer with **zero** call-site changes. The full comparison (Overlay vs. ICU
vs. suffix-resolver vs. full-formal-catalogs vs. locale-variants) is in the spec's
**Options Considered** table.

### Round-1 findings that carry forward (still valid)

These were verified in Round 1 and remain requirements the Frontend specialist must honour:

- **Default = informal** (`PRODUCT.md` "Brand Commitments"). The feature adds the **formal**
  variant as opt-in; existing informal copy is the unchanged default — no migration needed.
- **`formality` (not `tone`)** for the setting name (collision with `StoryTone`).
- **English unchanged** — en has no du/Sie distinction; one "you". No `formality/en.json`.
- **Cookie-only persistence (v1)** — `NEXT_FORMALITY` cookie, analogous to the existing
  `NEXT_LOCALE` cookie, set by a Settings toggle mirroring the locale-switcher. **No backend
  `UserSettings.formality` field, no Alembic migration** for v1 (this is a real simplification
  over the Round-1 suffix-resolver estimate, which assumed a SET-001 change).

### Editorial cost (the one real price — unchanged across architectures)

Authoring and reviewing the formal variants: conservatively ~150–300 differing strings per
language for `de` and `fr` (the full-sentence, second-person/salutation subset; single-word
imperatives like "Speichern"/"Abbrechen" are tone-neutral and excluded). This is the cost of the
**content**, identical under Overlay-Merge, ICU, or suffix-keys — plan editorial time for it.

### Implementation handoff → Frontend specialist

See the **HANDOFF** block at the bottom of this file.

---

> **Status:** ✅ Resolved (2026-08-08) — **→ Feature Spec [I-Copy-001](../../features/i18n/I-Copy-001-formality-register.md)
> (Overlay-Merge)**. PO re-approved after external-AI consultation (2/3) confirmed low-effort
> infrastructure + zero duplication. Loader-level deep-merge of a sparse `formality/{locale}.json`
> overlay; `next-intl` + all call sites untouched; `en` unchanged; setting = `formality`;
> cookie-only persistence (no backend/migration v1); RULE-02 boundary verified. The one real cost
> is editorial (~150–300 formal DE/FR variants). Round-1 "not low-effort" verdict applied to the
> suffix-resolver architecture only; Overlay-Merge meets the PO precondition.

---

## HANDOFF → Frontend specialist

> **Spec:** `docs/features/i18n/I-Copy-001-formality-register.md`. **No ADR** (frontend-only loader
> concern; documented Options-Considered). **No backend work for v1** (cookie-only — no SET-001
> change, no Alembic migration). This is a pure `packages/web` + `packages/i18n` feature.

### Goal
Let the user choose the UI formality register (familiar default / neutral opt-in) for `de` and
`fr`; `en` unchanged. Resolve it one layer before next-intl via a sparse overlay deep-merged at
load time. Zero call-site migration.

### Architecture (from the spec — read it in full)
- **Loader:** `packages/web/lib/i18n/request.ts` — read `NEXT_FORMALITY` cookie; when
  `locale !== "en" && formality === "formal"`, deep-merge `packages/i18n/overlays/formality/{locale}.json`
  over the base `messages`. (Overlays live under `overlays/formality/`, **not** `messages/` —
  `messages/` is reserved for locales only, so `validate-i18n` treats `formality` as a register,
  not a locale.)
- **Overlay shape:** `{namespace: {key: "formal variant"}}` — sparse; existing strings ARE the
  informal default. New `packages/i18n/overlays/formality/de.json` + `…/fr.json`.
- **Merge:** a small, **tested recursive** merge helper `lib/i18n/mergeOverlay.ts` (~15–25 LOC).
  Deep-merge is mandatory — `settings.json` has nested objects (`themes`); verify the helper
  preserves sibling leaves when overriding one nested key.
- **Setting:** `type Formality = "informal" | "formal";` (default `"informal"`). Name it
  **`formality`**, never `tone`.
- **Persistence:** `NEXT_FORMALITY` cookie, set by a Settings toggle that mirrors the existing
  locale-switcher pattern.

### RULE-02 boundary (critical invariant)
This setting is **UI-copy-only**. It MUST NOT reach `core/prompts/`. The loader-only design keeps
it airtight. Do not wire `formality` into any prompt context, agent deps, or the cascade.

### Governance (extend the existing AST test)
Extend `packages/web/__tests__/i18n-namespace-registry.test.ts`:
1. every overlay key path resolves to a base key (no orphaned overrides);
2. de/fr overlay key-path sets match (parity);
3. no `formality/en.json` exists (en byte-identical).
Add `packages/web/__tests__/i18n-mergeOverlay.test.ts` (flat + nested + leaf-only-override cases).

### Editorial cost
Author + review the formal variants for `de` and `fr` (~150–300/lang). This is the bulk of the
real effort — budget time for it. Single-word tone-neutral labels are excluded.

### Acceptance / DoD
Per the spec's "Acceptance criteria": cookie read + deep-merge + helper tests + populated overlays +
Settings toggle + extended governance test + en byte-identical + zero call-site changes + zero
`core/prompts/` changes + frontend tests green + `just check` green.

### Risks
- **Deep-merge correctness** is the main technical risk — unit-test it against the real nested
  shapes (`settings.themes` and any other nested namespace found by scanning the message files).
- If server-side cross-device persistence is later wanted, add `UserSettings.formality` (SET-001) +
  migration then — explicitly **out of scope for v1**.
