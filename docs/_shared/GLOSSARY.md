# Narrare — Glossary

> **Shared vocabulary for all agents and developers.**
> If a term is used in code, documentation, or agent communication,
> it should be defined here. Ambiguous terms cause architectural drift.
>
> Location: `docs/_shared/GLOSSARY.md`
> Maintained by: Architecture Agent

---

## A

**ADR (Architecture Decision Record)**
A document that captures an architectural decision, its context, the options
considered, and the rationale for the choice. Lives in
`docs/architecture/decisions/`. Every significant structural decision
gets an ADR. See `_TEMPLATE.md` for format.

**Agent (AI Agent)**
A configured LLM invocation with a system prompt, optional tools, and defined
input/output contracts. In Narrare code, agents are defined in `*_agent.py` files
and always invoked via the LLM Gateway. Never confused with "Agent Definition"
(see below).

**Agent Definition (Dev Agent)**
A role definition for an AI coding assistant (Architecture Agent, Implementation
Agent, etc.). Lives in `docs/`. Not to be confused with AI agents in the
product code.

**A2A (Agent-to-Agent)**
A planned communication protocol allowing external AI agents to call Narrare
services. Adapter lives in `apps/a2a/`. The Service Layer does not change to
accommodate A2A — only the transport adapter changes.

---

## B

**Budget (Token Budget)**
The maximum number of tokens allocated for a specific part of a prompt — typically
for KB context injection. Managed by `core/context/budget.py`. When context exceeds
budget, it is truncated by relevance score, not truncated blindly.

**Bundled Prompt**
A prompt file shipped with the application in `core/prompts/_bundled/`. It is the
lowest-priority source in the cascade. Users can override it without modifying the
source.

---

## C

**Cascade (Prompt Cascade)**
The resolution order for prompt files:
1. DB template (user-saved override, highest priority)
2. Project-level file override (`.narrare/prompts/...`)
3. User-global file override (`~/.config/narrare/prompts/...`)
4. Bundled default (lowest priority, always present)

There is exactly one cascade implementation: `core/prompts/registry.py`.

**Chapter**
A named section of a Novel. Has a body (Markdown), position, optional volume
assignment, and a summary (AI-generated or manual). The primary unit of writing.

**Context Bundle**
The assembled collection of KB entries, chapter summaries, and memory items
that are injected into a prompt. Built by `core/context/assembler.py`. Represented
as `ContextBundle` type.

**Contract**
A Python `Protocol` class that defines the public interface of a service.
Lives in `contracts.py` within each domain module. Written before the
implementation. Enables mocking, testing, and client substitution.

**Co-Author Session**
An interactive writing mode where the AI acts as a collaborative writing partner,
taking turns with the user. Different from a Writing Session (which is AI-driven)
and a KB Session (which is knowledge-editing).

**cva (class-variance-authority)**
A utility for composing variant-based Tailwind class names. Used in UI primitives
(Button, etc.) to define variant maps (`primary`, `secondary`, `ghost`, `danger`)
and size maps (`sm`, `md`, `lg`). Replaces BEM-style modifiers with Tailwind utilities.
Located in `packages/web/components/ui/`.

---

## D

**Decision**
A typed result from the `ReviewDraft` graph node that determines branching in the
WritingGraph. Two variants: `Approved` (routes to `Finalize`) and `NeedsRevision`
(routes to `ReviseDraft` → loop back to `WriteDraft`). Max 3 revision attempts before
force-finalize. Defined in `core/agents/writing_graph_types.py`. Part of ADR-015 Phase 4.

**Domain Module**
A self-contained directory within `apps/api/narrare/` that owns one business
domain (e.g., `writing/`, `kb/`, `analysis/`). Contains its own schemas, models,
repository, service, contracts, and router. Never imports from another domain's
internal modules.

**DraftAgent**
A pydantic-ai Agent (`NarrareAgent[DraftDeps, DraftOutput]`) that generates
chapter drafts using an Output Function for post-processing and a tool for
KB context lookup. Defined in `core/agents/draft_agent.py`. Replaces the
manual DraftProcessor pipeline path when the `use_draft_agent` feature flag
is active (Phase 2 of ADR-015). In Phase 3, accepts an optional `kb_agent`
parameter to inject KBAgent KB tools and ToolSearch capability.

**Draft**
A single AI-generated version of a chapter or section. Multi-Draft mode
generates several drafts simultaneously for comparison.

---

## E

