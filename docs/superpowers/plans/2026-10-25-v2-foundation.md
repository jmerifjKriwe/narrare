# Narrare v2 — Foundation Plan (living document)

> **Status:** Agreed direction, 2026-10-25. Not yet implemented beyond the as-built state.
> **Purpose:** The working plan for the foundation work that precedes Tier-1 features.
> Readable by a future session without prior context.
> **Authority:** `docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md`
> (ADR-100) for structure and boundaries; `docs/superpowers/specs/2026-10-22-frontend-design.md`
> for the frontend. This document records how we apply them and which decisions were taken.
>
> **The code is the newest artefact.** Where this document and the tree disagree, the
> tree wins and the document is wrong. Docs are overwritten, not superseded: this file
> lives in the repo, so git is its archive.

---

## 0. How to use this document

- One work package at a time, one commit per WP, the capability's E2E as the gate.
- A decision recorded here is binding until it is explicitly reopened (§10).
- Every dependency carries the prove-it sentence: what it saves, what it costs, what
  smaller thing it replaces (§9.5).
- No new rule, registry, check script, hook, required field or mandatory document
  without `NEEDS-APPROVAL` and the three statements (failure prevented, effort per
  change, cheaper alternative).

---

## 1. As built, 2026-10-25

Backend (5 capabilities, one folder each, `capability.yaml` facts, generated views):

- `writing`: novels, chapters, autosave, continuation stream. `Novel.genre`, `Novel.blurb`,
  `updated_at` on novels and chapters.
- `knowledge`: document upload and semantic search; entities; extraction suggestions;
  consistency findings; entity merge. `kernel/jobs` (table, worker, runtime) runs
  extraction and the whole-novel check.
- `chat`: retrieval-grounded chat with sources, streamed.
- `setup`: first-run user + first novel.
- `settings`: locale only. No UI of its own (`capability.yaml`: `path: /`, `nav: false`).

Kernel: `contracts` (models), `db`, `embeddings`, `llm` (fake + openai-compatible),
`jobs`, `retrieval`, `auth`, `testing` (E2E stack, vendor server, axe).

Frontend: capability `web/` folders, generated route table and dock registry
(`web/lib/generated/{routes,docks}.ts`), TanStack Query (`web/lib/query.ts`),
React Aria components behind `web/ui/`, workbench with URL panel state and focus
steps, ghost text as a ProseMirror decoration (never document content), live
announcer, axe assertions and keyboard-only E2E flows.

