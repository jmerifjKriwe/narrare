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

**AdoptionPolicy**
A value object describing which adoption requirements apply to a feature mode:
`preference_requirement`, `kb_suggested_requirement`, `requires_output_budget`,
and `requires_final_validation`. See ADR-038.

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
services. The future adapter will live in `apps/a2a/` and call the existing
Service Layer. The Service Layer does not change to accommodate A2A — only the
transport adapter changes. Q-002 remains open until the adapter spec is written.

**AUFG (Architecture UX Finding Gate)**
Ein governance-Mechanismus aus CR-07 für AI-UX-Compliance-Findings. Findings
werden im AUFG-Registry (`docs/architecture/governance/aufg-registry.md`) als
Lebenszyklus-Einträge geführt. Jeder AUFG-Eintrag trägt Design-, Implementation-
und Enforcement-Evidence gemäß `docs/development/finding-lifecycle.md`. Der
Lifecycle wird via `scripts/checks/check_ai_interaction_compliance.py` (Check 11)
und `scripts/check_governance_health.py` CI-blockend überwacht. Siehe ADR-043,
ADR-047.

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

**ContextEnricher**
A Protocol for runtime context enrichment before `PromptComposer`. Implementations
add data to `PromptInvocationContext.dynamic_inputs`.

**Contract**
A Python `Protocol` class that defines the public interface of a service.
Lives in `contracts.py` within each domain module. Written before the
implementation. Enables mocking, testing, and client substitution.

**Co-Author Session**
An interactive writing mode where the AI acts as a collaborative writing partner,
taking turns with the user. Different from a Writing Session (which is AI-driven)
and a KB Session (which is knowledge-editing).

**ChatAgent**
A pydantic-ai Agent (`NarrareAgent[ChatDeps, str]`) that provides free-form chat
for writing craft discussion. Uses `HistoryPolicy.CONVERSATIONAL` for cross-turn
continuity (ADR-034). Invoked via `run_stream()` which yields `StreamEvent` objects.
Defined in `core/chat/chat_agent.py`. Part of CHAT-001.

**character_voice**
Der `context_mode` für `LLMIntent.VOICE`. Nutzt ein governed EN Prompt-Template
in `core/prompts/_bundled/analysis/en/character_voice/system.md`. Wird durch
`PromptComposer` Mode 1 (`composer.build(intent=LLMIntent.VOICE, context=...,
context_mode="character_voice")`) aufgelöst. Siehe ANAL-008, ADR-055.

**ChatDeps**
A dependency container for `ChatAgent`, providing the prompt composition infrastructure
needed for each chat turn. Contains `prompt_composer: PromptComposer`, `context: PromptContext`,
and `user_prompt: str`. Injected by the service layer. Defined in `core/chat/chat_deps.py`.

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

**DialogueParser**
Eine deterministische Analysekomponente in `core/analysis/dialogue_parser.py`,
die Dialogue (wörtliche Rede) aus Text extrahiert und Attributions-Informationen
(wer spricht) mit Confidence-Signal ergänzt. Nutzt tag-basierte (said, whispered),
action-beat und em-dash Attributionsmuster. Quotes ohne deterministische Attribution
lösen auf `speaker=None` bei niedriger Confidence auf — die LLM `CharacterVoiceAgent`
löst diese inline auf (ADR-055 Decision 3 — self-contained hybrid, keine Coreference-
Kopplung zur Laufzeit). Siehe ADR-021, ANAL-008.

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
A structured piece of information extracted from a chapter or KB entry.
Stored in the Knowledge Graph. Example: "Character X is married to Character Y."
Used for consistency checking.

**FeatureInvocationEvidence**
Privacy-safe proof that an AI invocation satisfies its adoption requirements.
Contains only structured metadata, never prompt text.

**FunctionToolset**
A pydantic-ai toolset (`pydantic_ai.toolsets.FunctionToolset`) that bundles
multiple `Tool` instances with `defer_loading=True`. Used by `KBAgent` to
provide KB tools (`search_kb`, `get_entity`, `get_related_entities`) to other
Agents via `Toolset` capability injection. Defined in `core/agents/kb_agent.py`.

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

**Governed Adoption Debt / Governed Debt**
Architektur- oder Adoption-Schulden, die explizit registriert, owned und durch
CI-Checks überwacht werden. Anders als "tolerierte" Schulden haben governed debts
eine Ratchet-Baseline und dürfen nicht wachsen — jeder neue oder unapproved Gap
fails the gate. Governed debt ≠ `PASS`. Beispiele: `INLINE-FEATURE-PROMPT`-Baseline,
character_voice runtime adoption (static-verified, runtime evidence pending CI).

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

**Infrastructure Complete**
The contracts, probes, checkers, registry entries, and evidence sinks for a feature or
adoption layer exist. This does not by itself mean static checks pass or that runtime
production paths are adopted. See ADR-045.

