# Assistant sessions — conversations that produce a proposal

> **Date:** 2026-11-20 · **Status:** draft for owner approval
> **Supersedes nothing.** It extends the roadmap's Phase 1 chat item and the
> "proposal and diff" contract (roadmap §2.2) with the shape the owner described
> on 2026-11-20: guided assistants that turn a conversation into an entity, a
> stub, an idea, or a novel.

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
einfügen" or "Auf Station 7 korrigieren / Ignorieren", the entity-genesis draft
ends in "Dossier verwerfen / Als Verknüpfung vormerken / Als kanonische Entität
speichern". v1 built exactly this shape once, as **KB sessions** (KB-002): a
guided interview with typed fields, reviewed and saved through the entities API,
with a bounded number of questions.

So the reusable part is the session and the proposal. The first cut proves them
on the mode the owner wants first: **create an entity**.

## The spine

```
door (graph's "new with assistant")
  → session (novel, mode, transcript)
  → turns (question, free-text answer, extracted slots)
  → proposal (name, type, aliases, tags, content)
  → the owning capability's create form, prefilled
  → the user edits and saves through POST /api/knowledge/entities
```

Chat never writes an entity row. The session is a producer; knowledge is the
owner. That is rule 1 read strictly, and it is also what makes the review step
honest: the entry the user saves is the entry they saw.

## Approaches considered

| | Shape | Trade-off | Verdict |
|---|---|---|---|
| A | **Modes over one session substrate.** A mode fixes the prompt key, the context, the slots and the target. Free chat is one mode, the entity interview another. | One contract, one table pair, then one wave per mode. A new field in a proposal touches two places. | **Chosen.** |
| B | *One chat, many tools.* The model gets a tool per capability and writes directly. | Flexible, one surface; but every write is non-deterministic, needs permissions and undo, the fake provider must simulate tool calls, E2E turns flaky, and the prompts capability becomes redundant. | Rejected: it moves the risk from the schema into the model. |
| C | *Guided forms only*, no free text. | Cheapest and most testable; loses the discussion the owner asked for. | Rejected. |

**Guided first, free chat second.** The owner's first real use is an assistant
that produces an entity, so cut 1 is the interview; free chat and the prose
sink follow on the same substrate. The order is deliberate: the interview
exercises persistence, extraction and acceptance, which are the hard parts;
prose insertion is comparatively mechanical.

## Goals

- A session that survives a reload, per novel, with the whole transcript.
- Turns that answer in prose **and** carry the slots extracted so far.
- A proposal the user reviews and edits before anything is written.
- The interview prompt is a **registered prompt key**, editable through the
  prompts API on the day this lands and through the prompts screen when that
  wave ships. This wave does not wait for that screen.
- Evidence for a later mode: adding one is a prompt key, a slot list and a
  target — not a new subsystem.
- The entity create endpoint the graph has been standing an honest disabled door
  for since W5.

## Non-goals

- Streaming the interview's answers (turn-based JSON is enough; free chat adds
  the stream).
