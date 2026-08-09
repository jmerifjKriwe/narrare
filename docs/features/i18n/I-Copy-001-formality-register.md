---
id: I-Copy-001
title: "User-Selectable UI Formality (du / Sie)"
status: planned
area: i18n
mvp: false

ui_tooltip: "Choose whether Narrare addresses you with the familiar or the neutral register."
ui_help_short: |
  Wähle, wie Narrare dich anspricht: vertraut (du) oder sachlich-neutral (Sie / vous).
  Betrifft nur die Benutzeroberfläche — niemals die KI-Ausgabe oder deine Geschichte.
ui_help_long: |
  ## Ansprechen wählen (du / Sie)

  Narrare kann die Benutzeroberfläche in zwei Anrede-Registern anzeigen:
  **vertraut** (*duzen*, „Weiter geht's") oder **neutral** (*Siezen* / *vouvoiement*,
  „Kapitel fortsetzen"). Standard ist vertraut — passend zu `PRODUCT.md`.

  **Was es macht:**

  - Schaltet die ton-sensitiven UI-Texte (Vollsätze, Dialoge, Erfolg-/Fehlermeldungen)
    zwischen den beiden Varianten um.
  - Trefferneutrale Labels (Speichern, Abbrechen, Löschen) bleiben in beiden Registern
    identisch — sie werden nicht verdoppelt.
  - Wirkt sich **nur auf UI-Texte** aus — niemals auf Prompts (`core/prompts/`) oder
    KI-generierte Inhalte.

  **Was es nicht macht:**

  - Kein Einfluss auf die Sprache der KI-Ausgabe.
  - Englisch hat keine du/Sie-Unterscheidung — daher ist `en` in beiden Registern
    byte-identisch.
  - Keine Verdopplung des gesamten Übersetzungskatalogs: nur die tatsächlich
    abweichenden Formulierungen werden als dünnes Overlay gepflegt.

service: packages/web/lib/i18n/request.ts
contract: (none — frontend-only loader concern; next-intl is untouched)
router: (none — no backend endpoint for v1; cookie-persisted)
prompt: (none — RULE-02 boundary: this setting MUST NOT reach core/prompts/)
requires: []
---

# I-Copy-001 — User-Selectable UI Formality (du / Sie)

> **Architecture owner:** Architecture Specialist. **Source:** Q-015 (resolved → this spec).
> **PO status:** Re-approved for implementation after external AI consultation confirmed the
> infrastructure is low-effort (Overlay-Merge variant). See "Editorial cost" for the one real
> cost block that remains.

## What it does

Lets the user choose the formality register of the UI copy — familiar (*duzen*, *tutoyer*) vs.
neutral (*Siezen*, *vouvoiement*) — for the `de` and `fr` locales. English is unchanged (it has no
formality distinction). The switch is a thin concern handled **one layer before next-intl**, in the
existing message loader. Existing components, the `useTranslations`/`getTranslations` API, and every
call site stay 100 % untouched.

## Why it exists

The Product Owner identified a real product opportunity (Brand Workshop / Q-015): some writers
prefer a familiar address, others a neutral-professional one. `PRODUCT.md` already commits to
**informal as the default**; this feature adds the **formal** variant as an opt-in, without
disturbing the default or duplicating the entire message catalog.

Round 1 of Q-015 assessed the feature as "feasible but not low-effort" under a suffix-key +
resolver-hook architecture. The Product Owner then consulted three external AIs; two strongly
recommended an **Overlay-Merge** approach that is genuinely low-effort on infrastructure and has
zero call-site churn. This spec specifies that approach.

## How it works (User perspective)

1. Open **Settings → Appearance** (or the existing language/locale area).
2. Pick **Anrede** (Address): *Vertraut (du)* [default] or *Neutral (Sie)*.
3. The ton-sensitive UI copy (full sentences, dialogs, success/error messages) swaps to the chosen
   register. Tone-neutral labels stay the same.
4. The choice persists across reloads (a cookie, analogous to the language cookie) and applies to
   `de` and `fr` only. English looks identical either way.

## How it works (Technical) — the Overlay-Merge architecture

Formality is resolved **one layer before next-intl**, in `packages/web/lib/i18n/request.ts` (the
existing message loader). `next-intl` and every component remain unaware that anything was merged.

### Data flow

```
                  NEXT_FORMALITY cookie (default "informal")
                          │
   locale (de|fr|en)      │
        │                 │
        ▼                 ▼
   load base messages   (locale !== "en" && formality === "formal")?
   messages/{locale}/{ns}.json
        │                 │ yes
        │                 ▼
        │     load sparse overlay overlays/formality/{locale}.json
        │                 │
        └────────┬────────┘
                 ▼
        DEEP-MERGE overlay over base   ← deep-merge is required (nested objects exist — verified)
                 │
                 ▼
           { locale, messages }  ← next-intl sees a normal message object
                 │
                 ▼
        useTranslations("ns") / t("key")   ← UNCHANGED at every call site
```

### The overlay

One sparse file per non-en locale, structured to mirror the `messages` object
(`{namespace: {key: value}}`):

```
packages/i18n/overlays/formality/
├── de.json
└── fr.json
```

Each file stores **only** the formal variants of keys whose copy actually differs in the formal
register. The existing message strings ARE the informal/default variant (matches `PRODUCT.md`:
default = *duzen*). A key absent from the overlay falls through to the base (unchanged). Example:

```jsonc
// packages/i18n/overlays/formality/de.json
{
  "common": {
    "next": "Bitte fortfahren"
  },
  "wizard": {
    "finish": "Assistenten abschließen"
  }
}
```

- `common.save` / `common.cancel` / `common.delete` are tone-neutral in DE/FR → **not** listed
  (they fall through unchanged).
- A new string added to the base catalog works for both registers immediately; it is added to the
  overlay only when someone decides its formal wording must differ (opt-in semantics).

### Deep-merge is required (verified — not assumed)

`packages/i18n/messages/de/settings.json` contains nested objects (e.g. `"themes": { "light": …,
"dark": …, "system": … }`). A shallow merge would **drop the entire `themes` sub-tree** when an
overlay overrides a sibling key. The merge MUST be a recursive/nested merge so an overlay leaf
(e.g. `settings.themes.light`) replaces only that leaf and preserves the rest of the namespace.
A small, tested recursive merge helper (~15–25 LOC) is the correct primitive — do NOT pull a
deep-merge dependency for this (no new dependency without an ADR; a tiny owned helper is simpler
and auditable). The helper lives alongside `request.ts` (e.g. `lib/i18n/mergeOverlay.ts`).

### Setting name + persistence

- **Setting name: `formality`** — NOT `tone`. `tone` / `StoryTone` / `tones.*` is an existing
  domain concept (the story's narrative tone — `lib/constants/tones.ts`, surfaced via the `studio`
  namespace). Reusing `tone` would collide. `formality` is unambiguous and matches the external-AI
  recommendation.
- **Type:** `type Formality = "informal" | "formal";` (default `"informal"`).
- **Persistence (v1, cookie-only):** a `NEXT_FORMALITY` cookie, set by a Settings toggle that
  mirrors the existing locale-switcher pattern (the loader already reads `NEXT_LOCALE` via
  `cookies()`). **No backend change, no `UserSettings.formality` field, no Alembic migration** for
  v1 — this keeps the feature fully frontend and is the reason the infrastructure is low-effort.
  Server-side persistence (SET-001 `UserSettings.formality`) can be added later if cross-device
  sync is wanted; it is explicitly out of scope for v1.
- Reading the cookie already makes the route dynamic (the locale cookie does the same today) — no
  new dynamic-rendering concern is introduced.

### CI governance (extend the existing AST test)

Extend `packages/web/__tests__/i18n-namespace-registry.test.ts` with overlay assertions:

1. **No orphaned overrides:** every overlay key path (`{ns}.{...path}`) must resolve to a key that
   exists in the corresponding base namespace (`packages/i18n/messages/{locale}/{ns}.json`). A typo
   or a key removed from the base must fail CI.
2. **de/fr parity:** the set of override key-paths in `overlays/formality/de.json` and `overlays/formality/fr.json`
   must match (the same strings need a formal variant in both languages). Report the diff on
   failure.
3. **en stays out:** no `overlays/formality/en.json` is created (en is byte-identical). A test asserts the
   file does not exist (or is empty) so no one adds redundant en overrides.

These mirror the precedent the namespace-registry test already sets for i18n conventions.

## Options Considered (architectural-discipline §3)

| Option | New infra | Call-site changes | Duplication | Verdict |
|--------|-----------|-------------------|-------------|---------|
| **A — Overlay-Merge (chosen)** | small (1 merge helper + cookie read + overlay files + CI assertions) | **0** | bounded: only de/fr formal-only leaves (~150–300/lang) | ✅ Chosen |
| B — ICU `{formality, select, …}` in strings | smallest (native next-intl) | **~200–300** (`t("key", {formality})` everywhere, or a wrapper-hook) | none (variants inside one key) | ❌ Rejected |
| C — Suffix-key resolver (`key_formal`) + wrapper hook | medium (new resolver abstraction) | **~200–300** (migrate every tone-sensitive call site to the wrapper) | bounded | ❌ Rejected |
| D — Separate full formal catalogs (`{de,fr}/formal/*.json`) | small | 0 | **massive** (×2 the whole catalog; sync drift) | ❌ Rejected |
| E — Locale-variants (`de-formal` locale) | large (routing, middleware, SEO, cookie logic) | 0 | none | ❌ Rejected (formality ≠ locale) |

### Chosen — A (Overlay-Merge, ki_23 variant refined)

The concern lives at the loader layer; `next-intl` sees an ordinary, already-merged message
object. `useTranslations("ns")` / `t("key")` are byte-identical at every call site — zero
migration, zero new hook abstraction in components, server- and client-side both unchanged (both
receive the request-prepared `messages`). Duplication is minimal: only the genuinely-different
formal leaves, in `de`/`fr` only. This is why the PO's "low-effort + no-duplication" precondition
is now met on the technical side.

### Rejected — B (ICU select)

Native to next-intl and type-safe, but ICU arguments are resolved per-`t()` call — there is **no
global ICU-value injection** in next-intl. Every tone-sensitive call site would need
`t("key", {formality})` (or a wrapper-hook that injects it), which is exactly the ~200–300-site
churn the feature set out to avoid. ICU strings are also markedly less readable for translators
(`"{formality, select, informal {…} formal {…} other {…}}"` vs. a plain string). Good for a
handful of keys; the wrong trade for ~200–300. (Documented in `_scratch/ki_22.md`, `_scratch/ki_23.md`.)

### Rejected — C (suffix-key resolver + wrapper hook)

This was the Round-1 architecture ("not low-effort"). It requires a new `useFormalityTranslations`
abstraction that every tone-sensitive component must adopt — real migration churn plus a new
wrapper leaking into components. Strictly worse than Overlay-Merge (same duplication, more
infra, more call-site work). Kept here only to document why the Round-1 assessment changed.

### Rejected — D / E

D doubles the entire catalog (~3 000 keys × 2) and creates sync drift. E treats formality as a
locale, which it is not — it drags in routing, middleware, cookie logic, and SEO implications for
no benefit.

## Constraints & Edge Cases

- **RULE-02 boundary (critical):** this setting is **UI-copy-only**. It MUST NOT reach
  `core/prompts/` or any AI-generated content. UI copy (next-intl message JSON in
  `packages/i18n/messages/`) is fully separate from prompt templates
  (`packages/core/.../prompts/_bundled/`). Verified: no code path forwards a UI setting into the
  prompt cascade. The loader-only design keeps the boundary airtight — `formality` never leaves the
  message-merge layer.
- **English is unchanged:** no `overlays/formality/en.json`; en message catalog byte-identical in both
  registers. CI asserts this.
- **Deep-merge correctness:** nested namespace objects exist (`settings.themes`); a shallow merge
  would corrupt sibling leaves. The merge helper must recurse and be unit-tested against nested
  inputs (including the overlay overriding a single nested leaf).
- **New strings are dual-register by default:** a key absent from the overlay is served in both
  registers — by design (opt-in). The CI parity check ensures that once a de formal variant is
  added, a fr one exists too (and vice-versa).
- **Subset drift:** what counts as "tone-sensitive" is governed by the overlay itself (only
  differing keys are listed), so there is no separate subset-definition lint to drift. The CI
  orphan + parity checks keep the overlay honest.
- **Translation tooling:** the overlay is plain JSON; translators edit it like any message file.
  The nested `{ns: {key}}` shape mirrors the base catalog structure for familiarity.

## Editorial cost (the one real price)

Infrastructure is low-effort, but the feature still has a legitimate, non-negotiable cost:
**authoring and reviewing the formal variants**. Conservatively ~150–300 differing strings per
language for `de` and `fr` (the full-sentence, second-person/salutation subset; single-word
imperatives are tone-neutral and excluded). This is the cost of the *content*, not of the
architecture — it is the same under any option (Overlay, ICU, or suffix-keys all require the same
~300–600 formal DE/FR strings to be written). Plan editorial time for this; do not let the
"low-effort infrastructure" framing hide it.

## Affected areas / file map

| Path | Change |
|------|--------|
| `packages/web/lib/i18n/request.ts` | read `NEXT_FORMALITY` cookie; deep-merge `overlays/formality/{locale}.json` over base when `locale !== "en" && formality === "formal"` |
| `packages/web/lib/i18n/mergeOverlay.ts` | NEW — small, tested recursive deep-merge helper |
| `packages/i18n/overlays/formality/de.json` | NEW — sparse formal DE overlay (`{ns: {key: value}}`) |
| `packages/i18n/overlays/formality/fr.json` | NEW — sparse formal FR overlay |
| `packages/web/__tests__/i18n-namespace-registry.test.ts` | extend: orphan-override check + de/fr parity + no-en-overlay assertion |
| `packages/web/__tests__/i18n-mergeOverlay.test.ts` | NEW — deep-merge unit tests (flat + nested + leaf-only override) |
| Settings UI (Appearance / language area) | NEW formality toggle mirroring the locale-switcher pattern |
| `packages/web/lib/constants/tones.ts` | UNCHANGED — confirms `formality` does not collide with `StoryTone`/`tones.*` |
| Backend (`apps/api`, SET-001, Alembic) | UNCHANGED for v1 — cookie-only persistence (no migration) |
| `core/prompts/` | UNCHANGED — RULE-02 boundary verified |

## RULE-XX Compliance

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-02 | ✅ | UI-copy-only; loader-level; `formality` cannot reach `core/prompts/` (verified separation) |
| RULE-04 | ✅ | Merge helper isolated in its own module; request.ts stays under the size limit |
| RULE-06 | ✅ | One responsibility per file: `request.ts` = load+merge, `mergeOverlay.ts` = merge only |
| RULE-09 | ✅ | `Formality` typed union; merge helper fully annotated; no `any` in the public seam |
| RULE-10 | ✅ | merge unit tests + extended AST governance test; existing frontend coverage threshold upheld |
| RULE-11 | ✅ | Missing/empty overlay falls through cleanly to base (no crash); cookie read already wrapped in try/catch |
| RULE-12 | n/a | No new public API/service — frontend-only concern |
| RULE-13 | n/a | No streaming involved |
| RULE-14 | n/a | No schema change (cookie-only v1; no migration) |
| RULE-18b | ✅ | Naming collision avoided: `formality` ≠ `StoryTone`/`tones.*` |

## Acceptance criteria / Definition of Done

- [ ] `NEXT_FORMALITY` cookie read in `request.ts`; default `"informal"`.
- [ ] Deep-merge of `overlays/formality/{locale}.json` over base when `locale !== "en" && formality === "formal"`.
- [ ] `mergeOverlay.ts` helper with unit tests covering flat, nested, and leaf-only-override cases.
- [ ] `overlays/formality/de.json` + `overlays/formality/fr.json` populated with the formal variants (~150–300/lang).
- [ ] Settings toggle mirrors the locale-switcher; choice persists across reloads.
- [ ] Extended AST test: orphan-override check + de/fr key parity + no `overlays/formality/en.json`.
- [ ] `en` message catalog byte-identical in both registers (asserted).
- [ ] Zero changes to `core/prompts/` (RULE-02 boundary verified); zero call-site migration.
- [ ] Frontend tests green; `just check` green.

## Related

- [Q-015](../../architecture/questions/resolved/Q-015-user-selectable-copy-tone.md) — resolved → this spec
- [Q-013](../../architecture/questions/resolved/Q-013-i18n-tone-drift.md) — formality register on the *prompt* side (this feature is UI-copy-only; the two are separate)
- `packages/web/PRODUCT.md` — Brand Commitments (default: informal, functional)
- `docs/development/ui-principles.md` — UI copy conventions

## Status & History

- `2026-08-08` — Feature Spec created (I-Copy-001). Overlay-Merge architecture chosen after
  external-AI consultation (2/3 recommended it) confirmed the infrastructure is low-effort and
  duplication-free. PO re-approved. Source question Q-015 flipped to ✅. Status: `planned`.
