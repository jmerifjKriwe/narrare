# Entity interview & create dialog — Stitch design brief (W9)

> **Date:** 2026-11-24 · **Status:** decided — the owner approved the round's
> six screens on 2026-11-24 (see «Round outcome»).
> **Purpose:** the content brief for the W9 Stitch round (W1 recipe:
> `generate_screen_from_text`, fresh screens). It says what the three screens must
> contain, grounded in the real v2 API and the owner's decisions of 2026-11-20
> and 2026-11-24. Stitch is the sole design authority; this brief feeds it the
> facts, it does not design the UI locally.
> **Design system:** Literary Modernism (light) `assets/485a76ff0aab4fafbc1a7ccf3a1e2deb`,
> Midnight Ink (dark) `assets/ca5cbb89adb2439894e462d599c80ac3`, modelId
> `GEMINI_3_8_FLASH`, deviceType `DESKTOP`, project `15314899202287259920`.
> **Spec:** `docs/superpowers/specs/2026-11-20-assistant-sessions-design.md`
> (revised by W9 — see the companion design revision in this folder).
> **Supersedes:** the drifted draft `screens/knowledge/entity-genesis-ai-dialog`
> (2026-11-13 set). It stays archived; the new screens are the authority for the
> interview. The graph page itself stays as ported in W5
> (`lore-graph-causality-harmonized`); this round adds what sits on it.

## Owner decisions (2026-11-24)

| # | Topic | Decision |
|---|---|---|
| 0 | Existing draft | **Redraw fresh** on the current lore-graph page. The old draft shows the writing workspace with a manuscript excerpt, a dossier column and a chat dock — a page the interview does not live on. |
| 1 | Relations in the proposal | **In.** The interview may propose how the new entity relates to existing entities. The create dialog shows every proposed relation as its own row, to keep, change or strike. |
| 2 | Type-dependent questions | **In.** The assistant asks only questions that fit the entity's type. The type is chosen first, in the panel, and cannot change afterwards — a wrong pick means a new interview. |
| 3 | «Keine Ahnung» | **Both.** It answers the current question: the model proposes an answer the writer takes over, edits or discards. A second action, «Alles vorschlagen lassen», fills everything still open at once. |
| 4 | PRs | Three, by theme (a record for the plan; nothing to draw). |
| 5 | Carried from the spec | One session produces one entity. Closing the panel hides it and never ends it; ending is an explicit act. The transcript stays listed and readable. The interview's prompt is the prompts editor's fifth key from day one. |

## Builder calls (2026-11-24) — check these while reading

- **Duplicate name is a notice, not a refusal.** Nothing stops two entities with
  the same name today (extraction creates them, the graph can merge them). The
  dialog says that the name exists and keeps «Entität speichern» enabled.
- **The create dialog carries fields and relation rows.** Relations are written
  in the same transaction as the entity, so nothing lands half-made.
- **A ended interview keeps a savable proposal.** The transcript is read-only
  after «Interview beenden»; its proposal can still be saved as an entity.
- **The graph door opens the panel.** With an open interview the door resumes the
  newest; without one it shows the type chooser. «Von Hand anlegen» is the
  chooser's secondary path. The dossiers page's «Neues Dossier» opens the empty
  dialog.
- **The panel owns the graph page's right column while it is open.** Today that
  column is the selected entity's dossier; it yields and returns when the panel
  closes.
- **Relation types stay free text**, as the API has them. The model may use any
  short label; the dialog offers the graph's known labels as suggestions.
- **Nothing is invented.** No completion percentage, no score, no «kanonisch»
  seal, no persona name, no model badge. What is open says so.
- **Generated parts are marked.** Whatever the model proposed carries the small
  tag «vorgeschlagen» — a tag, a description, a relation row — so the writer
  can tell it from what she said. «Vorschläge verwerfen» removes the marked
  parts and keeps her own answers; the marks travel into the create dialog.
