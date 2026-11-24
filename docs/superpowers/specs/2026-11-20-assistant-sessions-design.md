# Assistant sessions — conversations that produce a proposal

> **Date:** 2026-11-20, revised 2026-11-24 · **Status:** approved by the owner
> for cut 1 (2026-11-24); cuts 2 and 3 stay a direction.
> **Supersedes nothing.** It extends the roadmap's Phase 1 chat item and the
> "proposal and diff" contract (roadmap §2.2) with the shape the owner described
> on 2026-11-20: guided assistants that turn a conversation into an entity, a
> stub, an idea, or a novel. The 2026-11-24 revision folds in the owner's
> decisions of that day and the Stitch round's result
> ([`2026-11-24-entity-interview-stitch-brief.md`](2026-11-24-entity-interview-stitch-brief.md));
> where this text and its first draft differ, this text wins.

## Intent and why

Chat is not one feature. It is the input side of four things the owner wants:

1. an assistant that helps **create an entity** (person, place, artefact) from a
   conversation with a workflow behind it;
2. an assistant that **fleshes out a stub** the user already wrote;
3. an assistant to **discuss an idea for a scene or chapter**, then take it or
   leave it;
4. a **novel-setting interview** whose answers land in the set-up fields.

They share one thing, and it is not the chat box: **a conversation ends in a
typed proposal, and the user accepts it into a real target.** Every AI answer in
the v2 drafts already follows this — the workspace dock ends in "Vorschlag
einfügen" or "Auf Station 7 korrigieren / Ignorieren". v1 built exactly this
shape once, as **KB sessions** (KB-002): a guided interview with typed fields,
reviewed and saved through the entities API, with a bounded number of questions.

So the reusable part is the session and the proposal. The first cut proves them
on the mode the owner wants first: **create an entity**. On 2026-11-24 the owner
added three things that mode must do: ask only questions that fit the entity's
type; let the writer answer "no idea" to any question and get a proposal instead;
and propose relations to existing entities beside the fields.

## The spine

```
door (the graph's "Neue Entität")
  → type chosen in the panel
  → session (novel, mode, entity type, transcript, proposal)
  → turns (question, free-text answer, extracted slots, proposed relations)
  → proposal (name, type, aliases, tags, content, relations)
  → the entity create dialog, prefilled
  → the user edits and saves through POST /api/knowledge/entities
```

Chat never writes an entity row. The session is a producer; knowledge is the
owner. That is rule 1 read strictly, and it is also what makes the review step
honest: the entry the user saves is the entry they saw.

## Approaches considered

### The substrate (2026-11-20)

| | Shape | Trade-off | Verdict |
|---|---|---|---|
| A | **Modes over one session substrate.** A mode fixes the prompt key, the context, the slots and the target. Free chat is one mode, the entity interview another. | One contract, one table pair, then one wave per mode. A new field in a proposal touches two places. | **Chosen.** |
| B | *One chat, many tools.* The model gets a tool per capability and writes directly. | Flexible, one surface; but every write is non-deterministic, needs permissions and undo, the fake provider must simulate tool calls, E2E turns flaky, and the prompts capability becomes redundant. | Rejected: it moves the risk from the schema into the model. |
| C | *Guided forms only*, no free text. | Cheapest and most testable; loses the discussion the owner asked for. | Rejected. |

**Guided first, free chat second.** The interview exercises persistence,
extraction and acceptance, which are the hard parts; prose insertion is
comparatively mechanical.

### How the type is fixed (2026-11-24, owner's pick)

| | Shape | Trade-off |
|---|---|---|
| A | **The writer picks the type first**, in the panel. Every question fits the type from the first turn; the type never changes. | One step before the first question. |
| B | The assistant asks for the type and infers it from the answer. | One step less, but the first question is generic and the model can guess wrong. |

A was chosen: type-dependent questions need the type before the first turn.

### "Keine Ahnung" (2026-11-24, owner's pick)