**INLINE-FEATURE-PROMPT**
(Veraltet) Ein Pattern, bei dem Prompt-Texte als Python-f-Strings in Service-Dateien
standen — ein RULE-02-Verstoß. Wurde durch ADR-049 (FIND-011 Gate A5) als ratchet-
baseline erfasst und durch ADR-054 auf 0 reduziert. Die drei betroffenen Services
(CharacterArcService, TimelineExtractionService, KBMergeService) wurden auf
PromptComposer Mode 1 migriert. Der CI-Checker `_check_inline_feature_prompt.py`
überwacht das Zero-Baseline.

**Invocation Evidence Correlation**
Privacy-safe linkage proving that preparation, prompt composition, budget resolution,
model/agent execution, and evidence recording belong to the same AI invocation. Uses
an `invocation_id`, fingerprints, and model-call markers instead of raw prompt text or
user prose.

**InvocationPipeline**
The orchestrator for the AI Invocation Adoption Contract (ADR-038). Coordinates:
Variable Validation → Enrichment → Budget Resolution → Prompt Composition → Final
Validation → Evidence Recording.

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

**LLM Wiki**
Siehe *Wiki (LLM Wiki)*.

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
as tools. The future adapter will live in `apps/mcp/` and use the same Service
Layer as the WebUI. Q-001 remains open until the adapter spec is written.

**Memory**
User and project-level persistent context managed by mem0. Stores writing
preferences, style patterns, rejection feedback. Accessed via `core/memory/`.
Always optional — the system degrades gracefully if unavailable.

**Meta Prompt**
Guaranteed Narrare identity and role guidance injected by the `NarrareMeta`
Capability (ADR-026). Universal fiction, conflict, and injection-defense rules
come from `NarrareUniversalRules`; customizable feature prompts remain in the
PromptComposer cascade under `core/prompts/_bundled/`.

**Mode 1 / Mode 2 (Invocation Modes)**
Zwei Invocations-Modi für die Prompt-Auflösung (ADR-048):
- **Mode 1:** Nutzt `PromptComposer` mit `intent` + `context_mode` + governed EN Template.
  Der Standard-Pfad für alle Feature-Prompts seit ADR-054. Aufruf:
  `composer.build(intent=..., context=..., context_mode=...)`.
- **Mode 2:** Nutzt `compose_invocation()` für nicht-Standard-Pfade, bei denen ein Agent
  die Prompt-Komposition selbst übernimmt. Nur für legitime Fälle (z. B. ChatAgent,
  DraftAgent) vorgesehen. Falsche Mode-2-Deklarationen wurden durch ADR-054/049 auf
  Mode 1 migriert.

**Mode (Writing Mode / Prompt Mode)**
The type of operation that determines which prompt file is selected and how
context is assembled. Two related concepts:
- **Writing mode**: The type of writing operation: `new_chapter`, `extend`,
  `rewrite`, `interactive`, `co_author`. Affects prompt selection, generation
  parameters, and context assembly.
- **Prompt mode**: The mode key used in the prompt cascade path
  `prompts/_bundled/{category}/{lang}/{mode}/system.md`. Includes writing modes
  plus planning modes (`outline`, `character_arc`, `timeline`), KB modes
  (`interview`, `improve`, `suggest`, `merge`, etc.), and analysis modes.

**Modifier (Prompt Modifier)**
Guaranteed Narrare identity and role guidance injected by the `NarrareMeta`
Capability (ADR-026). Universal fiction, conflict, and injection-defense rules
come from `NarrareUniversalRules`; customizable feature prompts remain in the
PromptComposer cascade under `core/prompts/_bundled/`.

**Mode (Writing Mode / Prompt Mode)**
The type of operation that determines which prompt file is selected and how
context is assembled. Two related concepts:
- **Writing mode**: The type of writing operation: `new_chapter`, `extend`,
  `rewrite`, `interactive`, `co_author`. Affects prompt selection, generation
  parameters, and context assembly.
- **Prompt mode**: The mode key used in the prompt cascade path
  `prompts/_bundled/{category}/{lang}/{mode}/system.md`. Includes writing modes
  plus planning modes (`outline`, `character_arc`, `timeline`), KB modes
  (`interview`, `improve`, `suggest`, `merge`, etc.), and analysis modes.

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

**OutputBudget / OutputBudgetDecision**
Intent/mode-specific token-budget resolution. `OutputBudget` is the validated
token value; `OutputBudgetDecision` adds provenance metadata.

**Output Validator**
A deterministic function registered via `agent.output_validator()` on a pydantic-ai
Agent that enforces domain invariants on the agent's structured output before it is
returned to the caller. Validators can reject or guide retries, but must not make
hidden LLM calls, write to the database, or assemble prompts. Policy defined in
ADR-035. Narrare has validators on all 17 structured-output agents (Phase 5: 4
priority agents, Phase 6: 13 remaining agents). 237 validation tests total.

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

**Precomputed Context Layer**
Ein Architekturpattern, bei dem Daten vorverarbeitet (precomputed) und als optimierte, LLM-lesbare Zusammenfassungen gespeichert werden — statt Rohdaten bei jedem LLM-Call live zu laden. Ermöglicht deterministischen, token-effizienten Context Assembly. In Narrare implementiert als LLM Wiki (WIKI-001, ADR-022).

