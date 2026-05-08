# Narrare — Glossary

> **Shared vocabulary for all agents and developers.**
> If a term is used in code, documentation, or agent communication,
> it should be defined here. Ambiguous terms cause architectural drift.
>
> Location: `docs/agents/_shared/GLOSSARY.md`
> Maintained by: Architecture Agent

---

## A

**ADR (Architecture Decision Record)**
A document that captures an architectural decision, its context, the options
considered, and the rationale for the choice. Lives in
`docs/agents/architecture/decisions/`. Every significant structural decision
gets an ADR. See `_TEMPLATE.md` for format.

**Agent (AI Agent)**
A configured LLM invocation with a system prompt, optional tools, and defined
input/output contracts. In Narrare code, agents are defined in `*_agent.py` files
and always invoked via the LLM Gateway. Never confused with "Agent Definition"
(see below).

**Agent Definition (Dev Agent)**
A role definition for an AI coding assistant (Architecture Agent, Implementation
Agent, etc.). Lives in `docs/agents/`. Not to be confused with AI agents in the
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

---

## D

**Domain Module**
A self-contained directory within `apps/api/narrare/` that owns one business
domain (e.g., `writing/`, `kb/`, `analysis/`). Contains its own schemas, models,
repository, service, contracts, and router. Never imports from another domain's
internal modules.

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

---

## F

**Fact**
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

**Gateway (LLM Gateway)**
The single entry point for all LLM calls in the system.
Lives in `core/llm/gateway.py`. Enforces: cost tracking, retry, error
classification, model routing, telemetry. No code outside `core/llm/` may
call an LLM directly.

**Genre**
A writing genre (e.g., fantasy, thriller, romance). Affects prompt selection
(genre-specific prompt files take precedence over generic ones) and generation
parameters.

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

---

## N

**Novel**
The top-level project container. Has metadata (genre, language, tone, style),
volumes, chapters, a KB, and a Knowledge Graph.

---

## P

**Prompt Context (`PromptContext`)**
A typed dataclass carrying all variables needed to render a prompt:
project metadata, language, mode, KB context bundle, style profile, etc.
Passed to `core/prompts/composer.py`. No service assembles prompts directly.

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

**Style Profile**
An AI-generated and embedding-based representation of an author's writing style.
Used for voice consistency checking and drift detection.

---

## T

**Transport Layer**
The HTTP routers (`apps/api/narrare/*/router*.py`), future MCP tools, and
future A2A agent handlers. Contains zero business logic. Maps protocol-specific
inputs to Service Layer calls.

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

**Writing Session**
See *Session (Writing Session)*.

---

> Last updated: project initialization
> Maintained by: Architecture Agent
> Add terms as they emerge — do not let ambiguous vocabulary persist
