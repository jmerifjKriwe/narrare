# ADR-069 — Adaptive Context + Dialogue Coach Vertical

> **Status:** ✅ Accepted (brainstorming approved 2026-07-19; user ADR review approved 2026-07-20)
> **Date:** 2026-07-19
> **Deciders:** Architecture Specialist; User (approved the brainstorming design
> on 2026-07-19; this ADR answers the 23 open questions the brainstorming deferred)
> **Supersedes:** — (LEARN-002 is **recalibrated**, NOT superseded — see Decision 13)
> **Related:**
> ADR-002 (prompt system),
> ADR-015 (agents first-class),
> ADR-021 (deterministic analysis),
> ADR-026 (capability prompt injection),
> ADR-032 (pydantic evals),
> ADR-033 (mem0 memory),
> ADR-037 (prompt-surface manifest),
> ADR-038 (AI invocation adoption contract — the enricher pattern this ADR extends),
> ADR-040 (ProjectWritingProfile SSOT),
> ADR-041 / ADR-045 (persistent evidence — the table this ADR extends for snapshots),
> ADR-043 (AI interaction primitives),
> ADR-046 (prompt-path compliance — §7 stub-variable detector),
> ADR-050 (cross-feature context contracts),
> ADR-052 (session stop/recovery),
> ADR-054 (Mode-1 PromptComposer mandate),
> ADR-055 (character-voice storage contract — the descriptive-vs-metric boundary this ADR preserves),
> ADR-056 (runtime-aware adoption gate),
> ADR-057 (voice-check checking-path contract — the metrics-never-reach-generation rule this ADR honours),
> ADR-065 (RULE-13 two-method run/stream contract),
> ADR-067 (reusable KB-context provider — the precedent this ADR mirrors for AdaptiveContextProvider),
> CONSTRAINTS.md RULE-02/02a/02b/03/04/05/06/07/08/09/10/11/12/13/14/16/17/18/18b/20/22/23,
> LEARN-001 / ANAL-008 / ASSIST-004 / WRITE-010 feature specs

> **Scope of this ADR:** contracts + 17 architectural decisions only. This
> document records the contracts the implementation must satisfy; the code,
> tests, governed template, and frontend components live in the modules
> named in the Retrofit-Plan, not in this ADR.

---

## Context

### Why this ADR exists

A completed brainstorming session
(`docs/superpowers/specs/2026-07-19-adaptive-context-dialogue-coach-design.md`,
2468 lines, all 6 sections user-approved) defined a three-component vertical
slice but explicitly deferred 23 architectural questions (Q-A1..Q-D4) to this
ADR. The vertical:

1. **AdaptiveContext (Core)** — a new contract consolidating
   `PreferenceProfile` (LEARN-001) + `CharacterVoiceProfile` (ANAL-008) into a
   single adaptive view that is injected into prompts.
2. **ASSIST-004 Dialogue Coach** — the first concrete AI operation that
   consumes `AdaptiveContext`, with analyze + improve modes over selected
   dialogue.
3. **LEARN-002 recalibrated** — reinterpreted from "statistical voice pipeline"
   to "Adaptivity Dashboard" (visibility + steering + transparency).

The vertical makes the existing adaptivity infrastructure (`PreferenceProfile`,
`CharacterVoiceProfile`, `ProjectWritingProfile`, four registered but
empty `{{style_constraints}}` / `{{avoidance_patterns}}` /
`{{user_preferences}}` / `{{character_voice_profiles}}` variables) visible and
controllable for the first time.

### Verified current state (grounded, not assumed)

| Concern | State | Location |
|---------|-------|----------|
| `PromptContext.user_preferences` field | EXISTS, registered as `{{user_preferences}}` | `core/prompts/context.py`, `variable_registry.py:94` |
| `PromptContext.style_constraints` field | EXISTS, registered, **always empty at runtime** | `core/prompts/context.py`, `variable_registry.py:96` |
| `PromptContext.avoidance_patterns` field | EXISTS, registered, **always empty at runtime** | `core/prompts/context.py`, `variable_registry.py:95` |
| `PromptContext.character_voice_profiles` field | EXISTS, registered, populated via `ProjectWritingProfile.formatted_voice_profiles` | `core/prompts/context.py`, `variable_registry.py:99` |
| `PreferenceContextEnricherImpl` | EXISTS, writes ONLY `user_preferences` (single variable of four) | `core/ai_invocation/enrichers/preferences.py` |
| `AdaptiveContext` / `AdaptiveWeights` / `AdaptiveSettings` | DO NOT EXIST | — |
| `AdaptiveContextProvider` Protocol | DOES NOT EXIST | `core/ai_invocation/contracts.py` (has `ContextEnricher`, `ProfileProvider`, but no adaptive) |
| `ProjectWritingProfile.formatted_voice_profiles` | EXISTS, renders `speech_summary` only, never `voice_metrics` (ADR-055/057 constraint) | `core/profiles/models.py:55-66` |
| `ProfileProvider.get_profile(project_id) → ProjectWritingProfile \| None` | EXISTS (ADR-040) | `core/ai_invocation/contracts.py:140` |
| `PreferenceProvider.get_preferences(user_id, project_id) → PreferenceProfile` | EXISTS (mem0-backed, ADR-033) | `core/memory/protocols.py:40` |
| `LLMIntent.DIALOGUE_COACH` | DOES NOT EXIST | `core/llm/intents/_enums.py` |
| Prompt category `ai_assist/` | DOES NOT EXIST | `core/prompts/_bundled/` has `writing/`, `kb/`, `analysis/`, `planning/`, `generation/`, `chat/`, `meta/`, `universal/`, `wiki/` |
| `LLMIntent.VOICE` routeable modes | `{"character_voice", "voice_check"}` (ADR-055/057) | `core/prompts/route_table.py:273` |
| `invocation_evidence` table | EXISTS (ADR-042/045); JSONB columns already used for `prepared_context_fingerprint` etc. | `apps/api/narrare/evidence/` |
| `ProjectSettings` model | EXISTS, has JSONB columns for `category_overrides`, `intent_overrides`, `token_limit_overrides` | `apps/api/narrare/settings/models.py:31` |
| `_COMMON_OPTIONAL_VARIABLES` includes `user_preferences`, `avoidance_patterns`, `style_constraints` (via PromptContext), `character_voice_profiles` | YES (declared optional on every writing/kb/analysis route) | `core/prompts/route_table.py:70-96` |
| `DialogueParser` (deterministic attribution) | EXISTS, reusable (ADR-055 D3) | `core/analysis/dialogue_parser.py` |
| ADR count | ADR-068 is the latest (mem0 test isolation); **next free is ADR-069** | `docs/architecture/decisions/INDEX.md` |

### Root cause (5× Why)

1. **Symptom:** Adaptivity infrastructure exists (`PreferenceProfile`,
   `CharacterVoiceProfile`, four registered prompt variables) but no user-
   facing feature demonstrates its value, and two of the four variables
   (`style_constraints`, `avoidance_patterns`) are *always* empty.
2. **Why is nothing visible?** No feature has been a concrete consumer of the
   consolidated adaptive view; the `PreferenceContextEnricherImpl` writes only
   one of the four adaptive variables, and there is no `AdaptiveContext`
   abstraction that aggregates all signals.
3. **Why does only one variable get populated?** ADR-038 narrowly scoped
   `PreferenceContextEnricherImpl` to preference text; voice-profile rendering
   was added later (ADR-040), but derived constraints/avoidance were never
   derived. There was no consumer demanding them.
4. **Why was there no consumer?** Every prior AI feature (WRITE-002..012,
   ANAL-001..008, WRITE-010) used the existing variables opportunistically;
   none was designed to *showcase* adaptivity. LEARN-002 (Style Adaptation)
   was specified as a separate statistical pipeline (sentence-length
   distribution, few-shot prompting) that duplicated `PreferenceProfile` and
   conflicted with `ANAL-007` (Author Voice Profiling) — it was never
   implemented because the scope was wrong.
5. **Why now?** The Voice vertical (ANAL-008, WRITE-010) is stable; the
   adaptivity primitives are tested in production; LEARN-002 needs a
   realistic reinterpretation; ASSIST-004 (Dialogue Coach) is the natural
   pilot consumer because dialogue is the place where preferences AND
   character voices both matter visibly.

**Verdict:** Build a clean consolidation contract (`AdaptiveContext`) that
**unifies** existing sources (no new SSOT), pair it with a concrete consumer
(ASSIST-004), and reinterpret LEARN-002 as the visibility/steering surface.
This is a consolidation + scope-correction decision, not a new abstraction.

---

## Decision Drivers

- **RULE-02/02a/02b** — Dialogue Coach's prompt MUST be PromptComposer Mode 1
  (intent + `dialogue_coach` context_mode + governed EN template). No inline
  f-strings, no production fallback, no system-prompt-in-user-channel.
- **RULE-03** — `AdaptiveContextProvider`, `AdaptiveContextService`, and
  `DialogueCoachService` Protocols MUST exist before any implementation.
- **RULE-04/06** — Modularise; one responsibility per file. Adaptive data
  models ≠ enricher ≠ provider ≠ service ≠ agent ≠ router.
- **RULE-07** — Core owns the contracts + data models + enricher; Backend
  owns the providers, services, routers; no `apps/`→`core` cycles; no
  `core/`→`apps/` imports.
- **RULE-08** — mem0 access stays behind `PreferenceProvider`; the
  `AdaptiveContextProvider` Backend impl composes existing providers, never
  touches mem0/SQL directly.
- **RULE-11** — A user with no preferences, no voice profiles, or with
  adaptivity disabled yields a graceful "no signals" result, never a crash
  or silent prompt regression.
- **RULE-12** — The Service Layer is the only public API. The dashboard
  (WebUI), future MCP, A2A, and CLI clients all hit `AdaptiveContextService`
  and `DialogueCoachService`, never each other.
- **RULE-13 (per ADR-065)** — `DialogueCoachService` MUST expose both
  `run()` (non-streaming, for MCP/A2A) and `stream()` (for SSE), two named
  methods sharing one provider/model-settings path.
- **RULE-14** — `ProjectSettings.adaptive_settings` JSONB column needs an
  Alembic migration in the same task as the model change.
- **RULE-16** — Three new i18n namespaces (`studio.dialogueCoach`,
  `settings.adaptive`, `editor.adaptiveIndicator`) MUST be registered in
  `request.ts` AND have JSON files in all 3 locales (en/de/fr), in the same
  commit.
- **RULE-17** — The `DialogueCoachOutput` Pydantic schema and the TypeScript
  `DialogueCoachOutput` interface MUST match field-by-field.
- **RULE-18b** — AdaptiveWeights MUST have a regression test proving that
  changing a weight changes the runtime prompt or the agent's output (Eval).
- **RULE-20** — No half-implementations: all three components (AdaptiveContext
  Core, ASSIST-004, LEARN-002 dashboard) ship together or not at all.
- **RULE-22** — Cross-feature coherence: `AdaptiveContext` reads from
  LEARN-001, ANAL-008, WRITE-010 (existing producers). Integration contracts
  must document change/deletion behaviour for each shared source.
- **ADR-038** — The `AdaptiveContextEnricher` follows the established
  enricher pattern (`ContextEnricher` Protocol, immutable `model_copy`,
  graceful degradation D7).
- **ADR-055/057** — `voice_metrics` stay **checking-path only**.
  `AdaptiveContext` renders only `speech_summary` (the descriptive profile).
  This is a hard constraint; Dialogue Coach does NOT use `voice_metrics`.
- **ADR-054** — Dialogue Coach's prompt is Mode 1 (composer-driven) from day
  one. No inline-feature-prompt debt.
- **ADR-056** — `dialogue_coach` runtime adoption evidence is required to
  move it off governed adoption debt.
- **ADR-065** — `DialogueCoachService.run()` + `stream()` as two methods, not
  a `stream: bool` union.
- **ADR-067** — `AdaptiveContextProvider` mirrors the `KBContextProvider`
  pattern (Core Protocol, Backend impl, composes existing providers).
- **architectural-discipline §1/§4/§7** — Root-cause solution; no workarounds;
  "documented ≠ implemented" — Retrofit-Plan makes the existing
  `PreferenceContextEnricherImpl` migration explicit.

---

## Options Considered — High-Level Approach

The brainstorming evaluated three approaches (§2.1 of the design spec):

### Approach 1 — Implement LEARN-002 as originally specified (statistical voice pipeline)

Build the originally-specified statistical profiler (sentence-length
distribution, vocabulary diversity, dialogue ratio, few-shot prompting).

**Pros:**

- Smallest deviation from the existing spec text.

**Cons:**

- Conflates with `ANAL-007` (Author Voice Profiling), which is the proper
  home for whole-novel voice profiling.
- Duplicates `PreferenceProfile` infrastructure.
- The actual user value (adaptivity made visible) is buried under a
  statistical pipeline users did not ask for.