| | Shape | Trade-off |
|---|---|---|
| A | A proposal for **the current question** only. | The writer keeps the lead over every field. |
| B | A proposal for **the whole dossier** at once. | Fast, but hard to check, and it ends the questions. |
| C | **Both**: "Keine Ahnung" answers the current question; a second action, "Alles vorschlagen lassen", fills everything still open. | One more path in panel and prompt. |

C was chosen.

### Relations in the proposal (2026-11-24, owner's pick)

The first draft left relations out of cut 1. The owner chose to let the
interview **propose relations** to existing entities; the create dialog shows
each as a row to keep, change or strike.

### How the wave is split (2026-11-24, owner's pick)

| | Shape | Trade-off |
|---|---|---|
| A | **Three PRs by theme**: create by hand; the session substrate with the editor's fifth key; the interview. Each has its own browser test. | Three gates under PR-für-PR. |
| B | Two PRs: create by hand, substrate and fifth key together; then the panel. | One gate less, but the first PR mixes two strangers. |

A was chosen.

## Goals

- A session that survives a reload, per novel, with the whole transcript.
- Turns that answer in prose **and** carry the slots extracted so far.
- A proposal the user reviews and edits before anything is written.
- Questions that fit the entity's type; "Keine Ahnung" and "Alles vorschlagen
  lassen" as first-class answers; proposed relations beside the fields.
- The interview prompt is a **registered prompt key**, in the prompts editor
  from the day it lands.
- Evidence for a later mode: adding one is a prompt key, a slot list and a
  target — not a new subsystem.
- The two create doors the knowledge capability has kept disabled since W5
  become real (#914).

## Non-goals

- Streaming the interview's answers (turn-based JSON is enough; free chat adds
  the stream).
- Tools, function calling, an agent loop.
- Automatic writes of any kind.
- A chat screen of its own; the session lives in a surface's side panel.
- Deleting a session; a history surface beyond the panel's list.
- Any model-quality claim: the fake provider's interview is deterministic and
  proves the plumbing, not the prose.

## Anti-goals

- A session whose transcript is not persisted, so a reload loses the interview.
- A proposal that silently differs from what lands in the fields.
- A model that decides what was "suggested": provenance is the server's, from
  the act the writer chose.
- A button that says "Speichern" and writes through a path the user cannot
  inspect.
- Invented completeness ("Synthese 85 %", "100 % kanonisch") — the draft's
  scores are gap rows, not fields.
- An interview that dies with its panel: closing the sidebar must not end the
  session, and a reload must not lose it.

## Constraints

- The five standing rules (`docs/_shared/CONSTRAINTS.md`). Chat and knowledge
  never import each other; the entity table is a **kernel** model
  (`app/kernel/contracts/knowledge.py`), so chat reads the roster through a
  scoped kernel repository, not through knowledge's service.
- No second data store: sessions and turns are two Postgres tables with
  `user_id`.
- English in code and tests; the transcript is user content and is not
  translated; chrome in en/de/fr through the hosting capability's catalog.
- The only fake is the provider at its boundary.
- No database transaction is held across a provider call.

## How it works

### Data

`assistant_sessions` — `id`, `user_id`, `novel_id` (foreign key, cascade on
delete), `mode`, `entity_type` (nullable in general; required for
`knowledge.entity`), `target_id` (nullable; the entity being improved, for the
stub mode), `proposal` (JSONB, nullable: the current validated proposal with
its provenance), `closed_at`, `created_at`, `updated_at`.

`assistant_turns` — `id`, `session_id` (foreign key, cascade), `seq`, `role`
(`user` | `assistant`), `text`, `act` (nullable; the writer's choice on a user
turn), `suggestion` (nullable; the proposed answer an assistant turn carries),
`suggestion_state` (nullable: `pending` | `accepted` | `rejected`),
`created_at`. The sequence is per session and monotonic; a turn is never edited.
Unique on `(session_id, seq)`.

