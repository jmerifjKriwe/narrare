# The W9 assistant sessions — the entity interview — what is still a placeholder, and what replaces it

> **Status:** living document, opened with the assistant sessions wave W9's
> PR 3 (2026-11-25, the gap ledger landing; PR 1 #956 (`38e1e58a4`) and PR 2
> #973 (`61f715fae`) merged before it, PR 3 is #974 on `feat/entity-interview`).
> Keep it current: when a row's trigger lands, update the row in the same
> commit that replaces the interim. This is the single English list of every
> element of the wave's surfaces — the lore-graph page's interview panel (the
> type chooser, the transcript, the composer, the proposal card, the failure
> faces, the interviews list, the door with its count), the create dialog
> (manual and interview-prefilled, with its relations) and the graph's and
> dossiers' create doors — that ships as a placeholder, a deliberate omission
> or a draft drift because the backend, the surface or the corrected draft
> does not exist yet.
>
> **Authority:** the owner-approved Stitch round of 2026-11-24, six screens
> under [`screens/knowledge/`](../screens/knowledge/):
> `entity-interview`, `entity-interview-states`, `entity-interview-dark`,
> `entity-interview-states-dark`, `entity-create-dialog` and
> `entity-create-dialog-dark` (brief:
> `docs/superpowers/specs/2026-11-24-entity-interview-stitch-brief.md`). Light
> drafts win; the dark faces ride the shell's token ladder. The gap contract
> is the W9 design's owner rulings (2026-11-24: relations are rows, the type
> is fixed once the interview starts) and the Stitch round's owner checkpoint
> (2026-11-24, passed without a note): the round ported as committed, no
> invented numbers, no invented metrics, no dead promises. The table's format
> follows the W8 ledger
> ([`2026-11-22-settings-ai-rules.md`](2026-11-22-settings-ai-rules.md)).
>
> The wave's index issue is **#975** (the
> [`follow-ups.md`](../../../superpowers/follow-ups.md) row carries its number).
> The filed children are **#966** and **#969**; every other finding of the
> wave was fixed in it — #951–#955, #957 and #958 close when PR 3 merges,
> #967, #968 and #970–#972 closed with PR 2, #914 closed with PR 1. Rows whose
> trigger is a later wave, a product or an owner decision record their trigger
> here and carry no issue — the ledger is their home until that trigger fires.

## Why placeholders exist

The owner's condition, carried from W3–W8: fidelity to the drafts without
lies. A feature the backend cannot serve keeps the draft's geometry with an
honest neutral — never an invented number, never a fabricated state. The W9
wave adds five rules of its own. The no-metrics rule: no completion
percentage, no score, no persona, no model badge — an open field says „noch
offen" (the catalog's word), and nothing computes a figure the wire does not
carry. The honest-faces rule: a failure names what the wire answered and
offers only the action that can help — the settings door for a missing model,
the prompt editor for a refused prompt, no retry for a stale suggestion — and
a code the panel does not know keeps its name beside the generic sentence.
The no-dead-actions rule: every failure action is real and every door opens
the surface it names; the drafts' chrome (a sheet's head, dimmed cards behind
a scrim, a mock persona) ships nowhere. The scoped-guard rule: a turn and a
close belong to the interview they were sent for; a slow answer from the
interview the writer left never touches the one now shown. The save-door
disclosure: a window ruled no action (the proposal on screen while a turn's
settle is still refetching) is recorded here rather than widened into a
flicker.

## The gap list

„Drafted" is what the round authority draws (or, for the rows the wave
decided itself, what a complete surface would ask). „Shipped in W9" is the
interim the wave commits to. „Trigger" is the surface, field or decision that
must exist before the interim can become the drafted value. „Wave/issue"
names the owner of the trigger and the row's child under the wave's index.