- Violates **RULE-20** (build it properly): the statistical pipeline was
  never realistic; it was a design option from before the Voice vertical
  existed.

**Rejected.**

### Approach 2 — Contract-only (AdaptiveContext in Core, no consumer)

Build only the `AdaptiveContext` abstraction, with no pilot consumer.

**Pros:**

- Smallest possible scope.

**Cons:**

- Violates **RULE-20** (no half-implementations): an abstraction without a
  consumer is speculation.
- Repeats the existing failure mode: infrastructure exists but no feature
  demonstrates its value.
- No way to prove (`RULE-18b`) that the abstraction has runtime effect.

**Rejected.**

### Approach 3 — Full vertical slice (CHOSEN)

Three components in one ADR:

1. **AdaptiveContext Core contract** (`AdaptiveContext`, `AdaptiveWeights`,
   `AdaptiveSettings`, `AdaptiveContextProvider` Protocol,
   `AdaptiveContextEnricher`).
2. **ASSIST-004 Dialogue Coach** as pilot consumer (Core agent + types,
   Backend service + SSE router, Frontend panel + hook + i18n, governed
   prompt template).
3. **LEARN-002 recalibrated** as Adaptivity Dashboard (visibility + steering
   + transparency).

**Pros:**

- Each component has a real purpose; the contract has a concrete consumer;
  the dashboard makes the value visible.
- Closes the feedback loop: accept/reject → PreferenceProfile → next AI call
  → visible adaptive activity.
- Demonstrates `RULE-18b` (Configuration Effect Integrity): the eval suite
  proves that changing weights changes outputs.

**Cons:**

- Large scope (6 phases, 4–6 sessions).
- New `LLMIntent.DIALOGUE_COACH`, new prompt category `ai_assist/`, new
  Backend domain `apps/api/narrare/ai_assist/`, new Backend domain
  `apps/api/narrare/adaptive/`.
- Breaking change to `PreferenceContextEnricherImpl` wiring (Decision 1).

**Accepted** — the tradeoff is the correct one because a partial
implementation would repeat the exact failure mode this ADR exists to fix.

---

## Decision

**We choose Approach 3 — the full vertical slice.**

The 17 decisions below answer the 23 open questions from §13 of the
brainstorming design spec (Q-A1..Q-A5, Q-B1..Q-B6, Q-C1..Q-C4, Q-D1..Q-D4).
User-already-decided questions (Q-C1, Q-C3 guidance, Q-D1) are honoured; the
remaining questions are answered here with root-cause analysis, alternatives,
and sustainability checks.

---

## Decision 1 — `AdaptiveContextEnricher` replaces `PreferenceContextEnricherImpl` (Q-A1, Q-A4) — Option β

### Root cause

`style_constraints` and `avoidance_patterns` are registered prompt variables
that are **always empty at runtime** because no enricher writes them.
`PreferenceContextEnricherImpl` (ADR-038) was scoped narrowly to write only
`user_preferences`. Three more variables (`character_voice_profiles`,
`style_constraints`, `avoidance_patterns`) are now needed for adaptive
operation, and the existing enricher's name and scope do not cover them.

### Options Considered

#### Option α — Two parallel enrichers (PreferenceContextEnricherImpl + AdaptiveContextEnricher)

`PreferenceContextEnricherImpl` keeps writing `user_preferences`;
`AdaptiveContextEnricher` writes the other three adaptive variables.

**Pros:** Minimal change to existing code.

**Cons:**

- **RULE-22 (cross-feature coherence) violation risk:** two enrichers could
  produce inconsistent views of the same preference profile (one sees a
  stale cache, the other a fresh fetch).
- Redundant provider calls (`PreferenceProfile` would be loaded twice — once
  by each enricher).
- Unclear ownership: which enricher "owns" the adaptive variables?
- Hidden coupling through `dynamic_inputs` — both write into the same dict.

**Rejected.**

#### Option β — `AdaptiveContextEnricher` replaces `PreferenceContextEnricherImpl` as the single enricher (CHOSEN)

`AdaptiveContextEnricher` becomes the **single enricher** that writes all
four adaptive variables. `PreferenceContextEnricherImpl` is removed (its
behavior is a strict subset — it only wrote `user_preferences`, which the new
enricher also writes).

**Pros:**

- Single source of truth: one enricher, one provider call, one coherent view.
- Clean RULE-06 mapping: "AdaptiveContextEnricher handles adaptive
  variables" — name matches responsibility.
- No redundant provider calls.
- Future-proof: adding a fifth adaptive variable later means extending one
  enricher.

**Cons:**

- Breaking change to ADR-038's named `PreferenceContextEnricher` Protocol
  consumers.
- Existing DI wiring must be updated.
- Existing tests that mock `PreferenceContextEnricherImpl` need rewiring.

#### Option γ — `PreferenceContextEnricherImpl` delegates internally to `AdaptiveContextProvider`

The existing enricher keeps its name but is rewired to call the new
`AdaptiveContextProvider`, populating all four variables.

**Pros:** No class-name churn.

**Cons:**

- **RULE-06 violation:** the name "Preference" does not suggest voice /
  constraints / avoidance. The class would be doing more than its name
  promises.
- Couples the enricher's identity to the old ADR-038 scope, even though its
  responsibility has expanded.
- Makes ADR-038's contract documentation inaccurate.

**Rejected.**

### Decision

**Option β.** `AdaptiveContextEnricher` replaces
`PreferenceContextEnricherImpl` as the single writer of all four adaptive
variables. The `ContextEnricher` Protocol (from ADR-038) is unchanged; only
the implementation class is swapped.

### Rationale

ADR-038's `PreferenceContextEnricher` Protocol and its `PREFERENCE_KEY`
constant were correct for the world that existed when ADR-038 was written —
a world where only `user_preferences` was a registered adaptive variable.
Since then, `character_voice_profiles`, `style_constraints`, and
`avoidance_patterns` have all become registered variables (CR-AUFG-04-04 and
earlier). The narrow enricher is now structurally incomplete: it leaves
three registered slots permanently empty.

The architecturally correct response is to introduce the enricher whose
name and scope match the actual responsibility. `AdaptiveContextEnricher`
is that enricher. Keeping two parallel enrichers (α) would recreate the
fragmentation that `KBContextProvider` (ADR-067) was created to eliminate;
delegating under the old name (γ) would be a RULE-06 violation by another
name.

This decision **completes** ADR-038 rather than superseding it. The
`ContextEnricher` Protocol stays; the `PreferenceContextEnricher` Protocol
stays as a named specialization (it documents the preference-injection
intent). Only the implementation class
`PreferenceContextEnricherImpl` is removed.

### Sustainability check

1. **Correct in 3 months?** Yes — any new adaptive variable lands in one
   place (`AdaptiveContextEnricher`), with one provider call.
2. **Hard-to-undo coupling?** None — the swap is mechanical (DI wiring +
   test fakes). The Protocol is unchanged.
3. **Simplest correct solution?** Yes — single enricher, single provider,
   no parallel paths.
4. **Design intent clear?** Yes — the class name documents its
   responsibility; future maintainers see one canonical adaptive writer.

### Migration consequences (§ Retrofit-Plan details the file list)

- `PreferenceContextEnricherImpl` is deleted; `AdaptiveContextEnricher` is
  wired into every DI site that currently uses
  `PreferenceContextEnricherImpl`.
- The `PREFERENCE_KEY = "user_preferences"` constant moves to the new
  enricher's module as one of four well-known keys.
- Existing tests instantiate fakes of the underlying `PreferenceProvider`
  directly (not the enricher class), so the test surface change is bounded.

---

## Decision 2 — AdaptiveSettings persistence: extend `ProjectSettings` with `adaptive_settings: JSONB` (Q-A2) — Option β

### Root cause

`AdaptiveSettings` (`enabled: bool`, `weights: AdaptiveWeights`) needs to
survive across sessions. The settings cascade (`UserSettings`,
`ProjectSettings`, `UserAISettings`, `ProjectSettingsAI`) already exists and
uses JSONB columns for bounded structured data
(`category_overrides`, `intent_overrides`, `token_limit_overrides`).

### Options Considered

#### Option α — Own table `adaptive_settings`

A purpose-built table with columns `(user_id, project_id, enabled, weights,
updated_at)` and a full repository + service.

**Pros:** Clean separation; easy to query.

**Cons:**

- Schema overhead: a new table + repository + migration for what is
  effectively 5 floats and a boolean.
- Violates the existing pattern: every other AI-behavior setting
  (`token_limit_profile`, `intent_overrides`, `category_overrides`) lives as
  JSONB on `ProjectSettings`. Adding a parallel table fractures the pattern.
- **RULE-06 concern:** adaptivity is one facet of AI behavior; it is not a
  distinct domain like KB or chapters.

**Rejected.**

#### Option β — Extend `ProjectSettings` with `adaptive_settings: JSONB` column (CHOSEN)

Add one nullable JSONB column to `ProjectSettings`. The Core
`AdaptiveSettings` dataclass is serialised to JSON on write and
deserialised on read. A small repository helper on the existing
`ProjectSettingsRepository` handles the (de)serialisation.

**Pros:**

- Reuses the existing settings cascade — no new table, no new repository
  class, no new migration framework.
- Matches the established JSONB pattern (`category_overrides`,
  `token_limit_overrides`).
- AdaptiveSettings lives at project level, which matches the per-novel AI
  configuration pattern.

**Cons:**

- Requires one Alembic migration (RULE-14).
- The JSONB column is weakly typed at the DB level (mitigated by Pydantic
  validation on read).

#### Option γ — Extend `UserSettings` instead (user-level)

Same as β but on `UserSettings`.

**Pros:** Reflects "this user wants adaptivity on / off."

**Cons:**

- Does not match the per-project AI configuration pattern
  (`ProjectSettings.ai_provider`, `ProjectSettings.token_limit_profile`).
- Different novels need different weights (literary fiction ↔ high voice
  fidelity; thriller ↔ low voice fidelity).
- `AdaptiveContext` is itself per-project (voice profiles are project-
  scoped); settings should match.

**Rejected.**

### Decision

**Option β.** Add `adaptive_settings: Mapped[dict | None] =
mapped_column(JSONB, nullable=True)` to `ProjectSettings`. Store the
Core `AdaptiveSettings` dataclass serialised as JSON. Alembic migration
adds the column; Pydantic validation on read guarantees shape.

### Rationale

Adaptive weights and the enabled flag are **per-project AI behavior** —
exactly the concern `ProjectSettings` already models
(`token_limit_profile`, `intent_overrides`). Storing them as a JSONB column
on the existing table is the established pattern; introducing a parallel
table would fracture that pattern and add infrastructure overhead
disproportionate to the data (5 floats + 1 bool).

Per-project (not per-user) is correct because the actual adaptive *data*
(`PreferenceProfile.user_id+project_id`, `CharacterVoiceProfile` per
character) is already project-scoped, and different novels warrant
different weight tuning.

### Sustainability check

1. **Correct in 3 months?** Yes — future user-level "global adaptivity
   toggle" can be added to `UserSettings` later as a separate JSONB column
   without disturbing this design.
2. **Hard-to-undo coupling?** None — one nullable column, one Alembic
   migration with a downgrade.
3. **Simplest correct solution?** Yes — reuses existing cascade.
4. **Design intent clear?** Yes — `ProjectSettings.adaptive_settings` is
   analogous to `ProjectSettings.token_limit_profile` (both per-project AI
   behavior).

---

## Decision 3 — `AdaptiveContextProvider` (Core Protocol) is a new, distinct contract (Q-A3, Q-A4) — yes, both Provider and Service are needed

### Root cause

`AdaptiveContext` aggregates data from three sources that no single
existing Protocol returns:

- `PreferenceProfile.text` (LEARN-001, via `PreferenceProvider`).
- `ProjectWritingProfile.formatted_voice_profiles` (ADR-040, via
  `ProfileProvider`).
- `AdaptiveSettings` (this ADR, via the new persistence layer).
- Derived `style_constraints_text` and `avoidance_patterns_text` (new
  derivation logic — currently empty everywhere).

### Options Considered

#### Option A — Reuse `ProfileProvider`; extend `ProjectWritingProfile` with derived fields

`ProfileProvider.get_profile()` returns a `ProjectWritingProfile` extended
with `preference_text`, `style_constraints_text`,
`avoidance_patterns_text`, and `weights`.

**Pros:** No new Protocol.

**Cons:**

- **RULE-06 violation:** `ProjectWritingProfile` is a value object for
  *writing* data (genre, tone, voice). Stuffs preference text and prompt-
  bound text blobs into a model that is otherwise structural.
- Conflates "what is this project's writing profile" with "what adaptive
  bundle does this invocation need."
- Forces every consumer of `ProjectWritingProfile` to carry fields they do
  not use.

**Rejected.**