- **«Kein Modell eingerichtet» is a turn's answer, not a gate.** The provider
  is resolved when a turn runs, so the face appears in the assistant's place of
  the transcript (like «Nicht auswertbar»), with the writer's text back in the
  composer and a door to the AI rules. There is no pre-check before the start.

## Scope consequence — what the wave must build

The designs show **real target surfaces** for features that do not exist yet:

1. **Session substrate** (capability `chat`): `assistant_sessions` and
   `assistant_turns` (both `user_id`, sessions cascade with their novel), five
   endpoints under `/api/chat/sessions` — open, list, read, turn, close — and the
   registered prompt key `knowledge.entity-interview` on the task `chat.ask`.
2. **A structured-answer helper in the kernel.** The spec assumed one; today
   `ask_structured` lives in `app/capabilities/knowledge/structured.py` and
   returns a list. It moves to `app/kernel/llm/` and returns any parsed shape;
   knowledge imports it from there.
3. **A prompt key that names its task.** The prompts live test resolves every
   key *as* a task key. The interview key runs on `chat.ask`, so the registry
   gains `task_key` (default: the key itself).
4. **The editor's fifth key.** The prompts editor pins exactly four keys (icons,
   three catalogs, kernel goldens, API tests, the page suite, its E2E). The fifth
   lands with its preview sample and live-test assembly.
5. **`POST /api/knowledge/entities`** — body `{novel_id, name, type, aliases?,
   tags?, content?, relations?}`, 201 with `EntityRead`; the creation logic moves
   out of `accept_suggestion` into a service method both paths call; `relations`
   is a list of `{to_entity_id, relation_type, note?}` written in the same
   transaction. The graph's «Neue Entität» and the dossiers page's «Neues
   Dossier» become real (`Closes #914`).