**Entity (KB Entity)**
A named element in the Knowledge Base — a character, location, object, concept,
or custom type. Each entity has a type, properties, and optional relationships
to other entities.

**Embedding**
A numerical vector representation of text, used for semantic similarity search.
Generated via `core/llm/embeddings.py`, stored in PostgreSQL via pgvector.
Used for KB search, chapter similarity, and style profiling.

**Error Boundary**
A React component that catches runtime errors in its child tree. In Narrare:
- Route-level `error.tsx` files catch errors per route segment (Next.js built-in)
- `global-error.tsx` catches catastrophic errors (replaces entire page)
- `<ErrorBoundary>` component wraps specific components like the TipTap editor
All error messages use i18n except `global-error.tsx` which runs before providers mount.

**Explanation Language**
A string field (2–50 chars) on the name generation request specifying the
language in which name meanings and explanations should be written. Defaults
to the novel's `writing_language`. Replaces the former `language` field on
name generation requests. Distinct from *Writing Language* and *Prompt Language*.

---

## F

**Fact**

**FunctionToolset**
A pydantic-ai toolset (`pydantic_ai.toolsets.FunctionToolset`) that bundles
multiple `Tool` instances with `defer_loading=True`. Used by `KBAgent` to
provide KB tools (`search_kb`, `get_entity`, `get_related_entities`) to other
Agents via `Toolset` capability injection. Defined in `core/agents/kb_agent.py`.
A structured piece of information extracted from a chapter or KB entry.
Stored in the Knowledge Graph. Example: "Character X is married to Character Y."
Used for consistency checking.

**First Message**
The opening assistant message in a KB Session or interactive writing session.
Defined in the prompt file under the `## First Message` section.
Not to be confused with the system prompt.

**Frontmatter**
YAML metadata at the top of a Markdown file, delimited by `---`.
Used in prompt files, KB entries, and chapter files.
Parsed by `core/shared/frontmatter.py` — the single implementation.

---

## G

**GraphBuilder**
The current pydantic-graph API (v1.97+) for constructing state-machine graphs.
Used to build the `WritingGraph` with nodes, edges, decisions, and forks.
Preferred over the deprecated `Graph()` constructor. Factory function:
`create_writing_graph()` in `core/agents/writing_graph.py`. Part of ADR-015 Phase 4.

**Gateway (LLM Gateway)**
The single entry point for all LLM calls in the system.
Lives in `core/llm/gateway.py`. Enforces: cost tracking, retry, error
classification, model routing, telemetry. No code outside `core/llm/` may
call an LLM directly.

**Genre**
A writing genre (e.g., fantasy, thriller, romance). Freetext field — users can
enter compound genres like "dark fantasy romance" or "scifi-western". Genre
influences generation parameters and context assembly. Does **not** select
genre-specific prompt files; tone and writing language are the primary prompt
modifiers.

---

## I

**Intent (LLM Intent)**
A typed enum value that describes the purpose of an LLM call.
Examples: `LLMIntent.WRITE`, `LLMIntent.ANALYSE`, `LLMIntent.EXTRACT`,
`LLMIntent.SUMMARIZE`. The Gateway uses intent to select model and parameters.
Defined in `core/llm/intents.py`.

**Interactive Session**
A stateful, multi-turn conversation with an AI assistant scoped to a specific
task (writing a chapter, editing a KB entry). Sessions are persisted in Redis
with filesystem checkpointing. Not to be confused with a stateless one-shot
API call.

---

## K

**KBAgent**
A pydantic-ai Agent (`NarrareAgent[KBDeps, None]`) that provides KB tools
for other agents — never executed directly (`output_type=None`). Exposes
3 deferred-loaded tools via `FunctionToolset`: `search_kb()`, `get_entity()`,
and `get_related_entities()`. Defined in `core/agents/kb_agent.py`.
Part of ADR-015 Phase 3.

**KB (Knowledge Base)**
The project-level structured knowledge store — characters, locations, world facts,
relationships. Distinct from the Knowledge Graph (which is derived from chapter
content). A user explicitly manages KB entries.

**KB Session**
An interactive AI session for creating or editing a KB entity. The AI acts as
an interviewer, asking questions to fill out the entity's properties.

**Knowledge Graph (KG)**
An automatically maintained graph of facts extracted from chapters and KB entries.
Nodes are entities, edges are relationships with typed facts. Used for consistency
checking and context assembly.

---

## L