#### Option B — New `AdaptiveContextProvider` Protocol that composes existing providers (CHOSEN)

```python
# packages/core/narrare_core/ai_invocation/contracts.py
class AdaptiveContextProvider(Protocol):
    async def get_context(self, user_id, project_id) -> AdaptiveContext: ...
    async def get_settings(self, user_id, project_id) -> AdaptiveSettings: ...
```

The Backend implementation composes `PreferenceProvider` +
`ProfileProvider` + the adaptive settings repository + the derivation
logic. The Protocol is the contract that `AdaptiveContextEnricher`
(Core) consumes.

**Pros:**

- Mirrors ADR-067 (`KBContextProvider` composes existing KB fetch + render
  primitives into a unified bundle).
- Keeps `ProjectWritingProfile` focused on writing-profile data.
- The Core enricher depends on a Core Protocol — clean RULE-07 boundary.
- Clear RULE-06 mapping: one provider = one responsibility (assemble
  adaptive bundle).

**Cons:**

- One new Protocol.

#### Option C — Skip the Provider, have the Backend service compose directly

`AdaptiveContextService` (Backend) directly calls `PreferenceProvider` +
`ProfileProvider` + settings repo and builds the `AdaptiveContext` inline.

**Pros:** One fewer Protocol.

**Cons:**

- The Core `AdaptiveContextEnricher` then cannot consume the abstraction
  (it would need to call Backend services, violating RULE-07 Core→Backend).
- Forces either: (a) the enricher is moved to Backend (violates ADR-038's
  Core enricher pattern), or (b) every feature service rebuilds the
  bundle (violates DRY).

**Rejected.**

### Decision

**Option B.** New `AdaptiveContextProvider` Protocol in Core
(`packages/core/narrare_core/ai_invocation/contracts.py`); Backend
implementation in `apps/api/narrare/adaptive/adaptive_context_provider.py`.

### Rationale

This is the ADR-067 pattern verbatim — a thin composer provider that
folds multiple existing sources into one canonical bundle. The Core
Protocol lets the Core enricher depend on an abstraction (RULE-07
boundary preserved); the Backend impl handles the I/O (mem0, DB).

### Cross-feature coherence (RULE-22)

The provider is the **single canonical writer** of all four adaptive
prompt variables. Other paths (services passing `extra=` to
`PromptContext`) MAY still set these variables, but the enricher's value
wins unless the service explicitly post-overrides. This guarantees one
coherent adaptive view per invocation.

### Sustainability check

1. **Correct in 3 months?** Yes — adding a sixth adaptive signal (e.g.,
   cross-session memory) means extending the provider, not introducing a
   parallel path.
2. **Hard-to-undo coupling?** None — composes existing providers via
   Protocol injection.
3. **Simplest correct solution?** Yes — mirrors the proven ADR-067
   pattern.
4. **Design intent clear?** Yes — Provider name documents the
   aggregation responsibility.

### Service-vs-Provider separation (Q-C4 answered)

`AdaptiveContextProvider` (Core Protocol) is distinct from
`AdaptiveContextService` (Backend Service Layer public API). They serve
different consumers:

| | `AdaptiveContextProvider` | `AdaptiveContextService` |
|---|---|---|
| Layer | Core Protocol, Backend impl | Backend Service (RULE-12) |
| Consumer | `AdaptiveContextEnricher` (invocation pipeline) | Frontend Dashboard (REST) |
| Methods | `get_context()`, `get_settings()` | `get_context()`, `set_enabled()`, `set_weights()` |
| Returns | Core value objects | API Pydantic schemas |

This is **not overengineering** — it mirrors the existing split between
`ProfileProvider` (Core Protocol, consumed by enricher) and a future
per-feature service that exposes profile CRUD to the API. Collapsing them
would mix invocation-pipeline concerns with REST API concerns (RULE-06).

---

## Decision 4 — Adaptivity is on by default for writing/analysis/planning/chat; off for KB/generation/embed (Q-A5)

### Root cause

Which intents should consume adaptive signals? Putting adaptivity
everywhere (including `KB_CREATE`, `NAME_GENERATE`, `EMBED`) is wrong;
keeping it only for `ASSIST-004` underutilises it.

### Options Considered

#### Option A — Every intent goes through `AdaptiveContextEnricher`

Wire the enricher into the global invocation pipeline so every AI call
sees adaptive variables.

**Pros:** Maximum coverage.

**Cons:**

- KB operations (entity CRUD, extraction) do not produce authorial prose;
  preferences and voice profiles are irrelevant.
- NAME_GENERATE produces names that do not carry style.
- EMBED is not even an LLM call.
- Wastes provider calls (loading preferences for an operation that will
  not use them).
- Risks prompt bloat for operations with small token budgets.

**Rejected.**

#### Option B — Opt-in per intent (each intent declares applicability)

Each `LLMIntent` carries an `uses_adaptive_context: bool` flag.

**Pros:** Fine-grained control.

**Cons:**

- Adds a new field to every `ROUTE_CONFIGS` entry.
- Doubles the governance surface (route table + applicability flag).
- No clear policy for what should be true/false — defaults still needed.

**Rejected.**

#### Option C — Default-on for prose-bearing intents, default-off elsewhere; controlled by DI wiring (CHOSEN)

The enricher is wired into the DI chain for services that produce or
evaluate authorial prose (writing, analysis, planning, chat). It is **not**
wired for KB, generation (names/titles), embed, or research services. The
wiring decision lives in `dependencies_prompts.py` (where the existing
`PreferenceContextEnricherImpl` is wired today).

The enricher still self-gates via `AdaptiveSettings.enabled` AND
`AdaptiveContext.has_any_signal` — so even when wired, it is a no-op for
users with no preferences and no voices.

**Pros:**

- No new metadata field; the wiring decision is local to the DI module.
- Self-gating preserves graceful degradation.
- Matches the current pattern (the existing
  `PreferenceContextEnricherImpl` is wired into specific services, not
  globally).

**Cons:**

- Policy is implicit in wiring, not declarative in route_table.

### Decision

**Option C.** The enricher is wired into writing, analysis, planning, and
chat services (replacing the existing
`PreferenceContextEnricherImpl` wiring). It is **not** wired into KB,
generation, embed, or research services.

### Rationale

Adaptive signals shape *authorial* output. KB extraction, name
generation, and embedding do not produce authorial output; loading
preferences for them is wasted work and risk of prompt bloat. Wiring
localises the decision to the DI module (`dependencies_prompts.py`),
where the existing preference enricher is already conditionally wired.

### Applicability table (documented for RULE-22 coherence)

| Intent category | Adaptive wired? | Rationale |
|---|---|---|
| `writing` (WRITE, EXTEND, REWRITE, CO_AUTHOR, SUGGEST, CHAT) | ✅ Yes | Produces authorial prose; preferences shape output |
| `analysis` (ANALYSE, BETA_READ, VOICE, CONSISTENCY, FACT_EXTRACT, SUMMARIZE) | ✅ Yes | Evaluates authorial prose; preferences shape "what counts as good" |
| `planning` (PLAN) | ✅ Yes | Outlines reflect style preferences |
| `ai_assist` (DIALOGUE_COACH — this ADR) | ✅ Yes | Pilot consumer |
| `kb` (KB_CREATE, KB_IMPROVE, KB_EXTRACT, KB_INTERVIEW, KB_SUGGEST, KB_ENHANCE, KB_WORLDBUILD, KB_CONSISTENCY) | ❌ No | Operates on entities, not authorial voice |
| `generation` (NAME_GENERATE, TITLE_GENERATE) | ❌ No | Names/titles do not carry style |
| `embedding` (EMBED) | ❌ No | Not an LLM call |
| `research` (RESEARCH) | ❌ No | Web research synthesis |

### Sustainability check

1. **Correct in 3 months?** Yes — a new intent's category determines its
   applicability automatically.
2. **Hard-to-undo coupling?** None — wiring is local.
3. **Simplest correct solution?** Yes — no new metadata; policy lives
   where the wiring lives.
4. **Design intent clear?** Yes — the table above documents the policy.

---

## Decision 5 — Dialogue Coach is a new `LLMIntent.DIALOGUE_COACH` with a new `ai_assist` category (Q-B4) — Option (a)

### Root cause

Dialogue Coach is neither pure analysis nor pure writing nor pure voice.
It analyses dialogue (analysis-like), produces rewrites in improve mode
(writing-like), and uses character voices (voice-like). ASSIST-004 sits in
the `ai_assist` feature area (distinct from `analysis` and `writing`).
Where does its prompt surface live?

### Options Considered

#### Option (a) — New `LLMIntent.DIALOGUE_COACH`, new category `ai_assist` (CHOSEN)

Add `LLMIntent.DIALOGUE_COACH` to the enum. Category `"ai_assist"`. Mode
`"dialogue_coach"`. New bundled template at
`core/prompts/_bundled/ai_assist/en/dialogue_coach/system.md`. New
prompt-surface manifest + adoption-registry entries.

**Pros:**

- Semantically accurate: ASSIST-004 is its own operation, not a sub-mode
  of analysis or voice.
- Aligns with the existing `ASSIST-*` feature area (ASSIST-001 Plot Check,
  ASSIST-002 Title Suggest).
- Future ASSIST features (Plot Check, Title Suggest) reuse the category
  with their own modes.
- Module home `apps/api/narrare/ai_assist/` matches the feature-area name.

**Cons:**

- New intent + new category = more governance surface (manifest, registry,
  route table, manifest checker).

#### Option (b) — Mode of `LLMIntent.ANALYSE`

Add `dialogue_coach` to `ROUTE_CONFIGS[LLMIntent.ANALYSE].allowed_context_modes`.

**Pros:** Smaller surface.

**Cons:**

- ANALYSE is "general-purpose multi-dimension text analysis." Dialogue
  Coach is more specific (dialogue-focused) and *produces rewrites* in
  improve mode — that is not analysis.
- Mixes a writer's aid with evaluative features (beta reader, voice check,
  readability, POV).
- ASSIST-004 is in the `ai_assist` area, not `analysis`.

**Rejected.**

#### Option (c) — Mode of `LLMIntent.VOICE`

Add `dialogue_coach` to `ROUTE_CONFIGS[LLMIntent.VOICE].allowed_context_modes`.

**Pros:** Voice is the closest semantic match (dialogue distinctiveness).

**Cons:**

- VOICE is "voice and style analysis" (per `_enums.py`) with modes for
  *voice profiling* (`character_voice`) and *voice checking* (`voice_check`).
- Dialogue Coach covers MORE than voice: subtext, exposition, redundancy,
  tag overuse. Voice is one of seven issue types.
- Would force dialogue-coach templates into the `analysis/` bundled
  directory, contradicting the `ai_assist` Backend domain and feature
  area.
- Per ADR-055 Decision 4, VOICE is reserved for voice-specific concerns.

**Rejected.**

### Decision

**Option (a).** Add `LLMIntent.DIALOGUE_COACH` to the enum, category
`"ai_assist"`, mode `"dialogue_coach"`. New prompt category `ai_assist/`
in `_bundled/`.

### Rationale

The pattern of "one intent per distinct operation" is established
(`BETA_READ`, `CONSISTENCY`, `FACT_EXTRACT` are all standalone intents,
not modes of `ANALYSE`). Dialogue Coach is operationally distinct
(analyze + improve modes; produces rewrites; pilot consumer of
adaptivity), and it lives in a distinct feature area (`ai_assist`). The
new intent + category is the semantically honest choice.

The governance cost (manifest entries, route table, registry) is the
standard cost of any new routeable surface and is paid by every new AI
feature.

### Sustainability check

1. **Correct in 3 months?** Yes — future ASSIST features (Plot Check,
   Title Suggest) add modes under their own new intents or under
   `DIALOGUE_COACH`'s sibling space.
2. **Hard-to-undo coupling?** Minimal — adding an enum value is additive.
3. **Simplest correct solution?** Yes — new operation, new intent.
4. **Design intent clear?** Yes — the intent name documents the
   operation.

---

## Decision 6 — `voice_metrics` stay checking-path only; Dialogue Coach uses only `speech_summary` (Q-B2)

### Root cause

ADR-055 Risk #1 (closed by ADR-057 D1) established a hard boundary:
`voice_metrics` (the deterministic numeric block) are surfaced ONLY on the
checking path (WRITE-010); they NEVER reach generation. Dialogue Coach
sits between analysis and generation — it analyses dialogue AND, in
improve mode, proposes rewrites that may be accepted into the chapter.

### Options Considered

#### Option A — Dialogue Coach may use `voice_metrics`

The Dialogue Coach agent receives both the descriptive `speech_summary`
AND the structured `voice_metrics` for each speaking character. The
rationale would be "Dialogue Coach is not generation; it is analysis."

**Pros:**

- Richer signal for voice-mismatch detection.

**Cons:**