| Nr | Element | Drafted | Shipped in W9 | Trigger | Wave/issue |
|---|---|---|---|---|---|
| 1 | Completion percentage and the canon seal | „Synthese 85 %" beside the proposal and the „100 % Kanonisch" seal on the type chip | not ported — invented numbers, and no read computes a score or a seal; an open field reads „noch offen" (the catalog's word), and the chip names the type alone | a score the product computes and the owner wants shown | owner decision · no issue |
| 2 | Graph preview in the dossier column | a small graph preview beside the interview | not ported — the real graph is the page behind the panel; the selected entity's dossier yields to the panel and returns when it closes | a corrected draft that draws the preview, or a preview surface the graph can serve | draft gap · no issue |
| 3 | Manuscript excerpt column and „Lore-Entität extrahieren" | an excerpt column beside the interview and the action that names an entity from it | not ported — the interview creates an entity the manuscript never named; extraction from prose is the existing review path | the interview reading the manuscript | later wave · no issue |
| 4 | The chat persona and its tabs | „Narrare Muse 4.5", the model badge „Prosa-Architekt", the tabs „Lore-Genesis / Kausalitäts-Graph / Kanon-Zitate" | not ported — no persona and no per-turn model fact exists, and the interview has one mode; the header names the panel and the session's type | a persona and a model fact the wire carries, or a corrected draft that drops them | draft gap · no issue |
| 5 | „Als Verknüpfung vormerken" as a third action | a third action beside save and end | replaced by owner decision 1 (2026-11-24): a relation is a row in the proposal and in the create dialog — kept, changed or struck; there is no mark-for-linking step | the owner reversing decision 1 | owner decision · no issue |
| 6 | The attach buttons | „Manuskript-Referenz anhängen" and „Lore-Graph anheften" in the composer | not ported — no attachment contract exists for a session; a turn carries text and one of five acts | an attachment contract for sessions | later wave · no issue |
| 7 | „Vorgeschlagene Kausal-Aktionen" as quick replies | quick replies that push actions onto the graph | not ported — the interview asks; it does not push actions (owner decision) | the owner asking for action suggestions; the graph's own actions stay the graph's | owner decision · no issue |
| 8 | „Modus: Dialogische Genesis" and „Muse bereit" | two header facts no read answers | not ported — decorative chrome with no fact behind it | a mode fact and a readiness fact a read answers | draft gap · no issue |
| 9 | The states sheet's head label | „Narrare — Dokumentation & Referenz" above the app chrome | not copied — sheet chrome, not app chrome; the panel's header reads „Neue Entität" and the session's type | a corrected draft whose head is app chrome | draft gap · no issue |
| 10 | The states sheet's count word | „Sitzungen" as the list's count word, where the product says „Interviews" | the list is titled „Interviews" (the catalog's word) and a row's state reads „offen" or „beendet"; the open group's own count keeps the catalog's plural „Sitzung/Sitzungen" — the word the tree uses for a session, not the sheet's head label | a catalog pass that counts interviews in that suffix, or a corrected draft | draft gap · no issue |
| 11 | The dialog sheet's copy | the button „Speichern"; the line „Toast-Meldung schließt automatisch" | „Entität speichern" (the catalog's word); the toast closes itself after six seconds, pauses while the pointer rests on it or a control inside it has focus, and carries a named close button — the surface shows the behaviour instead of promising it | a corrected draft that draws the real button and drops the toast line | draft gap · no issue |
| 12 | The dialog sheet's variant B | the word „Fixiert" set beside the type as if it were a value, and a type name cut off in row 1's select | the locked type is a chip with the lock glyph and the catalog's type word, the badge beside it the catalog's „Fixiert"; no name is truncated — the field grows and the row wraps | a corrected draft that draws the locked chip and truncates nothing | draft gap · no issue |
| 13 | The dialog sheet's dark variant | dimmed entity cards behind the dialogs („Subraum-Relaisnetz") | not copied — backdrop decoration, not app chrome; the dark face rides the shell's token ladder with a plain scrim | a corrected dark draft without the backdrop cards | draft gap · no issue |
| 14 | The type tiles' icons | icon names the app does not carry | the port maps every type through `TYPE_ICONS` (`app/capabilities/knowledge/web/entityTypes.ts`), so a tile's glyph is the app's own | a corrected draft that draws the app's icon set | draft gap · no issue |
| 15 | The type chooser's first state | the states tile draws „Objekt" selected, and the panel header a type chip in every state | nothing is preselected — no type is the default, so „Interview starten" waits for a pick — and the header chip appears once a session exists | an owner call preselecting a type | owner decision · no issue |
| 16 | The no-model face's actions | one action („KI-Regeln öffnen") | both „KI-Regeln öffnen" and „Erneut versuchen", each real: the first opens the AI-Regeln page, the second re-sends the turn | a corrected draft or an owner call dropping one | owner decision · no issue |
| 17 | Failure faces the reference does not draw | none — the states sheet draws the not-evaluable and the no-model faces | three honest faces for codes the wire answers with: `provider-error`, `prompt-refused` (with the door to `/settings/prompts`) and `suggestion-mismatch` (its own face, no retry — retrying would send a stale body); an unknown code shows the generic face with its code | a corrected states reference drawing them | draft gap · no issue |
| 18 | The create dialog's hardening beyond the approved screen | the approved screen, without the edges PR 1's review found | PR 1's parked findings, fixed in PR 3's first round: the add control stops at twelve relations with a note; every coded refusal has a catalog sentence, and a relation code marks the visible row it names; duplicate rows are flagged before the save; the toast pauses while read and closes on demand; the sibling relation routes answer the create endpoint's coded 422 | — (fixed in-wave) | resolved · no issue |
| 19 | The panel's hidden state | the spec's „Closing the panel only hides it" | the conversation's state outlives the hide (a host component owns it): reopened during a turn, the panel shows that it is thinking with the composer closed; a turn that fails keeps its face and the text; an unsent draft survives; a turn acts only on the interview it was sent for; the shown interview is busy while its own turn is in flight, whoever was sent after it | — (fixed in-wave) | resolved · no issue |
| 20 | The save door between a turn's settle and the session's refetch | — | for one read's duration the save door is open while the cache still holds the previous proposal; the writer saves the proposal on screen. Ruled no action: widening `busy` would flicker the composer after every answer | a report of a save that missed the last answer | no action recorded · no issue |
| 21 | Two closes in flight on different interviews | — | the close's busy and failed flags read the latest close sent, so a close of A still in flight after the writer ended B leaves A's end button enabled (the server's close is idempotent — a second click is harmless) and its failure unreported. Ruled no action: the window is one request's flight time; the fix is the turn's per-session count | a report or a browser leg showing it | no action recorded · no issue |
| 22 | Resolution against a list that failed to load | — | a roster that is still loading withholds the outcome and the save; a roster whose read failed is settled-empty, so proposed rows read „Kein Treffer — zuordnen oder streichen" beside the note that unassigned relations are not created (the manual dialog's long-standing exposure) | an error face for the roster's read | later wave · no issue |
| 23 | An invalid `act` on a turn | — | the framework's own 422, not a coded refusal — the panel's chips send only the five defined acts | chat gaining client-chosen acts beyond the five | chat wave · no issue |
| 24 | The interviews list's bound | an unbounded list | `SESSION_LIST_LIMIT` (200) per state, open sessions first, newest first in each; the door opens row one | a novel with more than 200 open interviews | later wave · no issue |
| 25 | A turn in flight cannot be cancelled | none — the reference draws no cancel | a turn runs to its end; the panel may be hidden meanwhile and the answer lands anyway; nothing reaches the novel without the author's save | the streaming cut (the free chat) or an owner call | later wave · no issue |

## Resolved this wave (recorded so nobody re-opens them as gaps)

- **The parked findings came back.** The owner's rule of 2026-11-14 — no
  finding deferred inside a running wave, not a minor — was applied too
  leniently at the first two gates: PR 1's seven findings were parked as
  issues and PR 2's five as issues; PR 2's came back in its own branch
  (#967, #968, #970–#972) and PR 1's in PR 3's first round (#951–#955, #957,
  #958). Two stay issues with a reason: #966 (a warning seen once, root cause
  unknown) and #969 (a generator check that needs the owner's approval under
  the governance budget).