**Loading Skeleton**
A visual placeholder shown during page navigation. Implemented as `loading.tsx` files
in Next.js App Router — React Suspense boundaries that display skeleton shapes
matching the target page layout. Never spinners — always shape-matching placeholders.

---

## M

**MCP (Model Context Protocol)**
A planned protocol adapter allowing external MCP clients to call Narrare services
as tools. Lives in `apps/mcp/`. Uses the same Service Layer as the WebUI.

**Memory**
User and project-level persistent context managed by mem0. Stores writing
preferences, style patterns, rejection feedback. Accessed via `core/memory/`.
Always optional — the system degrades gracefully if unavailable.

**Meta Prompt**
A global persona/system prompt prepended to all feature-specific prompts.
Defines the AI's overall character and writing philosophy.
Loaded by `core/prompts/meta.py`. One implementation, used by all features.

**Mode (Writing Mode)**
The type of writing operation: `new_chapter`, `extend`, `rewrite`, `interactive`,
`co_author`. Affects prompt selection, generation parameters, and context assembly.

**Modifier (Prompt Modifier)**
An optional prompt fragment appended to a base prompt to adjust behavior.
Examples: `tone:formal`, `length:short`, `style:dialogue_heavy`.
Applied by `core/prompts/composer.py`.

**motion**
Animation library (formerly Framer Motion) for React component transitions.
Provides `AnimatePresence` for mount/unmount animations and `motion.div` for
declarative motion. Used for AI streaming text appearance, panel transitions,
and focus mode animations. Located in `packages/web/` dependencies.

---

## N

**Novel**
The top-level project container. Has metadata (genre, writing_language, tone, style),
volumes, chapters, a KB, and a Knowledge Graph.

**Name Style**
A freetext field (1–100 chars) describing the cultural or aesthetic style for
generated character/place names (e.g., "Norse mythology", "Victorian English",
"high fantasy"). Replaces the former `culture` field. If a bundled name-style
definition file exists, it is loaded; otherwise the raw string is injected
directly into the prompt.

---

## O

**Output Function**
A callable registered as part of `output_type` in a pydantic-ai Agent (e.g.,
`output_type=[callable, Model]`). The callable is called by the model as a
tool — it receives structured parameters and returns the typed output. In
Narrare, the `DraftAgent` uses an Output Function to post-process generated
text (artifact removal, markdown normalization, word-target enforcement)
instead of the legacy `DraftProcessor` pipeline path. Defined inline in
`core/agents/draft_agent.py` as `_process_draft_output`.

---

## P

**Prompt Context (`PromptContext`)**
A typed dataclass carrying all variables needed to render a prompt:
project metadata, language, mode, KB context bundle, style profile, etc.
Passed to `core/prompts/composer.py`. No service assembles prompts directly.

**Prompt Language**
The language of the prompt template files themselves. Selected via the prompt
cascade — the resolver picks the best-matching language file (e.g., `de/names/system.md`).
Configured per-prompt-category, not per-user. Distinct from *Writing Language*
(what language the AI writes in) and *UI Language* (what language the interface shows).

**Protocol (Python Protocol)**
A structural subtyping interface definition (`typing.Protocol`).
Used as the contract for every service class. Enables static type checking
and clean mocking in tests.

---

## R

**Repository**
A class responsible solely for database queries. No business logic.
Receives an `AsyncSession`, returns domain objects.
Lives in `*/repository.py` within each domain module.

**Resolver (Prompt Resolver)**
`core/prompts/registry.py` — the single class that resolves a prompt file
from the cascade for a given category, language, and mode.
Previously: three competing implementations. Now: one.

---

## S

**Service Layer**
The set of service classes in `apps/api/narrare/*/service.py`.
Contains business logic. Called by routers (HTTP), MCP tools, A2A agents, and CLI.
Never contains HTTP-specific code.

**Session (Writing Session)**
A stateful interactive writing conversation. Persisted in Redis + filesystem.
Distinct from an analytics session (tracking writing time).

**SSE (Server-Sent Events)**
The streaming transport used for real-time AI output delivery over HTTP.
Used for all streaming LLM responses in the WebUI.
Client implementation: `packages/web/lib/api/streaming.ts` (`connectSSE`).

**SSE Streaming Client**
The utility in `packages/web/lib/api/streaming.ts` that handles Server-Sent Events.
Uses native `fetch` + `ReadableStream` (axios cannot do SSE). Parses SSE `data:` lines,
handles `[DONE]` sentinel, and supports `AbortSignal` for cancellation.
Every streaming AI response in the frontend uses this client.