- Tools, function calling, an agent loop.
- Automatic writes of any kind.
- Relations inside the proposal (cut 1 proposes fields only; the create form's
  relation step stays the user's).
- A chat screen of its own; the session lives in a surface's side panel.
- Any model-quality claim: the fake provider's interview is deterministic and
  proves the plumbing, not the prose.

## Anti-goals

- A session whose transcript is not persisted, so a reload loses the interview.
- A proposal that silently differs from what lands in the fields.
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
  translated; chrome in en/de/fr through the capability catalogs.
- The only fake is the provider at its boundary.

## How it works

### Data

`assistant_sessions` — `id`, `user_id`, `novel_id`, `mode`, `target_id`
(nullable; the entity being improved, for the stub mode), `closed_at`,
`created_at`, `updated_at`. A session is open until closed; a closed session is
read-only and still listed.

`assistant_turns` — `id`, `session_id`, `seq`, `role` (`user` | `assistant`),
`text`, `proposal` (JSONB, null unless the turn carries one), `created_at`.
The sequence is per session and monotonic; a turn is never edited.

Full transcripts are kept. They are the user's own material, they cost kilobytes,
and "what did it propose last week" is a question the product should answer. No
retention job in cut 1.

**Lifecycle.** A session is open until the user ends it. Closing the panel only
hides it; the door reopens the newest open session for the same mode and target
and offers "neu beginnen" beside it. Several sessions may be open at once — the
list shows them — and ending one is explicit. Deleting a novel deletes its
sessions with it; the cascade is the database's, not a cleanup job.

### Endpoints (capability `chat`)

| Method | Path | What it does |
|---|---|---|
| POST | `/api/chat/sessions` | Open a session: `{mode, novel_id, entity_type?, target_id?}` → the session read |
| GET | `/api/chat/sessions?novel_id=` | List sessions for a novel, newest first |
| GET | `/api/chat/sessions/{id}` | The transcript |
| POST | `/api/chat/sessions/{id}/turns` | `{text}` → `{reply, proposal?}` |
| POST | `/api/chat/sessions/{id}/close` | Idempotent close |

`entity_type`, when the door fixes one, is validated against `ENTITY_TYPES` at
the boundary and becomes the mode's preset slot. The opening question is **chrome,
not a turn**: it is the mode's first prompt, rendered from the hosting
capability's catalog, so it is translated and costs no model call. The transcript
holds only what the user and the model actually said.

A turn against a closed session is a 409 with a named reason. A session of
another user is a 404, indistinguishable from absent — the codebase's existing
IDOR rule.

### Chat has no surface of its own

The panel that hosts a session belongs to the capability whose page it sits on:
the entity interview is knowledge's panel on the graph page, the free chat is
writing's dock in the workspace. It reaches `/api/chat/*` through the shared API
client, which every surface already has — no capability imports another, and no
page-level registry is invented. Chat states the contract and owns the tables;
the host owns the chrome, the catalogs and the E2E. Chat's `capability.yaml`
then drops `path: /chat` and `nav: true`: today they generate nothing (there is
no web module), and a declared surface that cannot exist is a promise the
record should not carry.

### The turn

Turn-based, JSON, no SSE. The model answers in prose and returns the slots it
has so far. Two calls per turn in the simplest implementation — one to answer,
one to extract — are allowed if one combined call proves unreliable; the
contract is the payload, not the call count. The model sees the transcript
(last ten turns, the same bound the v1 chat used) as well as the slots.

**Nothing is written until the model has answered.** The turn's two rows (the
user's text and the reply) are written in one transaction after the provider
returns; a failed call leaves the transcript untouched and the client keeps the
text in the composer. This keeps the "never edited, monotonic seq" invariant and
never holds a database transaction across a provider call.

Retry after a failure is therefore not a second user turn: the failed attempt
left no row.

Model output, per turn: `{"reply": str, "slots": {name?, type?, aliases?,
tags?, content?}}`. Extraction uses the kernel's JSON request helper (a schema
where the adapter supports one, an instruction plus one repair attempt where it
does not); a second parse failure is a 502 with a named reason, never an empty
proposal. `ready` is **not** the model's to decide: the interface enables
"Saving" once `name` and `type` are present, which is a fact it can check.

### The prompt

A new registered key, `knowledge.entity-interview`, with a bundled template and
the same override chain as the other four (global, then novel). Variables: the
novel's title and genre, the entity type being created (when the door fixes
one), the current slots, the last ten turns of the transcript, and the roster of
existing entities (names, types, aliases) so the interview can notice a
near-duplicate and ask instead of duplicating. Sample variables are what the
prompts screen shows in preview.

The task key stays `chat.ask`: the interview is a chat, and a fifth assignable
task would change the settings screen and the resolution table for no user-
visible gain. Split it the day an interview needs a different model than chat.

### The first mode

`mode = "knowledge.entity"`. Slots: `name` (required), `type` (required, one of
`ENTITY_TYPES`), `aliases`, `tags`, `content`. The door may fix the type
("new character"), in which case the interview does not ask for it.

The proposal is the slot set. The UI maps it onto the entity create dialog; the
user edits, then saves. Nothing is written until that save.

### The knowledge create endpoint