6. **The fake provider's interview.** Deterministic from the transcript alone, and
   able to answer with prose instead of JSON so the browser test reaches the
   «nicht auswertbar» face for real (today no fake can produce an unparseable
   answer in a browser test — the gap issue #932 describes).

Everything else in the brief is backed by the API that exists today.

## Screen 1 — `knowledge-entity-interview` (light, the authority)

The lore-graph page as ported in W5, with the interview panel open in its right
column. State shown: **proposal ready** — name and type are present, two
relations were proposed, one field came from a suggestion.

**Page chrome** (as every ported screen): left icon rail, top bar with the
breadcrumb «Manuskripte / Dead Signal», «Gespeichert», the ⌘K search, the word
count, the language switch DE / EN / FR, the theme toggle.

**Graph page** (as `lore-graph-causality-harmonized`): breadcrumb «Atelier / Dead
Signal / Lore & Wissensnetzwerk / Kausaler Entitäten-Graph», heading «Kausales
Wissensnetzwerk», view chips «Beziehungsnetz · Matrix · Hierarchie», the door
**«＋ Neue Entität»**, the filter chips by type, the canvas with the entity nodes
of the demo novel. While the panel is open the canvas stays visible but is the
secondary thing; the selected entity's dossier column yields to the panel.

**Panel, top to bottom:**

1. **Header.** Title «Neue Entität», the type chip «Objekt», an icon button that
   opens the list of this novel's interviews, an icon button that hides the panel
   (hiding never ends the interview).
2. **Proposal card** («Vorschlag»), pinned above the transcript, collapsible:
   - Name: «Resonanz-Transponder LC-89»
   - Typ: «Objekt»
   - Aliasse: «LC-89», «Transponder»
   - Schlagworte: «Technologie», «Relikt» — one of them carries the small tag
     «vorgeschlagen», because it came from the model, not from the writer
   - Beschreibung: a short excerpt
   - Beziehungen: two rows, each the existing entity's name with its type chip
     and the relation label — «Forschungsstation 7 (Ort) — Liegt in»,
     «Dr. Lin Chen (Figur) — Gebaut von»
   - A quiet text action «Vorschläge verwerfen», present only while the proposal
     holds suggested parts; it removes them and keeps what the writer said.
3. **Transcript**, newest at the bottom. Assistant turns are labelled
   «Assistent», the writer's «Du», each with its time. The questions fit the
   type Objekt: what it is, what it does, where it comes from. No persona name,
   no model badge.
4. **Composer**: text area «Antworten …», two quiet chip buttons beside it —
   «Keine Ahnung» and «Alles vorschlagen lassen» — and a send icon button. Hint
   line: «Enter sendet, Shift + Enter für eine neue Zeile».
5. **Footer actions**: primary «Als Entität speichern» (it opens the create
   dialog, screen 3) and secondary «Interview beenden».

## Screen 2 — `knowledge-entity-interview-states` (light, state reference)

A sheet of tiles, each drawn inside the panel's frame, labelled with its state
number and name:

1. **Typ wählen** (the opening, when no interview is open). «Was möchtest du
   anlegen?» The eight types as a grid of selectable tiles with icon and label:
   Figur, Ort, Fraktion, Objekt, System, Zeitleiste, Ereignis, Allgemein. One
   line under it: «Der Assistent stellt Fragen passend zum Typ. Der Typ lässt
   sich danach nicht mehr ändern.» Primary «Interview starten», quiet text
   action «Von Hand anlegen».
2. **Erste Frage**. The assistant's first question for the chosen type; the
   proposal card shows every field as «noch offen»; the composer is ready;
   «Als Entität speichern» is disabled with the hint «Der Name fehlt noch» —
   the type is already fixed when the interview starts.
3. **Der Assistent überlegt**. The writer's answer stands in the transcript; a
   pending row «Der Assistent überlegt …»; composer, chips and send are disabled.
4. **Geantwortet**. The assistant's acknowledgment and the next question; the
   proposal card now holds name and a description excerpt; «Als Entität
   speichern» is enabled.
5. **Vorschlag für eine Frage** (after «Keine Ahnung»). The writer's turn shows
   «Keine Ahnung»; the assistant answers with a suggestion card — the proposed
   answer — and three actions: «Übernehmen», «Ändern», «Verwerfen».
6. **Alles vorgeschlagen** (after «Alles vorschlagen lassen»). Every field that
   was open is filled and carries the tag «vorgeschlagen»; the relations list
   has grown; the text action «Vorschläge verwerfen» stands on the card.
7. **Nicht auswertbar**. The assistant's turn is an inline alert: «Die Antwort
   war nicht auswertbar. Dein Text ist noch im Eingabefeld.» with «Erneut
   versuchen». The proposal is unchanged; the composer holds the text again.
8. **Kein Modell eingerichtet**. The author's answer stands in the transcript;
   in the assistant's place an inline alert: «Für das Interview ist kein Modell
   eingerichtet.» with the button «KI-Regeln öffnen». The composer holds the
   text again.
9. **Interview beendet**. A banner «Dieses Interview ist beendet. Das Gespräch
   bleibt lesbar.» No composer; the transcript is read-only; the proposal card
   stays, and «Als Entität speichern» stays available; «Neues Interview» beside
   it.
10. **Die Liste der Interviews** (the header's list button). «Interviews»,
    «Neues Interview» at the top, then the open interviews first — each row the
    type chip, the proposal's name or «noch ohne Name», the status «offen» and
    «Fortsetzen» — then the ended ones, quieter, with «Ansehen».
11. **Die Tür** (a small tile, not in the panel frame). One click on «＋ Neue
    Entität» opens the panel. Without an open interview it shows state 1; with
    one it resumes the newest. While interviews are open the door carries their
    count.

## Screen 3 — `knowledge-entity-create-dialog` (light)

One dialog, two variants side by side over the graph page, then the small
states under them.

**Heading** «Neue Entität anlegen», with the source as a chip: «Aus dem
Interview» or «Von Hand».

**Fields:** Name (required), Aliasse (chips, free entry), Schlagworte (chips,
free entry), Beschreibung (multi-line), and Typ — a select of the eight types
when the dialog was opened by hand, a fixed value with a lock when it came from
the interview (decision 2: the type cannot change once the interview started).

**Beziehungen** (a section under the fields): rows, each with the related
entity (its name and type; a select to change it), the relation label (a text
input that suggests the graph's known labels), and an optional short note; a
strike icon per row; «Beziehung hinzufügen» for an empty row. A row that came
from the interview shows where it stands:
- matched to exactly one entity — no remark;
- «Mehrere Treffer — wählen»: the model's name «Chen» is an alias of two
  entities; the select offers both;
- «Kein Treffer — zuordnen oder streichen».
A line above the footer while such rows exist: «Nicht zugeordnete Beziehungen
werden nicht angelegt.»

**Footer:** «Abbrechen» and primary «Entität speichern».

**Variant A — von Hand (empty):** Name and Typ empty, no relation rows, «Entität
speichern» disabled with the hint «Name und Typ sind Pflicht».

**Variant B — aus dem Interview (prefilled):** every field filled from the
proposal; the parts the model suggested carry their mark — the tag
«vorgeschlagen» on the Technologie chip and on Beschreibung, a small spark in
front of the entity name on the suggested relation rows; two rows matched, one
row with «Mehrere Treffer — wählen».

**Small states:**
- **Name schon vergeben:** a quiet notice under Name: «Eine Entität mit diesem
  Namen gibt es schon. Speichern ist trotzdem möglich.»
- **Speichert …:** the primary button pending, the fields disabled.
- **Abgelehnt:** an inline alert with the named reason, e.g. «Die Entität wurde
  nicht angelegt: <Grund>.» The fields keep their content.
- **Angelegt:** the dialog is gone; the new entity is selected in the graph and
  its dossier stands in the right column; a short toast «Entität angelegt ·
  2 Beziehungen verknüpft».

## Omitted — reason rows for the gap doc

None of the following gets a slot on the new screens:

| From the old draft | Why it is not drawn |
|---|---|
| Completion percentage («Synthese 85 %») and «100 % Kanonisch» seal | Invented numbers; there is no score behind them. Open fields say «noch offen». |
| Graph preview in the dossier column | The real graph is the page behind the panel. |
| Manuscript excerpt column and «Lore-Entität extrahieren» | The interview creates an entity the manuscript never named; extraction is the existing review path. |
| Chat persona «Narrare Muse 4.5», model badge «Prosa-Architekt», tabs «Lore-Genesis / Kausalitäts-Graph / Kanon-Zitate» | No persona and no per-turn model fact exists to show; the interview has one mode. |
| «Als Verknüpfung vormerken» as a third action | Replaced by decision 1: relations are rows in the proposal and the dialog. |
| Attach buttons («Manuskript-Referenz anhängen», «Lore-Graph anheften») | No attachment contract exists for sessions. |
| «Vorgeschlagene Kausal-Aktionen» quick replies | The interview asks; it does not push actions. |
| «Modus: Dialogische Genesis», «Muse bereit» | Decorative chrome with no fact behind it. |

## States, i18n, dark (all screens)

- Every read: empty, loading, error (the named faces above), success.
- Every write: idle, pending, refused (named), done.
- Dark variant of each screen on the Midnight Ink token ladder; light is
  authoritative.
- Chrome in DE / EN / FR (rule 5, three catalogs, du-tone in German and tu in
  French). Transcript and proposal are user content, never localized.
- No invented numbers: counts only where the API returns them, otherwise neutral
  «—» or «noch offen».

## What the round decided, and what is left to the owner

The round settled the open points of the first draft of this brief:

- The proposal card sits **above** the transcript, collapsible; the composer
  stays at the foot.
- The door is one button with a count of open interviews; no two-item menu.
- The ending action reads «Interview beenden»; the drafts draw no confirm step.

Left to the owner at the checkpoint:

- The look itself: panel width, type tiles, suggestion card, relation rows.
- «Vorschläge verwerfen» on the proposal card (my call above) — keep or drop.
- Whether ending an interview needs a confirm step (it is irreversible).
- Whether the count on the door is wanted.

Draft gaps the port must not copy (gap-ledger rows for the wave):

| Where | What the draft shows | Why it is not ported |
|---|---|---|
| States sheet, head | the label «Narrare — Dokumentation & Referenz» | sheet chrome, not app chrome |
| States sheet, tile 10 | the count word «Sitzungen» | the product says «Interviews» |
| Dialog sheet, state 1 and 4 | a button «Speichern»; the line «Toast-Meldung schließt automatisch» | copy drift: the button is «Entität speichern»; the toast line is not specified |
| Dialog sheet, variant B | the word «Fixiert» beside the type; row 1's select shows the type cut off | copy comes from the catalog; a port never truncates a name |
| Dialog sheet, dark | dimmed entity cards behind the dialogs («Subraum-Relaisnetz») | backdrop decoration |
| All screens | icon names of the type tiles differ from the app's icon set | the port uses `TYPE_ICONS` |

## Round outcome (2026-11-24)

Generated fresh via MCP (`generate_screen_from_text`, Literary Modernism light,
Desktop, `GEMINI_3_8_FLASH`), then corrected by forced regeneration
(`edit_screens`, «GENERIERE EINE NEUE VERSION DIESES SCREENS»). Three findings of
the audit drove the corrections: relation labels were cut with an ellipsis; the
reference sheets came with a documentation-site chrome and three notes that
stated facts the product will not have (sessions «im Browser-Storage», an
ambiguous door rule); the interview dialog let the type change although
decision 2 forbids it. Two traps are recorded for the next round: a tiny edit
runs as a canvas change and never reaches the export, and a generation with the
dark design-system asset stays light inside a conversation that began light —
dark variants are forced regenerations that name the Midnight Ink values.

Light and dark of every screen were compared on their extracted text: same
labels, nothing lost.

Stitch screen records (project `15314899202287259920`); the first name is the
authority, the ones in brackets the drafts it supersedes:

- Interview panel, light: `screens/a90a3630398745c8859643f92a8fc105`
  (`8b2df2ed68e24915842c88b296fe89ad`)
- Interview panel, dark: `screens/2997d9b845bf47f286c7998f60c064d0`
  (`f832626beb7342f89c7bf1edaef2a6fa`)
- States reference, light: `screens/492d5bc6299446b68e2e4aa008bad1e0`
  (`6c7c3417739f4887bc774d82551ffe03`, `f274a1cff7f64a338515b6e69eaf3cd1`)
- States reference, dark: `screens/88522c05948a42a7a874e6020fa72f5e`
- Create dialog, light: `screens/b0ea6084939845f09b7524ef7e2a5f7a`
  (`39081331b1314e44b058561fdefc5a76`, `cd02cc90d8e44a5e9fd7f8d24736cfb6`,
  `5de8cdc421c8436a9dbfb3ee6f6b96d7`, `4a948af6628f42f38bf8876171466e14`)
- Create dialog, dark: `screens/6bd51d574528428583c2fe410ae8e7ad`
  (`ff7a3ab65c9541db926ce9e977884f5a`, `b8b07720a73a46feb9f871f58e6caa28`,
  `042b5231396d4644b44e8e9dec54e0ed`, `b556bde578f5436f973b1cd71c2a6176`)

Three light duplicates of the failed first dark attempts stay in the
conversation and are no authority: `bbe34a1680ca4acca905de2cb3e84591`,
`ed7e97d8412c48609617e8e0d8f68b0f`, `3ba5526c70c242ef8a4b2363219507af`.
`list_screens` does not show most of these screens; the owner's project export
is the complete set.

Archive slugs for the wave (under `docs/design/stitch/screens/knowledge/`):
`entity-interview`, `entity-interview-dark`, `entity-interview-states`,
`entity-interview-states-dark`, `entity-create-dialog`,
`entity-create-dialog-dark`; the `entity-genesis-ai-dialog` row is marked
superseded by `entity-interview`.

**Owner checkpoint:** passed 2026-11-24, without a note — all six screens are
the authority for the port.

The port and the six builds are scoped into the wave's plan
(writing-plans) before any port wires a control to them; the designs show the
real target surfaces.
