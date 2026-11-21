# Settings Allgemein W7 — design

Date: 2026-11-21 · Status: awaiting owner approval (approach C picked)

## Decided in conversation (2026-11-21)

1. **Commit model**: Sprache and Erscheinungsbild apply **at once** — the
   page reuses the existing seams (`useLanguageChoice`, the theme toggle;
   no form state). Autorenname and Tagesziel are **one dirty form** with
   Verwerfen/Änderungen speichern (the GoalSetter pattern, the
   partial-update contract on the wire). The Stitch brief draws exactly
   this split into the W7 authority.
2. **Clean retirement, no corpses** (owner ruling): writing's
   `BookSettings` profile section (locale, author_name,
   daily_goal_words) **retires in W7** — the row's home is `/settings`;
   writing's surface routes there. The old draft's Projekt-Regeln fields
   (novel.ai_role, canon_strictness, author_typotyp, target_words) stay
   where they live (BookSettings) — W8's AI-Regeln authority gets a
   pointer, never a copy.
3. **The user-block menu wires** (owner ruling): Autorenname bearbeiten
   and Tagesziel festlegen door into the settings surface at their
   sections; Einstellungen opens /settings; Abmelden stands honestly
   disabled with its no-backend note.
4. **The causality strip's disclaimer lands** (owner ruling): one honest
   line on the W6 strip (reworded without the banned vocabulary, the
   "kommt mit dem weiteren Aufbau" family), riding the W7 opener.

## Intent and why

The settings capability's **general** surface — language, appearance, profile
(author name, daily goal), the honest offline note — on the complete existing
backend, as W7 of the frontend rebuild. The owner split the settings work into
two waves: **W7 = Allgemein** (this design), **W8 = AI-Regeln** (providers,
models, assignments, prompt overrides — its own wave, own design later).

**Approach C (owner's pick):** before any porting, a Stitch harmonization
round SPLITS the old `settings-ai-rules` draft into two clean authorities —
an Allgemein-only screen (W7's authority) and an AI-Regeln screen (W8's).
The `ai-prompts-overrides` draft stays W8's second surface untouched. Nothing
of the old mixed draft is ported as-is.

## Real fields (the API is the authority)

- `GET/PUT /api/settings`: `locale` (present-and-nullable — `null` follows
  the browser, `{}` is a client bug), `author_name` (trimmed, ≤200, null =
  the email label answers), `daily_goal_words` (1..WORD_GOAL_MAX, null = no
  goal); `email` read-only (the fallback label).
- `GET/PUT /api/settings/theme`: `light`/`dark`, null = follow the system.
- Absent-vs-carried-null is the partial-update contract (the novel update's
  rule): absent keeps the stored answer, carried null clears it. The locale
  switchers carry the locale alone.

## Wave opener (owner's "kleine Fixes" ruling)

Ride on the W7 branch before the surface: **#928** (route-leave guard over a
dirty scene draft — the same confirm machinery), **#929** (consume the
generated `structures.ts` instead of the hand-copied switcher ids — the
sharpened shape), **#926** (knowledge dialog viewport containment CSS).
Optional one-key: the W6 causality strip's bottom disclaimer, honestly
reworded — the owner's pending yes/no.

## Non-goals

- No AI tabs content, no provider/model/assignment/prompt UI (W8).
- No chat surface (no draft exists; own wave when Stitch draws it).
- No new backend.

## Anti-goals

- Fake provider names, invented model metrics, dead-promise tabs.
- The old mixed draft ported unsplit.

## Constraints

- Standing rules (CONSTRAINTS.md); SDD flow; **PR für PR** (owner ruling
  2026-11-20: one PR green + all threads resolved before development
  continues).
- Seats: implementer `glm-5.3-flash`, reviewer `glm-5.3` (rev. 7, until
  qwencloud returns 2026-12-13).
- Stitch alone designs; the harmonized Allgemein draft is owner-approved
  before porting.
- i18n: three catalogs, sorted parity, du-tone (fr tu).
- Route `/settings` (global — the gear door; `nav: false` already in
  capability.yaml).
- The kernel discovery expectation stays `{"knowledge","planning","setup",
  "writing"}` — W7 adds no e2e suite directory (settings E2E rides the W7
  gate as browser legs over the existing suites' conventions, or waits for
  W8's combined settings suite — plan decides, disclosed).

## Approaches (picked in conversation)

- **C — harmonize and split first (owner's pick).** A Stitch round produces
  the Allgemein-only authority for W7 and the AI-Regeln screen for W8;
  cleanest authorities, one round of cost.
- A — port as drawn with honest gap-doors for the AI tabs. Rejected: the
  owner wants the split.
- B — minimal Allgemein page without the tab chrome. Rejected: the draft's
  geometry is the authority.

## Left to the builder

- Task breakdown at plan time (the W6 shape: harmonization gate, opener,
  surface, E2E legs, ledger, wave gate — fewer tasks; this is a small wave).
- Exact catalog keys and testids from the harmonized draft.
- Whether the settings surface seeds its own e2e directory (kernel
  expectation grows in the same commit) or rides the existing suites.

## Open follow-up children of earlier waves (context, not W7 scope)

#920–#922, #930, #932 stay filed; #928/#929/#926 close in the opener.
