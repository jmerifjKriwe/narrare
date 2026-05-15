## Context

Narrare has a production-ready LLM gateway (`core/llm/gateway.py`), a unified prompt system (`core/prompts/`), configurable model routing (SET-002/SET-003), and full chapter/novel CRUD. The editor runs TipTap v3 with autosave and a context panel. However, there is no AI-powered writing capability — the editor is a plain text editor with no generation features.

The `generation-prompt-memory-foundation` change (prerequisite) adds: mem0-based memory layer, feedback collection API, prompt management service, generation intents, culture/genre injection, and extended `PromptContext` with `user_preferences` and `avoidance_patterns` fields. This change consumes all of that to build the first writing feature.

Key constraints from the codebase:
- RULE-01: All LLM calls go through `gateway.py` — no direct provider imports
- RULE-02: Prompts built only in `core/prompts/` — no f-strings in services
- RULE-03: Protocol (contract) before implementation
- RULE-04: Modularize, don't compress — hard file size limits enforced
- RULE-06: One responsibility per file — router delegates to service immediately
- ADR-011: Content versioning exists for chapters — drafts should integrate with it

## Goals / Non-Goals

**Goals:**
- Establish the reusable writing generation pipeline that WRITE-003 through WRITE-010 will extend
- Implement WRITE-002 (New Chapter Generation) with four modes: full draft, scene-by-scene, interview-assisted, and interactive session (WRITE-005)
- Implement writing-specialized context assembly (5-tier ranking with token budgeting)
- Create bundled writing prompts in EN/DE/FR for all generation modes
- Integrate draft tracking with existing content versioning (ADR-011)
- Deliver complete frontend generation UX in the TipTap editor
- Consume foundation's memory layer for preference-aware generation and feedback collection

**Non-Goals:**
- Building memory layer, feedback API, or prompt management (provided by `generation-prompt-memory-foundation`)
- WRITE-003 (Extend Chapter) — same pipeline, different prompts; separate change
- WRITE-004 (Rewrite Selection) — same pipeline, different scope; separate change
- Style analysis / voice profiling (LEARN-002) — post-MVP, requires 3+ chapters
- Full mem0 integration — consumed via foundation, not built here
- Offline generation — requires LLM availability
- Multi-draft comparison (WRITE-008) — future enhancement

## Decisions

### D1: SSE for one-shot generation, WebSocket for interactive sessions

**Decision:** Use Server-Sent Events for `full_draft`, `scene_by_scene`, and `interview_assisted` modes. Use WebSocket for `interactive_session` mode.

**Rationale:** SSE is unidirectional (server → client), simpler to implement, works through proxies and load balancers, and auto-reconnects. One-shot generation only needs server-to-client streaming. Interactive sessions (WRITE-005) need bidirectional communication (user sends direction, AI responds) which requires WebSocket.

**Alternatives considered:**
- WebSocket for everything: Overkill for one-shot generation, more complex connection management
- SSE for everything: Cannot handle bidirectional interactive sessions without workarounds
- Polling: Unacceptable latency for real-time text streaming

### D2: Hybrid draft persistence — generation_requests + chapter_versions

**Decision:** Two-table approach:
- `generation_requests` — operational metadata only (status, mode, model_id, tokens_used, started_at, completed_at, error)
- `chapter_versions` (existing ADR-011) — actual content, with new `version_type: "ai_draft"` and nullable `generation_request_id` FK

**Rationale:** Separates operational concerns (tracking generation lifecycle, analytics, cost) from content concerns (versioning, diffing, rollback). The existing versioning system already handles diff, comparison, and rollback — we just add a new version type. The generation_requests table provides analytics the versioning system wasn't designed for (token costs, model performance, generation timing).

**Alternatives considered:**
- Single generation_requests table with content: Duplicates versioning logic, no diff/rollback support
- Only chapter_versions: Loses operational metadata, can't track in-progress generations
- In-memory only: Lost on server restart, no analytics

### D3: Pipeline as protocol-based, mode-driven orchestration

**Decision:** Single `WritingPipeline` protocol with mode-dependent behavior. Each mode (`full_draft`, `scene_by_scene`, `interview_assisted`, `interactive_session`) shares the same stages but varies in control flow:

```
All modes share:
  ContextAssembly → PromptBuilding → LLMCall → PostProcessing

Mode differences:
  full_draft:        Single pass, stream until word target or natural end
  scene_by_scene:    Loop per scene, pause between scenes for user review
  interview_assisted: Pre-generation interview (3-5 questions), then full_draft
  interactive_session: Continuous loop with conversation history
```

**Rationale:** A single pipeline with mode switches is simpler to maintain than four separate pipelines. The shared stages (context, prompt, LLM, post-process) are identical — only the control flow differs. Future writing features (WRITE-003 extend, WRITE-004 rewrite) reuse the same pipeline with different context scope.

