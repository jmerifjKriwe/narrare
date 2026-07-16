# ADR-067 — Reusable KB-Context Provider (consolidate fragments; feed planning)

> **Status:** ✅ Accepted — W2a implements the provider
> (`apps/api/narrare/kb/_context_provider.py` + `kb/contracts.py` Protocol).
> The first consumer wiring is **W2b** (`timeline_analysis`) and **W4**
> (`coreference`); see *Consumer integration* below.
> **Date:** 2026-07-16
> **Deciders:** Architecture Specialist
> **Supersedes:** —
> **Related:** ADR-050 (KB Envelope), ADR-025 (ContextAssembler base), ADR-049 (prompt identity/path), ADR-054 (inline-prompt debt), the umbrella §7 closing plan, CONSTRAINTS.md RULE-03/06/07/11/22, `architectural-discipline.md` §7

---

## Problem

Several AI features declare KB-context prompt variables in their governed
templates but leave them **empty at runtime** — the §7 anti-pattern
("template declares slots the runtime leaves empty"). The verified primary
case:

`apps/api/narrare/planning/timeline_analysis_service.py:200-211` builds its
`PromptContext` with `kb_characters`/`kb_locations`/`kb_factions`/
`entity_events`/`culture_guidelines` hardcoded to `""` (only
`kb_relationships` is populated). Its template
`_bundled/planning/en/timeline/system.md` declares a `### Knowledge Base`
section with `{{kb_characters}}`/`{{kb_locations}}` (lines 23/26) and an
`### Instructions` rule "a character cannot be in two locations at the same
time" (line 63) that can only be honoured if character/location data is
actually present. The LLM is asked to reason over KB it never receives.

**Root cause (5-whys):**
1. *Why are the slots empty?* No KB assembler is wired into the planning
   call path.
2. *Why is none wired?* Each non-writing feature rolls its own ad-hoc
   fetch/format helper (or none), because there is **no canonical
   service-layer KB-context provider**.
3. *Why no provider?* ADR-050 defined the canonical *render* contract
   (`KBContextEnvelope` / `RenderedKBContext`) but left the *fetch +
   per-type assembly* step to each consumer. Writing has a complete one
   (`WritingContextAssembler`) but it is fused to writing's 5-tier
   TokenBudget system and takes already-fetched entities.
4. *Why does that matter?* Because every non-writing consumer re-invents a
   fetch+format path with a different shape, none carries provenance, and
   some (planning) simply give up and stub `""`.
5. *Why now?* The kb-debt fix (commit 238200ad) added yet another fragment
   (`kb/_world_context.py`) — the fragmentation is actively growing.

**Verdict:** consolidate the fragments behind ONE reusable provider that
renders through the existing ADR-050 envelope, then point the stubbing
consumers at it. This is a consolidation/SSOT decision, not a new
abstraction.

---

## Inventory — fragment map (what exists today)

| Path | Produces | Shape | Envelope? | Status |
|------|----------|-------|-----------|--------|
| `core/context/_kb_envelope.py` (ADR-050) | `RenderedKBContext` render **contract** | Protocol + value type | = canonical | ✅ SSOT |
| `core/writing/_helpers.py` `format_entities` | compact `### Type: Name\nContent` render | `list[KBEntity]→RenderedKBContext` | ✅ compliant | canonical compact renderer |
| `core/prompts/context.py` `_format_kb_entries` | compact render for `kb_context_entries` | `list[KBContextEntry]→RenderedKBContext` | ✅ compliant | PromptContext path |
| `writing/_relationship_helpers.py` `fetch_formatted_relationships` | `kb_relationships` | `RenderedKBContext` | ✅ compliant | good — fold into provider |
| `kb/worldbuilding_entity_assembly.py` `list_entities` | fetch+paginate+filter KB entries | `KBRepositoryProtocol→list[KBEntry]` | n/a (fetch) | good — reuse as fetch |
| `analysis/dependencies_voice_check.py` `_entry_to_kb_entity` | `KBEntry→KBEntity` mapping | dataclass ctor | n/a (map) | good — reuse as mapper |
| `kb/_world_context.py` (238200ad) | `world_context` aggregate | `- name (type): brief` | ❌ own format | **fragment** — keep format, route via provider |
| `kb/assist_service.py:120-131` | `world_context` inline `"\n".join(...)` | ad-hoc | ❌ | **duplicate** of `_world_context` |
| `kb/improve_analyzer.py:122-131` | `world_context` inline `"\n".join(...)` | ad-hoc | ❌ | **duplicate** of `_world_context` |
| `analysis/context_assembler.py` `_fetch_kb_context` | characters/locations as `list[dict]` | `{name,type,summary}` dicts | ❌ | **fragment** (beta reader) |
| `analysis/coreference_kb.py` `fetch_kb_characters` | `kb_characters` str | own render | ❌ | **fragment** (characters only) |
| `planning/timeline_analysis_service.py:206-210` | stubs `""` | — | — | **the bug** |
| `planning/character_arc_service.py:143-144` | stubs `culture_guidelines`/`existing_plot_points` `""` | — | — | partial debt — **NOT a `kb_*` consumer** (see *Out of scope — dissolved*) |
| `analysis/character_voice_prompt.py` / `voice_check_prompt.py` | stubs kb_* `""` | — | — | partial debt |
| `writing/story_suggest_service.py:163` | stubs `chapter_outline` `""` | — | — | different var (Out-of-scope) |