**ProcessHistory**
A lightweight dataclass for storing pydantic-ai message history across conversational
turns. Used by agents with `HistoryPolicy.CONVERSATIONAL`. Provides `add()`, `clear()`,
and `is_empty` operations. Defined in `core/agents/process_history.py`. Part of ADR-034.

**PromptComposer Mode 1**
Konkrete Implementierung des Mode 1 Invocation-Patterns (ADR-048/054):
`composer.build(intent=..., context=..., context_mode=...)` mit governed Template.
Der Service injected `PromptComposer`, erstellt ein `PromptContext`, und resolved
den Prompt über `composer.build()`. Mode 1 ist der Standard für alle Feature-Prompts
seit ADR-054, die f-String-Baseline (`INLINE-FEATURE-PROMPT`) ist auf 0 gesetzt.
Siehe *Mode 1 / Mode 2*.

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

**Runtime Adopted / Runtime Adoption**
An adoption state (Status in der Adoption-Registry, ADR-045) where static checks pass
and correlated runtime evidence proves the required production invocation path used the
intended context enrichment, prompt merge, budget enforcement, model/agent call, and
evidence recording. Static adoption alone is not runtime adoption. In der Registry:
"Infrastructure complete" ≠ "Static verified" ≠ "Runtime verified" ≠ "Runtime adopted."
Der Status wird durch `just check-adoption` überwacht.

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

**StreamEvent**
An event yielded during `NarrareAgent.run_stream()`. Two types: `"token"` (text chunk)
and `"done"` (completion with usage info and `new_messages`). The `"done"` event carries
`new_messages` for updating `ProcessHistory`. Defined in `core/agents/base.py`. Part of
the unified streaming interface (RULE-13).

**Stale (WikiSummary)**
Der Status eines WikiSummary, dessen Abhängigkeiten (Prompt-Version, Entity-Content, Template-Version) sich seit der Generierung geändert haben. Ein stale Summary löst einen Lazy-Refresh beim nächsten Zugriff aus — der Write-Call fällt dabei auf Rohdaten zurück. Siehe *WikiSummary*.

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

**voice_analysis**
Ein Sub-Modell auf `SpeechPatterns` (in `kb/schemas/character.py`), das deskriptive
und Metrik-Daten zur Charakter-Stimme enthält. Die deskriptive Gruppe (formality,
vocabulary_level, sentence_profile, emotional_range, cultural_regional_markers,
voice_examples) wird durch den erweiterten `get_speech_data()`-Consumer in die
Generierung gerendert. Die Metrik-Gruppe (`voice_metrics`) ist comparison-only und
erreicht niemals die Generierung. Siehe ADR-055, ANAL-008.

**Voice Check**
An analysis (WRITE-010) that checks a chapter's **character dialogue** against
each speaking character's stored **per-character voice profile** (produced by
Character Voice Profiling, ANAL-008), reporting a per-character match score and
flagging specific dialogue lines whose voice deviates from the established
profile. Read-only (it checks; it does not profile or rewrite) and flag+score
only (no rewrite suggestions — rewrite reuse of WRITE-004 is a separate step).
See ADR-057, WRITE-010. *Not* a check against the author's own style profile
(that is a separate, author-voice concern; see ANAL-007/ANAL-009).

---

## W

**Wiki (LLM Wiki)**
Ein System aus vorberechneten, LLM-generierten Zusammenfassungen von KB-Entities und Kapiteln. Dient als Precomputed Context Layer für das Context Assembly System (INFRA-003). WikiSummaries (~40 Tokens) ersetzen Rohdaten (~200 Tokens) im Writing-Context. Jedes Summary hat einen `depends_on`-Tracker für Prompt-Versionierung und Stale-Erkennung. Betrieben via TaskIQ-Background-Jobs bei Entity-Änderung. Feature: WIKI-001.

**WikiChapterSummary**
Eine erweiterte Kapitelzusammenfassung, die über das ChapterSummary (WRITE-012) hinausgeht: enthält Key-Events, beteiligte Entitäten und Themes. Wird beim Finalisieren eines Kapitels generiert. Siehe *Wiki (LLM Wiki)*.

**WikiSummary**
Eine LLM-generierte, präcomputierte narrative Zusammenfassung einer KB-Entity (2-3 Sätze). Enthält: narrative Beschreibung, Rolle in der Story, Schlüsselattribute, Beziehungen und Kapitel-Referenzen. Status: fresh | stale | pending. Siehe *Wiki (LLM Wiki)*.

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

> Last updated: 2026-06-30 — Corrected "Voice Check" definition to match ADR-057/WRITE-010 (character dialogue checked against stored per-character voice profiles, not the author's style profile). 2026-06-29 — Added terms: AUFG, character_voice, DialogueParser, governed debt, INLINE-FEATURE-PROMPT, Mode 1/Mode 2, PromptComposer Mode 1, Runtime Adoption cross-ref, voice_analysis. Updated existing: Governed Adoption Debt, Runtime Adopted, InvocationPipeline verified.
> Maintained by: Architecture Agent
> Add terms as they emerge — do not let ambiguous vocabulary persist