- **Violates ADR-055/057 constraint.** In improve mode, the coach
  produces rewrites; if the user accepts a rewrite, voice_metrics have
  indirectly influenced generated chapter text. The ADR-055/057 boundary
  is "metrics never reach generation" — accepting this option punches a
  hole in that boundary.
- The `CharacterVoiceAgent` (ANAL-008) already detects voice
  characteristics from the descriptive profile alone, proving the LLM
  does not need numeric metrics to judge voice.
- Numeric metrics are for *deterministic comparison* (ANAL-009 drift,
  WRITE-010 delta), not for LLM reasoning.

**Rejected.**

#### Option B — Dialogue Coach uses only `speech_summary` (descriptive profile), mirroring generation (CHOSEN)

The Dialogue Coach agent receives only the same `formatted_voice_profiles`
text that generation receives — the descriptive profile rendered by
`ProjectWritingProfile.formatted_voice_profiles`. No `voice_metrics`
field on the agent's Deps; no `voice_metrics` in the governed prompt.

**Pros:**

- Preserves the ADR-055/057 boundary perfectly.
- Mirrors the proof from `CharacterVoiceAgent`: the LLM can identify voice
  mismatches from descriptive profiles alone.
- Dialogue Coach and the generation pipeline share the same voice view
  (coherent).

**Cons:**

- Loses the deterministic signal. Mitigated: the coach is qualitative
  (LLM judgment), not quantitative (delta scoring). Numeric drift is
  ANAL-009's job.

### Decision

**Option B.** `AdaptiveContext.voice_profiles_text` renders only the
descriptive profile (the `formatted_voice_profiles` text). The
`DialogueCoachDeps` carries only that text. The governed template
references only `{{character_voice_profiles}}` (the existing registered
variable).

### Rationale

ADR-057's boundary exists because deterministic metrics are for
*comparison* (drift, checking) — they are not authorial instructions. An
LLM reasoning over metrics tends to over-weight numeric deltas and
produce mechanistic rewrites. Letting the LLM reason over the descriptive
profile produces qualitative judgments aligned with how readers actually
perceive voice.

This decision is also a *sustainability* decision: keeping the boundary
intact means future ANAL-009 (drift) and any future "metrics-based"
feature can rely on the boundary being universally honoured.

### Sustainability check

1. **Correct in 3 months?** Yes — ANAL-009 will reuse metrics; dialogue
   coach continues to use descriptive text only.
2. **Hard-to-undo coupling?** None — single boundary preserved.
3. **Simplest correct solution?** Yes — reuses existing
   `formatted_voice_profiles` text.
4. **Design intent clear?** Yes — `formatted_voice_profiles` already has
   a code comment (in `profiles/models.py:30`) documenting this
   boundary.

---

## Decision 7 — Speaker attribution: reuse `DialogueParser` + inline LLM resolution (Q-B3) — Option A

### Root cause

ASSIST-004 needs to attribute dialogue lines to speaking characters
before voice matching. ADR-055 Decision 3 already established the
project-wide pattern for this problem.

### Options Considered

#### Option A — Reuse `DialogueParser` (deterministic) + inline LLM resolution of residual ambiguity in `DialogueCoachAgent` (CHOSEN)

The Backend service uses `core/analysis/dialogue_parser.py` (established
by ADR-055 D3) to extract attributed utterances deterministically. Any
residual ambiguous speakers are resolved inline by the `DialogueCoachAgent`
in its single LLM call — exactly the ADR-055 pattern.

**Pros:**

- Reuses existing, tested infrastructure.
- Consistent with ANAL-008 and WRITE-010.
- No new cross-feature coupling (ANAL-005 Coreference stays decoupled).
- Single LLM call (cheap).

**Cons:**

- Some ambiguous speakers may be misattributed; the agent resolves them
  best-effort.

#### Option B — Couple ANAL-005 Coreference as a runtime pre-step

Run `coreference_service.resolve()` before the coach agent.

**Pros:** Higher attribution accuracy.

**Cons:**

- Doubles LLM cost/latency (two model calls per coach invocation).
- Creates a runtime cross-feature dependency rejected by ADR-055 D3.
- ANAL-005 is chapter-scoped; ASSIST-004 is selection-scoped — scope
  mismatch.

**Rejected.**

#### Option C — User must manually tag speakers

The UI requires the user to annotate which character speaks each line.

**Pros:** Perfect attribution.

**Cons:**

- Massive UX burden. Users will not do it.
- Defeats the purpose of an AI Coach.

**Rejected.**

### Decision

**Option A.** Reuse `DialogueParser`; resolve residual ambiguity inline
in `DialogueCoachAgent`. No new infrastructure, no new coupling.

### Rationale

This is a strict reuse of the ADR-055 D3 decision. ANAL-008 (profiling)
and WRITE-010 (checking) both use this pattern successfully. ASSIST-004
(dialogue coaching) is the third consumer; consistency wins.

### Sustainability check

1. **Correct in 3 months?** Yes — `DialogueParser` is reusable Core
   infrastructure; future dialogue features use the same pattern.
2. **Hard-to-undo coupling?** None — parser is already decoupled.
3. **Simplest correct solution?** Yes — no new code beyond consuming the
   existing parser.
4. **Design intent clear?** Yes — matches the established pattern.

---

## Decision 8 — One endpoint `/dialogue-coach` with `mode` parameter (Q-B1) — Option (a)

### Root cause

ASSIST-004 has two operation modes (analyze, improve). Should the API
expose one endpoint with a mode parameter or two endpoints?

### Options Considered

#### Option (a) — Single endpoint `POST /api/v1/ai-assist/dialogue-coach` with `mode: "analyze" | "improve"` in body (CHOSEN)

**Pros:**

- Mirrors the established `REWRITE` pattern (one endpoint, mode in body).
- Reduces API surface area.
- The underlying service is one resource (dialogue coaching); the two
  modes are variations of one operation.
- RULE-06: one resource = one endpoint.

**Cons:**

- Slightly weaker OpenAPI discoverability (the mode is a body field, not
  a path segment).

#### Option (b) — Two endpoints `/dialogue-coach/analyze` and `/dialogue-coach/improve`

**Pros:** Path-discoverable.

**Cons:**

- Artificial split — the service logic is 90% shared; only the output
  structure differs.
- Doubles API surface area.
- Doubles OpenAPI schema entries.
- Future modes (e.g., a conversational `coach` mode) would require a
  third endpoint.

**Rejected.**

### Decision

**Option (a).** Single endpoint with `mode` in body.

### Rationale

The two modes share: selection parsing, speaker attribution, adaptive
context assembly, prompt composition (one governed template), agent
invocation, SSE streaming, and FeedbackEvent emission. Only the output
shape (`alternatives` present in improve mode; absent in analyze mode)
and a small prompt branch differ. Splitting into two endpoints would
duplicate all of that.

---

## Decision 9 — Modify-tracking: simple before/after block, NOT char-level inline diff (Q-B5) — Option B

### Root cause

In improve mode, the coach proposes `DialogueAlternative`s. How should
the UI present and apply them?

### Options Considered

#### Option A — Char-level inline diff (compute minimal edit sequence)

Compute a char-level diff between `original_quote` and `rewrite`,
highlight insertions/deletions inline in TipTap.

**Pros:** Visually precise.

**Cons:**

- Requires a diff library (e.g., `diff-match-patch`) — new dependency
  unless vendored.
- Requires TipTap mark manipulation to render the diff — high complexity,
  risk of editor corruption.
- For dialogue rewrites (often full sentence replacements), char-level
  diffs are visually noisy (everything looks changed).
- Accept/application logic must translate the diff back into a text
  replacement, adding failure modes.

**Rejected** — too much complexity for marginal value.

#### Option B — Simple before/after block with visual highlight; apply by full-string replacement (CHOSEN)

Each `DialogueAlternative` renders as two stacked text blocks
(original → rewrite). Accept applies the rewrite by finding
`original_quote` in the chapter text and replacing it with `rewrite`
(string-level operation, no char-level diff).

**Pros:**

- TipTap integration is a simple text replacement (no marks, no diffs).
- Visually clear: user sees the full original and the full rewrite.
- No new dependency.
- Aligns with the existing WRITE-004 (Rewrite Selection) accept pattern.

**Cons:**

- Less visually flashy than char-level diff.

#### Option C — Side-by-side panels

Two columns: original on the left, rewrite on the right.

**Pros:** Compact comparison.

**Cons:**

- Requires more horizontal real estate; the dialogue coach panel is
  typically narrow (right sidebar).

**Rejected** for layout reasons.

### Decision

**Option B.** Stacked before/after blocks; accept applies by full-string
replacement. The `DialogueInlineDiff.tsx` component from the brainstorming
is renamed to `DialogueAlternativeCard.tsx` and renders the two blocks
with subtle background highlighting (red tint for original, green tint
for rewrite).

### Rationale

KISS. The rewrite is usually a full-sentence-or-paragraph replacement;
char-level diffs add complexity without clarity. The accept mechanism
becomes trivial (string find-and-replace), eliminating an entire class
of TipTap integration bugs.

### Sustainability check

1. **Correct in 3 months?** Yes — if users request char-level diff later,
   it is an additive enhancement to `DialogueAlternativeCard.tsx`, not an
   architectural change.
2. **Hard-to-undo coupling?** None — application logic is simple string
   replace.
3. **Simplest correct solution?** Yes.
4. **Design intent clear?** Yes — the component name documents the
   responsibility (alternative card, not diff view).

---

## Decision 10 — §7 Stub-Variable-Detector entry: YES — `dialogue_coach` is a new routeable surface (Q-B6)

### Root cause

ADR-046 §7 + ADR-037 require every new routeable prompt surface to
declare its variables in the prompt-surface manifest. `DIALOGUE_COACH`
with `context_mode = "dialogue_coach"` is a new routeable surface.

### Decision

**YES — register in the manifest.** This is not an architectural choice;
it is a governance requirement.

### Required registrations (detailed in Retrofit-Plan §1)

- `scripts/architecture/prompt-surface-manifest.yaml`: add
  `ai_assist/dialogue_coach` with `required_variables: []`,
  `optional_variables: [user_preferences, style_constraints,
  avoidance_patterns, character_voice_profiles, mode, characters,
  text_to_analyze]`, `fallback_policy: fail_loudly_if_bundled_missing`.
- `scripts/architecture/adoption-registry.yaml`: add `ai_assist/dialogue_coach`
  with `requires_runtime_evidence: true`.
- `core/prompts/route_table.py`: add `LLMIntent.DIALOGUE_COACH` to
  `INTENT_TO_CATEGORY`, `INTENT_TO_MODE`, `ROUTE_CONFIGS`; ensure it is
  NOT in `NON_ROUTEABLE_INTENTS`.
- `core/prompts/_bundled/ai_assist/en/dialogue_coach/system.md`: NEW
  governed EN template (9-section Mode-1 skeleton, ADR-054).

### New template variables

Two new template variables appear in the `dialogue_coach` template that
are not currently registered:

- `{{mode}}` — already registered in `SYSTEM_VARS` (`variable_registry.py:152`).
- `{{characters}}` — **NOT registered**; new variable.
- `{{text_to_analyze}}` — **NOT registered**; new variable.

Per RULE-22 §4, these MUST be registered before use:

- `characters` → `SYSTEM_VARS` (system-generated list of speaker names).
- `text_to_analyze` → `USER_CONTENT_VARS` (user-authored selection from
  the editor; must be wrapped in XML tags in the template per RULE-22 §6).

The Retrofit-Plan lists this registration explicitly.

---

## Decision 11 — Adaptive Snapshot: extend `invocation_evidence` with two nullable JSONB columns (Q-C3) — Option β

### Root cause

The "Recent Adaptive Activity" UI in the Adaptivity Dashboard needs to
show, per recent AI call, which adaptive signals were active and with
what weights. Two storage options.

### Options Considered

#### Option α — New table `adaptive_snapshots`