Full transcripts are kept. They are the user's own material, they cost
kilobytes, and "what did it propose last week" is a question the product should
answer. No retention job in cut 1.

**Lifecycle.** A session is open until the user ends it. Closing the panel only
hides it; the door reopens the newest open session and offers «Neues Interview»
beside it. Several sessions may be open at once — the list shows them — and
ending one is explicit and irreversible: the transcript becomes read-only, the
proposal stays savable. Deleting a novel deletes its sessions with it; the
cascade is the database's, not a cleanup job.

**One session, one entity.** A session whose proposal was saved is closed by
the client right after the create call answered 201.

### Endpoints (capability `chat`)

| Method | Path | What it does |
|---|---|---|
| POST | `/api/chat/sessions` | Open a session: `{mode, novel_id, entity_type?, target_id?}` → 201, the session read |
| GET | `/api/chat/sessions?novel_id=` | List sessions for a novel, newest first |
| GET | `/api/chat/sessions/{id}` | The session with its transcript |
| POST | `/api/chat/sessions/{id}/turns` | `{text, act?}` → `{reply?, proposal?, suggestion?}` |
| POST | `/api/chat/sessions/{id}/close` | Idempotent close → the session read |

`mode` is `knowledge.entity` in cut 1; another mode is a 422 with a named
reason. For that mode `entity_type` is **required** and must be one of
`ENTITY_TYPES`; it is stored on the session and never asked for, never changed.
A foreign or absent novel or session is a 404, indistinguishable from absent —
the codebase's existing IDOR rule.

**The opening question is chrome, not a turn.** It is rendered from the hosting
capability's catalog for the chosen type, so it is translated and costs no model
call. The transcript holds only what the user and the model actually said.

**`act` names the writer's choice.** The text stored is what the panel sent —
the localized label of the chip or the answer itself — so the transcript reads
naturally. The act is what the server acts on:

| `act` | Model call | What happens |
|---|---|---|
| _(absent)_ | yes | The writer's answer; the model updates the proposal and asks on |
| `accept-suggestion` | yes | `text` is the suggestion; the pending suggestion becomes `accepted`, the answer is recorded as the writer's own |
| `no-idea` | yes | The model proposes an answer to its last question in `suggestion`; the proposal is not changed |
| `fill-all` | yes | The model fills every open slot and may propose relations; all of it is marked suggested |
| `reject-suggestion` | no | The pending suggestion becomes `rejected`; the question stands |
| `drop-suggestions` | no | Every suggested part leaves the proposal; what the writer said stays |

### Chat has no surface of its own

The panel that hosts a session belongs to the capability whose page it sits on:
the entity interview is knowledge's panel on the graph page, the free chat will
be writing's dock in the workspace. It reaches `/api/chat/*` through the shared
API client, which every surface already has — no capability imports another, and
no page-level registry is invented. Chat states the contract and owns the
tables; the host owns the chrome, the catalogs and the E2E. Chat's
`capability.yaml` drops `path: /chat` and `nav: true`: they generate nothing
(there is no web module), and a declared surface that cannot exist is a promise
the record should not carry. The capability generator reads both fields
unconditionally today, so it learns to treat them as optional in the same change.

### The turn

Turn-based, JSON, no SSE. One provider call per turn carries the contract; a
second call is allowed only if a combined call proves unreliable. The model sees
the proposal so far, the proposed relations, and the **last twenty turns** of
the transcript (the first draft said ten; a guided interview asks more questions
than a lookup, and the model must not repeat itself).

**Nothing is written until the model has answered.** The request runs in three
steps and never holds a transaction across the call:

1. A short read: the session, its proposal and the last twenty turns. A closed
   session answers 409 here. The read's transaction ends before the model is
   called.