`POST /api/knowledge/entities` — body `{novel_id, name, type, aliases?, tags?,
content?}`, 201 with `EntityRead`. The creation logic exists inside
`accept_suggestion`; it moves to a service method both paths call, so the two
cannot drift on type validation or alias dedupe. The graph's disabled door
becomes a real dialog in the same wave (W5's ruling: a door becomes real when
the endpoint exists, not before).

### The surface

The entity-genesis draft (`docs/design/stitch/screens/knowledge/
entity-genesis-ai-dialog.html`) is the basis and needs a harmonization round: it
shows a dossier preview, a completion percentage, a graph preview and a
"Verknüpfung vormerken" action, none of which cut 1 has. The harmonized draft
keeps: the side panel, the transcript, the dossier preview with four fields, and
two actions — discard, and save-as-entity (which opens the prefilled create
dialog). States the round must draw: opening, asking, answered, proposal ready,
extraction failed (named), closed/read-only.

## Failure modes, named

| Situation | Answer |
|---|---|
| Extraction unparseable twice | 502 `extraction-failed`; nothing was written, the composer keeps the text, "erneut versuchen" re-sends it |
| Session closed | 409 `session-closed` |
| Foreign or absent session | 404, identical |
| Provider missing for the task | 502 `provider-unavailable`, with the cascade's reason |
| Proposal conflicts with a duplicate name | Not an error: the roster hint already flagged it; the create endpoint decides, as it does for manual creation |

## Cuts

1. **This wave:** session tables, the five endpoints, the prompt key, the
   `knowledge.entity` mode, `POST /api/knowledge/entities`, the create dialog,
   the harmonized panel, E2E (a full interview → edit → save → the entity is in
   the graph), gap ledger.
2. **Next:** the free-chat mode on the same substrate — streaming, stop,
   regenerate, sources, and the prose sink (insert at the caret, replace the
   selection) in the workspace dock.
3. **Then, one wave per mode:** stub elaboration (`mode =
   "knowledge.entity"` with `target_id`, fields prefilled from the row), novel
   interview (set-up fields; most of it is the existing wizard), scene and
   chapter brainstorm (writing's sink).

## Builder check (2026-11-20)

A fresh builder read the design against the code. Seven questions came back; six
are settled here and the seventh is a dependency the roadmap already fixes.

| Question | Settlement |
|---|---|
| Does the wave need the settings and prompts screens? | No for the build; the roadmap puts settings, then prompts, then this. The prompt is edited through `/api/prompts` in this wave's E2E and through the screen once that wave ships. |
| Is the opening question model-generated? | No: chrome, from the host's catalog. No row, no token, translated. |
| Whose code is the panel? | The host's — knowledge's graph page. Chat has no surface and its `capability.yaml` loses `path`/`nav`. |
| Does the prompt see the transcript? | Yes, the last ten turns; it was missing from the variable list, and an interview that cannot refer to an earlier answer is not an interview. |
| What does a failed turn persist? | Nothing: both rows are written after the provider answers, in one transaction. |
| What closes a session? | An explicit act, not a panel unmount. The door resumes the newest open session for its mode and target. |
| Where does a door-fixed type ride? | `entity_type` on the session body, validated against `ENTITY_TYPES`. |

## What is left to the builder

- Whether one call or two carries the turn.
- How the JSON request helper is shaped in the kernel, and which adapters get a
  schema and which get the instruction.
- Whether the roster read is a kernel repository method or a small read model.
- The exact wording of the opening turn per mode.
- Where the session list lives (panel header dropdown vs. the surface's own
  list).
- Whether `assistant_turns.proposal` is JSONB or a typed column set — the payload
  is small and shape-stable; either is defensible.

## Open decisions

| Decision | Why it matters | Default if nobody decides |
|---|---|---|
| Do proposals ever carry relations? | The draft asks for "als Verknüpfung vormerken"; cut 1 leaves it out | Out of cut 1; revisit with the stub mode |
| Is a session per entity or per conversation? | One session that produces three entities would need a proposal per entity | One session, one artifact, in cut 1 |
| Where does the closed transcript go? | Nowhere — it stays in the list; a "history" surface is a later wave | Stays, no surface beyond the panel's list |
