# The W5 knowledge capability — what is still a placeholder, and what replaces it

> **Status:** living document, opened with the knowledge rebuild wave W5's
> PR C (2026-11-19, the E2E suite landing). Keep it current: when a row's
> trigger lands, update the row in the same commit that replaces the
> interim. This is the single English list of every element of the
> capability's four surfaces — the workspace dock (entity chips, extraction
> suggestions, findings), the lore graph, the dossiers and the sources
> archive — that ships as a placeholder, a deliberate omission or a draft
> drift because the backend, the surface or the corrected draft does not
> exist yet.
>
> **Authority:** the owner-approved harmonized drafts — `screens/writing/`
> `knowledge-ai-dock` and `workspace-ai-dock` (the dock), `screens/knowledge/`
> `lore-graph-2`, `dossiers-2`, `sources-archive-2`. Light drafts win; the
> dark faces ride the shell's token ladder. The gap contract is the W5
> plan's owner decisions (2026-11-19: invented dossier fields are honest
> disabled placeholders, never fake content; no new backend — the whole
> wave rides existing endpoints). The table's format follows the W4
> ledger ([`2026-11-16-w4.md`](2026-11-16-w4.md)).
>
> The wave's index issue is #907; every actionable row hangs under it with
> its own child. Rows whose trigger is a later wave's model record their
> trigger here and carry no issue — the ledger is their home until that
> wave opens.

## Why placeholders exist

The owner's condition, carried from W3/W4: fidelity to the drafts without
lies. A feature the backend cannot serve keeps the draft's geometry with an
honest neutral — a disabled control with the drafted (or permanent-truth)
note, a „—", never an invented number, never a fabricated state. The
binding rule of this wave: entities are born only through the extraction
review, so every create-shaped door the drafts draw enabled stays disabled
with the note that names why (D8's family). The drafts' mock figures (8
entités, „Permafrost Station 7", „Chunk 14 · Seite 14") are draft data,
never shipping data.

## The gap list

„Drafted" is what the round authority draws. „Shipped in W5" is the interim
the wave commits to. „Trigger" is the surface, field or decision that must
exist before the interim can become the drafted value. „Wave/issue" names
the wave that owns the trigger and the row's child under index #907.

| Nr | Element | Drafted | Shipped in W5 | Trigger | Wave/issue |
|---|---|---|---|---|---|
| 1 | Create-entity door (graph + dossiers subbars) | enabled „+ Neue Entität" / „+ Neues Dossier" | disabled + the permanent truth („Entitäten entstehen über die Extraktions-Review; die API bietet keine direkte Anlage.") — the API has no create path; Task 4's binding deviation, the note shared by both doors | a manual creation path the backend decides on (a create endpoint, or manual suggestions through the existing review) + the create dialog | knowledge follow-up · #914 |
| 2 | Psychological profile (Want/Need/Lie geometry) | the dossier draft's profile card | honest disabled area (`dossier-psych-gap`, „Kommt mit einer späteren Welle") — no profile fields on the entity model | profile fields on the model, served by the API | profiles · #915 |
| 3 | Linguistic profile / dialogue patterns | the dossier draft's second profile card | honest disabled area (`dossier-linguistic-gap`) — same family, same note | the profile fields above (one trigger family with row 2) | profiles · #915 |
| 4 | AI sparring / dialogue simulation | the overview rail's sparring area | honest disabled area (`dossier-ai-gap`) — no entity-scoped simulation endpoint | an entity-scoped sparring surface (the chat wave's family) | chat wave family · #916 |
| 5 | Dossier status line | a status word per entity | neutral `NeutralRow` „—" (the shared component, both homes) — no model carries an entity status | a status field on entities, then a corrected draft that draws the line | model wave · no issue |
| 6 | Manuscript excerpts + jump-to-manuscript | the dossier's evidence list / the footer's jump door | disabled dashed area + disabled door, the shared note — no mention tracking exists | the mention-tracking model (which entity appears in which scene) | knowledge model wave · no issue |
| 7 | Bookmark + export (the Kompendium) | the dossier's merken/export doors | disabled with „kommt mit einer späteren Welle" notes — no bookmark row, no export endpoint | a reading-list feature and an export endpoint | later wave · no issue |
| 8 | Original-document view (sources) | enabled „Ansehen" row door + „Im Originaldokument anzeigen" hit door | disabled with the gap note on both — no endpoint serves the original's bytes. **Carried condition:** the note rides the disabled doors' `title` only; when a door goes live, an `aria-describedby` must carry it so screen readers hear it too (Task 6 review, minor 4) | a GET document-content endpoint | sources follow-up · #917 |
| 9 | Footnote & citation linking | the sources draft's footnote area | dashed disabled area, the draft's exact note — no mention-tracking model | the mention-tracking model (row 6's family, manuscript-side) | knowledge model wave · no issue |
| 10 | Automated fact-check & causality | the sources draft's fact-check area | dashed disabled area, the draft's note — the consistency check exists but is novel-scoped, not source-scoped | a source-scoped check surface | later wave · no issue |
| 11 | Re-embed door | (not drafted — the 409's answer) | the mismatch face names the condition honestly; `POST /api/knowledge/reembed` exists but no surface offers it | a re-embed door on the mismatch face — frontend only, the endpoint is real | sources follow-up · #918 |
| 12 | Search-hit meta | „Chunk 14 · Seite 14" | the rank badge (the server's ordering) + title + excerpt — `SearchHit` carries no chunk index or page, and the raw `score` is never rendered (no invented percentage) | a contract that carries chunk/page figures, or a corrected draft | contract wave · no issue |

## Resolved in-wave (recorded so nobody re-opens them as gaps)

- **The dock's inert chips** (Task 2's carried row): the chips shipped as
  honestly-inert `<li>`s pending the dossier route; Task 3 landed the graph
  and retired the interim — each chip is a button that navigates with its
  row's id in the `entity` param. The E2E flow pins the chip → dossier
  navigation. No issue was needed; the trigger fired in-wave.
- **The rail's Wissen door** (Task 2's transient note): the stale „kommt mit
  der Wissens-Welle" wording retired in Task 3 — the door opens the active
  book's graph, active face on all three knowledge routes. The writing
  chrome E2E (a77386ac) pins it live.
- **The dock's #866/#867 interims** (the W4 ledger's rows 1/2): retired by
  Tasks 1/2 — the findings face and the entity chips are real; both issues
  closed from `112fd9be`. The W4 rows are marked resolved in the same
  commit that opens this ledger.