2. The prompt is rendered and the model is asked through the kernel's
   structured-answer helper. The audit rows of the calls are collected while
   they run and written afterwards — with both turns on success, alone in their
   own short transaction when the turn fails. `record_call` only adds to the
   session and never commits, so nothing lands outside the request's own
   transaction. Each provider attempt is one row (`task_key` `chat.ask`,
   `prompt_key` `knowledge.entity-interview`); a repair retry is a second row,
   so a turn that fails «nicht auswertbar» leaves two rows and no turn. The
   client keeps the text in the composer. Retry is therefore not a second user
   turn: the failed attempt left no row.
3. One transaction: the session row is locked, «closed» is checked again, both
   turns are written with `seq` allocated under the lock, the model's changes
   are merged into the proposal as it stands under the lock, the audit rows of
   the calls are written.

**The proposal is merged, not replaced.** The model's output is compared with
the input it was given: what it changed is written, what it left alone is taken
from the proposal as it stands now. The provenance rule reads the same
comparison.

Concurrent turns on one session (two tabs, a double submit) cannot interleave
their rows and cannot erase each other: each allocates `seq` inside its own
write transaction, and each merges only its own changes. The composer is
disabled while a turn runs, so the case stays an edge, not a feature.

Model output, per turn:
`{"reply": str, "slots": {"name"?, "aliases"?, "tags"?, "content"?},
"relations": [{"target": str, "type": str, "note"?}]?, "suggestion"?: str}`.
The entity type is never in the output — it is the session's. Extraction uses
the kernel's structured-answer helper: a schema where the adapter supports one,
an instruction plus one repair attempt where it does not; a second parse failure
is a 502 with a named reason, never an empty proposal.

The server normalises what the model returned before it is stored — the same
limits the create endpoint will apply later: name and labels trimmed, non-blank,
at most 200 characters, labels deduplicated case-insensitively; relation types
non-blank, at most 80 characters; targets at most 200; at most 12 relations and
10,000 characters of content. A string over its limit is cut to the limit and
a list over its cap keeps its first entries — the dialog shows the stored
value, so nothing changes silently; blank entries are dropped, and a name that
would be blank is not stored at all.