**shadcn/ui**
A collection of copy-paste React component primitives built on Radix UI.
Not a runtime dependency — components are owned and customized locally.
Styled with Tailwind CSS. Located in `packages/web/components/shadcn/`.
Used as the foundation for UI primitives (Button, Dialog, Toast, etc.).

**Style Profile**
An AI-generated and embedding-based representation of an author's writing style.
Used for voice consistency checking and drift detection.

---

## T

**Tone**
The narrative tone for generated text. Nine bundled tones are available:
dramatic, humorous, suspenseful, contemplative, romantic, dark, adventurous,
quiet, balanced. The "balanced" tone produces no additional tone instructions
(neutral/default). Users can also define custom tones (up to 20 per user)
via the Tone Library in settings. Custom tones are stored as `{id, name, instructions}`
in user preferences. Both bundled and custom tone identifiers are accepted
by the `tone` field on novels and generation requests.

**ToolSearch**
A pydantic-ai capability (`pydantic_ai.capabilities.ToolSearch`) that enables
an Agent to discover and load tools on demand (deferred loading). In Narrare,
integrated into `DraftAgent` when a `KBAgent` is present (`strategy="keywords"`).
The model sees only tool names and short descriptions until it requests the
full schema via ToolSearch. Part of ADR-015 Phase 3.

**Toolset**
A pydantic-ai capability (`pydantic_ai.capabilities.Toolset`) that injects a
`FunctionToolset` (from another Agent like `KBAgent`) into an Agent's available
tools. Combined with `ToolSearch`, tools are only loaded when the model decides
they are needed.

**Transport Layer**
The HTTP routers (`apps/api/narrare/*/router*.py`), future MCP tools, and
future A2A agent handlers. Contains zero business logic. Maps protocol-specific
inputs to Service Layer calls.

---

## U

**UI Language**
The display language of the user interface. Supported: `en`, `de`, `fr`.
Stored in user settings. Affects all labels, buttons, placeholders, and
system messages. Distinct from *Writing Language* (the language the AI writes in)
and *Prompt Language* (the language of prompt template files).

---

## V

**Volume**
An optional grouping of chapters within a Novel (e.g., Part 1, Book 1).
Chapters belong to at most one volume.

**Voice Check**
An analysis that compares a newly written chapter against the author's established
style profile, flagging deviations in tone, sentence structure, vocabulary, etc.

---

## W

**Writing Language**
The language in which the AI generates creative text (prose, dialogue, narration).
A freetext field (no enum) — users can enter any language name like "English",
"Deutsch", "日本語". Stored as `writing_language` on the Novel model. Injected
into prompts via `WritingContext` and `PromptContext`. Defaults to the UI locale
on novel creation. Distinct from *UI Language* (interface language) and
*Prompt Language* (template file language).

**Writing Session**
See *Session (Writing Session)*.

**WritingGraph**
A pydantic-graph state machine implementing the creative writing workflow:
PlanOutline → WriteDraft → ReviewDraft → Decision (Approved → Finalize | NeedsRevision → ReviseDraft → WriteDraft loop).
State is carried by `WritingState`, dependencies by `WritingDeps`. Built via `GraphBuilder` API
in `core/agents/writing_graph.py`. Integrated into `WritingPipeline` via `use_writing_graph` feature flag.
Mermaid diagram at `docs/architecture/workflows/writing-graph.mermaid`. Part of ADR-015 Phase 4.

**WritingState**
A dataclass carrying the full state of a WritingGraph run: `chapter_id`, `novel_id`,
`outline`, `draft`, `revision`, `final`, `status` (`WritingStatus` enum), and `attempts` counter.
Passed between graph nodes during execution. Defined in `core/agents/writing_graph_types.py`.
Part of ADR-015 Phase 4.

**WritingStatus**
An enum tracking the current phase of a WritingGraph run: `PLANNED`, `OUTLINED`, `DRAFTED`,
`IN_REVIEW`, `NEEDS_REVISION`, `APPROVED`, `REVISED`, `COMPLETED`. Used by `WritingState.status`.
Defined in `core/agents/writing_graph_types.py`. Part of ADR-015 Phase 4.

---

> Last updated: 2026-05-21 — Metadata-consistency change: Tone, Writing Language, UI Language, Prompt Language, Name Style, Explanation Language entries; Genre correction
> Maintained by: Architecture Agent
> Add terms as they emerge — do not let ambiguous vocabulary persist