```sql
CREATE TABLE adaptive_snapshots (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    project_id UUID NOT NULL REFERENCES projects(id),
    invocation_id UUID REFERENCES invocation_evidence(id),
    intent VARCHAR(50) NOT NULL,
    source_summary JSONB NOT NULL,
    weights JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Pros:** Clean separation; queryable independently.

**Cons:**

- Schema overhead: a new table + repository + migration for what is
  metadata about an existing invocation_evidence row.
- Synchronisation risk: snapshot rows must be kept in sync with evidence
  rows.
- Duplicates the `user_id`/`project_id`/`intent`/`created_at` columns
  already on `invocation_evidence`.

**Rejected.**

#### Option β — Extend `invocation_evidence` with `adaptive_source_summary JSONB` and `adaptive_weights JSONB` nullable columns (CHOSEN)

Two nullable JSONB columns on the existing `invocation_evidence` table
(ADR-042/045). Populated only when the invocation consumed adaptive
signals; NULL otherwise.

**Pros:**

- Reuses existing infrastructure (evidence sink, evidence repository,
  evidence queries).
- Auto-correlates with the invocation evidence row — no sync risk.
- No new table, no new repository, no new migration framework.
- Semantically fits: "this invocation's adaptive state" is invocation-
  scoped metadata, exactly what `invocation_evidence` models.
- Querying for the dashboard: `SELECT * FROM invocation_evidence WHERE
  user_id = ? AND project_id = ? AND adaptive_source_summary IS NOT NULL
  ORDER BY created_at DESC LIMIT 20`.

**Cons:**

- Two nullable columns on a shared table.
- Adaptivity becomes coupled to the evidence table (but the coupling is
  semantically correct — adaptivity state IS invocation metadata).

### Decision

**Option β.** Extend `invocation_evidence` with two nullable JSONB
columns. Populated by the Backend `AdaptiveContextProvider` impl when it
is called during an invocation (correlated via `invocation_id`).

### Rationale

The "Recent Adaptive Activity" UI is fundamentally about *which AI calls
used adaptivity and how*. That is invocation-scoped data; it belongs
with the invocation evidence. A separate table would duplicate the
existing schema and add sync overhead for no benefit.

This mirrors the pattern ADR-042 established: invocation evidence
accumulates privacy-safe metadata about each AI call (`feature_id`,
`intent`, `prepared_context_fingerprint`, …). Adaptive state is one more
such metadata field.

### Sustainability check

1. **Correct in 3 months?** Yes — future "adaptive analytics" features
   query the same table.
2. **Hard-to-undo coupling?** None — two nullable columns; downgrade
   migration drops them.
3. **Simplest correct solution?** Yes — reuses existing infrastructure.
4. **Design intent clear?** Yes — the column names document the
   content.

---

## Decision 12 — `AdaptiveContextProvider` (Core) vs `AdaptiveContextService` (Backend): both needed (Q-C4)

See **Decision 3** for the full analysis. The Provider is the Core
Protocol consumed by the Core enricher; the Service is the Backend
public-API wrapper consumed by the dashboard. Both are needed; they
serve different consumers (invocation pipeline vs REST API).

---

## Decision 13 — Feature-ID `LEARN-002` stays; status becomes `in-progress` (Q-C1, Q-C2)

### User decisions honoured

- **Q-C1 (User: ✅):** Feature-ID `LEARN-002` stays. This is a
  recalibration, not a superseding. No new feature ID is allocated.
- **Q-C2 (Architecture Specialist):** Status value.

### Q-C2 — Is `status: recalibrated` a valid feature status?

**Analysis:**

The feature-status schema in `docs/features/INDEX.md` (lines 18-25, 295)
is:

```
✅ stable | 🔨 in-progress | 📋 planned | 💡 idea | ⛔ deprecated
```

There is **no** `recalibrated` status. Adding it would require:

- A schema change to `docs/features/INDEX.md`.
- Updates to any tool that parses the status field.
- Documentation of what "recalibrated" means semantically (is it
  planned? in-progress? a hybrid?).

**Root cause:** "Recalibrated" describes an *event* (the spec was
reinterpreted), not a *state*. The current state of LEARN-002 after
recalibration is "being implemented" — which maps cleanly to
`in-progress`.

### Decision

**Use `status: in-progress`.** Do not add a `recalibrated` enum value.

The recalibration is documented in:

1. A prominent **Changelog** section at the top of the LEARN-002 spec
   (verpflichtend per the brainstorming §7.5).
2. The "Status & History" section with the entry:
   `2026-07-19 — Recalibrated from statistical voice pipeline to
   Adaptivity Dashboard (ADR-069). Original concept (sentence-length
   distribution, few-shot prompting) is no longer pursued. New scope:
   visibility + steering + transparency of existing adaptive signals
   (PreferenceProfile + CharacterVoiceProfile).`
3. `docs/features/INDEX.md` "Last updated" footer.

### Rationale

- Existing schema covers the state.
- Avoids schema bloat (RULE-04/06 — don't add enum values when existing
  ones suffice).
- "Recalibration" is an event, not a state. The state is "being
  implemented."
- Future recalibrations follow the same pattern (set `in-progress`,
  document the recalibration in the changelog).

### Sustainability check

1. **Correct in 3 months?** Yes — every recalibration uses the same
   pattern.
2. **Hard-to-undo coupling?** None.
3. **Simplest correct solution?** Yes.
4. **Design intent clear?** Yes — the Changelog documents what changed
   and why.

---

## Decision 14 — Adaptivity indicator in editor toolbar (Q-D1, Q-D2) — Editor only for v1

### User decisions honoured

- **Q-D1 (User: ✅):** Yes, the adaptivity indicator goes in the editor
  toolbar. Visibility is part of the value proposition.

### Q-D2 — In all AI panels or only editor?

**Decision:** Editor only for v1.

**Rationale:**

- The editor is the primary writing surface — that is where adaptivity
  matters most visibly.
- Other AI panels (analysis, beta reader, voice check) are invoked
  occasionally; users can check the dashboard for adaptive state.
- Adding the indicator everywhere creates visual noise without
  proportional value.
- KISS — ship the high-value placement first; expand later if user
  feedback warrants.

The indicator has three states (active, paused, no-data) per the
brainstorming §8.3. A click opens the Adaptivity Dashboard (in Settings)
or a quick popover (Frontend-Specialist decides based on
`frontend-design` skill).

### Sustainability check

1. **Correct in 3 months?** Yes — adding the indicator to other panels
   is additive.
2. **Hard-to-undo coupling?** None.
3. **Simplest correct solution?** Yes.
4. **Design intent clear?** Yes — the indicator lives where writing
   happens.

---

## Decision 15 — TanStack Query cache invalidation for cross-component updates (Q-D3) — ADR-043-conform

### Root cause

When the user changes weights in the dashboard, all components showing
adaptive state must update. The brainstorming proposed TanStack Query
cache invalidation. Is this ADR-043-conform?

### Analysis

ADR-043 governs the **AI operation** primitive (`useAIOperation` hook)
— generation, extend, rewrite, etc. Adaptive settings CRUD is **not**
an AI operation; it is regular REST CRUD (toggle, update weights, get
context). TanStack Query cache invalidation is the standard React
Server State pattern for CRUD:

```typescript
// AdaptiveWeights mutation
const mutation = useMutation({
  mutationFn: (weights) => api.post('/adaptive/weights', weights),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['adaptive-context'] });
  },
});
```

All active components subscribed to `useQuery({ queryKey: ['adaptive-context'] })`
refetch automatically. This includes:

- `AdaptiveStatusIndicator` (editor toolbar).
- `AdaptiveDashboard` (settings).
- `AdaptiveSnapshotHistory` (settings).
- `DialogueCoachPanel` (refetches adaptive context for the next call).

### Decision

**YES, TanStack Query cache invalidation is conform.** ADR-043 is
silent on non-AI CRUD; this is standard React Server State practice.

The cache key `['adaptive-context']` is the canonical key; all adaptive
queries use it. Mutation invalidation propagates updates without
component-level event buses or global stores.

### Sustainability check

1. **Correct in 3 months?** Yes — TanStack Query is the server-state
   standard; this pattern is stable.
2. **Hard-to-undo coupling?** None — standard pattern.
3. **Simplest correct solution?** Yes — no event bus, no Zustand for
   server state.
4. **Design intent clear?** Yes — the cache key is the SSOT for
   adaptive state.

---

## Decision 16 — Dialogue Coach as a Tab in the Analysis Panel (Q-D4)

### User decision honoured

- **Q-D4 (User: Architect/Frontend-Specialist decides with
  `frontend-design` + `vercel-composition-patterns` skills):** My call
  as Architecture Specialist, in consultation with the Frontend-Specialist
  at implementation time.

### Options Considered

#### Option A — Tab in the Analysis Panel (CHOSEN)

Dialogue Coach is a tab alongside Beta Reader, Voice Check, Character
Voice, etc., in the existing `AnalysisPanel` component family.

**Pros:**

- Consistency with established analysis layout (ANAL-001 beta reader,
  ANAL-008 character voice, WRITE-010 voice check).
- Reuses existing panel infrastructure (collapsible, resizable).
- Fits the editor's right-sidebar model.
- Cohesive with siblings (RULE-06 — analysis-adjacent features live
  together).
- The "improve" mode's Accept/Reject UI fits within the tab.

**Cons:**

- Less screen real estate than a standalone panel.

#### Option B — Standalone right-side panel

A dedicated panel separate from the Analysis Panel.

**Pros:**

- More screen real estate.

**Cons:**

- Inconsistent with the established analysis panel pattern.
- Forces a new layout slot in the editor.
- The "more space" benefit is marginal — the Accept/Reject UI is
  compact.
- Violates the cohesion of analysis-adjacent features.

**Rejected.**

### Decision

**Option A.** Dialogue Coach is a tab in the Analysis Panel.

### Rationale

ASSIST-004 is conceptually adjacent to analysis (it analyses dialogue)
even though it can also propose improvements. The existing
`AnalysisPanel` already hosts features with mixed output shapes (Beta
Reader = text report; Voice Check = score + flags; Character Voice =
profile cards). Dialogue Coach (issues + alternatives) fits this
pattern.

The `frontend-design` skill will be used at implementation time to
design the tab content; `vercel-composition-patterns` will guide the
component composition (avoiding boolean-prop proliferation in the panel
container). `web-design-guidelines` will validate accessibility (ARIA,
keyboard nav, reduced motion).

### Sustainability check

1. **Correct in 3 months?** Yes — future ASSIST features (Plot Check,
   Title Suggest) follow the same pattern.
2. **Hard-to-undo coupling?** None — promoting to a standalone panel
   later is possible if user feedback warrants.
3. **Simplest correct solution?** Yes — reuses established
   infrastructure.
4. **Design intent clear?** Yes — the tab placement matches the
   analysis-adjacent identity.

---

## Decision 17 — `DialogueCoachService` exposes both `run()` and `stream()` per RULE-13 / ADR-065

### Root cause

The brainstorming spec shows only `run_stream()` on the service. RULE-13
(per ADR-065) requires two named methods (`run()` non-streaming +
`stream()` streaming) sharing one provider/model-settings path, so MCP
and A2A clients can call `run()` against the same service that SSE
clients call via `stream()`.

### Decision

`DialogueCoachServiceProtocol` exposes BOTH:

```python
class DialogueCoachServiceProtocol(Protocol):
    async def run(self, request: DialogueCoachRequest) -> DialogueCoachResponse:
        """Non-streaming: returns the full coach result. For MCP/A2A clients."""

    async def stream(self, request: DialogueCoachRequest) -> AsyncIterator[bytes]:
        """Streaming: yields SSE events. For WebUI."""