**Not built yet:** provider profiles and task assignment; a model catalog; prompt
overrides; demo content; Markdown storage and export; entity relations; entity types
beyond `character|place|thing`; a context budget; hybrid search;
a settings surface; the ⌘K palette; chapter and novel management (rename, delete,
reorder, a chapter's own title); document deletion and document metadata.

Two shipped behaviours are better than the previous plan and stay: extraction is a
review queue (`EntitySuggestion`), not auto-apply; continuation is ghost text, so a
stream that dies never autosaves half a sentence.

---

## 2. Decisions taken 2026-10-25

| Area | Decision |
|---|---|
| Entity model | **C+**: seven types + generic, aliases, tags, Markdown body, relations. No typed metadata per type, no revisions. A narrow `attributes` JSONB lands only with the canon-vs-text check (§4.9). |
| Markdown | Canonical in the DB for chapters, entities and prompts. Export/import uses the demo format (§6). |
| Provider transport | One adapter per **protocol**, not per vendor. `openai-chat` via the `openai` SDK; native adapters (Anthropic, Google) as separate files when needed. `litellm` only if a third native protocol appears. |
| Model costs | **Transport and catalog are separate.** Vendored `models.dev` snapshot + per-profile override; cost computed at write time on `LlmCall`. |
| Prompt templating | Jinja2 `SandboxedEnvironment` + `StrictUndefined`, not a hand-rolled renderer. |
| Context | One budget module in the kernel; the profile carries `context_window` and `max_output_tokens`; the whole-novel check is map-reduce, not one giant prompt. |
| Audit | `LlmCall` stores the rendered prompt, the raw answer, tokens, cost, latency and status. |
| Structured output | `response_format` when the profile supports it, one retry with the validation error, `json_repair` as the pre-parse fallback. |
| Server state | The workspace moves onto Query; Query is the one server-state path. |
| Settings | Becomes a route (`/settings`) with its own `web/` folder; the gear links to it. |
| Palette | Built in WP5 (⌘K: entities, chapters, nav). |
| Phone | Not a design target; no mobile layouts. Below 1024 px the rail and the dock are **overlays over the editor**, never columns beside it; at every width the prose column measures at least 320 px, and no page overflows horizontally at 360 px. Measured 2026-10-25 on the running stack: the workbench with a dock open leaves the editor **0 px** at 640 px wide (`scrollWidth 672` at a 640 px viewport), and the workbench alone overflows at 360 px (`scrollWidth 384`). The bar is therefore a measurement, not a formality: a gate that only reads `scrollWidth` passes at 390 px with a 110 px column. |
| Docs | Overwritten in place (spec, frontend spec, AGENTS pointer). No supersede sections. |
| Architecture | Reopenable with the three statements and explicit owner approval (§10). |
| Search | `pg_trgm` + `unaccent` now; hybrid vector + full-text later. No ANN index (see §9.1). |
| Chat scope | `Document.novel_id` nullable; retrieval filters when a novel context exists (§9.2). |
| Deletion | Export before delete now; soft delete when relations exist (§9.4). Hard deletes for chapter, novel and document land in WP6, after WP3's export exists. |
| Packages | Accepted: `openai`, `jinja2`, `sse-starlette`, `json-repair`, `pg_trgm`/`unaccent` (extensions), `keyring` (or `cryptography`), `pyyaml` at runtime, `hypothesis` + `time-machine` (dev). Rejected: `litellm` (for now), `instructor`/`pydantic-ai`, `zustand`, `react-hook-form`+`zod`, `tiktoken`, `promptfoo`/Langfuse/Phoenix, Neo4j/AGE/`networkx` (for now). |

---

## 3. Phase 0 — corrections and the AI boundary

Lands before WP1. These are defects and gaps in what is already shipped, not new scope.

### 3.1 Documentation overwrite

- **Architecture spec §13/§14**: Query and `kernel/jobs` move from "open/unbuilt" to
  decided; the frontend-location bullet, the "Query never entered" bullet and the
  "jobs not built" bullet are replaced by the current facts; the section date becomes
  2026-10-25. The §3 "Next.js shell" wording already has an as-built note; leave it.
- **Frontend spec**: phone paragraph, palette status, settings placement.
- **AGENTS.md**: one clause in the capability bullet ("…including its frontend under
  `web/`; routes are generated — `just generate`") and the §10 pointer.
- **This plan**: overwritten (this file).

### 3.2 Bounded prompts

The shipped whole-novel check sends every chapter body in one prompt; extraction sends
the full body. With the fake this passes; with a real model a novel overflows the
context window.

- **Consistency**: map-reduce. One extraction pass per chapter (a job step, progress
  per chapter), then merge findings and deduplicate by `summary`. A chapter that does
  not fit is reported as skipped — never silently dropped.
- **Extraction**: bounded at 20 000 characters of body; the tail is cut and the job
  result carries `truncated: true`, which the UI shows.

### 3.3 Structured output

Prompts keep the `PURPOSE:` marker (the fake reads it). The handler:
1. sends `response_format={"type":"json_schema", ...}` when the profile supports it;
2. parses; on failure retries **once** with the validation error appended;
3. falls back to `json_repair` before the retry;
4. a second failure fails the job with the parse reason visible in `Job.error`.

### 3.4 `LlmCall` audit

Table: `id, user_id, novel_id?, task_key, prompt_key, profile_id?, provider_kind, model,
input_tokens, output_tokens, cost_usd, latency_ms, status, error, prompt_text,
response_text, truncated, created_at`.

- Written by the job handler or the stream finalizer, **after** the answer — a record,
  not a mutation. This is the explicit exception to "no side effect in the request
  path": the audit is a log row, not user data.
- Each text column is capped (64 KB) with `truncated` set.
- It is what makes WP2's and WP4's E2E provable: "the request used profile X and the
  prompt contained Y" is an assertion on this table, not on prose.

### 3.5 LLM contract

`TextProvider.stream(prompt: str)` cannot express a system message, `max_tokens`,
temperature, JSON mode or usage. Replace with:

```python
CompletionRequest(messages, temperature?, max_tokens?, response_schema?)
CompletionEvent = Delta(text) | Usage(input_tokens, output_tokens) | Done
```

The fake keeps deriving answers from the `PURPOSE:`/`SOURCE:` markers and emits
deterministic `Usage`. The `openai-chat` adapter maps `response_format`,
`stream_options.include_usage` and typed errors. A usage object the endpoint
reports but cannot stand behind — a count missing, not an integer, a boolean,
negative — ends the call with a visible error rather than recording counts that
lie; the audit keeps the answer text either way.

### 3.6 Autosave tells the truth

`web/lib/save.tsx:36-41` fires the `PUT`, never reads the answer, then reports
`saved` and hands the body to its caller. A refused write — 413, 500, a schema that
drifted — is displayed as saved, and the only copy of that sentence is the tab about
to close. `SaveStatus` has no failure state at all, so the mistake is not an
oversight in one branch: the type cannot express it.

- The answer decides the state: `"idle" | "saving" | "saved" | "failed"`.
- A failed write is named beside the editor (one catalog key, en/de/fr), keeps the
  body pending, and retries on the next keystroke and on `visibilitychange`.
- The caller's `onSaved` — which invalidates `["novels"]` — runs on success only.
- E2E, on the real stack: `Stack.stop_api()`, type, assert the failure is named and
  no "Saved" appears; `Stack.start_api()`, type, assert "Saved" **and** the body in
  the database. The red side is the half that matters: today's code passes the first
  half by lying.

---

## 4. WP1 — Entity depth (C+)

**Why first:** the demo, extraction, relations, the graph view and the consistency
check all build on the entity model; it is also the schema change with no data to lose.

### 4.1 Model

```
Entity
  id, user_id, novel_id
  type        str(40): character | location | faction | object | system | timeline | event | generic
  name        str(200)
  aliases     json list[str]
  tags        json list[str]
  content     text (Markdown body; may be empty)
  embedding   vector nullable (name + aliases + tags + content)
  created_at, updated_at

EntityRelation
  id, user_id
  from_entity_id, to_entity_id  FK Entity (cascade)
  relation_type str (free text, suggested vocabulary in the UI)
  note          text nullable
  created_at
  unique (user_id, from_entity_id, to_entity_id, relation_type)
```

- `type` is a string with a closed vocabulary in code (`ENTITY_TYPES`), not a PG enum:
  adding a type must not need `ALTER TYPE` in a world without migrations.
- The shipped `description` column becomes `content`. The extraction writes the
  description into the body.
- No `metadata` column. Structured fields live in the Markdown body (§4.9 for the one
  exception).

### 4.2 Relations

- Directional; both directions shown on the detail view. Self-relations allowed and
  flagged.
- Suggested vocabulary (free text, autocomplete): `ally_of`, `enemy_of`, `mentor_of`,
  `student_of`, `family_of`, `friend_of`, `rival_of`, `located_in`, `controls`, `owns`,
  `inhabits`, `member_of`, `leads`, `founded`, `created`, `destroyed`,
  `transformed_into`, `appears_in`, `mentioned_in`, `caused`, `related_to`.
- `merge_entities` re-points the source's edges to the target, drops duplicates, then
  deletes the source. This is the change the current merge comment explicitly awaits.

### 4.3 API (knowledge capability)

- Extend the existing entity endpoints with `type`, `aliases`, `tags`, `content`.
- `GET/POST /entities/{id}/relations`, `PATCH/DELETE /relations/{id}`.
- `GET /entities?type=&tag=&q=` (the `q` tier ranks by needle-first `word_similarity`
  at the measured 0.5 threshold; §9.1's `similarity() ≥ 0.8` stays the dedup tier,
  not the search bar).
- Delete cascades relations (export is the safety net, §9.4).

### 4.4 Extraction and review

- The prompt asks for the eight types and relations; `EntitySuggestion` gains `type`
  and keeps `description`.
- Accepting a suggestion creates the entity with the description as body and any
  proposed relations; the relation target resolves by name within the novel and is
  skipped with a visible note when absent.

### 4.5 Frontend

- Entity list with type filter (including "generic"), tag filter, search.
- Detail: type badge, aliases, tags, Markdown body (same editor as chapters),
  relations (incoming/outgoing, add/edit/delete), merge.
- Graph view stays out (trigger: §11).

### 4.6 E2E (done criterion)

Create an entity of each type; edit body/aliases/tags; link two entities; merge two
entities and see the edges move; delete an entity and its edges; filter by type and
tag; search by a misspelt name (trigram); accept an extraction suggestion with a
relation. Real UI, real API, real DB, fake LLM. `assert_accessible` on each page.

### 4.7 Not in scope

Revisions/temporal model, typed metadata forms, attribute validity, cross-novel
entities (Series), graph visualisation, AI interview creation.

### 4.8 Migration

No data exists. `just db-reset` after the model change; E2E fixtures and the fake's
type vocabulary are updated in the same commit.

### 4.9 Deferred: `attributes`

When the **canon-vs-text** check is built (a deterministic comparison of stored canon
against prose), add one narrow JSONB column `attributes` for exactly the keys that
check compares (age, dates, affiliation). Not a schema per type, no forms, no
revisions. Until then, prose is the canon.

### 4.10 As built, 2026-10-26 (WP1)

- `ENTITY_TYPES` ships as the eight-entry tuple in `app/kernel/contracts/models.py`
  (the §4.1 list above, `event` included); prompt, parse and validation import it
  from there, and the panel labels mirror the tuple as catalog keys, a type the
  contract later adds falling back to `generic`.
- Review is the only birth path: `POST /entities` does not exist — an entity enters
  the canon exclusively through an accepted extraction suggestion.
- Merge folds the source into the survivor: the edges re-point in both directions,
  only exact `(from, to, relation_type)` duplicates drop, the source's name becomes
  an alias of the survivor, aliases and tags union case-insensitively, the source's
  body folds under a `## <source name>` heading, and the survivor's type wins.
- Deletion is the hard delete with edge cascade that §9.4 pointed at — no soft
  delete; export stays the safety net.
- The entity embedding is computed synchronously in the request's own transaction —
  at birth, on update when name/aliases/tags/content changed, and for the merge
  survivor — with the 20 000-character cap applied to the vector text only.
- The list's `q` tier ranks by `word_similarity(query, search_text)` — the query is
  the needle — with the threshold measured at 0.5 (`ENTITY_SEARCH_THRESHOLD`); plain
  `similarity() ≥ 0.8` remains the §9.1 dedup tier, not the search bar.

---

## 5. WP2 — Providers, catalog, budget

### 5.1 Data model

```
ProviderProfile
  id, user_id, name, kind, base_url, model, api_key,
  is_default, context_window?, max_output_tokens?, temperature?,
  request_timeout?, created_at, updated_at

TaskAssignment
  id, user_id, task_key, profile_id, created_at, updated_at
  unique (user_id, task_key)
```

Kernel-owned (resolution happens in the kernel); the settings capability provides the
HTTP surface.

### 5.2 Kinds and adapters

- `fake` — deterministic, no network.
- `openai-chat` — the `openai` SDK, `base_url` override. Covers OpenAI, Azure,
  OpenRouter, Groq, DeepSeek, Mistral, xAI, Together, vLLM, llama.cpp, LM Studio,
  Ollama `/v1`, LocalAI.
- Native adapters when a user needs them: `anthropic-messages`, `google-generateContent`
  (one file each, `httpx`, streaming parsed per protocol). `litellm` only when a third
  native protocol appears.
- A kind is one catalog entry plus one adapter file; no per-vendor branching.

### 5.3 Catalog and costs

- `app/kernel/llm/catalog.py` + `data/models.json`: a vendored `models.dev` snapshot
  with `snapshot_date`, refreshed by a manual script (no recipe, no gate, no network
  at runtime).
- `ModelInfo`: `context_window`, `max_output_tokens`, input/output price per Mtok,
  `supports_json_schema`, `supports_tools`, `supports_vision`.
- Lookup: exact id → provider prefix → normalized match → profile override → UI asks.
- `LlmCall.cost_usd` is computed at write time; unknown prices are stored as NULL, not 0.
  Local endpoints cost 0.
- Attribution in `THIRD-PARTY-NOTICES.md`.

### 5.4 Context budget

- `app/kernel/context.py`: one allocator, named slices, token estimates
  (`chars_per_token` on the profile, default 3.5 — German is token-hungry).
- Replaces `NARRE_CONTEXT_CHARS` and every ad-hoc cap. Continuation keeps the
  60/25/10/5 split (immediate text, referenced entities, recent chapters, style hints).
- The check and the extraction use the budget per chapter (§3.2).

### 5.5 Resolution

`resolve_provider(session, user_id, task_key)`:
exact task → capability prefix → user default → environment → fake.
Unknown task keys are allowed (forward-compatible); the UI lists the known ones.

### 5.6 Security

- API keys via `keyring` (OS keychain) with a `cryptography` Fernet fallback driven by
  `NARRE_SECRET_KEY` when no keychain is available (headless).
- List/read endpoints return masked keys (`sk-…abcd`); update with an empty key keeps
  the stored one; create returns the full key once.
- Keys never appear in logs or in `LlmCall`.

### 5.7 E2E

Two fake profiles (default + task override), set default, assign `writing.continuation`
to the alt profile, run a continuation, assert on `LlmCall` that the alt profile and
model were used; test connection; model discovery against the real vendor server;
masked key round-trip; delete guard on the default profile.

### 5.8 Not in scope

Embedding-provider profiles (env-based; re-embed handles switches), hosted auth,
per-request overrides beyond task keys.

---

## 6. WP3 — Markdown, demo, export

### 6.1 Markdown canonical

- `@tiptap/markdown` (official since 3.7; the project is on 3.31.3): `contentType:
  'markdown'`, `editor.getMarkdown()` on save.
- Chapters, entity bodies and prompt overrides are Markdown. Existing HTML bodies are
  converted once; `db-reset` is acceptable (no live data).
- A golden round-trip test over the demo corpus (real prose) is the gate: parse →
  serialize → byte-identical, or a named, documented normalisation.

### 6.2 Export / import format

The demo format is the interchange format:

```
novel/
  metadata.json      title, author, genre, language, logline, chapters[], entities[]
  chapters/*.md      frontmatter (title, position) + body
  kb/*.md            frontmatter (type, name, aliases, tags) + body
```

- One parser for demo loading and user import.
- Import creates a new novel or merges into an existing one; conflicts are reported
  per file, never resolved silently.
- Export is the backup that makes "no migrations" defensible (§9.4).

### 6.3 Anchors

Findings and entity mentions that attach to a passage store a quote plus a short
prefix/suffix, not an offset, and are re-resolved on import. An anchor that cannot be
resolved is reported, not dropped.

### 6.4 Demo rebuild

- Three demos (fantasy, sci-fi, German literary) rebuilt in the C+ shape: the
  eight-entry type vocabulary (seven concrete + generic), aliases/tags, relations,
  Markdown bodies. The v1 flat fields become body sections;
  the v1 `relationships:` map becomes `related_to` edges with the prose as `note`.
- The bundled demos are the round-trip fixture and the import test.

### 6.5 E2E

Setup wizard with a demo → chapters and entities present with relations; export → a
directory that re-imports into an identical novel (same titles, types, bodies,
relations); blank path unchanged.

---

## 7. WP4 — Prompt overrides

### 7.1 Registry

- `kernel/prompts/`: `PromptRegistry`, Jinja `SandboxedEnvironment` +
  `StrictUndefined`, no autoescape.
- Bundled templates are Python string constants in the owning capability's
  `prompts.py`; registration at import time; no central list.
- Resolution: novel-specific DB template → user-global DB template → bundled.
- `{% include 'prompt.key' %}` resolves through the registry loader with a depth
  limit (5) and cycle detection.

### 7.2 Save-time validation

`PUT` renders the override with sample variables before storing. A template that
fails (unknown variable, syntax, cycle) is refused with 422 and the render error.
A broken override can therefore never reach a model call.

### 7.3 Data model and API

```
PromptTemplate
  id, user_id, novel_id?, prompt_key, content,
  created_at, updated_at
  unique (user_id, novel_id, prompt_key)
```

`GET /prompts`, `GET/PUT/DELETE /prompts/{key}`, `GET /prompts/{key}/diff` (raw
`bundled_content` + `override_content`; the frontend renders the diff). Keys contain
dots and are ordinary path segments.

### 7.4 Smoke tests

Every bundled prompt renders with sample variables and is snapshot-compared. This is
the cheap replacement for the deleted evals suite: prompt rot becomes a failing test,
not a surprise in production.

### 7.5 E2E

Edit `writing.continuation`, save, run a continuation, assert on `LlmCall.prompt_text`
that the override was sent; reset; assert the bundled template is back; a broken
template is refused at save time.

---

## 8. WP5 — UI coherence

### 8.1 Settings route

`/settings` with `web/routes.tsx`; `capability.yaml` gains the path, `nav: false`
(the gear in the top bar links to it). Sections: language, providers, prompts.

### 8.2 Palette

⌘K opens a dialog (React Aria) over entities of the current novel, chapters, and the
generated nav. The mouse is never required for navigation afterwards.

### 8.3 Workspace server state

`NovelPage` moves onto Query (`["novels", id]`, `["chapters", id]`); autosave
invalidates `["novels"]`. Hand-rolled `pending`/`failed` states become Query states.

### 8.4 Signals and URL state

- One typed signal module (`web/lib/signals.ts`) on `useSyncExternalStore` replaces the
  two bespoke buses; each channel names its producer and consumer.
- The active chapter becomes URL state (`?chapter=`), which removes one channel.
- A store is introduced only if a channel gains a second producer or state must
  survive navigation. It would live in the shell; the import rule does not forbid it.

### 8.5 i18n

Every new key ships in en, de and fr in the same commit. `fr` may carry the English
string as a marked placeholder in the WP commit; the translation pass is its own
commit. The build error for a missing key stays.

### 8.6 E2E

Full flow: setup (demo) → workspace → entity with relation → settings (provider,
prompt) → continuation uses both → ⌘K jumps to an entity. Language switch renders all
new surfaces; axe on each page; measured at 360, 768, 1024 and 1280 px: no horizontal
overflow, a prose column of at least 320 px, and the rail and dock as overlays below
1024 px (§2).

---

## 8A. WP6 — Chapter and novel management

*Lettered rather than renumbered: AGENTS.md points at §10, and renumbering the
sections after WP5 would break that pointer silently.*

**Why:** the writing loop does not close. A chapter's title is written once — by the
server, as `""` or the localized placeholder — and never again: `ChapterUpdate.title`
exists and no field renders it. No surface deletes or renames a novel, a chapter or a
document, and `Chapter.position` exists with no way to change it. A writer can fill a
book and cannot then arrange it, correct it, or throw a mistake away. WP1–WP5 touch
none of it.

**Depends on:** WP3 (export exists before anything can be deleted, §9.4). Independent
of WP4. Reads best after WP5, whose files it reopens (Query, `NovelPage`); it may be
pulled forward to directly after WP3 when the daily loop matters more than the order.

### 8A.1 API

`writing`:

- `PATCH /novels/{id}` — title, genre, blurb.
- `DELETE /novels/{id}` — chapters cascade.
- `DELETE /chapters/{id}`.
- `PUT /novels/{id}/chapter-order` — the full ordered list of chapter ids, rewritten
  contiguously (`0..n-1`) in one transaction. No fractional positions and no gaps: the
  list the rail renders is the truth, and a half-written order is not a state the
  table can hold.

`knowledge`:

- `DELETE /documents/{id}` — chunks cascade. A wrong upload is permanent today, which
  is why the corpus guard can tell a user to re-embed but never to remove.

### 8A.2 One sentence per delete

Every delete lands with the same statement in its own UI: export is the backup (WP3),
hard delete is what happens after it. Nothing is deleted on the first click, and a
novel's confirmation names its chapter count.

### 8A.3 Frontend

- **Chapter title** in the editor header, edited in place and saved by the same
  debounced `PUT` as the body — one request, one status indicator (§3.6).
- **Rail**: rename, delete (the confirmation names the chapter), reorder by drag
  **and** by keyboard (`Alt+↑`/`Alt+↓` on the focused chapter button — the mouse may
  not be the only way to arrange a book; the E2E's keyboard flows already hold that
  line).
- **Rail scaling**: the rail becomes its own scroll container, sticky beside the
  editor, with a filter field once the count passes 20. Measured today: 45 chapters
  scroll the whole page and take the list out of sight while the editor is written in.
- **Shelf**: rename and delete a novel.
- **Documents**: size, chunk count, upload date and a delete button; the empty state
  names the formats and the size limit.

### 8A.4 E2E

Rename a chapter → the rail, the open editor's header and the shelf's "last touched"
all carry it. Move chapter 3 to 1 by drag and by `Alt+↑` → the order survives a reload.
Delete a chapter → its neighbour opens and the table has one row fewer. Rename a
novel. Export, then delete a novel → gone from the shelf and from the database.
Delete a document → its passages no longer answer a search. A 60-chapter novel keeps
the rail inside the viewport while the editor scrolls. `assert_accessible` on each
page.

### 8A.5 Not in scope

Multi-select, chapter duplication, parts/volumes (Series is Tier 2), undo/trash (soft
delete lands with relations, §9.4), importing an existing manuscript at scale (that is
WP3's import).

---

## 9. Cross-cutting

### 9.1 Search

- `CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;`
  in `db-init`; a `search_text` column on entities (name + aliases + tags) with a GIN
  trigram index.
- Dedup tiers: exact/alias → trigram similarity ≥ 0.8 → embedding cosine ≥ 0.85.
- Hybrid retrieval (full-text + vector, reciprocal rank fusion) when entity count or
  document count makes vector-only visibly weak; `simple` text search config for a
  multilingual corpus.
- **No ANN index**: `Vector()` without a dimension cannot be HNSW-indexed. At novel
  scale a sequential scan is correct. Revisit at ~100k chunks, which forces a fixed
  dimension per corpus (already the corpus guard's rule).

### 9.2 Chat scope

`Document.novel_id` nullable (NULL = the user's library). Upload accepts an optional
novel; retrieval filters by novel when the caller has one. `PassageRepository.search`
gains the filter.

### 9.3 Jobs

Built. Re-embed stays synchronous while the corpus is small; it becomes a job (kind
`reembed`) when a full corpus exceeds ~30 s. The lane is single-worker, at-least-once;
handlers stay idempotent.

### 9.4 Deletion and backup

- Export before delete is the safety net now.
- Soft delete (`deleted_at` + default filter) was the "decide at WP1 review" question
  for deletes that take edges with it — decided 2026-10-26: hard delete with edge
  cascade; export is the safety net, no soft delete.
- `db-reset` runs `pg_dump` into `.narrare/backups/` first (three lines, no recipe).

### 9.5 Dependencies

| Package / data | Saves | Costs | Replaces |
|---|---|---|---|
| `openai` | SSE framing edge cases, retries, JSON schema, usage | one package; OpenAI-shaped assumption | hand-written parser |
| `jinja2` | conditionals, loops, includes, cycles, good errors | sandbox config; template syntax for users | hand-rolled renderer + Python conditionals |
| `sse-starlette` | ping, timeouts, disconnect detection | one small package | three hand-written loops |
| `json-repair` | near-miss JSON from local models | may mask a prompt bug | a failed job |
| `keyring` / `cryptography` | keys out of dumps and logs | OS dependency / fallback | plaintext |
| `pg_trgm` + `unaccent` | fuzzy names, dedup middle tier | two extensions | a Python matcher |
| `models.dev` snapshot | context windows and prices for all providers | a refresh script and attribution | a hand-maintained table |
| `hypothesis`, `time-machine` | parser, budget and timestamp properties | dev-only test time | hand-written edge cases |

Rejected for now, with the trigger that would change it: `litellm` (third native
protocol), `instructor`/`pydantic-ai` (retry logic beyond ~150 lines), `zustand`
(second producer per channel or state that survives navigation), `react-hook-form`+
`zod` (a form surface the generated schema cannot drive), `tiktoken` (all providers
OpenAI), `promptfoo`/Langfuse (a hosted prompt service), `networkx` (centrality or
clustering), Neo4j/AGE (a real performance wall).

---

## 10. Rules and reopening

Standing rules (AGENTS.md) stay: one capability one folder; no capability imports
another; green E2E as done; no side effect beyond the request's transaction; `user_id`
on every user-owned row; English in code and docs; en/de/fr for user-visible text;
governance budget.

Two clarifications:

1. **The budget counts rules, not modules.** A kernel module is allowed when two or
   more capabilities need it. Three truncation constants and two SSE loops are the
   evidence that the opposite reading costs more than it saves.
2. **The architecture is a decision, not a law.** Any boundary may be proposed for
   reopening with the governance budget's three statements: the failure it prevents,
   the effort it creates, the cheaper alternative. Crossing a boundary — a capability
   importing another, a second data store, a global store, a migration tool — needs
   the product owner's explicit approval and is recorded as a dated decision. Until
   then, the boundary stands.

Provability: the fake provider stays the only fake, but the fake alone cannot prove
which profile or prompt a call used. `LlmCall` is the evidence; WP2 and WP4 assert on
it.

---

## 11. Deferred, with the trigger that resolves it

| Deferred | Trigger |
|---|---|
| Entity revisions / temporal model | a feature asks "state at chapter N" and prose derivation is too slow or too lossy |
| `attributes` JSONB | the canon-vs-text check is built (§4.9) |
| Graph visualisation (KB-008) | relations exist and a user asks for the picture |
| `kernel/graph.py` traversal | the first consumer after the graph view or context assembly |
| `networkx` | centrality/clustering beyond BFS |
| `litellm` | a third native protocol |
| Alembic | the first novel written in Narrare that must survive a schema change |
| ANN index | ~100k chunks, or a fixed dimension per corpus |
| Embedding provider profiles | a user wants two embedding models side by side |
| Prompt file overrides (Phase B) | a user asks to edit prompts outside the DB |
| Series / cross-novel entities | Tier 2 |
| Encrypted API keys | done in WP2 (keyring/Fernet) |
| Chat thread memory (each ask replaces the last; the page and the dock share nothing) | a user keeps an answer beyond the session, or Tier-1 chat work starts |
| Focus depth 2's visible exit (Esc only, undocumented) and shortcut hints | WP5 ships the palette, which is the one place a shortcut can be named without new chrome |
| The shelf's hero repeats the list's first row; the first paint is `null` (white, not a skeleton) | WP5 touches `NovelsPage` and the shell anyway (§8.3) — fold in there, do not open a WP |
| Packaging: a one-command install (`docker compose up` / an image), instead of a five-tool toolchain | a writer who is not a developer asks how to run it — which is the README's audience already |

---

## 12. Verification per WP

- `just check` before every commit; `just verify` before a WP closes.
- The capability's E2E is the gate; `assert_accessible` on every page it visits.
- Phase 0: a test that a 200k-character novel check runs as map-reduce with per-chapter
  progress; a test that a malformed JSON answer retries once and then fails visibly;
  a test that `LlmCall` records profile, tokens and cost; a test that a refused save
  is named and never shown as "Saved", on the real stack with the API stopped
  (§3.6).
- WP1: entity type/relation/merge/delete E2E; trigram search finds a misspelt name.
- WP2: two fake profiles, task override proven via `LlmCall`; masked key round-trip;
  cost present for a priced model and NULL for an unknown one.
- WP3: round-trip over the demo corpus; export → import → identical novel.
- WP4: prompt smoke snapshots; override proven via `LlmCall.prompt_text`; broken
  template refused at save.
- WP5: ⌘K reaches an entity; settings route; language switch; axe; 360/768/1024/1280 px
  with no overflow and a prose column of at least 320 px (§2).
- WP6: rename, reorder by drag and by keyboard, delete (chapter, novel after export,
  document), a 60-chapter rail that stays inside the viewport, and every delete's
  cascade proven against the database rather than the screen.
