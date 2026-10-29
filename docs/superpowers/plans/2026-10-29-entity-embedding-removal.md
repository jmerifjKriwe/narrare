# Entity Embedding Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the entity vector, its width guard, its three 409 paths and its UI, leaving the document vector path (chat sources) untouched.

**Architecture:** Three narrow slices, each green on its own: the knowledge capability stops writing and guarding entity vectors; the kernel's interchange engine stops embedding imported entities; the schema drops the now-unread column. A docs task records the fake-provider finding and marks WP1's D5 superseded for entities.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy async, PostgreSQL 17 + pgvector, pytest, React/Vite, Playwright.

**Spec:** This plan implements the audit decision of 2026-10-29. The design of record it narrows is `docs/superpowers/specs/2026-10-26-wp1-entity-depth-design.md` D5; the standing rules are `docs/_shared/CONSTRAINTS.md`.

**Out of scope:** the `fake` embedding default (recorded as a follow-up row, never fixed here), the document vector path, `isModelChange` in `web/lib/api/client.ts`, anything in `docs/features/`.

---

## Global Constraints

- The five rules in `docs/_shared/CONSTRAINTS.md` apply unchanged. No new gate, registry, hook, required field or mandatory document.
- No migrations: the models are the schema. A schema change is `just db-reset` against the dev database; the test and E2E harnesses rebuild their own databases.
- English in code, comments, tests and this plan; user-visible text in en, de and fr in the same change, or the build fails.
- Only the embedding/LLM provider may be faked, at its boundary. The E2E drives the real UI, API and database.
- No side effect in the request path beyond the request's own transaction.
- Nothing is committed before the review is green. The `Commit` steps name the message the coordinator uses after that review; the implementer leaves the tree uncommitted.

## Review Focus