```

Both share the same agent, the same prompt composition, the same model
resolution. The SSE endpoint (`POST /api/v1/ai-assist/dialogue-coach`)
calls `stream()`; future MCP/A2A adapters call `run()`.

### Rationale

This is a direct application of ADR-065. Two methods give precise return
types; no union return; MCP/A2A interoperability from day one.

### Sustainability check

1. **Correct in 3 months?** Yes — when the MCP adapter lands, it calls
   `run()` without service changes.
2. **Hard-to-undo coupling?** None.
3. **Simplest correct solution?** Yes — ADR-065 is the standard.
4. **Design intent clear?** Yes — two methods, one service, two
   transport shapes.

---

## Consequences

### Positive

- **Adaptivity becomes visible and controllable.** Four registered-but-
  empty variables (`user_preferences`, `style_constraints`,
  `avoidance_patterns`, `character_voice_profiles`) are now fed by a
  single coherent provider. Users see which signals shape AI output and
  can adjust influence weights.
- **LEARN-002 gets a realistic scope.** The unrealistic statistical
  pipeline (sentence-length distribution, few-shot prompting) is
  replaced by a dashboard that visualises existing data. The feature
  becomes implementable in 1–2 sessions instead of 5+.
- **ASSIST-004 becomes the pilot consumer.** The Dialogue Coach is the
  first feature that *visibly* uses both `PreferenceProfile` (LEARN-001)
  and `CharacterVoiceProfile` (ANAL-008) in one operation. This closes
  the feedback loop: accept/reject → PreferenceProfile → next coach
  call.
- **Voice boundary preserved.** `voice_metrics` (ADR-057) stay
  checking-path only; Dialogue Coach uses only the descriptive
  `speech_summary`. The ADR-055/057 boundary is universal.
- **Single source of truth for adaptive enrichment.**
  `PreferenceContextEnricherImpl` (single-variable) is replaced by
  `AdaptiveContextEnricher` (four-variable). No parallel enrichers, no
  drift risk.
- **Provider pattern extended.** `AdaptiveContextProvider` mirrors the
  proven ADR-067 `KBContextProvider` pattern — Core Protocol, Backend
  impl, composes existing providers.
- **MCP/A2A-ready from day one.** `DialogueCoachService.run()` +
  `stream()` (ADR-065) means future adapters call `run()` without
  service changes.
- **RULE-18b proven by Eval.** The Pydantic Eval suite proves that
  changing `voice_fidelity` weight from 1.0 → 0.1 measurably changes
  the coach's output. This is the configuration-effect-integrity
  evidence RULE-18b requires.

### Negative / Tradeoffs

- **Breaking change to ADR-038 enricher wiring.**
  `PreferenceContextEnricherImpl` is removed; the DI sites and tests
  that reference it must be rewired. Mitigated: the new
  `AdaptiveContextEnricher` is a strict functional superset (it writes
  `user_preferences` plus the three additional variables), so behavior
  is preserved for existing features.
- **Two new Backend domains.** `apps/api/narrare/ai_assist/` and
  `apps/api/narrare/adaptive/` add operational surface area. Each
  follows the established domain-module pattern (contracts, schemas,
  service, router, dependencies), so the cost is bounded.
- **New prompt category `ai_assist/`.** Adds one directory to
  `_bundled/`; manifest and adoption registry gain entries. Future
  ASSIST features reuse the category.
- **Two Alembic migrations.** (1) `ProjectSettings.adaptive_settings`
  JSONB column; (2) `invocation_evidence.adaptive_source_summary` +
  `adaptive_weights` JSONB columns. Both are additive + nullable +
  backward-compatible.
- **Existing prompts will see non-empty `style_constraints` and
  `avoidance_patterns` for the first time.** Templates that reference
  these variables will render derived content where they previously
  rendered empty strings. This is the *intended* effect of the ADR but
  is a behavioral change. Mitigated: the enricher self-gates via
  `AdaptiveSettings.enabled` AND `AdaptiveContext.has_any_signal`; users
  with no preferences and no voice profiles see no change.
- **Three new i18n namespaces × three locales = nine JSON files.**
  Standard RULE-16 cost.
- **New template variables registered.** `{{characters}}` (SYSTEM_VARS)
  and `{{text_to_analyze}}` (USER_CONTENT_VARS). The latter requires
  XML-tag wrapping in the template per RULE-22 §6.

### Constraints introduced

- `AdaptiveContextEnricher` is the **single canonical writer** of the
  four adaptive prompt variables. Services that need to override must
  do so explicitly post-enrichment (and document why).
- `voice_metrics` MUST NOT appear in any `AdaptiveContext` field,
  `DialogueCoachDeps` field, or `dialogue_coach` governed template
  (preserves ADR-055/057 boundary).
- `AdaptiveSettings` lives at project level (`ProjectSettings` JSONB);
  future user-level "global toggle" requires a separate column.
- `AdaptiveContextProvider` is the only Core-Protocol surface the
  `AdaptiveContextEnricher` may consume for adaptive data (RULE-22
  coherence).
- The `dialogue_coach` governed template MUST be Mode 1
  (PromptComposer-driven); no inline f-string feature prompt.
- `DialogueCoachService` MUST expose both `run()` and `stream()`; the
  SSE endpoint calls `stream()`.

---

## CR-04 Cross-Feature Impact (coherence)

This ADR is a cross-feature contract change: it consumes data from
LEARN-001, ANAL-008, and WRITE-010, and feeds variables that every
writing/analysis/planning/chat prompt template already references.
Per RULE-22, the integration contracts are documented here.

### Integration Contract: ASSIST-004 ↔ LEARN-001 (PreferenceProfile)

**Shared data source:** `PreferenceProfile` (per `user_id` + `project_id`).

**Data direction:** ASSIST-004 reads ← LEARN-001 writes.

**On data change** (LEARN-001 adds/removes a preference via feedback):

- ASSIST-004 sees the update on its **next** invocation (no cache; the
  `AdaptiveContextProvider` calls `PreferenceProvider.get_preferences()`
  fresh per call).
- In-flight invocations are NOT retroactively updated.
- The dashboard's "Recent Adaptive Activity" reflects the state at
  invocation time (snapshot in `invocation_evidence`).

**On data deletion** (user resets preferences):

- `AdaptiveContext.has_any_signal` returns False for the preference
  component.
- The enricher skips injection (graceful).
- Past snapshots retain their `source_summary` (audit trail; deletion
  does not rewrite history).

**Expected schema:** `PreferenceProfile` from
`narrare_core.memory.models` (LEARN-001 SSOT).

### Integration Contract: ASSIST-004 ↔ ANAL-008 (CharacterVoiceProfile)

**Shared data source:** `CharacterVoiceProfile` (per character).

**Data direction:** ASSIST-004 reads ← ANAL-008 writes (via KB entity
`metadata["speech"]["voice_analysis"]`).

**On data change** (ANAL-008 re-profiles a character):

- ASSIST-004 sees the update on its next invocation (the
  `AdaptiveContextProvider` calls `ProfileProvider.get_profile()` fresh
  per call).
- Stale profiles (>7 days, per `profiles/_freshness.py::is_stale()`)
  are surfaced with `is_fresh=False`; the dashboard shows a ⚠ marker.

**On data deletion** (character deleted from KB):

- `ProfileProvider.get_profile()` returns a profile without that
  character.
- ASSIST-004 dialogue lines attributed to the deleted character are
  surfaced as `voice_mismatch` issues with `speaker=<deleted>` or
  skipped (Edge Case E5).

**Expected schema:** `CharacterVoiceProfile` from
`narrare_core.profiles.models` (ADR-040 SSOT). Only the descriptive
fields (`speech_summary`); `voice_metrics` is NOT consumed.

### Integration Contract: LEARN-002 (Dashboard) ↔ ASSIST-004

**Shared data source:** `invocation_evidence.adaptive_source_summary`
+ `adaptive_weights` (per `invocation_id`).

**Data direction:** LEARN-002 reads ← ASSIST-004 writes (via the
Backend adaptive-context provider, correlated through `invocation_id`).

**On data change** (new ASSIST-004 call):

- LEARN-002 dashboard "Recent Adaptive Activity" list updates on next
  refetch (TanStack Query, 60-second stale time + refetchOnWindowFocus).

**On invocation deletion** (none currently; evidence is append-only):

- N/A.

**Expected schema:** `invocation_evidence` rows with non-null
`adaptive_source_summary` (this ADR's migration adds the columns).

### Cross-feature context precedence (per RULE-22 §7)

When adaptive signals conflict (e.g., a user preference contradicts a
character voice profile), the following precedence applies (highest →
lowest):

1. Current author instruction (selection, mode, runtime override).
2. Explicit project writing profile / manual override (settings).
3. Current scene/storyboard/timeline plan.
4. Curated KB (CharacterVoiceProfile).
5. Learned memory/mem0 preferences (PreferenceProfile).
6. Generated suggestions / derived constraints (this ADR's derivation).

High-impact conflicts (e.g., user preference says "use simple vocabulary"
but character voice is "complex vocabulary") are surfaced in the
`DialogueCoachOutput.adaptive_summary` text and logged at INFO level,
not silently resolved.

---

## Retrofit-Plan (mandatory — prompt-mechanics + cross-feature change, per adr-process.md §D.4)

This ADR introduces a new routeable intent
(`LLMIntent.DIALOGUE_COACH`), a new prompt category (`ai_assist`), a new
`context_mode` (`dialogue_coach`), new registered template variables,
and a breaking change to the enricher wiring. Retrofit-Plan:

### 1. Inventory of affected paths

**Core — data models + contracts:**

- `packages/core/narrare_core/ai_invocation/adaptive_context.py` — NEW:
  `AdaptiveWeights`, `AdaptiveContext`, `AdaptiveSettings` dataclasses.
- `packages/core/narrare_core/ai_invocation/contracts.py` — ADD:
  `AdaptiveContextProvider` Protocol.
- `packages/core/narrare_core/ai_invocation/enrichers/adaptive.py` — NEW:
  `AdaptiveContextEnricher` (replaces `PreferenceContextEnricherImpl`).
- `packages/core/narrare_core/ai_invocation/enrichers/preferences.py` —
  DELETE: `PreferenceContextEnricherImpl` (after migration cutover).
- `packages/core/narrare_core/ai_invocation/enrichers/__init__.py` —
  UPDATE: export `AdaptiveContextEnricher`, remove
  `PreferenceContextEnricherImpl`.
- `packages/core/narrare_core/agents/dialogue_coach_agent.py` — NEW:
  `DialogueCoachAgent` (NarrareAgent subclass).
- `packages/core/narrare_core/agents/dialogue_coach_types.py` — NEW:
  `DialogueCoachDeps`, `DialogueCoachOutput`, `DialogueIssue`,
  `DialogueAlternative`, `DialogueIssueType`, `DialogueSeverity`.
- `packages/core/narrare_core/agents/__init__.py` — EXPORT
  `DialogueCoachAgent`.

**Core — prompt system:**

- `packages/core/narrare_core/llm/intents/_enums.py` — ADD
  `DIALOGUE_COACH = "dialogue_coach"` member to `LLMIntent`.
- `packages/core/narrare_core/llm/intents/_docs_*.py` — ADD doc entry
  for `DIALOGUE_COACH` (Scope/Input/Output/NOT).
- `packages/core/narrare_core/prompts/route_table.py` — ADD
  `LLMIntent.DIALOGUE_COACH: "ai_assist"` to `INTENT_TO_CATEGORY`,
  `LLMIntent.DIALOGUE_COACH: "dialogue_coach"` to `INTENT_TO_MODE`, and
  a new `ROUTE_CONFIGS` entry
  (`PromptRouteConfig("ai_assist", "dialogue_coach", optional_variables=…)`);
  do NOT add to `NON_ROUTEABLE_INTENTS`.
- `packages/core/narrare_core/prompts/_bundled/ai_assist/en/dialogue_coach/system.md`
  — NEW governed EN template (9-section Mode-1 skeleton, ADR-054).
- `packages/core/narrare_core/prompts/variable_registry.py` — ADD
  `"characters"` to `SYSTEM_VARS`; ADD `"text_to_analyze"` to
  `USER_CONTENT_VARS`.

**Backend — adaptive domain:**

- `apps/api/narrare/adaptive/__init__.py` — NEW.
- `apps/api/narrare/adaptive/contracts.py` — NEW:
  `AdaptiveContextServiceProtocol`.
- `apps/api/narrare/adaptive/schemas.py` — NEW:
  `AdaptiveContextResponse`, `AdaptiveSettingsResponse`,
  `AdaptiveWeightsInput`, `AdaptiveWeightsResponse`,
  `AdaptiveSourceSummary`.
- `apps/api/narrare/adaptive/service.py` — NEW:
  `AdaptiveContextService` (implements Protocol; consumes
  `AdaptiveContextProvider` + project settings repo).
- `apps/api/narrare/adaptive/repository.py` — NEW or extend
  `settings/project_ai_settings_repository.py`: load/save
  `adaptive_settings` JSONB.
- `apps/api/narrare/adaptive/router.py` — NEW: 3 endpoints
  (`GET /adaptive/context`, `POST /adaptive/toggle`,
  `POST /adaptive/weights`).
- `apps/api/narrare/adaptive/dependencies.py` — NEW: DI factories
  (`get_adaptive_context_service`, `get_adaptive_context_provider`).
- `apps/api/narrare/adaptive/adaptive_context_provider.py` — NEW:
  `AdaptiveContextProviderImpl` (implements Core Protocol; composes
  `PreferenceProvider` + `ProfileProvider` + settings repo +
  `invocation_evidence` snapshot writes).
- `apps/api/narrare/_app/main.py` — REGISTER adaptive router.

**Backend — ai_assist domain:**

- `apps/api/narrare/ai_assist/__init__.py` — NEW.
- `apps/api/narrare/ai_assist/contracts.py` — NEW:
  `DialogueCoachServiceProtocol` (with both `run()` and `stream()`
  per Decision 17).
- `apps/api/narrare/ai_assist/schemas.py` — NEW: `DialogueCoachRequest`,
  `DialogueCoachResponse`, `DialogueCoachStreamEvent`.
- `apps/api/narrare/ai_assist/service.py` — NEW:
  `DialogueCoachService` (Mode-1 PromptComposer, DialogueParser reuse,
  DialogueCoachAgent invocation).
- `apps/api/narrare/ai_assist/router.py` — NEW:
  `POST /api/v1/ai-assist/dialogue-coach` (SSE) calling `stream()`.
- `apps/api/narrare/ai_assist/dependencies.py` — NEW: DI factories.
- `apps/api/narrare/ai_assist/_agent_runner.py` — NEW: agent invocation
  helper (RULE-04 split).
- `apps/api/narrare/ai_assist/_prompt.py` — NEW: PromptComposer call
  helper (RULE-04 split).
- `apps/api/narrare/ai_assist/_speaker_attribution.py` — NEW:
  `DialogueParser` wrapper for selection-scoped attribution.
- `apps/api/narrare/ai_assist/_runtime_content.py` — NEW:
  AdaptiveContext → template variables mapping.
- `apps/api/narrare/ai_assist/_results.py` — NEW: agent output → API
  response mapping.
- `apps/api/narrare/_app/main.py` — REGISTER ai_assist router.

**Backend — DI rewiring:**

- `apps/api/narrare/_app/dependencies_prompts.py` — REPLACE
  `PreferenceContextEnricherImpl` wiring with `AdaptiveContextEnricher`
  wiring. For services where adaptivity does not apply (KB, generation,
  embed), do NOT wire the enricher.

**Backend — models + migrations:**

- `apps/api/narrare/settings/models.py` — ADD
  `adaptive_settings: Mapped[dict | None] = mapped_column(JSONB,
  nullable=True)` to `ProjectSettings`.
- `apps/api/alembic/versions/NNNN_add_adaptive_settings.py` — NEW
  migration: add column.
- `apps/api/narrare/evidence/models.py` (or equivalent) — ADD
  `adaptive_source_summary: Mapped[dict | None]` and
  `adaptive_weights: Mapped[dict | None]` to the `invocation_evidence`
  model.
- `apps/api/alembic/versions/NNNN_add_adaptive_evidence_columns.py` —
  NEW migration: add columns.

**Frontend:**

- `packages/web/types/dialogue-coach.ts` — NEW (RULE-17: matches
  backend Pydantic schema field-by-field).
- `packages/web/types/adaptive.ts` — NEW.
- `packages/web/lib/api/dialogue-coach.ts` — NEW: SSE client.
- `packages/web/lib/api/adaptive.ts` — NEW: REST client.
- `packages/web/hooks/dialogue-coach/useDialogueCoach.ts` — NEW (uses
  `useAIOperation` per ADR-043).
- `packages/web/hooks/dialogue-coach/useDialogueCoachAccept.ts` — NEW.
- `packages/web/hooks/adaptive/useAdaptiveContext.ts` — NEW (TanStack
  Query, key `['adaptive-context']`).
- `packages/web/components/analysis/dialogue-coach/*` — NEW:
  `DialogueCoachPanel.tsx`, `DialogueModeSelector.tsx`,
  `DialogueIssueList.tsx`, `DialogueIssueCard.tsx`,
  `DialogueAlternativeList.tsx`, `DialogueAlternativeCard.tsx` (was
  `DialogueInlineDiff` per Decision 9), `DialogueCoachProgress.tsx`,
  `DialogueCoachEmptyState.tsx`, `__tests__/`.
- `packages/web/components/studio/settings/*` — NEW:
  `AdaptiveDashboard.tsx`, `AdaptiveToggle.tsx`,
  `AdaptiveWeightSlider.tsx`, `AdaptiveWeightControls.tsx`,
  `AdaptiveSourceList.tsx`, `AdaptiveSnapshotHistory.tsx`,
  `__tests__/`.
- `packages/web/components/studio/editor/AdaptiveStatusIndicator.tsx`
  — NEW + `__tests__/`.
- `packages/web/lib/i18n/request.ts` — ADD namespaces
  `"studio.dialogueCoach"`, `"settings.adaptive"`,
  `"editor.adaptiveIndicator"`.
- `packages/i18n/messages/{en,de,fr}/studio.dialogueCoach.json` — NEW
  (3 files).
- `packages/i18n/messages/{en,de,fr}/settings.adaptive.json` — NEW (3
  files).
- `packages/i18n/messages/{en,de,fr}/editor.adaptiveIndicator.json` —
  NEW (3 files).

**Evals:**

- `evals/dialogue_coach/test_analyze_basic.py` — NEW.
- `evals/dialogue_coach/test_improve_basic.py` — NEW.
- `evals/dialogue_coach/test_voice_fidelity_weight_effect.py` — NEW
  (RULE-18b evidence).
- `evals/dialogue_coach/test_preferences_respected.py` — NEW.
- `evals/adaptive_context/test_with_and_without_preferences.py` — NEW.

**Governance artefacts:**

- `scripts/architecture/prompt-surface-manifest.yaml` — ADD
  `ai_assist/dialogue_coach` entry.
- `scripts/architecture/adoption-registry.yaml` — ADD
  `ai_assist/dialogue_coach: true` +
  `features.ai_assist.modes.dialogue_coach: {requires_runtime_evidence: true}`.

**Documentation:**

- `docs/features/learning/LEARN-002-style-adaptation.md` — RECALIBRATE
  (title, frontmatter, all sections, Changelog entry).
- `docs/features/ai_assist/ASSIST-004-dialogue-coach.md` — DETAIL
  (implementation paths, technical section).
- `docs/architecture/decisions/INDEX.md` — ADD ADR-069 row.
- `docs/features/INDEX.md` — UPDATE LEARN-002 status → `in-progress`;
  ASSIST-004 status → `in-progress`.

### 2. Migration steps per path (atomic, independently testable)

**Phase 1 — Core data models + Protocol (no behavior change):**

1. Add `AdaptiveWeights`, `AdaptiveContext`, `AdaptiveSettings`
   dataclasses to `ai_invocation/adaptive_context.py` (pure; unit-test
   clamping, defaults, `has_any_signal`).
2. Add `AdaptiveContextProvider` Protocol to
   `ai_invocation/contracts.py` (no impl yet; Protocol-only).
3. Add `LLMIntent.DIALOGUE_COACH` enum member + docs entry.
4. Register `characters` + `text_to_analyze` template variables.

**Phase 2 — Enricher swap (breaking change to enricher wiring):**

5. Implement `AdaptiveContextEnricher` in
   `ai_invocation/enrichers/adaptive.py` (Core; consumes the Protocol;
   writes all four variables).
6. Implement Backend `AdaptiveContextProviderImpl` in
   `apps/api/narrare/adaptive/adaptive_context_provider.py` (composes
   PreferenceProvider + ProfileProvider + settings repo + evidence
   snapshot writes).
7. Rewire `apps/api/narrare/_app/dependencies_prompts.py`: replace
   `PreferenceContextEnricherImpl` with `AdaptiveContextEnricher` for
   writing/analysis/planning/chat services. Do NOT wire for KB/
   generation/embed.
8. Run existing enricher tests — they must still pass (the new enricher
   is a functional superset for `user_preferences`).
9. Add new tests for the three additional variables.
10. Delete `PreferenceContextEnricherImpl` (Phase 2 cleanup commit).

**Phase 3 — Backend adaptive domain:**

11. Add `ProjectSettings.adaptive_settings` JSONB column + Alembic
    migration + schema regression test (RULE-14).
12. Add `invocation_evidence.adaptive_source_summary` +
    `adaptive_weights` JSONB columns + Alembic migration + regression
    test.
13. Implement `AdaptiveContextService` + 3 REST endpoints + DI.
14. Integration tests for the 3 endpoints (401/422/200 paths).

**Phase 4 — Backend ai_assist domain:**

15. Create governed EN template
    `_bundled/ai_assist/en/dialogue_coach/system.md` (9-section Mode-1
    skeleton).
16. Register in `prompt-surface-manifest.yaml` +
    `adoption-registry.yaml`.
17. Add route_table entry for `DIALOGUE_COACH`.
18. Implement `DialogueCoachAgent` (Core) + types.
19. Implement `DialogueCoachService` (Backend, both `run()` and
    `stream()` per Decision 17) + SSE router + DI.
20. Integration tests (SSE flow; TestModel for structured output).

**Phase 5 — Frontend:**

21. TS types (RULE-17 field-by-field match).
22. API clients (SSE for dialogue coach; REST for adaptive).
23. Hooks (useDialogueCoach via useAIOperation; useAdaptiveContext via
    TanStack Query).
24. Dialogue Coach components (panel, mode selector, issue list,
    alternative cards).
25. Adaptive Dashboard components (toggle, weight sliders, source list,
    snapshot history).
26. Adaptive Status Indicator (editor toolbar).
27. i18n: 3 namespaces × 3 locales = 9 JSON files; register in
    `request.ts` (RULE-16).
28. Vitest unit tests; axe-core a11y tests; Playwright VRT screenshots
    (ADR-059).

**Phase 6 — Evals + Docs:**

29. Pydantic Eval suite (RULE-18b evidence for weight changes).
30. Recalibrate LEARN-002 spec; detail ASSIST-004 spec.
31. Update `docs/architecture/decisions/INDEX.md`;
    `docs/features/INDEX.md`.
32. CHANGELOG entry.

### 3. Breaking-change assessment

- **Enricher swap:** Existing services that depend on `user_preferences`
  being populated by the enricher continue to work (the new enricher is
  a superset). Tests that mock `PreferenceContextEnricherImpl` directly
  need to mock `AdaptiveContextEnricher` instead — mechanical change.
- **New prompt variables `characters` and `text_to_analyze`:** Additive
  to the registry; no existing template references them yet. The
  `dialogue_coach` template (new) references them; no regression.
- **New JSONB columns:** Additive + nullable. Existing rows deserialize
  with `None` defaults. No data migration.
- **`LLMIntent.DIALOGUE_COACH`:** Additive enum member. No existing
  caller routes it yet.
- **`style_constraints` + `avoidance_patterns` become non-empty:** This
  is the *intended* behavior change. Templates that reference these
  variables will render derived content where they previously rendered
  empty strings. Self-gated by `AdaptiveSettings.enabled` AND
  `has_any_signal`; users with no preferences and no voices see no
  change.
- **`PreferenceContextEnricherImpl` deletion:** After Phase 2 step 10,
  any out-of-tree caller referencing it directly breaks. The Core
  `ContextEnricher` and `PreferenceContextEnricher` Protocols stay; only
  the impl class is removed.

### 4. Checker update plan

- `scripts/architecture/_checkers/_check_prompt_orphan.py` — verify the
  new `dialogue_coach` template is reachable (DIALOGUE_COACH routeable);
  no orphan exemption needed.
- `prompt-surface-manifest` checker (ADR-037) — `ai_assist/dialogue_coach`
  must be declared; the manifest INTENT-COMPLETENESS gate recognises it.
- `_check_inline_feature_prompt.py` (ADR-054) — verify the dialogue
  coach service uses Mode 1 (PromptComposer), not inline f-string.
- Prompt-Path-Compliance test (ADR-046 §D.1) — assert DIALOGUE_COACH
  resolves through PromptComposer Mode 1 to
  `_bundled/ai_assist/en/dialogue_coach/system.md` (no inline fallback).
- ADR-056 commit gate — `dialogue_coach` runtime evidence (agent +
  service probes) required to move off governed adoption debt.
- `check_empty_kb_vars.py` analog — verify `style_constraints` and
  `avoidance_patterns` are non-empty in templates that declare them
  when an adaptive context is present (regression test for the
  "slots-fed-not-stubbed" guarantee).
- i18n-namespace-registry test (RULE-16) — verify the 3 new namespaces
  are registered and present in all 3 locales.

### 5. Test update plan

**Core:**

- `tests/unit/core/ai_invocation/test_adaptive_context.py` — dataclass
  tests (clamping, defaults, `has_any_signal`).
- `tests/unit/core/ai_invocation/test_adaptive_enricher.py` — enricher
  tests (no provider, missing IDs, provider failed, disabled, no
  signals, success path; verify all four variables written).
- `tests/unit/core/ai_invocation/test_adaptive_provider_protocol.py` —
  Protocol conformance with a Fake.
- `tests/unit/core/agents/test_dialogue_coach_agent.py` — TestModel
  structured-output tests (ADR-035).
- Existing preference enricher tests rewired to mock
  `AdaptiveContextEnricher`.

**Backend:**

- `tests/unit/api/adaptive/test_service.py` — service unit tests with
  fakes.
- `tests/unit/api/adaptive/test_provider_impl.py` — Backend
  `AdaptiveContextProviderImpl` with faked PreferenceProvider +
  ProfileProvider + settings repo.
- `tests/integration/adaptive/test_endpoints.py` — REST endpoint tests
  (401/422/200; rule-19 SessionDep enforcement).
- `tests/unit/api/ai_assist/test_dialogue_coach_service.py` — service
  unit tests (both `run()` and `stream()`).
- `tests/integration/ai_assist/test_dialogue_coach_sse.py` — SSE flow
  with TestModel.
- `tests/integration/test_adaptive_effect.py` — the
  `test_adaptive_context_changes_prompt_variables` and
  `test_adaptive_disabled_skips_enrichment` tests from brainstorming
  §9.2.
- Alembic migration round-trip tests for both schema changes.

**Frontend:**

- Vitest unit tests for every component (states: empty/loading/error/
  loaded).
- axe-core a11y tests (keyboard nav, ARIA, contrast).
- Playwright VRT screenshots for `AdaptiveStatusIndicator` (3 states)
  and `AdaptiveDashboard`.

**Evals (RULE-18b evidence):**

- `evals/dialogue_coach/test_voice_fidelity_weight_effect.py` — the
  critical test: changing `voice_fidelity` weight from 1.0 → 0.1
  measurably changes the count of `voice_mismatch` issues detected.

---

## Risks Surfaced for Coordinator/User Decision (before implementation)

These are NOT blockers for approving this ADR (they are downstream or
cross-feature), but the coordinator/user should be aware before planning
implementation:

1. **Enricher-swap migration risk.** Replacing
   `PreferenceContextEnricherImpl` is the single highest-risk change in
   this ADR. Mitigation: Phase 2 runs both enrichers side-by-side first
   (only `AdaptiveContextEnricher` wired, but tests assert the four
   variables match expected values); cutover commit is isolated and
   revertible.

2. **Behavioral change for existing prompts.** Templates that reference
   `{{style_constraints}}` or `{{avoidance_patterns}}` will render
   derived content where they previously rendered empty strings.
   Mitigation: self-gating via `AdaptiveSettings.enabled` AND
   `has_any_signal`; users with no adaptive signals see no change. The
   CHANGELOG documents the behavioral shift explicitly.

3. **Derived constraints/avoidance logic is heuristic.** The
   `AdaptiveContextProviderImpl` must derive `style_constraints_text`
   and `avoidance_patterns_text` from `PreferenceProfile` data. The
   exact derivation rules (e.g., "if user has rejected >50% of passive-
   voice suggestions, add 'avoid passive voice' to avoidance_patterns")
   are implementation details, not architectural decisions. The Core
   specialist tunes them via Eval at implementation time.

4. **`AdaptiveContextProviderImpl` snapshot writes couple to evidence
   sink.** Writing `adaptive_source_summary` to `invocation_evidence`
   during every adaptive invocation adds DB writes. Mitigation: the
   writes are bounded (one row per invocation), privacy-safe (JSON
   metadata only), and aligned with ADR-045's existing evidence
   pipeline.

5. **Three new i18n namespaces × three locales = nine JSON files.**
   Translation effort (en is canonical; de + fr follow the existing
   translation pattern). Mitigation: the Docs specialist coordinates
   translations; English-only is NEVER acceptable per RULE-16 (the
   frontend would render raw keys).

6. **Adoption debt for `dialogue_coach`.** The new routeable surface
   starts as governed adoption debt per ADR-056. Mitigation: runtime
   evidence probes land in Phase 4; the debt is paid before merge.

No decision requires a user call before implementation beyond approving
this ADR + the spec rewrites.

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-02/02a/02b | ✅ | `dialogue_coach` prompt = PromptComposer Mode 1 (intent + `dialogue_coach` context_mode + governed EN template); no inline f-string, no production fallback, no system-prompt-in-user-channel. Adaptive variables flow as `dynamic_inputs` (category 3 runtime data). |
| RULE-03 | ✅ | Contracts (`AdaptiveContextProvider`, `AdaptiveContextServiceProtocol`, `DialogueCoachServiceProtocol`, `DialogueCoachAgent` output types) defined before implementation. |
| RULE-04 | ✅ | Modularised: data models in `adaptive_context.py`; enricher in `enrichers/adaptive.py`; agent in `dialogue_coach_agent.py` + `_types.py`; Backend split per domain (`contracts.py` / `schemas.py` / `service.py` / `router.py` / `dependencies.py` + RULE-04 helpers `_agent_runner.py`, `_prompt.py`, `_results.py`, `_runtime_content.py`, `_speaker_attribution.py`). |
| RULE-05/06 | ✅ | Core owns contracts + data models + enricher + agent; Backend owns providers/services/routers; one responsibility per file. The `AdaptiveContextEnricher` name documents its responsibility (replacing the misleadingly-narrow `PreferenceContextEnricherImpl`). |
| RULE-07 | ✅ | `core → apps` direction only; Core Protocol consumed by Core enricher; Backend impl handles I/O; no `apps/`→`core` cycles; `ai_invocation → profiles → kb.schemas` read-direction only (reuses the ADR-057 verified acyclic path). |
| RULE-08 | ✅ | mem0 stays behind `PreferenceProvider`; `AdaptiveContextProvider` Backend impl composes providers, never touches mem0/SQL directly. |
| RULE-09 | ✅ | All new Protocols, dataclasses, services carry full type annotations. No `Any` in public signatures. |
| RULE-10 | ✅ | Testing strategy defined per layer (Core unit ≥95%, Backend unit ≥90%, integration ≥85%, Frontend unit ≥85%, Eval smoke). |
| RULE-11 | ✅ | Missing preferences / missing voice profiles / disabled adaptivity → graceful "no signals" result; `AdaptiveContext.has_any_signal` gates injection; provider failures log warnings and return context unchanged (mirrors ADR-038 D7). |
| RULE-12 | ✅ | Service Layer is the only public API: `AdaptiveContextService` + `DialogueCoachService` are reachable from WebUI / future MCP / future A2A / future CLI without service changes. |
| RULE-13 | ✅ | `DialogueCoachService.run()` (non-streaming `DialogueCoachResponse`) + `stream()` (`AsyncIterator[bytes]` SSE) per ADR-065; share one provider/model-settings path. |
| RULE-14 | ✅ | Two Alembic migrations (ProjectSettings JSONB; invocation_evidence JSONB) created in the same task as model changes; both have round-trip regression tests. |
| RULE-16 | ✅ | Three new i18n namespaces registered in `request.ts` + 9 JSON files (3 namespaces × 3 locales) created in the same commit. |
| RULE-17 | ✅ | `DialogueCoachOutput` Pydantic schema fields match TypeScript interface fields exactly; contract test enforced. |
| RULE-18 | ✅ | All router parameters (model config, weights, project_id) come from DI / settings cascade, not hardcoded strings. |
| RULE-18b | ✅ | `AdaptiveWeights` effect-integrity proven by `evals/dialogue_coach/test_voice_fidelity_weight_effect.py` (changing weight measurably changes output). Per-value regression test is the enforcement. |
| RULE-20 | ✅ | All three components (Core contract + ASSIST-004 + LEARN-002 dashboard) ship together. Backend SSE + REST endpoints, frontend dashboard + status indicator + dialogue-coach panel, governed template, manifest entries, adoption registry — all required before the ADR reaches ✅ Implemented. |
| RULE-22 | ✅ | Cross-feature coherence: producer (LEARN-001, ANAL-008) + consumer (ASSIST-004) + dashboard (LEARN-002) integration contracts documented; variable registration for `characters` + `text_to_analyze` explicit; adaptive variables have one canonical writer (`AdaptiveContextEnricher`). |
| RULE-23 | ✅ | No `# type: ignore` introduced; full type annotations; Protocol-based fakes. |
| ADR-038 | ✅ | `AdaptiveContextEnricher` follows the established enricher pattern (Protocol, immutable `model_copy`, graceful degradation D7). The `ContextEnricher` Protocol stays; only the impl class is swapped. |
| ADR-021 | ✅ | Reuses `DialogueParser` (deterministic attribution) per ADR-055 D3; no LLM-based attribution pre-step. |
| ADR-026 | ✅ | Adaptive data flows as category-3 runtime content (`dynamic_inputs`), not as Capability instructions. Universal/Meta Capabilities unchanged. |
| ADR-032 | ✅ | Pydantic Evals are the SSOT for the adaptivity-effect evidence (RULE-18b). |
| ADR-033 | ✅ | mem0 access stays via `PreferenceProvider` (ADR-033); graceful `NullMemoryClient` degradation preserved. |
| ADR-037/046 | ✅ | New `ai_assist/dialogue_coach` routeable surface registered in prompt-surface manifest; §7 stub-variable-detector satisfied. |
| ADR-041/045 | ✅ | Adaptive snapshot reuses `invocation_evidence` (no new table); evidence writes are privacy-safe JSON metadata. |
| ADR-043 | ✅ | `useDialogueCoach` uses `useAIOperation`; TanStack Query cache invalidation for adaptive CRUD is conform (ADR-043 governs AI operations, not settings CRUD). |
| ADR-050 | ✅ | `ProfileProvider` and `PreferenceProvider` contracts honoured; `AdaptiveContextProvider` composes them, does not bypass. |
| ADR-052 | ✅ | SSE recovery for network disconnects (Edge Case E15) via existing session-recovery infrastructure. |
| ADR-054 | ✅ | Dialogue Coach prompt is Mode 1 from day one; no inline-feature-prompt debt reintroduced. |
| ADR-055/057 | ✅ | `voice_metrics` never reach `AdaptiveContext`, `DialogueCoachDeps`, or the `dialogue_coach` template. Only the descriptive `speech_summary` is used. Boundary universally preserved. |
| ADR-056 | ✅ | `dialogue_coach` runtime-evidence probes land in Phase 4; adoption debt cleared before merge. |
| ADR-065 | ✅ | `DialogueCoachService.run()` + `stream()` two-method contract. |
| ADR-067 | ✅ | `AdaptiveContextProvider` mirrors `KBContextProvider` (Core Protocol, Backend impl, composes existing providers into a unified bundle). |

---

## Sustainability Check

1. **Correct in 3 months?** Yes. The four adaptive variables have a
   single canonical writer; future adaptive signals extend
   `AdaptiveContextProvider`; future ASSIST features reuse the
   `ai_assist` prompt category; future MCP/A2A clients call
   `DialogueCoachService.run()` without service changes.
2. **Hard-to-undo coupling?** Minimal. The enricher swap is mechanical
   (Protocol unchanged, only impl class replaced). JSONB columns are
   nullable + downgradable. New LLMIntent is additive. New prompt
   category is additive.
3. **Simplest correct solution?** Yes. Each decision picks the option
   that addresses the root cause without over-building: extending
   existing tables (not new tables), composes existing providers (not
   new SSOTs), mirrors proven patterns (ADR-038 enricher, ADR-067
   provider, ADR-065 two-method service).
4. **Design intent clear?** Yes. 17 decisions, each with alternatives,
   rationale, and sustainability check. Class names document
   responsibilities (`AdaptiveContextEnricher`, `AdaptiveContextProvider`,
   `DialogueCoachService`). The ADR + Retrofit-Plan together let a new
   maintainer trace from intent to implementation.

---

## Review Trigger

- [ ] When the enricher swap (Decision 1) lands — verify all four
      adaptive variables are populated by `AdaptiveContextEnricher`
      alone, no parallel paths remain, and existing features that
      depended on `user_preferences` still work.
- [ ] When MCP or A2A adapter is implemented — verify
      `DialogueCoachService.run()` is callable without service changes.
- [ ] When ANAL-009 (Voice Drift) is implemented — verify it continues
      to read `voice_metrics` via the ADR-050 consumer contract; the
      ADR-055/057 boundary is preserved.
- [ ] When a fifth or sixth adaptive signal is added (e.g., cross-
      session memory) — extend `AdaptiveContextProvider` rather than
      creating a parallel enricher.
- [ ] When a second ASSIST feature lands (ASSIST-001 Plot Check or
      ASSIST-002 Title Suggest) — verify it reuses the `ai_assist`
      category and follows the same Mode-1 / Manifest / Adoption
      pattern.
- [ ] If the enricher-swap migration produces unexpected prompt
      regressions in existing features — re-review Decision 1 and
      consider a feature-flag cutover.
- [ ] If users request char-level inline diff for Dialogue Coach
      rewrites — re-review Decision 9; the current design permits
      additive enhancement.
- [ ] If the LEARN-002 dashboard needs to show non-LLM activities
      (e.g., settings changes) — re-review Decision 11; a separate
      audit-log table may be needed for non-invocation events.

---

## Cross-References

- **Source spec:** `docs/superpowers/specs/2026-07-19-adaptive-context-dialogue-coach-design.md`
- **ADR-038** — AI Invocation Adoption Contract (the enricher pattern extended).
- **ADR-040** — ProjectWritingProfile SSOT (ProfileProvider reused).
- **ADR-041 / ADR-045** — Persistent invocation evidence (table extended for snapshots).
- **ADR-046** — Prompt-Path Compliance (§7 stub-variable detector satisfied).
- **ADR-050** — VoiceProfileConsumer (consumer contract honoured).
- **ADR-054** — Mode-1 PromptComposer mandate (Dialogue Coach from day one).
- **ADR-055 / ADR-057** — Voice boundary (metrics never reach generation).
- **ADR-056** — Runtime-aware adoption gate (dialogue_coach debt cleared before merge).
- **ADR-065** — RULE-13 two-method run/stream contract.
- **ADR-067** — Reusable KB-Context Provider (the pattern mirrored here).
- **LEARN-001** — Feedback & Learning Loop (preference source).
- **LEARN-002** — Adaptivity Dashboard (recalibrated by this ADR).
- **ANAL-008** — Character Voice Profiling (descriptive voice source).
- **WRITE-010** — Voice Consistency Checker (the metrics-boundary precedent).
- **ASSIST-004** — Dialogue Coach (pilot consumer; spec detailed by this ADR).