**Alternatives considered:**
- Four separate pipelines: Massive code duplication, harder to maintain consistency
- Plugin architecture: Over-engineered for the current scope, premature abstraction
- Strategy pattern per mode: Viable but adds unnecessary indirection for 4 modes

### D4: 5-tier context ranking with token budget

**Decision:** Writing context assembly uses 5 tiers with fixed budget allocation:

| Tier | Budget | Source | Priority |
|------|--------|--------|----------|
| Immediate Context | 30% | Current chapter content + frontmatter | Always included |
| Recent History | 20% | Last 2-3 chapters (summarized if long) | Always included |
| KB Entries (referenced) | 25% | Characters/locations/factions from frontmatter | Always included |
| KB Entries (suggested) | 15% | Similarity-ranked from remaining KB | Best-effort |
| Pinned Items | 10% | User-pinned KB entries | Always included |

Overflow from a lower tier fills higher tiers. Pinned items bypass budgeting.

**Rationale:** The 5-tier system from INFRA-003 spec provides a principled approach. Fixed percentages are simpler than dynamic allocation and predictable for prompt engineering. Summarization of recent chapters (rather than full text) preserves budget for KB context.

### D5: Interview-assisted mode as structured prompt sequence

**Decision:** Interview-assisted mode uses a structured sequence of 3-5 LLM calls (not a free conversation) to gather scene information before generation. Questions are templated (scene goal, characters present, tone, conflict, desired length), but the AI can adapt questions based on answers.

**Rationale:** Free-form interview before generation is too open-ended and expensive. A structured sequence with 3-5 fixed questions (with AI adaptation) provides enough information for good generation while keeping token costs predictable. The user can skip any question. This mirrors the pattern from `_scratch/features/characters.md` ("answer the interview questions, or use AI suggestions").

### D6: Scene-by-scene with client-side review loop

**Decision:** Scene-by-scene mode generates one scene at a time via SSE. After each scene, the server pauses and waits for a client signal (accept/edit/regenerate/stop). The accepted scenes accumulate as separate chapter versions. The final chapter is assembled from all accepted scenes.

**Rationale:** Gives users granular control over generation without the complexity of a full WebSocket session. Each scene is a discrete SSE generation that the user reviews independently. The server maintains state about which scenes have been generated and accepted.

**Alternatives considered:**
- Generate all scenes at once with markers: User can't review between scenes
- WebSocket for scene review: Unnecessary bidirectional overhead — the server only needs to know "continue with next scene" or "stop"

## Risks / Trade-offs

**[Token cost for long chapters]** → Mitigation: Token budget enforcement, word count targets, stop-at-target logic. Track cost per generation in `generation_requests` for user visibility.

**[Quality degradation with sparse KB]** → Mitigation: Detect sparse KB (fewer than 3 entities) and inform the user that generation quality may be lower. Suggest adding more KB entries. Fall back to chapter-history-only context.

**[SSE connection drops during generation]** → Mitigation: Generated text is persisted in real-time to `chapter_versions` as it streams. Reconnection resumes from last persisted position. Client shows "connection lost" with retry option.

**[WebSocket session state on server restart]** → Mitigation: Session state (conversation history, prose buffer) persisted to Redis with TTL. Server restart recovers active sessions from Redis. Sessions timeout after 30 minutes of inactivity.

**[Scope creep from WRITE-005 inclusion]** → Mitigation: Interactive session shares the same pipeline stages — only the control flow differs. The `SessionManager` is a thin layer over the pipeline, not a separate system.

**[Dependency on `generation-prompt-memory-foundation`]** → Mitigation: Clean protocol boundaries — this change depends on foundation's protocols, not implementations. If foundation is delayed, writing pipeline can be tested with mock protocols. But full integration requires foundation to be complete.

**[File size limits (RULE-04)]** → Mitigation: Pipeline split across `pipeline.py` (orchestration), `context_assembler.py` (context), `draft_processor.py` (post-processing), `session_manager.py` (interactive sessions), `contracts.py` (protocols). Each file under 300 lines.

## Open Questions

1. **Scene boundary detection**: How does the AI know where a scene ends? Options: explicit `***` scene break markers, paragraph gap heuristics, or user-defined scene breaks in the outline. Decision needed for scene-by-scene mode.

2. **Interview prompt vs. generation prompt**: Should the interview phase use a different prompt template than the generation phase, or a single template with a mode variable? Affects prompt file organization.

3. **Streaming chunk granularity**: SSE chunks should be sentence-level (not token-level) for readable streaming display. Need to confirm this works with the gateway's streaming API.

4. **Concurrent generation limits**: Should we allow only one active generation per chapter? Per user? No limit? Affects `generation_requests` design and resource management.