**Confirmed by probe:** there is **no** `planning/outline` AI service —
`ChapterOutline` is CRUD-only (`planning/service.py`). The outline-shaped
AI consumers are `character_arc_service` (planning) and
`story_suggest_service` (writing).

---

## Canonical mechanism — choice

### Options considered

**Option A — Make planning consume `WritingContextAssembler` directly.**
Reuse the writing assembler as the one path.
- *Rejected.* It is fused to writing's 5-tier TokenBudget system and takes
  pre-fetched `list[KBEntity]`; planning/analysis need a *fetch* +
  simple per-type split, not chapter-content tiers, frontmatter orphan
  checks, or pinned bypass. Coupling planning to it violates RULE-06
  (writing-specific concerns leak) and forces token-budget spend planning
  does not need.

**Option B — One new central renderer + one wire format (reinvent).**
- *Rejected.* ADR-050 Option-A precedent: a single wire format breaks
  tier-specific formats (kb merge/extract's `- name (type): brief` is
  validated by `validate_world_context`; changing it is a prompt
  regression). Rejected for the same reasons ADR-050 rejected it.

**Option C — Thin reusable `KBContextProvider` that wraps the ADR-050
envelope + existing renderers (CHOSEN).** A Backend service-layer provider
that fetches via `list_entities`, maps via the existing KBEntry→KBEntity
mapper, splits by `entity_type`, and renders each type through
`format_entities` (the canonical compact envelope renderer). Provenance
flows through automatically (`RenderOptions` passed to `format_entities`,
`RenderedKBContext.preserved/omitted_fields` carried in the bundle). The
existing relationships helper and `_world_context` aggregate fold behind
it as convenience methods.

### Why C (against ADR-050's intent)

ADR-050 §Decision 1 explicitly states renderers **stay in their current
modules** ("no cross-module move"); it governs the *render* boundary, not
fetch. C honours that: `format_entities` is reused in place, not moved.
C fills the gap ADR-050 deliberately left open (per-type fetch+assembly
for non-writing features) without touching the render contract, the
writing tier system, or the KB repo layer. It is the **simplest correct**
consolidation: one fetch path, one render path (the envelope), zero new
wire formats.

### Layer placement (RULE-07)

- **`KBContextProvider` Protocol + `KBContextBundle` value type** →
  `apps/api/narrare/kb/contracts.py`. The Protocol depends on
  `KBRepositoryProtocol`/`RelationshipRepositoryProtocol` (Backend
  contracts), so it is Backend. This mirrors `planning/contracts.py`,
  `kb/contracts.py` precedent. All 4 clients reach it via the Service
  Layer (RULE-12); the bundle never crosses to MCP/CLI/A2A directly.
- **Implementation** → `apps/api/narrare/kb/_context_provider.py`
  (RULE-04 helper, mirrors `_world_context.py`).
- Core owns the *vocabulary* (`RenderedKBContext`, `KBEntity`,
  `RenderOptions`, `format_entities`); Backend owns *fetch+assembly*.
  Direction is Backend→Core only. ✓

---

## Contract (Protocol) — RULE-03