## Known-pattern notes (no row owed — the pattern is the record)

- **Shared review mutations** (Task 2's review carry): the dock's review
  cards (findings and suggestions) share one mutation per decision kind and
  discriminate the pending/refused card by `variables === row.id`; a retry
  of the same row while its ask is in flight is locked by the card's
  two-door guard, and a consumed row's second decision answers 409, named
  per card. No ledger row is owed unless a surface multiplexes one mutation
  across rows without the guard.
- **The edge popover outlives its filter** (Task 3's out-of-scope
  observation): the popover reads the unfiltered relation list, so a filter
  that hides the edge whose popover stands open leaves the popover standing
  (anchored at the hidden edge's midpoint) until Escape or the close door
  ends it. Harmless today — both close paths own the focus return, and the
  E2E's keyboard leg pins them; a corrected behavior would fold the popover
  when its edge leaves the visible set. Recorded as the note it is: nothing
  lies, nothing is stranded from the keyboard.

## Handovers

- **The W4 ledger's rows 1/2** resolve with this wave (the dock's finding
  card and entity spotlight are the live findings face and chips); rows 3/4
  (atmosphere, chat composer) keep their own waves' triggers — the knowledge
  wave defined no atmosphere fields and built no composer. Rows 5/6 (the
  workspace's context-chips and prose-tags slots) remain gated on their
  named re-open condition, „a corrected draft draws the slot first": W5
  shipped the lore graph as the capability's own page (the rail's door),
  not as workspace chrome, so the undrafted workspace slots stay out.
- **The shelf ledger's row 4** (the hero's lore door): its trigger — the
  knowledge wave's lore graph UI — fired with this wave, but the door's
  rewire is writing-capability work the wave's task scopes did not include;
  **#919** hangs under the index for it and the shelf row now names the
  issue. Row 14 (the search-scope residual) is untouched: novels still
  carry no tags field.

## How a row becomes real

1. Land the trigger the row names (a surface, a field, a corrected draft, an
   owner decision).
2. Replace the interim at the element; a disabled control becomes the real
   door.
3. Update the row here (or remove it if nothing is left) in the same commit.
4. Close the row's child from that commit: `Closes #<n>`. The index (#907)
   closes with its last child.

No placeholder is removed by deleting its slot — the slot is the draft's,
and it stays. Only the neutral content is replaced.