- **PR 2's review rounds.** The proposal is merged under the session's lock,
  not replaced (two racing turns keep both answers); a slot has three states
  in a model answer — omitted is untouched, empty clears, a value sets;
  „Übernehmen" carries the settled suggestion's own text and a changed
  suggestion answers 422 `suggestion-mismatch`; a relation's target must be
  an entity of the same user in the same novel; every user-derived string
  that enters a rendered prompt line passes `single_line`, so no writer's
  text can forge a marker line; a render-refused prompt answers 502
  `prompt-refused`.
- **A failed button's message.** The failure faces that offer „Erneut
  versuchen" carry the approved screen's sentence for a typed answer; a
  button („Keine Ahnung", „Alles vorschlagen lassen") sends its label, never
  the composer's text, so each such sentence has a second catalog key for a
  failed button's turn — the same sentence without the clause about the
  input field.
- **A release-notes gap, named here because it cannot be fixed.** Commit
  `bb2e3747` on PR 2 is typed `chore(prompts)` but changes what a user sees:
  the prompt cards of `knowledge.extract-entities` and
  `knowledge.check-consistency` used to open their card on the line
  „PURPOSE: …" and now open on their first prose line (one rule for every
  key). The commit is pushed and force push is forbidden, so the next
  release's notes miss that line; this record and PR 3's body name it.

## Known-pattern notes (no row owed — the pattern is the record)

- **The visibility refs of the interview controller are written in a layout
  effect** (`useInterview.ts`): a settle must never land between a hide's
  commit and a passive effect still reading `true`, so `visible` and
  `sessionId` are mirrored in `useLayoutEffect`. The sub-frame window that
  closed has no unit test because it cannot be hit deterministically in
  jsdom (three probes in the round's report, SDD ledger
  `pr3-hidden-panel-fix-report.md`).

## Handovers

- **The W5 ledger's row 1** (the create-entity door, child #914): resolved
  with W9 — the door is live since #956 (`38e1e58a4`); both subbars open the
  create dialog, and from the graph also the interview's door (PR #974);
  #914 closed with PR 1. The W5 ledger
  ([`2026-11-19-knowledge.md`](2026-11-19-knowledge.md)) marks the row in the
  same commit that opens this ledger.
- **The W8 ledger's rows**: none resolves with W9 — the settings and prompts
  surfaces were not this wave's subject; their triggers keep standing.

## How a row becomes real

1. Land the trigger the row names (a surface, a field, a corrected draft,
   an owner decision, or user feedback).
2. Replace the interim at the element; a placeholder becomes the real
   thing, an omitted element returns only if its re-open condition is met.
3. Update the row here (or remove it if nothing is left) in the same
   commit.
4. Close the row's child from that commit: `Closes #<n>`. The wave's
   index closes with its last child.

No placeholder is removed by deleting its slot — the slot is the draft's,
and it stays. Only the neutral content is replaced.