- **Existing dev database:** after Task 3 entity queries no longer reference `embedding`, so an existing database may retain the nullable column; no reset is required to keep this change running. `just db-reset` recreates the database with the new schema but deletes all development data. `just db-init` creates missing tables but does not alter existing ones.
- **Update path:** a change to name, aliases, tags or body must still rewrite `search_text` (the trigram search's only writer); a type-only change must still skip the rewrite. Losing it silently breaks entity search.
- **Merge:** the row locks must still serialize two concurrent merges into one survivor. The reworked race test must go red when `.with_for_update()` is removed from `EntityRepository.locked`.
- **Import:** a failing import must still commit nothing, and `entities_new`/`entities_revised`/`entities_already_current` must keep their current counts.
- **Re-embed on a real corpus:** documents at an old width must still re-embed, the response must now be `{"documents", "chunks"}` only, and the button must stop promising entities in all three catalogs.

---

### Task 1: The knowledge capability stops embedding entities

**Files:**
- Modify: `app/capabilities/knowledge/service.py` (`_embedding_text`, `EMBEDDING_CONTENT_LIMIT`, `_embed_entity`, its three calls, the entity half of `reembed`, the `ReembedResult` argument)
- Modify: `app/capabilities/knowledge/repository.py` (`EntityRepository.create` signature; delete `stored_entity_width`)
- Modify: `app/capabilities/knowledge/router.py` (the three `except EmbeddingMismatchError` blocks in accept, update, merge)
- Modify: `app/capabilities/knowledge/schemas.py` (`ReembedResult`)
- Modify: `app/capabilities/knowledge/web/ExtractionPanel.tsx` (import and announce branch)
- Modify: `i18n/en.json`, `i18n/de.json`, `i18n/fr.json` (`knowledge.modelChanged`, `knowledge.reembed`; delete `knowledge.embeddingMismatch`)
- Modify: `app/capabilities/knowledge/tests/test_entity_crud.py`, `test_entities.py`, `test_knowledge.py`
- Modify: `app/capabilities/knowledge/e2e/test_knowledge_e2e.py`
- Generated: `web/lib/api/openapi.json`, `web/lib/api/schema.d.ts` (by `just generate`)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `EntityRepository.create(novel_id, name, type, content, aliases, tags) -> Entity` (no `embedding` parameter); `ReembedResult(documents: int, chunks: int)`; `KnowledgeService(session, user_id, embeddings)` unchanged, because document ingestion still embeds.

- [ ] **Step 1: Write the failing test** in `app/capabilities/knowledge/tests/test_entity_crud.py`

```python
class _ExplodingEmbedding:
    def describe(self) -> str:
        return "exploding"

    def configuration_problems(self) -> list[str]:
        return []

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise AssertionError(f"an entity write must not embed: {texts!r}")


async def test_entity_writes_never_reach_the_embedding_provider() -> None:
    """Accept, update and merge are entity writes, not corpus writes: none of
    them may reach the provider, because no read path consumes the vector."""
    # Seed one novel one chapter two entities and one pending suggestion,
    # through the repositories (the same shape as the merge-race test below).
    async with Session() as session:
        service = KnowledgeService(session, LOCAL_USER_ID, _ExplodingEmbedding())
        await service.accept_suggestion(suggestion_id)
        await service.update_entity(mira_id, EntityUpdate(name="Mira Lang"))
        await service.merge_entities(haus_id, see_id)
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest app/capabilities/knowledge/tests/test_entity_crud.py -k never_reach -v`
Expected: FAIL with `AssertionError: an entity write must not embed: ['Mira …']`.

- [ ] **Step 3: Remove the write path** from `app/capabilities/knowledge/service.py`: delete `_embedding_text`, `EMBEDDING_CONTENT_LIMIT`, `_embed_entity`, its calls in `accept_suggestion`, `update_entity` and `merge_entities`, and the entity loop plus the `entities=` argument in `reembed`. `update_entity` keeps writing `search_text` exactly where it does today.

- [ ] **Step 4: Remove the guard and its surface**

- `repository.py`: `EntityRepository.create` loses the `embedding` parameter and the `embedding=` keyword; delete `stored_entity_width`.
- `router.py`: delete the `except EmbeddingMismatchError` blocks in the accept, update and merge routes (the document upload, search and chat routes keep theirs).
- `schemas.py`: `ReembedResult` loses `entities`; docstring says "every document and every chunk".
- `ExtractionPanel.tsx`: drop the `isModelChange` import and the announce branch; the catch becomes `.catch(() => undefined)`.

- [ ] **Step 5: Rewrite the catalogs** (all three, same keys)

- `knowledge.modelChanged`: en `"The embedding model changed. Re-embed the documents."` · de `"Das Embedding-Modell hat sich geändert. Bette die Dokumente neu ein."` · fr `"Le modèle d'embeddings a changé. Ré-encodez les documents."`
- `knowledge.reembed`: en `"Re-embed documents"` · de `"Dokumente neu einbetten"` · fr `"Ré-encoder les documents"`
- Delete `knowledge.embeddingMismatch` in all three.

- [ ] **Step 6: Update the existing tests**

- Delete `test_an_accept_at_another_embedding_width_is_refused_and_writes_nothing` (`test_entities.py`), `test_an_update_at_another_embedding_width_is_refused_like_an_upload` and `test_a_merge_at_another_embedding_width_is_refused_and_deletes_nothing` (`test_entity_crud.py`).
- Delete the two `assert row.embedding is not None` / `assert row.embedding is not None  # the vector rode…` assertions.
- Change every `repository.create(..., None)` in the test helpers to the new five-argument call.
- Re-seam the merge-race test: replace the `KnowledgeService._embed_entity` monkeypatch with a patch of `EntityRepository.locked` that spawns the second merge after the first service has taken both locks (`self.session is not session_a` guards the second service; the second call on `session_a` is the trigger). The loop that waits up to one second for `race["task"]` stays, and the final fold assertions stay unchanged.
- `test_reembed_rebuilds_the_corpus_at_the_new_width` becomes document-only: drop the seeded entity and the pending suggestion, assert the response `{"documents": 2, "chunks": 2}`, keep the 409-then-reembed-then-search assertions. `test_reembed_on_an_empty_corpus_is_a_no_op` expects `{"documents": 0, "chunks": 0}`.
- `test_knowledge_e2e.py`: the button is now `"Dokumente neu einbetten"`.

- [ ] **Step 7: Regenerate the client and run the gates**

Run: `just generate`
Run: `just test-file app/capabilities/knowledge/tests/test_entity_crud.py`
Expected: PASS, including the exploding-provider test and the merge race.
Run: `just test-file app/capabilities/knowledge/tests/test_knowledge.py`
Run: `just test-file app/capabilities/knowledge/tests/test_entities.py`
Run: `just check`
Expected: ruff, pyright and tsc clean.

- [ ] **Step 8: Commit** (after a green review)

```bash
git add app/capabilities/knowledge i18n web/lib/api
git commit -m "refactor(knowledge): entity writes no longer embed a vector nothing reads"
```

Body: `User-visible: accepting a suggestion, editing an entity and merging no longer wait for the embedding provider and can no longer be refused with 409 by it; the re-embed now rebuilds documents only.`

---

### Task 2: The interchange import stops embedding entities

**Files:**
- Modify: `app/kernel/interchange/engine.py` (`_embedding_text`, `_Entities.stored_entity_width`, `_embed_entity`, `EMBEDDING_CONTENT_LIMIT`, the provider parameter and both calls, the imports and the module docstring sentence about the provider)
- Modify: `app/kernel/tests/test_interchange_engine.py`
- Modify: `app/capabilities/writing/tests/test_interchange_api.py`

**Interfaces:**
- Consumes: `Entity.embedding` still exists in this task; the test pins that nothing writes it.
- Produces: `_merge_entities(session, user_id, novel, archive, report)` (no provider); the import route answers no `embedding-mismatch` 409.

- [ ] **Step 1: Rewrite the failing test** in `app/kernel/tests/test_interchange_engine.py`: rename `test_import_maintains_search_text_and_embedding` to `test_import_maintains_search_text_and_leaves_the_vector_unset`. Keep the search_text and untouched-Mira assertions; replace the three vector assertions with `caspar.embedding is None`, `emile_row.embedding is None`, `list(mira_row.embedding) == sentinel`.

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest app/kernel/tests/test_interchange_engine.py -k leaves_the_vector_unset -v`
Expected: FAIL, `assert [0.08…] is None`.

- [ ] **Step 3: Remove the path** from `app/kernel/interchange/engine.py`: delete the helper functions, the constant, the `get_embedding_provider()` call, the `provider` argument through `_merge_entities`, `EmbeddingMismatchError` and `EmbeddingProvider` imports, and the docstring sentence naming the provider.

- [ ] **Step 4: Delete the now-dead tests**

- `test_import_embedding_mismatch_is_409_and_writes_nothing` in `app/capabilities/writing/tests/test_interchange_api.py`.
- The autouse `fake_embeddings` fixtures in both test modules, once nothing reads the variable.

- [ ] **Step 5: Run the gates**

Run: `just test-file app/kernel/tests/test_interchange_engine.py`
Run: `just test-file app/capabilities/writing/tests/test_interchange_api.py`
Run: `just check`
Expected: PASS and a clean typecheck.

- [ ] **Step 6: Commit** (after a green review)

```bash
git add app/kernel/interchange app/kernel/tests/test_interchange_engine.py app/capabilities/writing/tests/test_interchange_api.py
git commit -m "refactor(interchange): importing an archive no longer embeds its entities"
```

Body: `User-visible: an archive import no longer fails with 409 when the embedding model changed, and no longer waits for an embedding call per entity.`

---

### Task 3: Drop the column

**Files:**
- Modify: `app/kernel/contracts/models.py` (`Entity.embedding`, the docstring sentence about the nullable vector)
- Modify: `app/kernel/tests/test_interchange_engine.py` (the temporary `is None`/sentinel assertions)

**Interfaces:**
- Consumes: Tasks 1 and 2 removed every writer.
- Produces: `Entity` without `embedding`; the pyright pass is this task's test, because it lists every stale reference.

- [ ] **Step 1: Remove the column** and the docstring sentence; keep `Vector` imported, `Chunk` still uses it.

- [ ] **Step 2: Recreate the development schema**

Run: `just db-reset`
Expected: `schema ready: narrare_v2_dev`.

- [ ] **Step 3: Delete the assertions the column left behind** in `test_interchange_engine.py` (all three vector assertions; the sentinel assignment goes with them). Sweep for leftovers: `rg -n "Entity.*embedding|entity\.embedding|stored_entity_width" app` must return nothing.

- [ ] **Step 4: Run the full gate**

Run: `just verify`
Expected: `check`, every pytest module, the frontend tests, the production build and every E2E green.

- [ ] **Step 5: Commit** (after a green review)

```bash
git add app/kernel/contracts/models.py app/kernel/tests/test_interchange_engine.py
git commit -m "refactor(knowledge): the entities table drops its unread embedding column"
```

Body: `User-visible: none — the column had no reader. Development databases need `just db-reset`; there are no migrations by design (spec §9).`

---

### Task 4: Record the fake-provider finding

**Files:**
- Modify: `docs/superpowers/follow-ups.md` (append one row)
- Modify: `docs/superpowers/specs/2026-10-26-wp1-entity-depth-design.md` (one dated line under D5)

**Interfaces:**
- Consumes: nothing.
- Produces: follow-up **F-101**.

- [ ] **Step 1: Append the row**

```markdown
| F-101 | 2026-10-29 | Embedding boundary defaults to `fake` | A fresh install logs `providers llm=fake embedding=fake` and nothing in the UI says so: document search and chat citations are ranked by 384-dim word hashing and shown as similarity. The LLM has profiles in `/settings`; embeddings have only `NARRE_EMBEDDING_PROVIDER`, so a real LLM still retrieves through the fake. Choosing a real embedding model afterwards answers 409 on every upload and search until the re-embed, which re-encodes the whole corpus in one request | `app/kernel/embeddings/__init__.py` (the `fake` default), `app/kernel/configuration.py`, `app/capabilities/knowledge/web/KnowledgePage.tsx` | major | v2 session audit | open |
```

- [ ] **Step 2: Mark D5 superseded for entities** in the WP1 design, directly under the decision:

```markdown
> **Superseded 2026-10-29 (entities only):** the entity vector, its width guard and
> its re-embed branch were removed — no read path consumed them. The document
> guard stands. See `docs/superpowers/plans/2026-10-29-entity-embedding-removal.md`.
```

- [ ] **Step 3: Commit** (after a green review)

```bash
git add docs/superpowers/follow-ups.md docs/superpowers/specs/2026-10-26-wp1-entity-depth-design.md
git commit -m "docs(follow-ups): record the fake embedding default (F-101)"
```

---

## Self-review

- **Coverage:** every deleted write path, guard, error surface, UI path, catalog key and test is named in a task. The document path is untouched in all four tasks.
- **Order:** each task is green on its own; Tasks 1 and 2 leave the nullable column in place, Task 3 removes it and deletes its last two assertions.
- **Types:** `EntityRepository.create` loses its last parameter in Task 1; every caller is listed. `ReembedResult` loses `entities` in Task 1 and the generated client follows.
- **Naming:** `test_entity_writes_never_reach_the_embedding_provider`, `test_import_maintains_search_text_and_leaves_the_vector_unset`, F-101.
