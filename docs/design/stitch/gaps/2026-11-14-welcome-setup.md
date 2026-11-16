# Welcome & setup — what is still a placeholder, and what replaces it

> **Status:** living document, opened with the welcome/setup rebuild wave W2
> (2026-11-14). Keep it current: when a row's trigger lands, update the row in
> the same commit that replaces the interim. This is the single English list
> of every element on the welcome screen, the four wizard steps and the
> landing that ships as a placeholder, a deliberate omission or a draft drift
> because the backend, the surface or the corrected draft does not exist yet.
>
> **Authority:** the archived drafts under `screens/library/` —
> `welcome-atelier`, `setup-step1-basis-vorlage`, `setup-step2-dramaturgie-struktur`,
> `setup-step3-ki-regeln-tonalitaet`, `setup-step4-bereitstellung-start`,
> `setup-states-reference`, `landing-atelier` (light drafts win; the dark
> drafts ride the shell's token ladder). The placeholder rules are the
> [rebuild spec](../../../superpowers/specs/2026-11-13-frontend-rebuild-design.md)
> §4 (owner decisions, 2026-11-13). The table's format follows the shelf
> fidelity wave's gap doc (`shelf-gaps.md`, branch `feat/shelf-fidelity`).
>
> **W3 update (2026-11-15):** the shelf rebuild wave took `/` from the
> landing (commit `b84a90f4`): post-setup the shelf is the home surface, and
> the welcome moved to `/setup`. `LandingPage` is kept **unrouted** —
> component, tests and its 29 catalog keys intact, absent from the
> production bundle — so rows 15–26 describe the kept component, not a
> shipped screen; their triggers stand unchanged (the workspace, knowledge
> and import waves still owe the doors). The live shelf's own ledger is
> [`2026-11-15-shelf.md`](2026-11-15-shelf.md); it carries the standing
> import-door row and the updated „Neues beginnen" reading (row 18 there).

## Why placeholders exist

The owner's condition is fidelity to the drafts without lies: a feature the
backend cannot serve keeps the draft's geometry with an honest neutral — a
disabled control with the drafted note, never an invented number, never a
fabricated quote. Where the draft itself invents data the archive does not
carry, the element stays out and the omission is argued here instead of
silently dropped. The wave's port reports disclosed every kept deviation;
this ledger collects the ones that need a trigger, a re-open condition or a
named reason.

Rows come in four kinds:

- **Feature gaps** — a drafted control whose action does not exist yet. It
  renders disabled with the note „kommt mit dem weiteren Aufbau"
  (`setup.welcome.comingSoon`), `aria-describedby` pointing at the note.
- **Draft gaps** — the draft overlooked something or contradicts the backend
  (a localStorage claim, a hidden slider thumb, a year the sibling drafts
  disagree on). The interim is the honest rendering; the trigger is a
  corrected draft through a Stitch round, never a local invention.
- **Reason rows** — deliberate omissions with no trigger: the draft draws
  invented data or a state that would lie. They return only if the named
  re-open condition becomes true.
- **Owner-decision rows** — the shared cover system replaced the drafts'
  hand-drawn book objects; what the cover owes the drafts is the
  cover-system wave's decision, not this wave's.

## The gap list

"Interim render" is what ships today. "Trigger" is the surface, field or
decision that must exist before the interim can become the drafted value.
"Follow-up" names the wave that owns the trigger (no issue numbers yet — the
wave's index is #855; a row that earns an issue hangs under it).

| # | Element | Draft value | Interim render | Trigger that makes it real | Follow-up |
|---|---|---|---|---|---|
| 1 | Welcome import card (card 3 CTA + drop zone) | enabled-looking „Manuskript importieren (.docx, .scriv)" | disabled button + drop zone, „kommt mit dem weiteren Aufbau" note | the import wave (upload, scene detection, entity extraction) | import wave |
| 2 | Welcome trust-strip handbook link | `href="#handbuch"` — dead in the draft too | kept as drafted, inert; no target exists | the help wave ships the handbook the anchor names | help wave |
| 3 | Wizard help button (steps 1–4, shared header) | enabled-looking „Hilfe & Anleitung" | disabled (opacity-50, cursor-not-allowed), label kept | the help content wave | help wave |
| 4 | Wizard header year chip (steps 1–3 drafts) | „Schreibjahr 2026" | „Schreibjahr 2025" — the welcome draft's own year, harmonized across the wizard | a draft-harmonization round settles the year | draft correction (Stitch round) |
| 5 | Step-1 live cover imprint | „Narrare Press • Anno 2026" publisher foot + „Ein Manuskript von Dir" author line | the shared BookCover's own contract: genre eyebrow, title, author line (Anonymus when absent) — no publisher imprint | the cover-system wave decides whether the imprint returns (owner decision) | cover-system wave |
| 6 | Step-1 status line | „Änderungen werden im lokalen Speicher gesichert" (localStorage claim) | „Änderungen im Entwurf synchronisiert" — the answers ride the address, posted at step 4 | the corrected draft drops the localStorage claim | draft correction (Stitch round) |
| 7 | Step-2 preview acts & beats list | „Akt I: Das verschollene Echo", „Akt II-A: Station 7 & Dekodierung", „Akt II-B: Der Kausalitätsbruch", „Akt III: Letzter Funkspruch" + chapter ranges, word counts, progress bars, „4 Handlungsphasen" | omitted — invented data the archive does not carry; the preview keeps header, curve, target, scale, sync and timeline status | none — reason row; returns only if the archive ever carries per-demo acts | — |
| 8 | Step-2 preview genre chip | „Thriller / Antarktis" | the archive's genre („Science Fiction") | none — reason row; archive facts only | — |
| 9 | Step-2 word-target slider thumb | `appearance-none` — hides the thumb in Chrome (draft bug) | native range with `accent-primary`, the draft's look kept | the corrected draft fixes the thumb | draft correction (Stitch round) |
| 10 | Step-3 sovereignty ban-filter section | „Bannung generischer KI-Floskeln" checkbox | omitted — no field in `SetupRequest` or the wizard seam; a live toggle would write nowhere | re-open condition: a settings field for the ban filter | settings wave (when the field lands) |
| 11 | Step-3 audit „92% Bindungsgrad" chip | „92% Bindungsgrad" | omitted — an invented binding metric with no backing at setup; the audit card keeps the neutral wording | none — reason row; re-open condition: a measured binding metric | — |
| 12 | Step-4 lore CTA | „Zuerst den Entitäten- & Lore-Graphen erkunden" | disabled + coming-soon note | the knowledge wave (entity & lore graph UI) | knowledge wave |
| 13 | Step-4 workspace CTA | „Direkt in den Schreib-Workspace eintreten (Kapitel 1)" | disabled + coming-soon note | the workspace wave (writing surface) | workspace wave |
| 14 | Step-4 stopped checklist (states panel 4) | half-checked rows on failure | omitted — the POST is atomic, nothing is half-bound; false check marks would lie. The failure card keeps the panel's title, body, cause line, retry and back | none — reason row | — |
| 15 | Landing hero book object | hand-drawn book, 256×352 (step 4 draws 176×256) | the shared BookCover at size `hero` (192×264), the system's own identity | the cover-system wave decides the hero sizes (owner decision) | cover-system wave |
| 16 | Landing word stand & progress track | decorative `w-12` sliver + „Wortstand wird beim ersten Schreiben gezählt • 3 Kapitel vordefiniert" | empty track (no sliver — nothing to measure) + the honest stand alone; the chapter count already rides the meta line | the workspace wave: the first writing produces a real word stand | workspace wave |
| 17 | Landing „Weiterschreiben — Kapitel 1" door | enabled-looking primary CTA | disabled + coming-soon note | the workspace wave | workspace wave |
| 18 | Landing „Entitäten- & Lore-Graph öffnen" door | enabled-looking secondary CTA | disabled + coming-soon note | the knowledge wave | knowledge wave |
| 19 | Landing storyboard door | „3-Akt-Storyboard einsehen" | disabled + coming-soon note, neutral label „Storyboard einsehen" — the „3-Akt-" prefix would claim a dramatic form the row does not necessarily carry | the workspace wave (storyboard surface) | workspace wave |
| 20 | Landing workroom card „Zen-Fokus & Atmosphäre" | room card with hover affordance | static coming-soon card, „demnächst" badge, no hover — a hover lift would imply a clickability it lacks | the workspace wave (zen focus room) | workspace wave |
| 21 | Landing workroom card „Chronologie & Timeline" | room card with hover affordance | static coming-soon card, „demnächst" badge, no hover | the workspace wave (timeline surface) | workspace wave |
| 22 | Landing workroom card „Manuskript importieren" | room card with hover affordance | static coming-soon card, „demnächst" badge, no hover | the import wave | import wave |
| 23 | Landing „Neues beginnen" doors („Projekt-Assistenten starten", „Vorlagen-Katalog durchblättern") | enabled-looking CTAs | disabled + coming-soon note in the kept, unrouted landing. W3 refuted the row's original premise — a single-user instance now holds many novels: the shelf's dialog creates them (`33ec3ca7`), the grid shows them (`2051b84c`), the menu duplicates them (`5814b5cd`). The real „Neues beginnen" door is the shelf's „+ Neues Buch anlegen"; the two drafted CTAs still name surfaces that do not exist (a per-book assistant, a template catalog). The reading stands in the W3 ledger, row 18 | product decision: the per-book assistant / template-catalog surfaces (multi-novel support is no longer the blocker) | product decision (multi-novel wave) |
| 24 | Landing hero blockquote | the demo seed's prose („Die Sensorenbatterie der Station Erebus schwieg seit drei Tagen …") | omitted — the archive's text, not the reader's; a blank-bound novel has none. The footer keeps the Atelier Notizen quote the welcome already speaks | none — reason row | — |
| 25 | Landing demo-roster meta | invented genre blurbs per demo | the manifest's facts (genre • chapters); the roster is non-interactive and the active mark follows the title match | none — reason row; archive facts only | — |
| 26 | Landing eyebrow & assurance „soeben" | „AKTIVES WERK • SOEBEN BEREITGESTELLT" / „Soeben im Setup bereitgestellt …" | „Aktives Werk" / „Im Setup bereitgestellt …" — the shelf welcomes every return, not only the first | none — deliberate wording decision | — |

### Reading the rows

- **Rows 1–3, 12–13, 17–23** are the feature gaps: every disabled control on
  the three screens, each with the drafted note and the wave that owes the
  action. The help button (row 3) is one control in the shared
  `WizardHeader`, not four.
- **Rows 4, 6, 9** are draft gaps the port corrected honestly; the drafts
  still carry the drift, so the trigger is a Stitch round, not a code change.
- **Rows 5, 15** are the cover-system's owner-decision family: the shared
  procedural cover replaced the drafts' hand-drawn objects (brief-mandated);
  the imprint and the hero sizes are what the cover-system wave still owes
  the drafts.
- **Rows 7, 8, 10, 11, 14, 24, 25** are reason rows: invented data or a state
  that would lie. They have no trigger — only rows 10 and 11 name re-open
  conditions (a settings field; a measured metric).
- **Rows 16, 26** are the landing's honesty wording: the empty track and the
  dropped „soeben" are decisions, and row 16 names the wave that makes the
  stand real.

## What is *not* a placeholder

These ship real and are listed so nobody mistakes them for gaps:

- **The demo doors** (welcome card 2, step-1 option B) — real: they bind the
  wizard to the generated archive demos; title, genre, chapters and blurbs
  are the archive's own facts.
- **The pre-setup locale mirror and its seam** — the structural 409 (the
  settings row does not exist before setup) was the welcome port's primary
  finding; the wizard's one POST now carries the mirrored choice onto the
  fresh row, a refusal keeps the mirror, and the landing adopts a kept
  mirror read-only until the next switcher touch. Resolved in this wave,
  pinned by tests — not a gap.
- **The bound checklist (step 4)** — rendered exactly from the
  `SetupResult`'s facts (genre, form label, chapter count, role label);
  „Bereit (100 %)" is the draft's own completion label, not a measured
  metric, and the binding face shows no percentage at all.
- **The landing roster's active mark** — a real title match against the
  shelf's row, never a hardcoded slug.
- **The language switchers** — all four faces are real: the welcome's and
  the wizard header's pre-setup mirror contract, the landing's and the
  shelf's post-setup row contract (the shelf's copy joined in `2051b84c`).
  Four capability-local copies of one contract are an extraction gap, not a
  placeholder — the W3 ledger carries the row (row 12 there; trigger: the
  shell rebuild re-owns the top bar, or a fifth face appears).

## How a row becomes real

1. Land the trigger the row names (a surface, a field, a corrected draft, an
   owner decision).
2. Replace the interim at the element; a disabled control becomes the real
   door, an omitted element returns only if its re-open condition is met.
3. Update the row here (or remove it if nothing is left) in the same commit.
4. If the row earned an issue under the wave's index, close it from that
   commit: `Closes #<n>`. The index closes with its last child.

No placeholder is removed by deleting its slot — the slot is the draft's,
and it stays. Only the neutral content is replaced.