**Provenance is the server's.** Every part of the proposal is either the
writer's own or suggested: `{"slots": {...}, "relations": [...], "suggested":
{"tags": [...], "content": true, ...}, ...}` records which. The rule is
mechanical: a part that is new after `fill-all` is suggested; a part that is new
or changed after any other turn is the writer's own; a part that is unchanged
keeps what it was. A per-question suggestion is not part of the proposal until
the writer takes it over — then it lands as her own answer.

**`ready` is not the model's to decide.** The interface enables «Als Entität
speichern» once the proposal holds a name (the type is always there), which is a
fact it can check.

### The prompt

A new registered key, `knowledge.entity-interview`, with a bundled template and
the same override chain as the others (global, then novel; it is
novel-scopable). Variables:

- the novel's title and genre (where the novel row carries a genre);
- `entity_type`, the type the interview creates;
- the proposal so far and the proposed relations;
- the last twenty turns of the transcript;
- the roster of existing entities (names, types, aliases) so the interview can
  notice a near-duplicate and ask instead of duplicating — capped at 200
  entities; the prompt says when the list was cut;
- `request`, the name of the writer's act.

**Machine markers.** The template renders the kernel-fed variables on marked
lines, and the interview's contract requires them: `PURPOSE: entity-interview`,
`TYPE: <entity type>`, `SLOTS: <the proposal as JSON>`, `RELATIONS: <the
relations as JSON>`, `TURNS:` followed by one `ASSISTANT:` or `USER:` line per
turn (oldest first), `ROSTER:` followed by one `name (type; aliases)` line per
entity, and `REQUEST: <act>`. `request` is the act's name — `answer` on a plain
turn, `accept-suggestion`, `no-idea`, `fill-all` — and the template explains in
prose what each one asks of the model. The fake provider reads these lines and
nothing else; that is how it tells an interview from any other prompt. Every
turn is exactly one line (`single_line`), so a writer's text can never forge a
marker line.

**Type tracks.** The template carries one block of question areas per entity
type — a figure is asked other things than a place, an object or an event — and
selects the block by `entity_type`. The tracks are part of the template, so the
author can change what is asked without touching code; the eight types are
`character`, `location`, `faction`, `object`, `system`, `timeline`, `event`,
`generic`. The template also tells the model what «Keine Ahnung» and «Alles
vorschlagen lassen» mean (`request` names the act; the model never has to
recognize a phrase), never to state a type, to ask one question at a time, to
propose relations only to entities of the roster or names the writer gave, and
to say when it has nothing left to ask.

**The task key stays `chat.ask`.** The interview is a chat; a fifth assignable
task would change the settings screen and the resolution table for no
user-visible gain. Today the prompts live test resolves every key *as* its task
key, so the registry gains `task_key` on a spec (default: the key itself) and
the interview key names `chat.ask` there. Split it the day an interview needs a
different model than chat. The live test follows the binding both ways: it
resolves on `spec.task_key` and records `task_key = spec.task_key`,
`prompt_key = spec.key` — equal for the four existing keys, `chat.ask` and
`knowledge.entity-interview` for the fifth.

Sample variables are what the prompts screen shows in preview: a sample novel, a
sample type, an empty proposal, a two-turn transcript, a three-entity roster.
The live test assembles the same sample beside the user's real roster for the
chosen novel.

### The first mode

`mode = "knowledge.entity"`. Slots: `name` (the one that makes the proposal
ready), `aliases`, `tags`, `content`. Relations:
`{target, type, note?}` with the target as a name the writer used or a name or
alias from the roster, and a short free-text relation type — the API has no
vocabulary, and the create dialog suggests the graph's known labels.

The proposal is the slot set plus the relations. The UI maps it onto the entity
create dialog; the user edits, then saves. Nothing is written until that save.

### The knowledge create endpoint

`POST /api/knowledge/entities` — body `{novel_id, name, type, aliases?, tags?,
content?, relations?}`, 201 with `EntityRead`. `relations` is a list of
`{to_entity_id, relation_type, note?}`: the client resolved every target to an
entity id. The creation logic moves out of `accept_suggestion` into one service
method both paths call, so the two cannot drift on name, type and label
validation. The entity and its relations are written in **one transaction**:
a relation line whose target is not in the novel refuses the whole request with
a named 422, and nothing lands half-made. Duplicate names are allowed, as they
are today (extraction creates them, the graph can merge them); the dialog says
so and keeps saving possible. The graph's «Neue Entität» and the dossiers page's
«Neues Dossier» become real in the same wave (W5's ruling: a door becomes real
when the endpoint exists, not before). `Closes #914`.

### The surface

The Stitch round of 2026-11-24 drew it on the current lore-graph page; the six
screens are the authority for the port (brief: «Round outcome»):

- **The panel** owns the graph page's right column while it is open; the
  selected entity's dossier yields and returns when the panel closes. From top
  to bottom: the header («Neue Entität», the type chip, the list of interviews,
  a close button that only hides), the collapsible proposal card («Vorschlag»:
  name, type, aliases, tags, description, the relations; open fields say «noch
  offen»; suggested parts carry the tag «vorgeschlagen»; «Vorschläge verwerfen»
  while any is present), the transcript («Assistent» and «Du», with times), the
  composer (the two chips «Keine Ahnung» and «Alles vorschlagen lassen», the
  text field, send), and the two actions «Als Entität speichern» and
  «Interview beenden».
- **Eleven states**: type chooser (with «Von Hand anlegen» as the quiet second
  path), first question, the assistant thinking, answered, a suggestion for one
  question («Übernehmen», «Ändern», «Verwerfen»), everything suggested, not
  evaluable, no model configured, interview ended, the list of interviews, the
  door with its count of open interviews.