```python
# apps/api/narrare/kb/contracts.py

@dataclass(frozen=True, slots=True)
class KBContextBundle:
    """Canonical per-type rendered KB context for one novel (ADR-067).

    Every non-writing KB-consuming feature populates its prompt from this.
    Each field is an ADR-050 ``RenderedKBContext`` (``.text`` = prompt-bound
    string; ``preserved/omitted_fields`` = provenance accounting).
    """
    characters:   RenderedKBContext
    locations:    RenderedKBContext
    factions:     RenderedKBContext
    relationships: RenderedKBContext
    render_options: RenderOptions            # what was applied (audit)

    def to_prompt_variables(self) -> dict[str, str]:
        """Map to registered KB vars: kb_characters/kb_locations/
        kb_factions/kb_relationships. Ready for PromptContext(extra=...)."""
        return {
            "kb_characters": self.characters.text,
            "kb_locations":  self.locations.text,
            "kb_factions":   self.factions.text,
            "kb_relationships": self.relationships.text,
        }


@runtime_checkable
class KBContextProvider(Protocol):
    """Single source for canonical KB prompt context (ADR-067).

    Fetches KB entries, renders per entity type through the ADR-050
    envelope, returns a ready-to-inject bundle. Replaces ad-hoc
    fetch/format helpers across planning, analysis, and kb.

    Graceful degradation (RULE-11): an unavailable repo or empty KB yields
    a bundle of empty ``RenderedKBContext`` (``.text == ""``) — never an
    exception — so a feature always composes its prompt.
    """

    async def fetch_context(
        self,
        novel_id: UUID,
        *,
        entity_types: list[str] | None = None,
        options: RenderOptions | None = None,
    ) -> KBContextBundle: ...

    async def fetch_world_context(
        self,
        novel_id: UUID,
        *,
        entity_type: str | None = None,
        max_entries: int = 30,
    ) -> str:
        """Aggregate compact world context for kb merge/extract.

        Succeeds ``kb/_world_context.py`` (same ``- name (type): brief``
        wire format — preserves ``validate_world_context`` compatibility).
        """
        ...
```

> **Naming note (implementation):** the code block above is the design
> sketch. The shipped symbols are `KBContextProviderProtocol` (the
> `runtime_checkable` Protocol in `kb/contracts.py`) and the concrete
> `KBContextProvider` impl in `kb/_context_provider.py`. The mapper is the
> canonical `kb_entry_to_kb_entity` (succeeding the private copy in
> `dependencies_voice_check`).

**Implementation reuses** (no new logic): `worldbuilding_entity_assembly.
list_entities` (fetch), the `kb_entry_to_kb_entity` mapper (the single
canonical `KBEntry→KBEntity` map), `format_entities` (per-type render), the
existing relationship format (`_relationship_format.format_relationships`),
and `format_world_context` (aggregate).

**Provenance (FIND-017):** flows for free. The provider forwards
`options` to `format_entities`; planning passes
`RenderOptions(annotate_provenance=True)` to get the same honest inline
brackets writing gets. The bundle carries `preserved/omitted_fields` for
audit/Context-Inspector.

---

## Consumer integration

> Scope of this ADR is the **KBContextProvider mechanism only**. The
> consumers below are grouped by the wave that wires them — not by this ADR.

### KB-context stub consumers (the `kb_*` slots)

These features' governed templates declare `kb_characters` / `kb_locations` /
`kb_factions` / `kb_relationships` and are the targets of the §7 "slot
declared but left empty" anti-pattern. They adopt the provider:

- **`planning/timeline_analysis` (W2b — first consumer).** Replaces the `""`
  stubs with `kb.to_prompt_variables()`. The direct
  `fetch_formatted_relationships` call is removed (the bundle includes
  relationships); the service constructor swaps `relationship_repo` for
  `kb_context_provider`; the factory wires the provider with
  `KBRepository` + `RelationshipRepository`.

  ```python
  kb = await self._kb_context_provider.fetch_context(
      novel_id,
      entity_types=["character", "location", "faction"],
      options=RenderOptions(annotate_provenance=True),
  )
  ctx = PromptContext(..., extra={
      "chapter_summaries": chapter_context,
      **kb.to_prompt_variables(),   # kb_* now NON-EMPTY
      "entity_events": "",          # NOT a kb_* slot — see "Out of scope"
  })
  ```

- **`analysis/coreference` (W4).** Adopts the provider for its `kb_*` slots
  (currently rolls its own character-only render). Second-wave migration.

