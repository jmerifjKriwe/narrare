# WP1 — Entity Depth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entities become C+ — eight types, aliases, tags, a Markdown body, directed relations with a suggested vocabulary, a merge that rewires edges, API filters (`type`/`tag`/`q`), and an extraction that proposes types and relations.

**Architecture:** The model change rides one `just db-reset` (no migrations, §4.8): `Entity.kind`/`description` become `type`/`content` plus `aliases`/`tags` (JSONB), `search_text` (GIN trigram), nullable `embedding`; `EntityRelation` is a new kernel-contracts table whose FKs cascade. Knowledge owns every consumer: repository (search + relations), service (merge folding, accept resolution, embedding), router, prompts/fake (eight types + relation proposals), and the Wissen-dock frontend. The only fake stays at the LLM/embeddings boundary.

**Tech Stack:** as shipped (FastAPI, SQLAlchemy async, PostgreSQL + pgvector + `pg_trgm`/`unaccent`, TanStack Query, React Aria behind `web/ui/`).

**Spec:** `docs/superpowers/specs/2026-10-26-wp1-entity-depth-design.md` (moved here with this plan; originally written in `~/.opencode/plan/`). Decisions D1–D10 are binding; the Fahrplan (`docs/superpowers/plans/2026-10-25-v2-foundation.md` §4) is corrected by Task 4.
**Base:** `narrare/main` @ `64a25e79`. Execute on a new branch `wp1-entity-depth` from it.

## Global Constraints

- English in code, comments, tests, commits. User-visible text only through `i18n/{en,de,fr}.json`, all three together (de du-form; fr may carry the English string as a marked placeholder); a missing key is a build error.
- Capabilities never import capabilities; kernel contracts/models are the shared domain. `ENTITY_TYPES` lives in `app/kernel/contracts/models.py` beside `Entity`. RAC only in `web/ui/`.
- No side effect in the request path beyond the request's own transaction (D14). Embedding in-transaction follows the document-ingestion pattern (design D5).
- No new rules, registries, check scripts, hooks or gates. Generated files carry the DO-NOT-EDIT header; `just generate` stays drift-free (run twice, diff clean).
- E2E = real UI, real API, real Postgres; fake only at the LLM/embeddings boundary; `assert_accessible(page)` ends every flow. Backend tests ride the real DB fixtures.
- Conventional commits; `feat`/`fix` carry a real `User-visible:` line; `--no-verify` forbidden; `just` recipes only (`just check` before every commit, `just verify` before the WP closes, `just db-reset` after model changes).

## Review Focus