- **The create dialog**: one dialog for both paths. From the interview the type
  is locked and the suggested parts keep their mark; every relation is a row —
  the entity, the label, an optional note — to keep, change or strike. A row
  the model named is resolved against the novel's entities by name or alias:
  one match is silent, several offer a choice («Mehrere Treffer — wählen»),
  none ask for one or a strike. Unresolved rows are not sent, and the dialog
  says so.
- The panel's open state and the active session ride the graph route's search
  parameters, as the selected entity does.

## Failure modes, named

The wire shape is the one the prompts capability already uses:
`{"detail": {"code": …, "detail": …}}`. No shared helper exists today; the
kernel gains one and both capabilities call it.

| Situation | Answer |
|---|---|
| Extraction unparseable twice | 502 `extraction-failed`; nothing was written, the composer keeps the text, «erneut versuchen» re-sends it |
| No serving tier for `chat.ask` | 502 `provider-unavailable`, with the cascade's reason; «KI-Regeln öffnen» beside it |
| The provider call fails or times out | 502 `provider-error`, the error class named; the composer keeps the text |
| Session closed | 409 `session-closed` |
| Foreign or absent session | 404, identical |
| Unknown mode, missing or unknown type | 422, `mode-unknown`, `entity-type-required`, `entity-type-unknown` |
| A relation line names an entity outside the novel | 422 `relation-target-invalid`, naming the row; nothing is written |
| Proposal conflicts with a duplicate name | Not an error: the roster hint already flagged it; the create dialog shows a notice and saves |

## Cuts

1. **This wave (W9):** session tables, the five endpoints, the prompt key, the
   `knowledge.entity` mode with relations and the two suggestion paths,
   `POST /api/knowledge/entities`, the create dialog, both doors, the panel,
   E2E (a full interview → edit → save → the entity and its relations are in the
   graph), gap ledger.
2. **Next:** the free-chat mode on the same substrate — streaming, stop,
   regenerate, sources, and the prose sink (insert at the caret, replace the
   selection) in the workspace dock.