### Consolidation consumer — kb merge / extract / assist / improve

These reuse the provider's `fetch_world_context` (NOT the per-type bundle).
Replace `_world_context.fetch_world_context` + the two inline
`"\n".join(...)` blocks (`assist_service.py`, `improve_analyzer.py`) with
`provider.fetch_world_context(...)`. Same `- name (type): brief` wire format →
no prompt regression; one call site. This folds the duplicated
`_world_context`/inline helpers behind the provider.

### NOT a KB-context consumer — out of scope by RULE-06

- **`planning/character_arc`** is **not** a KB-context stub consumer: its
  governed template declares no `kb_*` variables. It stubs
  `culture_guidelines` / `existing_plot_points`, which are *different* data
  sources (see the dissolved Out-of-scope list below). It is therefore
  **removed** from this ADR's consumer list.
- **`character_voice` / `voice_check` / beta-reader** stub `kb_*=""` or roll
  own dicts, but their KB needs are voice-profile / dict-shaped, not the
  per-type entity render this provider offers. They are covered by their own
  mechanisms (see Out-of-scope cross-ref).

---

## Consolidation / removal list

**Folded behind the provider:**
- `kb/_world_context.py` `fetch_world_context`/`format_world_context` →
  provider methods (`format_world_context` stays as the provider's
  internal aggregate renderer; the module is removed or thinned).
- `kb/assist_service.py:120-131` inline world_context →
  `provider.fetch_world_context(...)`.
- `kb/improve_analyzer.py:122-131` inline world_context → same.
- `writing/_relationship_helpers.py` `fetch_formatted_relationships` →
  provider's relationships path (helper kept as thin delegate or removed;
  writing services keep their current call site, just sourced via provider).

**Stays as-is (do NOT over-reach):**
- `WritingContextAssembler` — writing's tier system is its own budget
  domain (out of scope).
- `core/prompts/context.py` `_format_kb_entries` — the PromptContext
  `kb_context_entries` path; separate concern.
- `format_entities` — stays in `core/writing/_helpers.py` per ADR-050
  ("renderers remain in their current modules"); the provider *imports*
  it, does not move it.

---

## Out of scope — dissolved (each closed by its own mechanism)

These variables are deliberately **kept out of the KBContextProvider**. They
are *not* the per-type KB-entity context this provider renders; each is fed
(or closed) by a distinct data source/ADR, tracked by the umbrella §7 closing
plan. They are listed here so the boundary is explicit (RULE-06) and not
silently re-absorbed.

- **`culture_guidelines`** — closed in **W1** (the PromptComposer now
  auto-injects it from `name_style`; the stub slots were removed in commit
  `29fac339`). Not a KB-entity render.
- **`entity_events` / `existing_plot_points` / `chapter_outline`** —
  **W3**: derived views (KB timeline entities / `timeline_events` / chapter
  outlines), distinct data sources, not raw entity-type KB context. Tracked
  as separate follow-ups under the §7 plan.
- **beta-reader `list[dict]` → envelope migration** — **W4**: the beta-reader
  consumes a `list[dict]` shape that needs a render adapter; it is not the
  per-type render this provider offers.
- **Writing TokenBudget tier-system, KB repo layer, ADR-050 render
  contract** — explicitly untouched (RULE-06; ADR-050 governs the render
  boundary).

> The authoritative close-out schedule for every §7 slot lives in the
> **umbrella §7 closing plan** — ADR-067 covers only the KBContextProvider
> mechanism. If any item here looks like it should fold into this provider,
> escalate before expanding (RULE-06).

---

## Migration / blast radius

The work is split into self-contained, independently-verifiable waves.

**W2a — the provider foundation (THIS ADR, DONE):**

| File | Change |
|------|--------|
| `apps/api/narrare/kb/contracts.py` | + `KBContextBundle`, `KBContextProviderProtocol` |
| `apps/api/narrare/kb/_context_provider.py` | NEW impl: fetch (`list_entities`) + canonical `kb_entry_to_kb_entity` mapper + per-type `format_entities` + `format_relationships` + `fetch_world_context` delegate |
| `analysis/dependencies_voice_check.py` | private `_entry_to_kb_entity` → thin delegate to the canonical mapper (dedup) |
| `tests/unit/api/kb/test_kb_context_provider.py` | NEW unit tests (populated render, RULE-11 degradation, provenance accounting, `to_prompt_variables`) |

