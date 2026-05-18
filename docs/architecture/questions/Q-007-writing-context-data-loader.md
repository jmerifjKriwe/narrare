# Q-007 — Writing Context Data Loader

> **Status:** 🔴 Blocking
> **Blocks:** Generation quality for full_draft, scene_by_scene, interview_assisted modes
> **Raised:** 2026-05-18

---

## Problem

The generation pipeline (`WritingPipeline.generate()`) receives **no context data** — no chapter content, no KB entities, no recent chapters, no project title, no genre. The entire `WritingContext` is empty strings.

### Root Cause

`router.py` calls `service.stream_generation(request_id, user_id)` without any context kwargs. The service passes these through to `pipeline.generate()` as `**context_kwargs` — which is empty.

```python
# router.py:110-111 — no context data loaded
async def event_stream():
    async for chunk in service.stream_generation(request_id, user_id):
        yield f"data: {json.dumps({'text': chunk.text})}\n\n"
```

```python
# service.py:137-142 — pipeline gets no chapter/KB data
async for chunk in self._pipeline.generate(
    pipeline_request,
    config=self._config,
    api_key=self._api_key,
    base_url=self._base_url,
    **context_kwargs,  # ← EMPTY
):
```

### Impact

| Mode | Impact |
|------|--------|
| full_draft | LLM generates generic text without story context. Sees empty sections and hallucinates missing variables. |
| scene_by_scene | Same — no chapter outline, no scene structure |
| interview_assisted | No KB context to ask informed questions |
| interactive_session | Partially works — ws_handler builds its own PromptContext, but also lacks KB/chapter data |

### What's Missing

A **Writing Context Data Loader** that, given a `chapter_id` and `project_id`:

1. Loads the chapter content + frontmatter from DB
2. Loads recent chapters (previous 2-3 chapters for style matching)
3. Loads KB entities referenced in the chapter frontmatter
4. Loads KB entities via similarity to chapter content
5. Loads project metadata (title, genre, language, tone)
6. Loads user preferences and avoidance patterns
7. Assembles everything via `WritingContextAssembler`
8. Passes the result to `pipeline.generate()`

### Dependencies

- **KB module** (next on roadmap) — needed for entity loading + similarity search
- **Chapters API** — needed for chapter content + recent chapters
- **Project settings** — needed for project-level metadata

### Proposed Solution

Create a `WritingContextLoader` service that orchestrates the data loading:

```python
# In apps/api/narrare/writing/context_loader.py

class WritingContextLoader:
    """Loads all context data for a generation request."""

    async def load(
        self,
        chapter_id: UUID,
        novel_id: UUID,
        user_id: UUID,
    ) -> WritingContext:
        """Load chapter, KB, recent chapters, project metadata."""
        ...
```

Then `stream_generation` in `service.py` calls this loader before invoking the pipeline.

### Resolution Criteria

- [ ] KB module implemented with entity loading
- [ ] Chapters API has content retrieval
- [ ] `WritingContextLoader` service implemented
- [ ] All 4 generation modes receive full context
- [ ] Integration tests verify context injection