3. **Then, one wave per mode:** stub elaboration (`mode = "knowledge.entity"`
   with `target_id`, fields prefilled from the row), novel interview (set-up
   fields; most of it is the existing wizard), scene and chapter brainstorm
   (writing's sink).

## The wave: three PRs by theme

PR-für-PR: one PR is finished (green, threads resolved) before the next starts.

| PR | Theme | Its browser test |
|---|---|---|
| 1 | **Create by hand** — the endpoint with relations, the shared creation method, the create dialog, both doors. `Closes #914`. | knowledge: an entity created from each door, with a relation; the duplicate-name notice |
| 2 | **Session substrate and the editor's fifth key** — the structured-answer helper in the kernel, the tables, the five endpoints, the prompt key, the fake's interview, the editor entry. No panel yet; chat stays «backend» in the inventory until PR 3. | prompts: five keys; the interview key's preview and live test against the fake |
| 3 | **The interview** — the panel in its eleven states, the handover into the dialog, the record. | knowledge: the interview end to end, including the «nicht auswertbar» face |

## Builder check (2026-11-20)

A fresh builder read the design against the code. Seven questions came back; six
are settled here and the seventh is a dependency the roadmap already fixes.

| Question | Settlement |
|---|---|
| Does the wave need the settings and prompts screens? | They exist since W7 and W8; the interview prompt is edited through the screen from day one. |
| Is the opening question model-generated? | No: chrome, from the host's catalog. No row, no token, translated. |
| Whose code is the panel? | The host's — knowledge's graph page. Chat has no surface and its `capability.yaml` loses `path`/`nav`. |
| Does the prompt see the transcript? | Yes — the last twenty turns since 2026-11-24. |
| What does a failed turn persist? | Nothing: both rows are written after the provider answers, in one transaction. |
| What closes a session? | An explicit act, not a panel unmount. The door resumes the newest open session. |
| Where does a door-fixed type ride? | Since 2026-11-24 the panel always sends `entity_type`; it is required for the mode. |

## Builder check (2026-11-24)

A fresh builder read the revision against the code. Three questions came back;
all three are the builder's to settle and are settled here, so none went to the
owner.

| Question | Settlement |
|---|---|
| How does the fake provider tell an interview prompt from any other, and what does `request` carry? | The template's marked lines, required by the interview's contract (`PURPOSE: entity-interview` and one line per variable); `request` is the act's name. |
| Which transaction writes the audit row of a failed turn, and is a repair retry two rows? | Rows are collected during the calls and written afterwards: with the turns on success, alone on failure. One row per provider attempt. |
| Does `task_key` change the live test's audit row too, or only its resolution? | Both: the live test resolves on `spec.task_key` and records it beside `prompt_key = spec.key`. |

## Builder calls (2026-11-24) — made while revising, for the owner to check

- The transcript bound is twenty turns, not ten.
- `act` names the writer's choice on the wire; the stored text is the label or
  the answer, so the transcript reads naturally and the model never parses a
  phrase.
- Provenance is decided by the server from the act; the model has no say.
- Two acts (`reject-suggestion`, `drop-suggestions`) need no model call.
- The audit rows of a turn are written after its calls, in the turn's own
  transaction; a repair retry is a second row.
- The proposal lives on the session, not on the turn; turns keep what was said.
- A session opened for `knowledge.entity` requires its type.
- The interview prompt is novel-scopable (the chat lookup is not).
- A failed or timed-out provider call has its own reason, `provider-error`.
- The coded error shape is shared through one kernel helper instead of a third
  private copy.
- The fake provider answers the interview from a small key–value syntax in the
  writer's turns (`Name: …`, `Beschreibung: …`, `Schlagworte: …`, `Alias: …`,
  `Beziehung: <name> | <label>`), answers «no idea» and «fill all» with canned
  values, and answers the single word `unparseable` with prose — so the browser
  test reaches the «nicht auswertbar» face for real, which no fake can today
  (the gap #932 describes).
- A closed interview keeps «Als Entität speichern».
- Unresolved relation rows are not sent, with a line in the dialog saying so.

## What is left to the builder

- The list envelope of `GET /api/chat/sessions` (the one the sibling reads use).
- How the kernel helper is named and where `MalformedAnswerError` lands.
- Whether the roster read is a kernel repository method or a small read model.
- The exact wording of the opening question per type, in three catalogs.
- The panel's behaviour on a narrow viewport (as the dossier column behaves).
- The icon and the label of the editor's fifth key.
- How the graph route's search parameters name the panel state.

## Decisions

Closed on 2026-11-24; they are not open again:

| Decision | Result |
|---|---|
| Do proposals carry relations? | **Yes** — proposed rows in the dialog |
| One session, one artifact? | **Yes** |
| Where does a closed transcript go? | Nowhere — it stays in the list; a history surface is a later wave |
| Who fixes the type? | The writer, first, in the panel |
| What does «Keine Ahnung» do? | A proposal for the question; «Alles vorschlagen lassen» fills the rest |
| How many PRs? | Three, by theme |

## Revisions since the first draft (2026-11-20)

- Relations are part of the proposal (owner, 2026-11-24).
- The type is chosen first and never changes; questions follow type tracks
  inside the template (owner, 2026-11-24).
- «Keine Ahnung» and «Alles vorschlagen lassen» exist, with «Übernehmen»,
  «Ändern», «Verwerfen» (owner, 2026-11-24).
- The two missing building blocks are named: the structured-answer helper
  (today `ask_structured` inside knowledge, returning a list) moves to the
  kernel and returns any parsed shape; a prompt key can name its task key.
- The editor's fifth key is work of its own: the editor pins exactly four keys
  in code, three catalogs, kernel goldens, API tests, the page suite and its
  E2E.
- The fake provider learns the interview, including a failure.
- Two doors become real, not one: #914 names the graph's and the dossiers'.
- The transcript bound is twenty turns; the proposal lives on the session;
  `act` and provenance are specified.
- The old entity-genesis draft is superseded by the six screens of the round.
