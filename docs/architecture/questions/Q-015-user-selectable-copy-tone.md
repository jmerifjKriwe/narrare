# Q-015 — User-Selectable UI Copy Tone (Familiar vs. Neutral)

> **Status:** 🟡 Open
> **Blocks:** Nothing (documented only — a default already exists in `PRODUCT.md`)
> **Raised:** 2026-08-05
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

Feature Spec (I-Copy-XXX) if the Product Owner gives the green light.
Until then this question is only documented — no implementation, no
blocked work.

## Related

- `packages/web/PRODUCT.md` — **## Brand Commitments** (default: informal, functional)
- Q-013 — i18n tone drift in bundled prompts (related formality-register topic on the prompt side; this question is UI-copy-only)
- `docs/development/ui-principles.md` — UI copy conventions

---

> **Status:** 🟡 Open — blocks nothing; feature spec (I-Copy-XXX) pending PO green light
