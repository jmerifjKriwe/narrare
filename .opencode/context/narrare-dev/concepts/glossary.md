<!-- Context: narrare-dev/concepts/glossary | Priority: high | Source: docs/_shared/GLOSSARY.md | Updated: 2026-05-30 -->

# Narrare Glossary

**Core Idea**: Shared vocabulary for all agents and developers. Ambiguous terms cause architectural drift.

**Reference**: `docs/_shared/GLOSSARY.md` (478 lines, full definitions with examples)

---

## Core Architecture Terms

| Term | Definition |
|------|-----------|
| **ADR** | Architecture Decision Record. Lives in `docs/architecture/decisions/` |
| **Agent (AI)** | Configured LLM invocation with system prompt, tools, I/O contracts. In `*_agent.py` files |
| **Contract** | Python `Protocol` class defining a service's public interface. In `contracts.py` |
| **Domain Module** | Self-contained directory owning one business domain (e.g., `writing/`, `kb/`) |
| **Gateway (LLM)** | Single entry point for all LLM calls. `core/llm/gateway.py`. Enforces routing, retry, telemetry |
| **Service Layer** | Business logic in `apps/api/narrare/*/service.py`. Called by routers, MCP, A2A, CLI |
| **Repository** | DB-query-only class. No business logic. In `*/repository.py` |
| **Transport Layer** | HTTP routers + future MCP/A2A handlers. Zero business logic |

---

## Prompt System Terms

| Term | Definition |
|------|-----------|
| **Cascade** | Prompt resolution order: DB template > project override > user-global > bundled default |
| **Intent (LLMIntent)** | Typed enum: `WRITE`, `ANALYSE`, `EXTRACT`, `SUMMARIZE`. Gateway uses for model selection |
| **Bundled Prompt** | Shipped in `core/prompts/_bundled/`. Lowest cascade priority |
| **PromptContext** | Typed dataclass with all variables to render a prompt |
| **Meta Prompt** | Narrare identity injected by `NarrareMeta` Capability (ADR-026); feature prompts stay in PromptComposer cascade |
| **Modifier** | Optional prompt fragment appended to base prompt (e.g., `tone:formal`) |
| **Resolver** | `core/prompts/registry.py` — single cascade implementation |

---

## Domain Terms

| Term | Definition |
|------|-----------|
| **Novel** | Top-level project container. Has metadata, volumes, chapters, KB, Knowledge Graph |
| **Chapter** | Named section of a Novel. Primary unit of writing |
| **Volume** | Optional chapter grouping within a Novel |
| **Entity (KB)** | Named KB element: character, location, object, concept. Has type + properties + relationships |
| **KB** | Project-level structured knowledge store (user-managed) |
| **Knowledge Graph** | Auto-maintained graph of facts extracted from chapters/KB |
| **Fact** | Structured info extracted from text. Stored in KG |
| **Draft** | Single AI-generated version of a chapter/section |
| **Genre** | Freetext field. Does NOT select genre-specific prompts |

---

## Language & Tone

| Term | Definition |
|------|-----------|
| **Writing Language** | Language AI generates prose in. Freetext (e.g., "Deutsch"). On Novel model |
| **UI Language** | Display language of interface. `en`, `de`, `fr`. In user settings |
| **Prompt Language** | Language of prompt template files. Per-category, not per-user |
| **Explanation Language** | Language for name meanings. Defaults to novel's writing_language |
| **Tone** | Narrative tone. 9 bundled + up to 20 custom per user |
| **Name Style** | Cultural/aesthetic style for generated names (e.g., "Norse mythology") |

---

## AI & Agent Terms

| Term | Definition |
|------|-----------|
| **NarrareAgent** | Typed pydantic-ai Agent wrapper. Base class in `core/agents/base.py` |
| **DraftAgent** | Generates chapter drafts with Output Function for post-processing |
| **KBAgent** | Provides KB tools for other agents. Never executed directly (`output_type=None`) |
| **WritingGraph** | State machine: PlanOutline → WriteDraft → ReviewDraft → Decision → Finalize/Revise |
| **ToolSearch** | pydantic-ai capability for deferred tool loading |
| **Toolset** | pydantic-ai capability injecting FunctionToolset from another Agent |
| **Output Function** | Callable in Agent's `output_type` for post-processing (artifact removal, normalization) |

---

## Wiki & Memory

| Term | Definition |
|------|-----------|
| **Wiki (LLM Wiki)** | Precomputed LLM-generated summaries of KB entities/chapters. ~40 tokens vs ~200 raw |
| **WikiSummary** | LLM-generated narrative summary (2-3 sentences). Status: fresh/stale/pending |
| **WikiChapterSummary** | Extended chapter summary with key-events, entities, themes |
| **Precomputed Context Layer** | Architecture pattern: pre-processed data stored as optimized summaries |
| **Memory** | Persistent user/project context via mem0. Always optional (graceful degradation) |
| **Embedding Cascade** | 4-tier fallback: OpenAI → provider-native → local sentence-transformers → disabled |

---

## Frontend Terms

| Term | Definition |
|------|-----------|
| **SSE** | Server-Sent Events. Streaming transport for real-time AI output |
| **SSE Streaming Client** | `packages/web/lib/api/streaming.ts` (`connectSSE`). Native fetch, not axios |
| **Error Boundary** | React component catching runtime errors. Route-level `error.tsx` + global `global-error.tsx` |
| **Loading Skeleton** | `loading.tsx` — shape-matching placeholders, never spinners |
| **shadcn/ui** | Copy-paste Radix UI primitives styled with Tailwind. Not a runtime dependency |
| **cva** | class-variance-authority for variant-based Tailwind class composition |
| **motion** | Animation library (formerly Framer Motion). For enter/exit, layout, gesture animations |

---

**Related**: `constraints/rules.md`, `lookup/tech-stack.md`, `concepts/project-vision.md`