1. **Merge loses a live edge or the source's name** — dedupe must drop only exact `(user, from, to, relation_type)` duplicates, and the source name must survive as the survivor's alias. Pinned by Task 1's merge tests (both directions re-pointed, duplicate dropped, self-edge survives flagged, name→alias).
2. **The misspelt-name search is unsatisfiable or floods** — a literal 0.8 would fail `Kathrina`→`Katharina` (≈0.58 plain). Pinned by Task 1's `q` tests with `word_similarity` and the measured threshold (start 0.5).
3. **Accept attaches a proposed relation to the wrong canon row** — two entities sharing a name/alias must skip visibly, never guess. Pinned by Task 2's ambiguity test (skip note, zero edges).
4. **A stale vector or `search_text` after update/merge** — every write path that changes name/aliases/tags/content must recompute both. Pinned by Task 1 (find by a freshly added alias; find the survivor by the source's name after merge).
5. **An embedding-model switch silently mixes vector widths** — the entity corpus keeps the document guard's rule. Pinned by Task 1's `stored_entity_width` mismatch test (refused like an upload, 409).

---

### Task 1: Model, search, relations API, merge

**Files:**
- Modify: `app/kernel/contracts/models.py` (Entity v2 + `ENTITY_TYPES` + `EntityRelation`; `EntitySuggestion.kind`→`type`, + `relations` JSONB)
- Modify: `app/kernel/db/init.py` (`CREATE EXTENSION IF NOT EXISTS pg_trgm`, `unaccent` beside `vector`)
- Modify: `app/capabilities/knowledge/{repository,service,schemas,router,prompts,jobs}.py` (`jobs.py` mechanical: canon grounding `(name, kind)`→`(name, type)`, `ENTITIES_SCHEMA`'s item key `kind`→`type` with `ENTITY_TYPES` enum, parse vocabulary)
- Modify: `app/kernel/llm/fake.py` (mechanical in this task: the extraction answer's item key `kind`→`type`, the vocabulary imported from `ENTITY_TYPES` — relation proposals arrive in Task 2)
- Modify: `app/capabilities/knowledge/web/EntitiesPanel.tsx`, `web/lib/query.ts` (mechanical `kind`→`type`, `description`→`content`; no new UI)
- Modify: `i18n/{en,de,fr}.json` (`knowledge.kind.*` → `knowledge.type.*`, eight keys)
- Test: extend `app/capabilities/knowledge/tests/test_entities.py`, `test_entity_crud.py`; create `app/capabilities/knowledge/tests/test_relations.py`
- After the model change: `just db-reset`, `just generate`

**Interfaces:**
- Produces: `ENTITY_TYPES = ("character", "location", "faction", "object", "system", "timeline", "event", "generic")` in kernel contracts — every consumer (prompts, parse, service validation, panel labels) imports it from there.
- Produces: `EntityRepository.list_for_novel(novel_id, *, type: str | None = None, tag: str | None = None, q: str | None = None)`; `create(novel_id, name, type, content, aliases, tags, embedding)` computes `search_text = " ".join([name, *aliases, *tags])`; `stored_entity_width() -> int | None`.
- Produces: `ENTITY_SEARCH_THRESHOLD = 0.5`; the `q` tier is `word_similarity(unaccent(lower(Entity.search_text)), unaccent(lower(q))) >= threshold`, ordered by that similarity descending; GIN trigram index on `search_text` (plain `gin_trgm_ops`; the unaccented expression scans at novel scale — correct per §9.1).
- Produces: `RelationRepository(ScopedRepository[EntityRelation])` with `list_for_entity(entity_id)` (both directions, `created_at` order), `get`, `create`, `delete`.
- Produces: service `list_entities(novel_id, type=None, tag=None, q=None)`, `entity_relations(entity_id)`, `add_relation(entity_id, to_entity_id, relation_type, note) -> EntityRelation`, `update_relation(relation_id, ...)`, `delete_relation(relation_id)`; errors `InvalidRelationError` (blank/over-long `relation_type`, >80 chars → 422) and `RelationExistsError` (unique violation → 409). Self-relations are **allowed** (flagged only in the UI). Relation `from`/`to` are immutable — moving an edge is delete plus create.
- Produces: `AcceptResult` stays `(Entity, EntitySuggestion)` this task — created with `aliases=[]`, `tags=[]`, `content=description or ""`, embedding and `search_text` computed; the suggestion's `relations` column is written as `[]` and not yet resolved (Task 2).
- Produces: embedding text `_embedding_text(entity)` = `name + aliases + tags + content[:20_000]` (`EMBEDDING_CONTENT_LIMIT = 20_000`, vector only); every later write path reuses it. The entity width guard reuses `EmbeddingMismatchError` → 409, exactly like upload.
- Produces: schemas `EntityRead {id, novel_id, name, type, aliases, tags, content, created_at, updated_at}`, `EntityUpdate {name?, type?, aliases?, tags?, content?}` (still `model_fields_set` semantics), `RelationCreate {to_entity_id, relation_type: 1..80, note?}`, `RelationPatch {relation_type?, note?}`, `RelationRead {id, from_entity_id, to_entity_id, relation_type, note, created_at}`.
- Produces: merge per D3 — re-point both directions, drop only exact duplicates, source name → survivor alias (case-insensitive dedupe), aliases/tags union, survivor body + `"\n\n## {source name}\n\n"` + source body when non-empty, survivor's type wins, re-embed survivor + recompute `search_text`, delete source.

- [ ] **Step 1: Failing backend tests** — relations CRUD (list both directions, patch, delete, duplicate → 409, self-relation → 201); list filters (`type` exact, `tag` JSONB contains, `q` finds `Katharina` by `Kathrina`, empty `q` = no filter); merge (edges re-pointed both directions, exact duplicate dropped, self-edge survives, name→alias, unions, body fold under `## <source>`, find survivor by source name); update recomputes (find by a just-added alias); width mismatch refusal. Update fixtures to the new columns. Run red.
- [ ] **Step 2: Implement** models + extensions + repository (JSONB `aliases`/`tags`, search) + service (validation: type in `ENTITY_TYPES`; aliases/tags each nonblank, ≤200 chars, case-insensitively deduped) + schemas + router + the mechanical frontend/catalog renames + fake's type vocabulary import.
- [ ] **Step 3: Green** — capability tests, full `just test`, existing E2E green (mechanically updated), `just generate` drift-free.
- [ ] **Step 4: Commit**

```
feat(knowledge): entities gain types, aliases, tags and relations

The C+ model lands in one db-reset: eight types, JSONB aliases and tags,
a Markdown body, trigram search over a maintained search_text, directed
relations whose foreign keys cascade, and a merge that re-points the
source's edges and folds its fields into the survivor instead of
dropping them.

User-visible: entities carry a type, aliases and tags; the list filters
and fuzzy-searches; merging keeps both texts and every edge.
```

### Task 2: Extraction v2 — types and relation proposals

**Files:**
- Modify: `app/capabilities/knowledge/prompts.py` (`ParsedRelation`, `ParsedEntity.type` + `relations`, extraction prompt asks the eight types and relations)
- Modify: `app/capabilities/knowledge/jobs.py` (`ENTITIES_SCHEMA` gains `type` enum + `relations: [{target, type}]`, required, `additionalProperties: false`; `parse_entities` validates)
- Modify: `app/kernel/llm/fake.py` (extraction branch cycles `ENTITY_TYPES`; entity *i* proposes `related_to` to entity *(i+1) mod n* when the answer has ≥2 entities)
- Modify: `app/capabilities/knowledge/{repository,service,schemas,router}.py` (suggestion stores `type` + `relations`; accept resolves and returns `AcceptRead`)
- Test: extend `app/capabilities/knowledge/tests/test_extraction.py`; `app/capabilities/knowledge/e2e/test_extraction_e2e.py`

**Interfaces:**
- Consumes: Task 1's model, `ENTITY_TYPES`, relation repository, embedding-on-birth.
- Produces: `ParsedRelation(NamedTuple)` with `target: str`, `relation_type: str`; `ParsedEntity` gains `type: str`, `relations: list[ParsedRelation]`. Parse refusals: target not a nonblank string ≤200, `relation_type` not a nonblank string ≤80 → `MalformedAnswerError` (nothing written).
- Produces: `AcceptRead {entity: EntityRead, skipped_relations: list[SkippedRelationRead {target_name, relation_type}]}`; `POST .../accept` returns it.
- Produces: accept resolution per D8 — trimmed, case-insensitive exact match on names **and** aliases (the just-created entity included); multiple matches → skip; no match → skip; skipped pairs ride the response, announced once by the UI (Task 3). No fuzzy matching.
- Produces: `SuggestionRead` gains `type` and `relations: list[ProposedRelationRead {target_name, relation_type}]`; the filing dedupe key becomes `(name, type)`.

- [ ] **Step 1: Failing backend tests** — parse with relations (valid; each malformed variant refuses); accept resolves by name and by alias case-insensitively; ambiguous (two entities share the alias) → skip note, zero edges created for it; absent target → skip note; accept order dependence (target pending → skip; target accepted first → edge exists); exactly-once unchanged. Run red.
- [ ] **Step 2: Implement** prompt + schema + fake + repository + accept resolution + `AcceptRead`.
- [ ] **Step 3: Green** — capability tests, full `just test`, extraction E2E updated and green (fake proposes a relation; accept creates the edge; the skip note rides the response), `just generate` drift-free.
- [ ] **Step 4: Commit**

```
feat(knowledge): extraction proposes eight types and relations

The prompt asks the C+ vocabulary and, per entity, relations to other
named entities; review files type and proposal with the suggestion, and
accept creates every relation whose target resolves by name or alias in
the novel — the ones that do not resolve come back as visible skips,
never silent drops.

User-visible: accepting a suggestion can link the new entity to the
entries it names, and says which links it could not place.
```

### Task 3: Frontend — filters, grown dialog, relations UI

**Files:**
- Modify: `app/capabilities/knowledge/web/EntitiesPanel.tsx` (filters row, card v2, grown EditEntityDialog, relations section, `ChipsField` built on `web/ui/TextField`)
- Create: `app/capabilities/knowledge/web/relations.ts` (`RELATION_TYPES` — the twenty §4.2 labels — plus the label-key helper)
- Modify: `app/capabilities/knowledge/web/ExtractionPanel.tsx` (ProposalCard shows type + proposed relations; skipped announce on accept)
- Modify: `web/lib/query.ts` (`useEntitiesQuery(novelId, filters)` with `{type?, tag?, q?}`; `useEntityRelationsQuery`, `useAddRelation`, `useUpdateRelation`, `useDeleteRelation`; accept mutation surfaces `AcceptRead`)
- Modify: `i18n/{en,de,fr}.json` (type filter, tag filter, aliases/tags/body labels, relation labels for the twenty types with raw-text fallback, incoming/outgoing, self-relation mark, skip announcement)
- Test: `app/capabilities/knowledge/e2e/test_knowledge_dock_e2e.py` extended; new flows red first. Every flow ends `assert_accessible(page)`.

**Interfaces:**
- Consumes: Task 1's `GET /entities?type=&tag=&q=`, relations endpoints; Task 2's `AcceptRead`.
- Produces: variant B (design D9) — the card stays compact (name, type badge, alias/tag chips, content preview, compact relation rows both directions, self-relation marked); all editing lives in the grown dialog: name, type ComboBox (`knowledge.type.*`), `ChipsField` aliases, `ChipsField` tags, body multiline TextField (Markdown source — no renderer, WP3 brings the editor), relations section (rows with inline edit/delete; add row = target ComboBox over the novel's other entities + relation-type ComboBox over `RELATION_TYPES` with free text allowed + optional note). Merge/Delete dialogs unchanged.
- Produces: the `q` box becomes the server search (debounced), replacing the client-side name filter; the passage second tier is untouched. Filter options (types, tags) come from the unfiltered entities query kept alongside the filtered one.
- Produces: the accept flow announces `skipped_relations` once through the live announcer.

- [ ] **Step 1: Failing E2E** (type/tag filter, misspelt search, dialog edit of aliases/tags/body, relation add/edit/delete, self-relation mark, skip announcement). Run red.
- [ ] **Step 2: Implement** filters + card + dialog + relations UI + queries + catalogs.
- [ ] **Step 3: Green** — full suite, typecheck, build, `just generate` drift-free.
- [ ] **Step 4: Commit**

```
feat(knowledge): the entity surface grows filters, fields and relations

The Wissen dock lists with type and tag filters and a fuzzy server
search; the detail card shows aliases, tags and both directions of a
relation; the edit dialog carries every field, and relations are added
against the novel's entries with the suggested vocabulary as
autocomplete and free text allowed.

User-visible: filter and find entities, edit their aliases, tags and
Markdown body, and maintain their relations beside the text.
```

### Task 4: The §4.6 E2E and the Fahrplan overwrite

**Files:**
- Create: `app/capabilities/knowledge/e2e/test_entity_depth_e2e.py`
- Modify: `docs/superpowers/plans/2026-10-25-v2-foundation.md` (§4.1 type line gains `event`; §4 records the merge folding, the hard-delete cascade as the settled §9.4 decision, the embedding lifecycle, `word_similarity` with measured threshold, and the birth-path invariant)

**Interfaces:**
- Consumes: everything above. Fake only at the LLM/embeddings boundary.

- [ ] **Step 1: Failing E2E** — the full §4.6 flow on the real stack: a chapter naming eight entities → one extraction → eight accepts (one per type; the fake cycles); edit body/aliases/tags; link two entities; merge two and see the edges move; delete an entity and its edges; filter by type and tag; find `Katharina` typed as `Kathrina`; a suggestion's relation resolves on accept. `assert_accessible` on every page. Run red.
- [ ] **Step 2: Make it green** — no product code changes expected here; a red is a Task 1–3 defect to fix and record.
- [ ] **Step 3: Fahrplan overwrite** — the corrections above, as as-built notes (docs overwritten in place, no supersede sections).
- [ ] **Step 4: `just verify`** — full gate green; read the output.
- [ ] **Step 5: Commit**

```
feat(knowledge): the entity-depth end-to-end proof

One E2E drives the whole C+ surface: eight types born through review,
edited bodies, aliases and tags, linked and merged entities whose edges
move, deletes that take their edges, filters, a misspelt-name search
that still finds, and an accepted relation. The Fahrplan takes the
as-built corrections this work decided.

User-visible: none beyond what the flow proves — the capability's
gate, run for real.
```

---

## Self-review notes

Spec coverage: design D1 (types) → T1; D2 (plain-source body) → T1/T3; D3/D4 (merge, hard delete) → T1; D5 (embedding) → T1; D6 (search) → T1; D7 (API) → T1; D8 (extraction, resolution, transient skip) → T2/T3; D9 (variant B UI) → T3; D10 (exclusivity) → T1/T2 tests; anti-goal "no `POST /entities`" → nowhere, pinned by T4's accept-driven creation; §4.8 same-commit fixtures/fake → T1 Step 2. Left-to-builder items (ENTITY_TYPES home, JSONB relations on the suggestion, chips mechanics, dedupe-vs-unique semantics, error-code continuity) are decided above where they were open. Proportion: four tasks, each independently gated, the full-flow proof last.
