# Q-013 — i18n Tone Drift in Bundled Universal/Meta Prompts (DE/FR)

> **Status:** ✅ Resolved (2026-06-18)
> **Raised:** 2026-06-18
> **Source:** CR-AUFG-04-13 (P2 finding)
> **Blocks:** Nothing (informational drift; user-visible but not
> architecturally load-bearing)
> **Related:** ADR-013 (i18n), ADR-019 (System-Prompt Consistency),
> ADR-050 (cross-feature contracts — recorded here for context, not
> for closure)

---

## Question

The bundled `universal/{de,fr}/system.md` and `meta/{de,fr}/system.md`
prompts mix formality registers within the same file. Should this be
fixed, and how?

## Finding (verified 2026-06-18)

### `universal/de/system.md`

* Line 9: *"Du bist Narrares garantierte Fähigkeit..."* — **informal Du**
* Line 13: *"...folge der Gliederung."* — **informal Du** (imperative singular)
* Line 15: *"...folgen Sie immer den Autorenanweisungen..."* — **formal Sie** (imperative plural/formal)

Within the same 17-line file, the assistant addresses the user
both as *Du* and as *Sie*.

### `universal/fr/system.md`

* Line 9: *"Tu es la capacité garantie..."* — **informal tu**
* Line 13: *"...suivez le plan."* — **formal vous** (imperative)
* Line 15: *"...suivez toujours les instructions..."* — **formal vous**

Same pattern: the file mixes *tu* and *vous* within the same
instructions.

### `meta/de/system.md` and `meta/fr/system.md`

* `meta/de/system.md` uses *Du* consistently (line 7: *"Du bist Narrare..."*,
  line 23: *"lenke sanft zurück"*, imperative singular).
* `meta/fr/system.md` uses *tu* consistently (line 7: *"Tu es Narrare..."*,
  line 23: *"redirige avec douceur"*, imperative singular).

These two are internally consistent — the drift is only in the
`universal/` files.

## Root cause

The universal prompts were translated from English without a
formality-register convention. English has no Tu/Vous distinction,
so translators defaulted to imperative-mood translation without
choosing a side. ADR-013 (i18n) does not prescribe a formality
register; ADR-019 (System-Prompt Consistency) covers identity
consistency across the *meta* prompt but does not extend to
formality register.

## Recommendation

**Decision needed:** informal (*Du* / *tu*) or formal (*Sie* / *vous*)
across all bundled DE/FR prompts?

The *meta* prompts already commit to *Du* / *tu*. Adopting the
same register in *universal* prompts gives one consistent voice.
The *meta* identity line ("Du bist Narrare") strongly implies the
assistant addresses the user informally — matching the
collaborative, co-author positioning in `docs/reference/project-vision.md`.

**Recommended:** align *universal/{de,fr}* to *Du* / *tu* to match
the *meta* prompts.

This is a **Docs/Platform task**, not an Architecture decision. No
new contract, no new ADR. A single PR fixes four lines in two
files and adds a one-line convention to ADR-013 (or to the prompt
content standards) prescribing the chosen register for future
bundled DE/FR prompts.

## Scope

* Fix: `packages/core/narrare_core/prompts/_bundled/universal/de/system.md`
  (lines 13, 15: *"folge"* stays, *"folgen Sie"* → *"folge"*)
* Fix: `packages/core/narrare_core/prompts/_bundled/universal/fr/system.md`
  (lines 13, 15: *"suivez"* → *"suis"* to match *tu*)
* Convention doc: add a one-line formality-register rule to
  `docs/development/prompt-content-standards.md` or ADR-013.
* Test: extend the i18n prompt validator
  (`scripts/architecture/_checkers/_check_i18n.py` or a new tone
  drift linter) to catch mixed-register imperative verbs in DE/FR
  bundled prompts. This is optional but recommended to prevent
  regression.

## Why this is Q-013 and not part of ADR-050

ADR-050 closes architecture gaps (contracts, registries,
lifecycle). i18n tone drift is a content-quality issue, not a
contract gap. It is recorded under ADR-050 Phase D for traceability
(because CR-AUFG-04 bundled it with the P1 findings), but the fix
does not require an architecture decision — only a content
convention.

## Status & History

- `2026-06-18` — Raised as Q-013 from CR-AUFG-04-13. Cross-linked
  from ADR-050 Phase D acceptance criteria.

---

## Resolution (2026-06-18)

**Decision:** align `universal/{de,fr}` to **Du / tu** to match the
`meta/{de,fr}` identity prompts (the recommended option).

**Implementation (content fix — verified on disk):**

- `universal/de/system.md` line 15: `"folgen Sie immer den Autorenanweisungen"`
  → `"folge immer den Autorenanweisungen"` (now consistent Du throughout).
- `universal/fr/system.md` line 13: `"suivez le plan"` → `"suis le plan"`.
- `universal/fr/system.md` line 15: `"suivez toujours les instructions"`
  → `"suis toujours les instructions"` (now consistent tu throughout).
- `universal/de/system.md` line 13 (`"folge der Gliederung"`) was already
  informal and unchanged.

**Enforcement (convention):** added §8 "Formality Register (DE/FR bundled
prompts)" to `docs/development/prompt-content-standards.md` prescribing *Du* /
*tu* for all bundled DE/FR prompts, with `_check_i18n.py` and prompt review as
the catch mechanism. `meta/{de,fr}/system.md` were already consistent and
required no change.

No new ADR was needed (this is a content-quality convention, not an
architecture decision — as the original recommendation stated). The optional
tone-drift linter listed under "Scope" was not added; the existing i18n checker
plus the documented convention cover the regression risk for now.