**W2b — first consumer (separate PR):** `planning/timeline_analysis_service.py`
+ `_timeline_analysis_factory.py` — replace `""` stubs with
`kb.to_prompt_variables()`; ctor `relationship_repo`→`kb_context_provider`;
factory wires `KBContextProvider(KBRepository, RelationshipRepository)`.

**Consolidation wave (separate PR):** fold `kb/_world_context.py` +
`kb/assist_service.py` + `kb/improve_analyzer.py` inline `"\n".join"` behind
`provider.fetch_world_context(...)` (same wire format → no prompt regression).

**W4 — second consumer:** `analysis/coreference` + beta-reader
dict→envelope adapter.

**Impact (W2a):** additive Protocol + one new module + one dedup delegate +
unit tests. No service-ctor signature change yet (that is W2b). No DB
migration. No prompt-template change. Wire formats unchanged → no prompt
regression.

**§7 enforcement (regression tests, mandatory):**
- Unit (W2a, DONE): `KBContextProvider` returns non-empty `.characters.text`
  given a populated KB; empty `RenderedKBContext` on empty/missing KB
  (degradation, no exception); provenance accounting with
  `annotate_provenance=True` yields non-empty `preserved_fields`.
- Integration (W2b): for `timeline_analysis_service`, given a novel with KB
  characters/locations, the composed `PromptContext.extra` has non-empty
  `kb_characters`/`kb_locations` — **the slot is now fed, not stubbed.** This
  is the §7 check that "template declares slot" ⇒ "runtime populates slot."

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-03 | ✅ | `KBContextProvider` Protocol + `KBContextBundle` defined before any consumer wiring. |
| RULE-06 | ✅ | Provider = one responsibility (fetch+render canonical KB context); render tier-system stays in writing. |
| RULE-07 | ✅ | Contract in Backend (`kb/contracts.py`); Core owns vocabulary (`RenderedKBContext`/`KBEntity`/`format_entities`); Backend→Core only. |
| RULE-11 | ✅ | Empty/unavailable KB → empty `RenderedKBContext`, never an exception. |
| RULE-22 | ✅ | Provenance carried via ADR-050 envelope; variable provenance of `kb_*` is now the provider (one source). |
| §7 | ✅ (W2a) / ⏳ (W2b) | W2a: provider-level unit tests assert non-empty render + graceful degradation + provenance (DONE). W2b adds the integration assertion that the timeline `PromptContext` `kb_*` slots are fed, not stubbed. |

---

## Verdict

Consolidate, do not reinvent. ADR-050 already gave us the canonical
*render* surface; this ADR adds the missing canonical *fetch+assemble*
surface behind it and points the stubbing `kb_*` consumers (`timeline` W2b,
`coreference` W4) at it, while folding the duplicated `_world_context`/inline
helpers behind `fetch_world_context`. Net: fewer fragments, planning finally
reasons over real KB data, provenance flows to non-writing features, writing's
tier system and the KB repo stay untouched. `character_arc` is explicitly not
a consumer (no `kb_*` vars in its template) and is removed from scope.

---

## Implementation status

**W2a — DONE (this ADR's scope):**

1. `kb/contracts.py` — `KBContextBundle` + `KBContextProviderProtocol`
   (RULE-03).
2. `kb/_context_provider.py` — impl reusing `list_entities` + the canonical
   `kb_entry_to_kb_entity` mapper + `format_entities` (per-type) +
   `format_relationships` + `fetch_world_context` (delegate).
3. `analysis/dependencies_voice_check.py` — private mapper deduped to the
   canonical one.
4. Unit tests (`tests/unit/api/kb/test_kb_context_provider.py`): populated
   render, RULE-11 degradation, provenance accounting, `to_prompt_variables`,
   `fetch_world_context` delegation, Protocol compliance — all green.

**Not in this ADR (separate waves):**

- **W2b** — wire `timeline_analysis_service` + factory as the first consumer.
- **Consolidation wave** — fold `_world_context.py` + assist/improve inline
  `world_context` behind `provider.fetch_world_context(...)`.
- **W4** — `coreference` consumer + beta-reader dict→envelope adapter.
- `character_arc` — not a `kb_*` consumer (see *Consumer integration*).
