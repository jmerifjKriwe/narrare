# ANAL-001: Beta Reader Simulation — Architecture Specification

> **Status**: Draft
> **Area**: Analysis / AI Chapter Analysis
> **Depends on**: INFRA-001/002/003 (LLM gateway, Redis, Model routing), KB-001 (KB entries), Chapters (chapter CRUD)
> **Author**: Architecture Specialist
> **Date**: 2026-05-26

---

## Table of Contents

1. [Executive Summary & Decision](#1-executive-summary--decision)
2. [Root Cause & Motivation](#2-root-cause--motivation)
3. [Alternatives Considered](#3-alternatives-considered)
4. [Contracts](#4-contracts)
5. [Module Map](#5-module-map)
6. [Data Flow](#6-data-flow)
7. [Caching Strategy](#7-caching-strategy)
8. [Core Layer — Agent, Types, Prompts](#8-core-layer--agent-types-prompts)
9. [Backend Layer — Service, Cache, Router, DI](#9-backend-layer--service-cache-router-di)
10. [Frontend Layer — Panel, API, Hooks, i18n](#10-frontend-layer--panel-api-hooks-i18n)
11. [Testing Plan](#11-testing-plan)
12. [RULE-XX Compliance Matrix](#12-rule-xx-compliance-matrix)
13. [Work Plan](#13-work-plan)

---

## 1. Executive Summary & Decision

### Decision: Two-Phase Hybrid with Inline Analysis Module

Create a new `analysis/` domain module in `apps/api/narrare/analysis/` with a
`BetaReaderService` + `BetaReaderAgent` + `BetaReaderCache` that implements a
two-phase analysis pipeline:

- **Phase 1 (required)**: Full chapter analysis → structured feedback across all
  categories (plot, character, prose, pacing, experience).
- **Phase 2 (optional, user-triggered)**: Deep-dive on a specific category →
  detailed suggestions with text-level references.

This is the **FIRST feature** in the `analysis/` module and establishes the
architectural pattern for all future ANAL features (ANAL-002 through ANAL-011).

| Aspect | Approach |
|--------|----------|
| **Module location** | `apps/api/narrare/analysis/` — new domain module (inline routes, like `kb/`, `writing/`) |
| **Agent** | `BetaReaderAgent` in `packages/core/narrare_core/agents/` — extends `NarrareAgent[BetaReaderDeps, BetaReaderOutput]` |
| **Pattern reuse** | Analyze → cache → respond pattern from KB-006b (WorldbuildingAnalyzer) — same architecture, different domain |
| **Infrastructure reuse** | `ModelRegistry`, `PromptComposer`, `RedisSessionCache`, `ChapterRepository`, `KBRepository` |
| **LLM intent** | `LLMIntent.BETA_READ` — already registered in `intents.py` line 52, maps to `IntentCategory.ANALYSIS` (line 119) |
| **Prompt path** | `core/prompts/_bundled/analysis/en/beta_reader/system.md` (already mapped in composer.py line 76) |
| **Streaming** | No SSE for Phase 1 — follows existing KB analysis pattern (POST → full response). Phase 2 same. SSE possible in future via RULE-13 interface. |
| **Cache** | Redis via `SessionCacheProtocol` — 30min TTL, key prefix `analysis:beta:` |
| **Frontend** | New collapsible `BetaReaderPanel` in the editor view, TanStack Query hooks |
| **Context sources** | Chapter text + frontmatter, previous chapters (summaries), KB entries (characters, locations) |

### Key Architectural Insight

ANAL-001 establishes the `analysis/` module as a **peer** of `kb/` and `writing/`.
Each future ANAL feature (sentiment, readability, POV, voice, etc.) follows the
same pattern: `{feature}_contracts.py` → `{feature}_service.py` →
`router_{feature}.py` → agent in core. The analysis module is not a monolith —
each feature gets its own files, sharing only the module namespace, DI wiring,
and the `analysis/contracts.py` umbrella for shared types.

---

## 2. Root Cause & Motivation

### Symptom

Writers complete chapter drafts but lack automated feedback from a reader's
perspective. They can see individual words on the page but cannot evaluate
plot coherence, character consistency, pacing effectiveness, or reader
engagement without external help (beta readers, critique partners).

### Root Cause (2x Why)

1. **Why is this a problem?** The existing Narrare infrastructure is
   **generation-centric**: it helps writers produce text (writing service,
   draft agent, extend, rewrite). There is no analysis infrastructure. A
   writer can generate a chapter but cannot evaluate it from a reader's
   perspective within the tool.

2. **Why does the generation-only approach fail?** Because writing quality
   requires both production AND evaluation. Without analysis, writers use
   external tools (or nothing) for feedback — breaking their flow. The gap
   between "text exists" and "text is effective" is unaddressed.

### Design Principle

> A beta reader simulation must see the **chapter as a reader would** —
> understanding context from previous chapters, recognizing characters and
> locations from the KB, and providing feedback organized by severity. It is
> not a grammar checker; it is a first-reader perspective.

The solution is a chapter-level analysis service that combines chapter text,
story context (previous chapters), and world context (KB entries) to produce
structured, actionable feedback — mimicking what a real beta reader would say.

---

## 3. Alternatives Considered

### Option A — Extend Writing Service (REJECTED)

Add beta reader analysis as a mode in the existing `writing/service.py`.

| Pro | Con |
|-----|-----|
| No new module needed | **Violates RULE-06**: Writing service handles generation. Analysis is fundamentally different — it reads and evaluates, it doesn't produce text |
| Same DI wiring | **Violates RULE-05**: Analysis is a different domain with different dependencies (no generation artifacts, different prompt strategy, different output types) |
| - | **Wrong module boundaries**: Writing service already has 8+ sub-services. Adding analysis would make it a catch-all |
| - | **Different cache semantics**: Generation caches drafts. Analysis caches feedback. TTLs differ. |
| - | Writing service exceeds 300-line soft limit on multiple files already |

**Verdict**: REJECTED — analysis is a separate domain, not a writing mode.

### Option B — Standalone Service Without Agent (REJECTED)

Direct LLM call via `PromptComposer.build()` + `Gateway.run()` without a
dedicated agent class.

| Pro | Con |
|-----|-----|
| Fewer files — no agent, no types | **Violates RULE-01b**: LLM operations must go through agents. The agent pattern provides structured output, deps injection, and observability |
| Simpler initial implementation | **No structured output**: Raw LLM text would need fragile parsing. Agent output types give validated Pydantic models |
| - | **No Phase 2 support**: Two-phase analysis requires agent-level orchestration (different deps, different prompts, same agent) |
| - | **Misses pattern establishment**: Future ANAL features need the agent pattern. Skipping it now creates inconsistency |

**Verdict**: REJECTED — agents are the standard LLM interface. No shortcuts.

### Option C — Two-Phase Hybrid with Dedicated Agent (SELECTED)

New `analysis/` module + `BetaReaderAgent` with two-phase analysis.

| Pro | Con |
|-----|-----|
| Clean domain separation — analysis is its own concern | New module (but this is correct — new domain = new module) |
| Follows proven agent pattern from KB-006b (WorldbuildingAgent) | Must create prompt files for Phase 1 and Phase 2 |
| Structured output via Pydantic models — no fragile text parsing | New i18n namespace |
| Establishes pattern for all future ANAL features | |
| Proper cache isolation (30min TTL, different prefix) | |
| Context assembly from chapters + KB mirrors ProactiveContextService pattern | |
| Phase 1 gives broad feedback, Phase 2 gives deep feedback — matches real beta reader behavior | |

**Verdict**: SELECTED — correct domain separation, proven agent pattern, pattern-establishing for future ANAL features.

---

## 4. Contracts

### 4.1 Analysis Module Shared Types

Location: `apps/api/narrare/analysis/contracts.py`

```python
"""Analysis service contracts — Protocol definitions.

Contracts are written before implementation (RULE-03).
This is the umbrella contract file for the analysis module,
shared across all ANAL features (ANAL-001 through ANAL-011).
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from uuid import UUID


# ---------------------------------------------------------------------------
# Shared Enums
# ---------------------------------------------------------------------------


class FeedbackSeverity(enum.StrEnum):
    """Severity level for analysis feedback."""

    CRITICAL = "critical"    # Blocks reader engagement — must fix
    MODERATE = "moderate"    # Noticeable issue — should address
    MINOR = "minor"          # Small improvement — nice to fix


class FeedbackCategory(enum.StrEnum):
    """Analysis feedback categories."""

    PLOT = "plot"            # Plot structure, goals, conflicts, resolution
    CHARACTER = "character"  # Character believability, motivation, consistency
    PROSE = "prose"          # Clarity, flow, show/tell, voice
    PACING = "pacing"        # Rhythm, momentum, chapter structure
    EXPERIENCE = "experience"  # Reader engagement, confusion, emotion


# ---------------------------------------------------------------------------
# ANAL-001: Beta Reader — Feedback Types
# ---------------------------------------------------------------------------


class BetaFeedbackItem(BaseModel):
    """A single feedback item from the beta reader.

    Attributes:
        category: Which aspect of writing this feedback addresses.
        severity: How impactful this issue is for readers.
        location: Where in the chapter this applies (paragraph/section reference).
        title: Short summary of the feedback (1-2 sentences).
        description: Detailed explanation of what the issue is.
        suggestion: Concrete actionable suggestion for improvement.
        text_excerpt: The specific text passage this refers to (if applicable).
    """

    category: FeedbackCategory
    severity: FeedbackSeverity
    location: str | None = None
    title: str
    description: str
    suggestion: str | None = None
    text_excerpt: str | None = None


class BetaReaderStrength(BaseModel):
    """A strength identified by the beta reader.

    Attributes:
        category: Which aspect of writing this strength relates to.
        title: Short summary of the strength.
        description: Why this works well.
        text_excerpt: Supporting text passage (if applicable).
    """

    category: FeedbackCategory
    title: str
    description: str
    text_excerpt: str | None = None


class BetaReaderQuestion(BaseModel):
    """A question a reader would ask while reading.

    Attributes:
        category: Which aspect triggered the question.
        location: Where in the chapter this question arises.
        question: The question itself.
        context: Why this question comes up (what triggered it).
    """

    category: FeedbackCategory
    location: str | None = None
    question: str
    context: str | None = None


class BetaReaderOverallAssessment(BaseModel):
    """Overall assessment of the chapter from a reader's perspective.

    Attributes:
        summary: 2-3 sentence overall impression.
        reader_engagement: How engaging the chapter is (1-10).
        emotional_impact: How emotionally resonant (1-10).
        pacing_score: How well-paced the chapter is (1-10).
        prose_quality: Clarity and style quality (1-10).
        plot_progression: How well the plot advances (1-10).
        character_development: How well characters are developed (1-10).
    """

    summary: str
    reader_engagement: int = Field(ge=1, le=10)
    emotional_impact: int = Field(ge=1, le=10)
    pacing_score: int = Field(ge=1, le=10)
    prose_quality: int = Field(ge=1, le=10)
    plot_progression: int = Field(ge=1, le=10)
    character_development: int = Field(ge=1, le=10)


# ---------------------------------------------------------------------------
# ANAL-001: Beta Reader — Request / Response
# ---------------------------------------------------------------------------


class BetaReaderRequest(BaseModel):
    """Request to run a beta reader analysis.

    Attributes:
        chapter_ids: Chapter(s) to analyze. At least one required.
        categories: Filter to specific categories. None = all categories.
        phase: Which phase to run. 'full' = Phase 1 only. 'deepdive' = Phase 2.
        deepdive_category: Required when phase='deepdive'. Which category to deep-dive.
        refresh: If True, bypass cache and force fresh analysis.
    """

    chapter_ids: list[str] = Field(min_length=1, max_length=5)
    categories: list[FeedbackCategory] | None = None
    phase: str = Field(default="full", pattern="^(full|deepdive)$")
    deepdive_category: FeedbackCategory | None = None
    refresh: bool = False


class BetaReaderResponse(BaseModel):
    """Complete beta reader analysis response.

    Attributes:
        novel_id: The project being analyzed.
        chapter_ids: Which chapters were analyzed.
        total_word_count: Total words across analyzed chapters.
        strengths: What works well.
        feedback: Issues and suggestions, organized by category and severity.
        questions: Questions a reader would ask.
        overall: Overall chapter assessment with scores.
        analyzed_at: When the analysis was performed.
        cache_key: Cache key for potential Phase 2 deep-dive reference.
    """

    novel_id: str
    chapter_ids: list[str]
    total_word_count: int
    strengths: list[BetaReaderStrength]
    feedback: list[BetaFeedbackItem]
    questions: list[BetaReaderQuestion]
    overall: BetaReaderOverallAssessment
    analyzed_at: str  # ISO datetime string
    cache_key: str


class BetaReaderDeepDiveRequest(BaseModel):
    """Request for Phase 2 deep-dive analysis.

    Attributes:
        chapter_ids: Same chapters as Phase 1.
        category: Which category to deep-dive.
        cache_key: Cache key from Phase 1 response (for context).
    """

    chapter_ids: list[str] = Field(min_length=1, max_length=5)
    category: FeedbackCategory
    cache_key: str


class BetaReaderDeepDiveResponse(BaseModel):
    """Response from Phase 2 deep-dive analysis.

    Attributes:
        novel_id: The project being analyzed.
        category: The category that was deep-dived.
        detailed_feedback: More granular feedback with text-level references.
        revision_suggestions: Concrete revision suggestions with before/after examples.
        category_score: Detailed score breakdown for this category.
    """

    novel_id: str
    category: FeedbackCategory
    detailed_feedback: list[BetaFeedbackItem]
    revision_suggestions: list[str]
    category_score: int = Field(ge=1, le=10)
    analyzed_at: str


# ---------------------------------------------------------------------------
# ANAL-001: Beta Reader — Service Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class BetaReaderProtocol(Protocol):
    """Protocol for beta reader analysis services.

    Provides two analysis phases:
      Phase 1 (full): Comprehensive chapter analysis across all categories.
      Phase 2 (deepdive): Focused deep-dive on a specific category.

    Results are cached with 30min TTL.
    """

    async def analyze(
        self,
        *,
        novel_id: UUID,
        user_id: UUID,
        request: BetaReaderRequest,
    ) -> BetaReaderResponse:
        """Analyze chapter(s) from a beta reader's perspective.

        Phase 1: Comprehensive analysis across all requested categories.
        Produces strengths, feedback items, reader questions, and an overall
        assessment with scores.

        Args:
            novel_id: The project containing the chapters.
            user_id: The user requesting analysis.
            request: Analysis parameters (chapter IDs, categories, options).

        Returns:
            Complete beta reader feedback with overall assessment.
        """
        ...

    async def deep_dive(
        self,
        *,
        novel_id: UUID,
        user_id: UUID,
        request: BetaReaderDeepDiveRequest,
    ) -> BetaReaderDeepDiveResponse:
        """Run Phase 2 deep-dive on a specific category.

        Takes the context from Phase 1 (via cache key) and produces
        more detailed feedback for a specific category, including
        text-level references and revision suggestions.

        Args:
            novel_id: The project containing the chapters.
            user_id: The user requesting the deep-dive.
            request: Deep-dive parameters (chapter IDs, category, cache key).

        Returns:
            Detailed category-specific feedback with revision suggestions.
        """
        ...
```

### 4.2 Agent Types

Location: `packages/core/narrare_core/agents/beta_reader_types.py`

```python
"""Output types for BetaReaderAgent.

Two output modes:
  - Phase 1 (Full Analysis): Broad feedback across all categories
  - Phase 2 (Deep Dive): Focused analysis on one category

Follows the same pattern as worldbuilding_types.py.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Phase 1: Full Chapter Analysis
# ---------------------------------------------------------------------------


class AgentFeedbackItem(BaseModel):
    """A single feedback item from the agent's raw output.

    The service layer maps this to the public BetaFeedbackItem.
    """

    category: str  # plot, character, prose, pacing, experience
    severity: str  # critical, moderate, minor
    location: str | None = None
    title: str
    description: str
    suggestion: str | None = None
    text_excerpt: str | None = None


class AgentStrength(BaseModel):
    """A strength identified by the agent."""

    category: str
    title: str
    description: str
    text_excerpt: str | None = None


class AgentReaderQuestion(BaseModel):
    """A question a reader would ask."""

    category: str
    location: str | None = None
    question: str
    context: str | None = None


class AgentOverallAssessment(BaseModel):
    """Overall assessment scores."""

    summary: str
    reader_engagement: int = Field(ge=1, le=10)
    emotional_impact: int = Field(ge=1, le=10)
    pacing_score: int = Field(ge=1, le=10)
    prose_quality: int = Field(ge=1, le=10)
    plot_progression: int = Field(ge=1, le=10)
    character_development: int = Field(ge=1, le=10)


class BetaReaderPhase1Output(BaseModel):
    """Agent output for Phase 1 (full chapter analysis)."""

    strengths: list[AgentStrength]
    feedback: list[AgentFeedbackItem]
    questions: list[AgentReaderQuestion]
    overall: AgentOverallAssessment


# ---------------------------------------------------------------------------
# Phase 2: Category Deep Dive
# ---------------------------------------------------------------------------


class AgentDeepDiveFeedback(BaseModel):
    """Detailed feedback item for a specific category."""

    category: str
    severity: str
    location: str | None = None
    title: str
    description: str
    suggestion: str | None = None
    text_excerpt: str | None = None


class BetaReaderPhase2Output(BaseModel):
    """Agent output for Phase 2 (category deep dive)."""

    detailed_feedback: list[AgentDeepDiveFeedback]
    revision_suggestions: list[str]
    category_score: int = Field(ge=1, le=10)


# ---------------------------------------------------------------------------
# Agent Dependencies
# ---------------------------------------------------------------------------


class BetaReaderDeps(BaseModel):
    """Dependencies for BetaReaderAgent.

    Attributes:
        language: Output language code.
        chapter_text: The full text of the chapter(s) being analyzed.
        chapter_titles: Titles of the chapters (for context).
        word_count: Total word count of the analyzed text.
        previous_chapter_summaries: Summaries of chapters before the analyzed ones.
        kb_characters: Relevant character entries from the KB.
        kb_locations: Relevant location entries from the KB.
        genre: The project's genre (if specified).
        focus_categories: Categories to focus on (None = all).
    """

    language: str = "en"
    chapter_text: str = ""
    chapter_titles: list[str] = Field(default_factory=list)
    word_count: int = 0
    previous_chapter_summaries: list[str] = Field(default_factory=list)
    kb_characters: list[dict[str, str]] = Field(default_factory=list)
    kb_locations: list[dict[str, str]] = Field(default_factory=list)
    genre: str = ""
    focus_categories: list[str] | None = None
    # Phase 2 only:
    deepdive_category: str | None = None
    phase1_strengths_summary: str | None = None
    phase1_feedback_summary: str | None = None
```

### 4.3 Agent Definition

Location: `packages/core/narrare_core/agents/beta_reader_agent.py`

```python
"""BetaReaderAgent — chapter-level beta reader simulation.

Two-phase analysis:
  Phase 1: Full chapter analysis → strengths, feedback, questions, scores
  Phase 2: Category deep-dive → detailed feedback with revision suggestions

Follows the same pattern as worldbuilding_agent.py.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import RunContext

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.beta_reader_types import (
    AgentDeepDiveFeedback,
    AgentFeedbackItem,
    AgentOverallAssessment,
    AgentReaderQuestion,
    AgentStrength,
    BetaReaderDeps,
    BetaReaderPhase1Output,
    BetaReaderPhase2Output,
)


class BetaReaderAgent(NarrareAgent[BetaReaderDeps, BetaReaderPhase1Output]):
    """Agent that simulates a beta reader's feedback.

    Phase 1: Full chapter analysis across all categories.
    Phase 2: Deep-dive on a specific category with revision suggestions.
    """

    def __init__(
        self,
        model: Any,
        system_prompt: str | None = None,
    ) -> None:
        """Initialize BetaReaderAgent.

        Args:
            model: LLM model from ModelRegistry.
            system_prompt: System prompt (composed by PromptComposer).
        """
        super().__init__(
            model=model,
            deps_type=BetaReaderDeps,
            output_type=[self._process_phase1, BetaReaderPhase1Output],
            system_prompt=system_prompt,
        )

    async def _process_phase1(
        self,
        ctx: RunContext[BetaReaderDeps],
        strengths: list[dict[str, Any]] | None = None,
        feedback: list[dict[str, Any]] | None = None,
        questions: list[dict[str, Any]] | None = None,
        overall: dict[str, Any] | None = None,
    ) -> BetaReaderPhase1Output:
        """Output function for Phase 1 — structures LLM response."""
        if ctx.partial_output:
            return BetaReaderPhase1Output(
                strengths=[],
                feedback=[],
                questions=[],
                overall=AgentOverallAssessment(summary="", reader_engagement=5,
                    emotional_impact=5, pacing_score=5, prose_quality=5,
                    plot_progression=5, character_development=5),
            )

        parsed_strengths = [AgentStrength(**s) for s in (strengths or [])]
        parsed_feedback = [AgentFeedbackItem(**f) for f in (feedback or [])]
        parsed_questions = [AgentReaderQuestion(**q) for q in (questions or [])]
        parsed_overall = AgentOverallAssessment(**(overall or {"summary": ""}))

        return BetaReaderPhase1Output(
            strengths=parsed_strengths,
            feedback=parsed_feedback,
            questions=parsed_questions,
            overall=parsed_overall,
        )

    async def run_phase1(
        self,
        prompt: str,
        deps: BetaReaderDeps,
        **kwargs: Any,
    ) -> BetaReaderPhase1Output:
        """Execute Phase 1 analysis (full chapter feedback)."""
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return result.output  # type: ignore[return-value]

    async def run_phase2(
        self,
        prompt: str,
        deps: BetaReaderDeps,
        model: Any,
        system_prompt: str | None = None,
    ) -> BetaReaderPhase2Output:
        """Execute Phase 2 deep-dive with separate agent instance.

        Phase 2 has its own agent instance with different output type
        and potentially different model/system prompt.
        """
        phase2_agent = NarrareAgent[BetaReaderDeps, BetaReaderPhase2Output](
            model=model,
            deps_type=BetaReaderDeps,
            output_type=[self._process_phase2, BetaReaderPhase2Output],
            system_prompt=system_prompt,
        )
        result = await phase2_agent.run(prompt, deps=deps)
        return result.output  # type: ignore[return-value]

    async def _process_phase2(
        self,
        ctx: RunContext[BetaReaderDeps],
        detailed_feedback: list[dict[str, Any]] | None = None,
        revision_suggestions: list[str] | None = None,
        category_score: int = 5,
    ) -> BetaReaderPhase2Output:
        """Output function for Phase 2 — structures deep-dive response."""
        if ctx.partial_output:
            return BetaReaderPhase2Output(
                detailed_feedback=[],
                revision_suggestions=[],
                category_score=5,
            )

        parsed = [AgentDeepDiveFeedback(**f) for f in (detailed_feedback or [])]
        return BetaReaderPhase2Output(
            detailed_feedback=parsed,
            revision_suggestions=revision_suggestions or [],
            category_score=min(max(category_score, 1), 10),
        )

    async def run(
        self,
        prompt: str,
        deps: BetaReaderDeps,
        **kwargs: Any,
    ) -> BetaReaderPhase1Output:
        """Default run for Phase 1 (backwards compatibility)."""
        return await self.run_phase1(prompt, deps, **kwargs)
```

---

## 5. Module Map

### 5.1 New Files

Files are listed in implementation order (Layer Ordering).

| # | Layer | File | Purpose | Est. Lines |
|---|-------|------|---------|-----------|
| 1 | Core | `packages/core/narrare_core/agents/beta_reader_types.py` | Agent output types (Phase 1 + Phase 2 + Deps) | ~150 |
| 2 | Core | `packages/core/narrare_core/agents/beta_reader_agent.py` | BetaReaderAgent (Phase 1 + Phase 2 orchestration) | ~150 |
| 3 | Core | `packages/core/narrare_core/prompts/_bundled/analysis/en/beta_reader/system.md` | Phase 1 system prompt (full chapter analysis) | ~120 |
| 4 | Core | `packages/core/narrare_core/prompts/_bundled/analysis/en/beta_reader_deepdive/system.md` | Phase 2 system prompt (category deep-dive) | ~100 |
| 5 | Backend | `apps/api/narrare/analysis/__init__.py` | Module init with public exports | ~10 |
| 6 | Backend | `apps/api/narrare/analysis/contracts.py` | BetaReaderProtocol + all Pydantic schemas | ~200 |
| 7 | Backend | `apps/api/narrare/analysis/beta_reader_cache.py` | Redis-backed cache wrapper for analysis results | ~80 |
| 8 | Backend | `apps/api/narrare/analysis/beta_reader_service.py` | Business logic: analyze() + deep_dive() orchestration | ~250 |
| 9 | Backend | `apps/api/narrare/analysis/context_assembler.py` | Context assembly: chapters + KB entries + previous chapters | ~150 |
| 10 | Backend | `apps/api/narrare/analysis/dependencies.py` | FastAPI DI factory functions | ~80 |
| 11 | Backend | `apps/api/narrare/analysis/router.py` | FastAPI routes (thin delegation) | ~80 |
| 12 | Frontend | `packages/web/lib/api/analysis.ts` | API types + client functions | ~100 |
| 13 | Frontend | `packages/web/lib/hooks/useBetaReader.ts` | TanStack Query hooks | ~70 |
| 14 | Frontend | `packages/web/components/studio/analysis/BetaReaderPanel.tsx` | Collapsible results panel with tabs | ~300 |
| 15 | Frontend | `packages/web/components/studio/analysis/BetaReaderTrigger.tsx` | Trigger button for editor toolbar | ~60 |
| 16 | Frontend | `packages/web/components/studio/analysis/FeedbackCard.tsx` | Reusable feedback item card component | ~100 |
| 17 | Frontend | `packages/web/components/studio/analysis/ScoreRadar.tsx` | Score visualization (radar/spider chart) | ~80 |
| 18 | Frontend | `packages/web/messages/en/analysis.json` | English i18n translations | ~60 |
| 19 | Frontend | `packages/web/messages/de/analysis.json` | German i18n translations | ~60 |
| 20 | Frontend | `packages/web/messages/fr/analysis.json` | French i18n translations | ~60 |

### 5.2 Modified Files

| # | File | Change | Reason |
|---|------|--------|--------|
| M1 | `packages/core/narrare_core/agents/__init__.py` | Export BetaReaderAgent | Module public API |
| M2 | `packages/core/narrare_core/prompts/composer.py` | Add `BETA_READ` deepdive mode mapping (if not already handled) | Phase 2 prompt routing |
| M3 | `packages/web/lib/i18n/request.ts` | Add `"analysis"` namespace | RULE-16 |
| M4 | `packages/web/components/studio/EditorView.tsx` | Add `BetaReaderTrigger` to toolbar + render `BetaReaderPanel` | Frontend integration |
| M5 | `packages/web/lib/stores/editorStore.ts` | Add `betaReaderPanelOpen` + `betaReaderResult` state | Frontend state management |
| M6 | `apps/api/narrare/_app/router.py` | Mount `analysis` router (if centralized mounting) | API registration |

### 5.3 Module Boundary Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                    apps/api/narrare/analysis/                     │
│                                                                   │
│  router.py ──→ beta_reader_service.py                             │
│                    │                                              │
│                    ├──→ context_assembler.py                      │
│                    │       │                                      │
│                    │       ├──→ ChapterRepository (via DI)        │
│                    │       ├──→ KBRepository (via DI)             │
│                    │       └──→ NovelRepository (for genre)       │
│                    │                                              │
│                    ├──→ beta_reader_cache.py                      │
│                    │       └──→ RedisSessionCache (via DI)        │
│                    │                                              │
│                    └──→ ModelRegistry + PromptComposer (via DI)   │
│                         → BetaReaderAgent (core/ via DI)          │
│                                                                   │
│  contracts.py ← Protocol definitions (RULE-03)                   │
│  dependencies.py ← DI factories                                   │
└──────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                    packages/core/narrare_core/                    │
│                                                                   │
│  agents/                                                          │
│    beta_reader_types.py   ← Output types (Phase 1 + Phase 2)     │
│    beta_reader_agent.py   ← NarrareAgent[BRDeps, BRPhase1Out]    │
│                                                                   │
│  prompts/_bundled/analysis/en/                                    │
│    beta_reader/system.md          ← Phase 1 prompt               │
│    beta_reader_deepdive/system.md ← Phase 2 prompt               │
│                                                                   │
│  llm/                                                             │
│    intents.py             ← BETA_READ (already registered)        │
│    gateway.py             ← ModelRegistry (reused)                │
│                                                                   │
│  prompts/                                                         │
│    composer.py            ← PromptComposer (reused)               │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                    packages/web/ (Frontend)                       │
│                                                                   │
│  EditorView.tsx                                                   │
│    ├── BetaReaderTrigger (toolbar button)                         │
│    └── BetaReaderPanel (collapsible panel)                        │
│         ├── FeedbackCard (per-item card)                          │
│         ├── ScoreRadar (score visualization)                      │
│         └── Tabs: Strengths / Issues / Questions / Overall        │
│                                                                   │
│  lib/api/analysis.ts       ← API client                          │
│  lib/hooks/useBetaReader.ts ← TanStack Query hooks               │
│  messages/{en,de,fr}/analysis.json ← i18n (RULE-16)             │
└──────────────────────────────────────────────────────────────────┘
```

### 5.4 Import Graph

```
router.py
  └──→ beta_reader_service.py (via DI from dependencies.py)
          ├──→ context_assembler.py
          │       ├──→ chapters.repository.ChapterRepository (imported by DI)
          │       ├──→ kb.repository.KBRepository (imported by DI)
          │       └──→ novels.repository.NovelRepository (imported by DI)
          ├──→ beta_reader_cache.py
          │       └──→ core.cache.redis_client.RedisSessionCache (imported by DI)
          └──→ core.agents.beta_reader_agent.BetaReaderAgent (via DI)
                  └──→ core.agents.beta_reader_types (internal)
```

All imports flow downward. No circular dependencies. No imports from `apps/` in `core/`.

---

## 6. Data Flow

### 6.1 Phase 1: Full Chapter Analysis

```
User clicks "Beta Reader" button in editor toolbar
        │
        ▼
┌────────────────────────────────┐
│  BetaReaderTrigger.tsx          │
│  Opens BetaReaderPanel          │
│  Calls useBetaReaderAnalysis    │
│  (TanStack Query mutation)      │
└──────────┬─────────────────────┘
           │ POST /api/v1/analysis/beta-reader
           ▼
┌────────────────────────────────┐
│  analysis/router.py             │  (thin — RULE-06)
│  service.analyze(...)           │
└──────────┬─────────────────────┘
           ▼
┌──────────────────────────────────────────────────────────┐
│  beta_reader_service.py: analyze()                        │
│                                                           │
│  1. Validate chapter_ids exist + belong to novel          │
│  2. Check word count (min 1000, max 10000)                │
│  3. Check cache (if not refresh)                          │
│     → Cache hit? Return cached BetaReaderResponse         │
│                                                           │
│  4. Assemble context via context_assembler:               │
│     a. Fetch chapter text + frontmatter                   │
│     b. Fetch previous chapter summaries (up to 3)         │
│     c. Fetch relevant KB entries (characters, locations)  │
│     d. Fetch genre from novel metadata                    │
│                                                           │
│  5. Build BetaReaderDeps from assembled context           │
│                                                           │
│  6. Compose prompt via PromptComposer:                    │
│     PromptComposer.build(BETA_READ, context)              │
│                                                           │
│  7. Resolve model via ModelRegistry:                      │
│     model = registry.get_model(config)                    │
│                                                           │
│  8. Execute agent:                                        │
│     agent = BetaReaderAgent(model=model, system_prompt=…) │
│     result = agent.run_phase1(user_prompt, deps=deps)     │
│                                                           │
│  9. Map agent output → public BetaReaderResponse          │
│                                                           │
│  10. Store in cache (30min TTL)                           │
│  11. Return BetaReaderResponse                            │
└──────────┬───────────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────┐
│  Frontend: BetaReaderPanel     │
│  Displays:                     │
│  - Tab: Strengths              │
│  - Tab: Issues (by severity)   │
│  - Tab: Reader Questions       │
│  - Tab: Overall Assessment     │
│  - Score radar chart           │
│  - "Deep Dive" button per tab  │
└────────────────────────────────┘
```

### 6.2 Phase 2: Category Deep Dive

```
User clicks "Deep Dive" on a category tab in BetaReaderPanel
        │
        ▼
┌────────────────────────────────────────┐
│  BetaReaderPanel.tsx                    │
│  Calls useBetaReaderDeepDive           │
│  (TanStack Query mutation)             │
└──────────┬─────────────────────────────┘
           │ POST /api/v1/analysis/beta-reader/deep-dive
           ▼
┌────────────────────────────────────────┐
│  analysis/router.py                     │
│  service.deep_dive(...)                 │
└──────────┬─────────────────────────────┘
           ▼
┌──────────────────────────────────────────────────────────┐
│  beta_reader_service.py: deep_dive()                      │
│                                                           │
│  1. Retrieve Phase 1 result from cache (via cache_key)    │
│  2. Assemble context (same chapters + Phase 1 summary)   │
│  3. Build BetaReaderDeps with:                            │
│     - deepdive_category set                               │
│     - phase1_strengths_summary                            │
│     - phase1_feedback_summary                             │
│  4. Compose Phase 2 prompt (deepdive mode)                │
│  5. Execute agent.run_phase2(...)                         │
│  6. Map output → BetaReaderDeepDiveResponse               │
│  7. Return response (not cached separately — client       │
│     can re-run if needed)                                 │
└──────────────────────────────────────────────────────────┘
```

### 6.3 Context Assembly Detail

```
context_assembler.py — build_beta_reader_context():

  INPUT: novel_id, chapter_ids, user_id

  STEP 1: Fetch chapters
    chapters = chapter_repo.list_by_novel(novel_id)
    target_chapters = [c for c in chapters if c.id in chapter_ids]
    → Validate: len(target_chapters) == len(chapter_ids)
    → Validate: sum(c.word_count for c in targets) in [1000, 10000]

  STEP 2: Fetch previous chapter summaries
    For each target chapter, find chapters with lower position:
    previous = [c for c in all_chapters
                if c.position < min(t.position for t in targets)]
    Take up to 3 most recent previous chapters.
    Extract: c.summary (or first 200 chars of c.content if no summary)

  STEP 3: Fetch relevant KB entries
    kb_entries = kb_repo.list_for_novel(novel_id)

    characters = [
        {"name": e.name, "type": e.entity_type,
         "summary": (e.body or "")[:200]}
        for e in kb_entries if e.entity_type == "character"
    ]
    locations = [
        {"name": e.name, "type": e.entity_type,
         "summary": (e.body or "")[:200]}
        for e in kb_entries if e.entity_type == "location"
    ]

  STEP 4: Fetch genre from novel metadata
    novel = novel_repo.get_by_id(novel_id)
    genre = novel.metadata.get("genre", "") if novel.metadata else ""

  STEP 5: Build BetaReaderDeps
    deps = BetaReaderDeps(
        language="en",
        chapter_text="\n\n---\n\n".join(c.content for c in targets),
        chapter_titles=[c.title for c in targets],
        word_count=sum(c.word_count for c in targets),
        previous_chapter_summaries=summaries,
        kb_characters=characters,
        kb_locations=locations,
        genre=genre,
        focus_categories=[c.value for c in request.categories]
            if request.categories else None,
    )

  OUTPUT: BetaReaderDeps (ready for agent.run_phase1())
```

---

## 7. Caching Strategy

### 7.1 Cache Design

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Backend** | Redis via `SessionCacheProtocol` (same as KB improve) | Proven infrastructure, no new dependencies |
| **Wrapper** | New `BetaReaderCache` class | Dedicated key prefix, 30min TTL |
| **Key prefix** | `analysis:beta:{novel_id}:{chapter_ids_hash}` | Novel-scoped + chapter-specific |
| **Key format** | `analysis:beta:{novel_id}:{hash(sorted(chapter_ids))}` | Stable key for same chapter set |
| **TTL** | 30 minutes (1800s) | Longer than KB (10min) — analysis is more expensive and stable |
| **Invalidation trigger 1** | Manual `refresh=True` in request | User clicks "Refresh" in UI |
| **Invalidation trigger 2** | On chapter content update | Content changes make feedback stale |
| **Cache-after-apply** | N/A — no apply step (unlike KB improve) | Beta reader is read-only analysis |
| **Phase 1 cache** | Yes — full result cached | Phase 2 reads Phase 1 from cache |
| **Phase 2 cache** | No — not cached separately | Deep-dive is on-demand, lighter weight |

### 7.2 Cache Implementation

```python
class BetaReaderCache:
    """Redis-backed cache for beta reader analysis results."""

    TTL = 1800  # 30 minutes
    KEY_PREFIX = "analysis:beta:"

    def __init__(self, cache: SessionCacheProtocol) -> None:
        self._cache = cache

    def _key(self, novel_id: str, chapter_ids_hash: str) -> str:
        return f"{self.KEY_PREFIX}{novel_id}:{chapter_ids_hash}"

    @staticmethod
    def hash_chapter_ids(chapter_ids: list[str]) -> str:
        """Create stable hash from sorted chapter IDs."""
        import hashlib
        sorted_ids = ",".join(sorted(chapter_ids))
        return hashlib.sha256(sorted_ids.encode()).hexdigest()[:12]

    async def get(self, novel_id: str, chapter_ids: list[str]) -> str | None: ...
    async def set(self, novel_id: str, chapter_ids: list[str], value: str) -> None: ...
    async def delete(self, novel_id: str, chapter_ids: list[str]) -> None: ...
```

### 7.3 Word Count Validation

The service enforces word count constraints before running analysis:

```python
MIN_WORDS = 1000  # Too short for meaningful feedback
MAX_WORDS = 10000  # Token limit safety
```

If word count is below minimum → return 422 with message.
If word count exceeds maximum → return 422 suggesting to analyze fewer chapters.

---

## 8. Core Layer — Agent, Types, Prompts

### 8.1 Agent Design

The `BetaReaderAgent` follows the exact pattern of `WorldbuildingAgent`:

| Aspect | Phase 1 | Phase 2 |
|--------|---------|---------|
| **Output type** | `BetaReaderPhase1Output` | `BetaReaderPhase2Output` |
| **Deps** | `BetaReaderDeps` (full context) | `BetaReaderDeps` (with `deepdive_category` set) |
| **Prompt** | `analysis/en/beta_reader/system.md` | `analysis/en/beta_reader_deepdive/system.md` |
| **Model** | From `ModelRegistry` (BETA_READ intent) | From `ModelRegistry` (BETA_READ intent, possibly different config) |
| **Run method** | `agent.run_phase1(prompt, deps)` | `agent.run_phase2(prompt, deps, model)` |

Key differences from WorldbuildingAgent:
- **No tool composition**: BetaReaderAgent doesn't need KBAgent tools. It analyzes
  text, it doesn't query the KB graph during analysis.
- **Simpler deps**: No entity summaries or relationship maps. Context is assembled
  by the service and passed as a flat string.
- **Two distinct prompts**: Phase 1 and Phase 2 have completely different system
  prompts (unlike Worldbuilding which uses the same prompt structure).

### 8.2 Prompt Design

#### Phase 1: `analysis/en/beta_reader/system.md`

```
## System Role
You are an experienced beta reader providing honest, constructive feedback
on creative writing. You read chapters from a reader's perspective, noting
what works, what doesn't, and what would improve the reading experience.

## Analysis Framework

Analyze the chapter across these categories:

### Plot
- Clear goals and conflicts
- Plot progression and momentum
- Questions and curiosity gaps
- Satisfying developments or cliffhangers
- Plot holes or inconsistencies

### Character
- Believability and consistency
- Motivation clarity
- Emotional depth
- Dialogue naturalness
- Character voice distinctness

### Prose
- Clarity and readability
- Show vs tell balance
- Description effectiveness
- Sentence variety
- Word choice precision

### Pacing
- Scene rhythm and flow
- Tension build and release
- Dragging sections
- Rushed moments
- Chapter structure effectiveness

### Reader Experience
- Engagement level
- Confusion points
- Emotional resonance
- Page-turner quality
- Immersion

## Context Available
{{chapter_text}}         ← The chapter(s) to analyze
{{chapter_titles}}       ← Chapter titles
{{word_count}}           ← Total word count
{{previous_summaries}}   ← Summaries of previous chapters (for continuity)
{{kb_characters}}        ← Character names + short descriptions from KB
{{kb_locations}}         ← Location names + short descriptions from KB
{{genre}}                ← Genre (if specified, adjusts expectations)
{{focus_categories}}     ← Categories to focus on (null = all)

## Severity Guidelines
- **critical**: Will significantly impair reader experience. Must address.
- **moderate**: Noticeable issue that some readers will find distracting.
- **minor**: Small improvement opportunity. Nice to address.

## Output Format
Respond with a structured JSON object containing:
- `strengths`: Array of { category, title, description, text_excerpt }
- `feedback`: Array of { category, severity, location, title, description, suggestion, text_excerpt }
- `questions`: Array of { category, location, question, context }
- `overall`: { summary, reader_engagement (1-10), emotional_impact (1-10),
    pacing_score (1-10), prose_quality (1-10), plot_progression (1-10),
    character_development (1-10) }

Be specific. Reference actual text passages. Give actionable suggestions.
Balance honesty with encouragement.
```

#### Phase 2: `analysis/en/beta_reader_deepdive/system.md`

```
## System Role
You are providing a deep-dive analysis on a specific aspect of creative
writing. You have already provided a broad analysis (Phase 1). Now focus
on one category and provide detailed, text-level feedback.

## Deep-Dive Category
{{deepdive_category}}

## Previous Analysis Summary
Strengths identified: {{phase1_strengths_summary}}
Issues identified: {{phase1_feedback_summary}}

## Chapter Text
{{chapter_text}}

## Instructions
For the category "{{deepdive_category}}":

1. Identify specific text passages that need attention
2. Explain WHY each passage works or doesn't work
3. Provide concrete revision suggestions with before/after examples
4. Score this category specifically (1-10)

## Output Format
Respond with a structured JSON:
- `detailed_feedback`: Array of { category, severity, location, title,
    description, suggestion, text_excerpt }
- `revision_suggestions`: Array of concrete revision suggestions as strings
- `category_score`: 1-10 score for this specific category

Be granular. Reference exact paragraphs or sentences. Give rewrites.
```

### 8.3 Prompt Composer Integration

The `BETA_READ` intent is already mapped in `composer.py`:
- Category: `analysis` (line 46)
- Mode: `beta_reader` (line 76)

For Phase 2 deep-dive, we add a second mode mapping:

```python
# In composer.py _INTENT_TO_MODE:
# Phase 2 uses a different mode path
# The service resolves this by building a custom PromptContext
# with mode="beta_reader_deepdive" for Phase 2
```

The service builds the prompt context differently for each phase:
- Phase 1: `PromptContext(intent=BETA_READ, mode="beta_reader", ...)`
- Phase 2: `PromptContext(intent=BETA_READ, mode="beta_reader_deepdive", ...)`

Both map to `category="analysis"`, but different mode directories.

---

## 9. Backend Layer — Service, Cache, Router, DI

### 9.1 Service — `beta_reader_service.py`

```python
"""Beta reader analysis service — business logic orchestration.

Orchestrates: validation → cache → context assembly → agent → cache → response.
No DB queries — delegated to repositories via context_assembler.
"""

class BetaReaderService:
    """Implements BetaReaderProtocol.

    Args:
        context_assembler: Builds BetaReaderDeps from chapter + KB data.
        cache: Redis-backed result cache (30min TTL).
        registry: ModelRegistry for LLM model resolution.
        config: Default ResolvedModelConfig for BETA_READ intent.
        composer: PromptComposer for system prompt assembly.
    """

    def __init__(
        self,
        context_assembler: ContextAssembler,
        cache: BetaReaderCache,
        registry: ModelRegistry,
        config: ResolvedModelConfig,
        composer: PromptComposer,
    ) -> None:
        self._assembler = context_assembler
        self._cache = cache
        self._registry = registry
        self._config = config
        self._composer = composer

    async def analyze(
        self,
        *,
        novel_id: UUID,
        user_id: UUID,
        request: BetaReaderRequest,
    ) -> BetaReaderResponse:
        """Phase 1: Full chapter analysis."""
        # 1. Validate
        self._validate_request(request)

        # 2. Check cache
        if not request.refresh:
            cached = await self._cache.get(str(novel_id), request.chapter_ids)
            if cached is not None:
                return BetaReaderResponse.model_validate_json(cached)

        # 3. Assemble context
        deps = await self._assembler.build_context(
            novel_id=novel_id,
            chapter_ids=[UUID(cid) for cid in request.chapter_ids],
        )

        # 4. Override focus categories from request
        if request.categories:
            deps.focus_categories = [c.value for c in request.categories]

        # 5. Compose prompt
        ctx = PromptContext(
            language=deps.language,
            mode="beta_reader",
            project_title="",
        )
        composed = await self._composer.build(LLMIntent.BETA_READ, ctx)

        # 6. Get model
        model = await self._registry.get_model(self._config)

        # 7. Run agent
        agent = BetaReaderAgent(model=model, system_prompt=composed.system)
        user_prompt = self._build_user_prompt(deps)
        result = await agent.run_phase1(user_prompt, deps=deps)

        # 8. Map to response
        response = self._map_phase1_response(
            result, novel_id, request.chapter_ids, deps.word_count,
        )

        # 9. Cache result
        cache_key = BetaReaderCache.hash_chapter_ids(request.chapter_ids)
        response.cache_key = cache_key
        await self._cache.set(
            str(novel_id), request.chapter_ids,
            response.model_dump_json(),
        )

        return response

    async def deep_dive(
        self,
        *,
        novel_id: UUID,
        user_id: UUID,
        request: BetaReaderDeepDiveRequest,
    ) -> BetaReaderDeepDiveResponse:
        """Phase 2: Category deep-dive."""
        # 1. Retrieve Phase 1 from cache for context
        phase1_json = await self._cache.get(
            str(novel_id), request.chapter_ids,
        )
        if phase1_json is None:
            raise AnalysisError("Phase 1 analysis not found. Run full analysis first.")

        phase1 = BetaReaderResponse.model_validate_json(phase1_json)

        # 2. Assemble context (same chapters)
        deps = await self._assembler.build_context(
            novel_id=novel_id,
            chapter_ids=[UUID(cid) for cid in request.chapter_ids],
        )
        deps.deepdive_category = request.category.value
        deps.phase1_strengths_summary = "; ".join(
            s.title for s in phase1.strengths
        )
        deps.phase1_feedback_summary = "; ".join(
            f.title for f in phase1.feedback[:10]
        )

        # 3. Compose Phase 2 prompt
        ctx = PromptContext(language=deps.language, mode="beta_reader_deepdive")
        composed = await self._composer.build(LLMIntent.BETA_READ, ctx)

        # 4. Get model
        model = await self._registry.get_model(self._config)

        # 5. Run Phase 2
        agent = BetaReaderAgent(model=model, system_prompt=composed.system)
        user_prompt = self._build_deepdive_prompt(deps)
        result = await agent.run_phase2(user_prompt, deps=deps, model=model)

        # 6. Map to response
        return self._map_phase2_response(result, novel_id, request.category)
```

### 9.2 Context Assembler — `context_assembler.py`

```python
"""Context assembly for analysis features.

Gathers chapter text, previous chapter summaries, KB entries, and novel
metadata into BetaReaderDeps for the agent.
"""

class ContextAssembler:
    """Assembles context for beta reader analysis.

    Args:
        chapter_repo: Chapter repository for text retrieval.
        kb_repo: KB repository for character/location lookup.
        novel_repo: Novel repository for genre metadata.
    """

    def __init__(
        self,
        chapter_repo: ChapterRepositoryProtocol,
        kb_repo: KBRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol,
    ) -> None:
        self._chapter_repo = chapter_repo
        self._kb_repo = kb_repo
        self._novel_repo = novel_repo

    async def build_context(
        self,
        novel_id: UUID,
        chapter_ids: list[UUID],
    ) -> BetaReaderDeps:
        """Assemble BetaReaderDeps from database.

        Steps:
          1. Fetch all chapters for the novel
          2. Identify target chapters (by IDs) and previous chapters
          3. Fetch KB entries (characters, locations)
          4. Fetch novel metadata (genre)
          5. Build and return BetaReaderDeps
        """
        ...

    async def _fetch_previous_summaries(
        self,
        chapters: list[Chapter],
        target_chapters: list[Chapter],
    ) -> list[str]:
        """Get summaries of up to 3 chapters before the targets."""
        ...

    async def _fetch_kb_context(
        self,
        novel_id: UUID,
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        """Fetch character and location entries from KB.

        Returns:
            Tuple of (characters, locations) as short dicts.
        """
        ...
```

### 9.3 Cache — `beta_reader_cache.py`

Follows the exact pattern of `improve_cache.py` (see Section 7.2 above).

### 9.4 Router — `router.py`

```python
"""Analysis API routes — thin delegation (RULE-06).

All business logic is in beta_reader_service.py.
This router only handles HTTP request/response mapping.
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from narrare.analysis.contracts import (
    BetaReaderDeepDiveRequest,
    BetaReaderDeepDiveResponse,
    BetaReaderRequest,
    BetaReaderResponse,
)
from narrare.analysis.dependencies import get_beta_reader_service

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/beta-reader", response_model=BetaReaderResponse)
async def analyze_chapter(
    novel_id: UUID,
    request: BetaReaderRequest,
    user_id: UUID,
    service: BetaReaderProtocol = Depends(get_beta_reader_service),
) -> BetaReaderResponse:
    """Run beta reader analysis on chapter(s).

    Phase 1: Comprehensive feedback across all categories.
    """
    return await service.analyze(
        novel_id=novel_id,
        user_id=user_id,
        request=request,
    )


@router.post("/beta-reader/deep-dive", response_model=BetaReaderDeepDiveResponse)
async def deep_dive_category(
    novel_id: UUID,
    request: BetaReaderDeepDiveRequest,
    user_id: UUID,
    service: BetaReaderProtocol = Depends(get_beta_reader_service),
) -> BetaReaderDeepDiveResponse:
    """Run Phase 2 deep-dive on a specific category.

    Requires a prior Phase 1 analysis (cache_key from Phase 1 response).
    """
    return await service.deep_dive(
        novel_id=novel_id,
        user_id=user_id,
        request=request,
    )
```

Estimated: ~80 lines (well under 150-line router limit).

### 9.5 Dependencies — `dependencies.py`

```python
"""Analysis dependency injection factories."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep

if TYPE_CHECKING:
    from narrare.analysis.beta_reader_service import BetaReaderService


def get_beta_reader_service(session: SessionDep) -> BetaReaderService:
    """Create a BetaReaderService with injected dependencies.

    Production wiring:
    - ModelRegistry for LLM model resolution
    - PromptComposer for system prompt assembly
    - ChapterRepository + KBRepository + NovelRepository for context
    - RedisSessionCache for result caching (30min TTL)
    """
    from narrare._app.config import get_settings
    from narrare._app.dependencies import get_composer, get_model_registry
    from narrare.analysis.beta_reader_cache import BetaReaderCache
    from narrare.analysis.beta_reader_service import BetaReaderService
    from narrare.analysis.context_assembler import ContextAssembler
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.cache.redis_client import RedisSessionCache
    from narrare_core.llm.intents import ResolvedModelConfig

    registry = get_model_registry()
    composer = get_composer()
    config = ResolvedModelConfig(
        provider_name="default",
        model_id="default",
        temperature=0.7,
        max_tokens=4096,
    )

    # Repositories
    chapter_repo = ChapterRepository(session)
    kb_repo = KBRepository(session)
    novel_repo = NovelRepository(session)

    # Context assembler
    assembler = ContextAssembler(
        chapter_repo=chapter_repo,
        kb_repo=kb_repo,
        novel_repo=novel_repo,
    )

    # Redis-backed cache with 30min TTL
    settings = get_settings()
    redis_cache = RedisSessionCache(settings.redis_url)
    beta_cache = BetaReaderCache(redis_cache)

    return BetaReaderService(
        context_assembler=assembler,
        cache=beta_cache,
        registry=registry,
        config=config,
        composer=composer,
    )
```

Estimated: ~80 lines (well under limits).

### 9.6 Error Handling

All errors follow RULE-11 (no silent failures):

```python
class AnalysisError(Exception):
    """Base exception for analysis operations."""

class ChapterNotFoundError(AnalysisError):
    """Chapter not found or not accessible."""

class InsufficientWordCountError(AnalysisError):
    """Chapter is too short for meaningful analysis."""

class ExcessiveWordCountError(AnalysisError):
    """Chapter(s) exceed token limit for analysis."""

class CacheRetrievalError(AnalysisError):
    """Phase 1 cache missing for deep-dive request."""
```

Service-level error handling pattern:

```python
try:
    deps = await self._assembler.build_context(...)
except Exception as exc:
    logger.error("context_assembly_failed", novel_id=str(novel_id), error=str(exc))
    raise AnalysisError("Failed to assemble analysis context") from exc
```

---

## 10. Frontend Layer — Panel, API, Hooks, i18n

### 10.1 Component Architecture

```
EditorView.tsx
├── [existing toolbar] + BetaReaderTrigger (new button)
└── [existing right panel area]
    ├── [existing panels: GenerationPanel, SessionPanel, etc.]
    └── BetaReaderPanel (new collapsible panel)
         ├── Header: "Beta Reader Analysis" + Close + Refresh buttons
         ├── Loading state: animated analysis spinner
         ├── Error state: error message + retry
         ├── Results state:
         │   ├── Tab bar: Strengths | Issues | Questions | Overall
         │   ├── Tab content:
         │   │   ├── Strengths tab: list of BetaReaderStrength cards
         │   │   ├── Issues tab: severity-grouped BetaFeedbackItem cards
         │   │   ├── Questions tab: list of BetaReaderQuestion cards
         │   │   └── Overall tab: ScoreRadar + summary text
         │   └── Footer: "Deep Dive" button (active when on a category tab)
         └── FeedbackCard (reusable)
              ├── Severity badge (color-coded)
              ├── Category badge
              ├── Title + description
              ├── Text excerpt (collapsible)
              └── Suggestion (if present)
```

### 10.2 State Management

```typescript
// editorStore.ts additions
interface EditorState {
  // ... existing state ...

  // Beta reader state
  betaReaderPanelOpen: boolean;
  betaReaderResult: BetaReaderResponse | null;
  betaReaderDeepDiveResult: BetaReaderDeepDiveResponse | null;
  betaReaderLoading: boolean;

  toggleBetaReaderPanel: () => void;
  setBetaReaderResult: (result: BetaReaderResponse | null) => void;
  setBetaReaderDeepDiveResult: (result: BetaReaderDeepDiveResponse | null) => void;
  setBetaReaderLoading: (loading: boolean) => void;
}
```

### 10.3 API Client — `lib/api/analysis.ts`

```typescript
/**
 * Analysis API client — typed wrappers for analysis endpoints.
 *
 * Field names MUST match backend Pydantic schemas (RULE-17).
 */

import { fetchApi } from "./client";

// --- Types (matching backend schemas) ---

export type FeedbackSeverity = "critical" | "moderate" | "minor";
export type FeedbackCategory = "plot" | "character" | "prose" | "pacing" | "experience";

export interface BetaFeedbackItem {
  category: FeedbackCategory;
  severity: FeedbackSeverity;
  location: string | null;
  title: string;
  description: string;
  suggestion: string | null;
  text_excerpt: string | null;
}

export interface BetaReaderStrength {
  category: FeedbackCategory;
  title: string;
  description: string;
  text_excerpt: string | null;
}

export interface BetaReaderQuestion {
  category: FeedbackCategory;
  location: string | null;
  question: string;
  context: string | null;
}

export interface BetaReaderOverallAssessment {
  summary: string;
  reader_engagement: number;
  emotional_impact: number;
  pacing_score: number;
  prose_quality: number;
  plot_progression: number;
  character_development: number;
}

export interface BetaReaderRequest {
  chapter_ids: string[];
  categories?: FeedbackCategory[];
  phase: "full" | "deepdive";
  deepdive_category?: FeedbackCategory;
  refresh?: boolean;
}

export interface BetaReaderResponse {
  novel_id: string;
  chapter_ids: string[];
  total_word_count: number;
  strengths: BetaReaderStrength[];
  feedback: BetaFeedbackItem[];
  questions: BetaReaderQuestion[];
  overall: BetaReaderOverallAssessment;
  analyzed_at: string;
  cache_key: string;
}

export interface BetaReaderDeepDiveRequest {
  chapter_ids: string[];
  category: FeedbackCategory;
  cache_key: string;
}

export interface BetaReaderDeepDiveResponse {
  novel_id: string;
  category: FeedbackCategory;
  detailed_feedback: BetaFeedbackItem[];
  revision_suggestions: string[];
  category_score: number;
  analyzed_at: string;
}

// --- API functions ---

export const analysisApi = {
  /** Run Phase 1 beta reader analysis. */
  analyze: (novelId: string, request: BetaReaderRequest) =>
    fetchApi<BetaReaderResponse>(
      `/analysis/beta-reader?novel_id=${novelId}`,
      { method: "POST", body: JSON.stringify(request) },
    ),

  /** Run Phase 2 deep-dive on a specific category. */
  deepDive: (novelId: string, request: BetaReaderDeepDiveRequest) =>
    fetchApi<BetaReaderDeepDiveResponse>(
      `/analysis/beta-reader/deep-dive?novel_id=${novelId}`,
      { method: "POST", body: JSON.stringify(request) },
    ),
};
```

### 10.4 TanStack Query Hooks — `lib/hooks/useBetaReader.ts`

```typescript
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { analysisApi, type BetaReaderRequest, type BetaReaderDeepDiveRequest,
         type BetaReaderResponse, type BetaReaderDeepDiveResponse } from "@/lib/api/analysis";

const analysisKeys = {
  all: (novelId: string) => ["analysis", novelId] as const,
  betaReader: (novelId: string, chapterIds: string[]) =>
    ["analysis", novelId, "beta-reader", ...chapterIds.sort()] as const,
};

export function useBetaReaderAnalyze(novelId: string) {
  const queryClient = useQueryClient();

  return useMutation<BetaReaderResponse, Error, BetaReaderRequest>({
    mutationFn: (request) => analysisApi.analyze(novelId, request),
    onSuccess: (data, variables) => {
      queryClient.setQueryData(
        analysisKeys.betaReader(novelId, variables.chapter_ids),
        data,
      );
    },
  });
}

export function useBetaReaderDeepDive(novelId: string) {
  return useMutation<BetaReaderDeepDiveResponse, Error, BetaReaderDeepDiveRequest>({
    mutationFn: (request) => analysisApi.deepDive(novelId, request),
  });
}
```

### 10.5 i18n Key Structure — `messages/en/analysis.json`

```json
{
  "title": "Beta Reader",
  "trigger": "Beta Reader Analysis",
  "triggerTooltip": "Get AI-powered feedback as if from a beta reader",
  "loading": "Reading your chapter...",
  "loadingSubtext": "Analyzing plot, characters, pacing, and prose",
  "error": "Analysis failed",
  "retry": "Try Again",
  "refresh": "Refresh Analysis",
  "close": "Close",
  "deepDive": "Deep Dive",
  "deepDiveLoading": "Analyzing {category} in detail...",
  "tabs": {
    "strengths": "Strengths",
    "issues": "Issues",
    "questions": "Questions",
    "overall": "Overall"
  },
  "severity": {
    "critical": "Critical",
    "moderate": "Moderate",
    "minor": "Minor"
  },
  "categories": {
    "plot": "Plot",
    "character": "Character",
    "prose": "Prose",
    "pacing": "Pacing",
    "experience": "Experience"
  },
  "overall": {
    "summary": "Summary",
    "scores": "Scores",
    "engagement": "Reader Engagement",
    "emotionalImpact": "Emotional Impact",
    "pacing": "Pacing",
    "proseQuality": "Prose Quality",
    "plotProgression": "Plot Progression",
    "characterDev": "Character Development"
  },
  "validation": {
    "tooShort": "Chapter is too short for meaningful analysis (minimum 1,000 words).",
    "tooLong": "Selected chapters exceed the analysis limit (maximum 10,000 words). Try fewer chapters.",
    "noChapters": "Select at least one chapter to analyze."
  },
  "empty": {
    "strengths": "No strengths identified yet.",
    "issues": "No issues found. Great job!",
    "questions": "No reader questions identified."
  }
}
```

### 10.6 Editor Integration Points

The `BetaReaderTrigger` button is added to the editor toolbar alongside
existing tools (generation, extraction, etc.):

```typescript
// In EditorView.tsx toolbar area:
<BetaReaderTrigger
  novelId={novelId}
  chapterId={activeChapterId}
  onClick={() => {
    toggleBetaReaderPanel();
  }}
/>
```

The `BetaReaderPanel` renders in the right panel area (same location as
GenerationPanel, SessionPanel, etc.):

```typescript
// In EditorView.tsx panel area:
{betaReaderPanelOpen && (
  <BetaReaderPanel
    novelId={novelId}
    chapterIds={[activeChapterId]}
    onClose={() => toggleBetaReaderPanel()}
  />
)}
```

---

## 11. Testing Plan

### 11.1 Core Layer Tests

| Test File | What It Tests | Est. Tests |
|-----------|--------------|-----------|
| `tests/unit/core/agents/test_beta_reader_agent.py` | Agent Phase 1 output parsing, Phase 2 output parsing, partial output handling, edge cases | 8 |
| `tests/unit/core/prompts/test_beta_reader_prompts.py` | Prompt template exists, variable substitution, Phase 1 vs Phase 2 mode | 4 |

### 11.2 Backend Layer Tests

| Test File | What It Tests | Est. Tests |
|-----------|--------------|-----------|
| `tests/unit/api/narrare/analysis/test_context_assembler.py` | Context assembly: chapter text joining, previous chapter fetching, KB entry extraction, genre resolution, word count calculation | 10 |
| `tests/unit/api/narrare/analysis/test_beta_reader_service.py` | Service orchestration: cache hit, cache miss, agent execution, response mapping, error handling, word count validation, Phase 2 cache miss error | 12 |
| `tests/unit/api/narrare/analysis/test_beta_reader_cache.py` | Cache: set/get/delete, key hashing, TTL, graceful degradation | 6 |
| `tests/integration/api/narrare/analysis/test_router_beta_reader.py` | Router: POST /analysis/beta-reader, POST /analysis/beta-reader/deep-dive, validation errors, auth | 6 |

### 11.3 Frontend Layer Tests

| Test File | What It Tests | Est. Tests |
|-----------|--------------|-----------|
| `packages/web/components/studio/analysis/__tests__/BetaReaderPanel.test.tsx` | Panel renders, tabs switch, feedback cards display, severity colors, loading/error states | 8 |
| `packages/web/components/studio/analysis/__tests__/FeedbackCard.test.tsx` | Card renders all fields, collapsible excerpt, severity badge | 4 |
| `packages/web/__tests__/i18n-namespace-registry.test.ts` | Verify "analysis" namespace registered (RULE-16) | 1 |

### 11.4 Test Count Summary

| Layer | Unit Tests | Integration Tests | Total |
|-------|-----------|-------------------|-------|
| Core | 12 | 0 | 12 |
| Backend | 28 | 6 | 34 |
| Frontend | 13 | 0 | 13 |
| **Total** | **53** | **6** | **59** |

---

## 12. RULE-XX Compliance Matrix

| Rule | Status | How ANAL-001 Satisfies It |
|------|--------|---------------------------|
| **RULE-01b** | ✅ | All LLM calls through `BetaReaderAgent` (extends `NarrareAgent`). Model from `ModelRegistry`. No direct `pydantic_ai.Agent` or `openai` imports outside `core/agents/`. |
| **RULE-02** | ✅ | Prompts built by `PromptComposer.build(BETA_READ, context)`. System prompts in `prompts/_bundled/analysis/en/beta_reader/`. No f-string prompts in service. |
| **RULE-03** | ✅ | `BetaReaderProtocol` in `analysis/contracts.py` written before implementation. Agent types in `beta_reader_types.py` before agent. |
| **RULE-04** | ✅ | File sizes respected: service ~250 lines, router ~80 lines, cache ~80 lines, context_assembler ~150 lines, contracts ~200 lines. If service grows → extract `beta_reader_mapper.py`. |
| **RULE-05** | ✅ | Module boundaries: `analysis/` owns its own contracts, service, cache, router. No cross-module `_internal` imports. |
| **RULE-06** | ✅ | One responsibility per file: router (delegates), service (orchestrates), cache (stores), context_assembler (gathers data), contracts (defines interfaces). |
| **RULE-07** | ✅ | Dependency direction: router → service → context_assembler → repos → DB. Service → ModelRegistry + PromptComposer (core/ via DI). No imports from apps/ in core/. |
| **RULE-08** | ✅ | Redis access only through `RedisSessionCache` (in `core/cache/`). No direct Redis imports in analysis module. |
| **RULE-09** | ✅ | All public functions fully typed. No `Any` in contracts. All Pydantic models have complete type annotations. |
| **RULE-10** | ✅ | Tests planned: 53 unit + 6 integration = 59 total. Coverage targets: core 90%, api 80%. |
| **RULE-11** | ✅ | All exception paths: log with structlog, raise typed `AnalysisError` subclasses. No bare `except: pass`. Cache errors gracefully degrade (log + continue). |
| **RULE-12** | ✅ | Service layer (`BetaReaderProtocol`) is the only public API. Callable from WebUI, MCP, A2A, CLI. Router is one client. |
| **RULE-13** | ✅ | Beta reader is POST → full response (no streaming). If streaming needed later, `analyze(stream=True)` follows RULE-13 pattern without breaking callers. |
| **RULE-14** | ✅ | No database model changes. No new tables. Uses existing Chapter, KBEntry, Novel models. |
| **RULE-16** | ✅ | Frontend i18n: `"analysis"` namespace registered in `request.ts`. Translation files in all 3 locales (`en`, `de`, `fr`). |
| **RULE-17** | ✅ | API-Frontend contract: TypeScript types in `analysis.ts` match Pydantic schemas in `contracts.py` field-for-field. |
| **RULE-18** | ✅ | No hardcoded configuration. Model resolved via `ModelRegistry` + `ResolvedModelConfig` from DI. |
| **RULE-19** | ✅ | `SessionDep` used in `dependencies.py` factory. No bare `AsyncSession`. |
| **RULE-20** | ✅ | Complete implementation: no stubs, no TODOs, no half-implementations. Both Phase 1 and Phase 2 fully specified. |

---

## 13. Work Plan

### 13.1 Layer Ordering

Implementation follows the dependency chain: **Core → Backend → Frontend**.

| Phase | Step | Task | Files | Depends On | Specialist | Est. Complexity |
|-------|------|------|-------|------------|------------|-----------------|
| **Core** | C1 | Define agent types | `beta_reader_types.py` | — | NarrareBackend | ★☆☆ |
| **Core** | C2 | Define agent | `beta_reader_agent.py` | C1 | NarrareBackend | ★★☆ |
| **Core** | C3 | Create Phase 1 prompt | `analysis/en/beta_reader/system.md` | — | NarrareCore | ★★☆ |
| **Core** | C4 | Create Phase 2 prompt | `analysis/en/beta_reader_deepdive/system.md` | — | NarrareCore | ★★☆ |
| **Core** | C5 | Export agent in `__init__.py` | `agents/__init__.py` (modify) | C2 | NarrareBackend | ★☆☆ |
| **Core** | C6 | Write agent unit tests | `tests/unit/core/agents/test_beta_reader_agent.py` | C2 | NarrareTesting | ★★☆ |
| **Backend** | B1 | Define contracts | `analysis/contracts.py` | — | NarrareBackend | ★★☆ |
| **Backend** | B2 | Create module init | `analysis/__init__.py` | B1 | NarrareBackend | ★☆☆ |
| **Backend** | B3 | Implement cache | `analysis/beta_reader_cache.py` | — | NarrareBackend | ★☆☆ |
| **Backend** | B4 | Implement context assembler | `analysis/context_assembler.py` | B1 | NarrareBackend | ★★★ |
| **Backend** | B5 | Implement service | `analysis/beta_reader_service.py` | B1, B3, B4, C2 | NarrareBackend | ★★★ |
| **Backend** | B6 | Implement DI factories | `analysis/dependencies.py` | B3, B4, B5 | NarrareBackend | ★★☆ |
| **Backend** | B7 | Implement router | `analysis/router.py` | B1, B6 | NarrareBackend | ★☆☆ |
| **Backend** | B8 | Write service unit tests | `tests/unit/.../test_beta_reader_service.py` | B5 | NarrareTesting | ★★★ |
| **Backend** | B9 | Write context assembler tests | `tests/unit/.../test_context_assembler.py` | B4 | NarrareTesting | ★★☆ |
| **Backend** | B10 | Write cache tests | `tests/unit/.../test_beta_reader_cache.py` | B3 | NarrareTesting | ★☆☆ |
| **Backend** | B11 | Write router integration tests | `tests/integration/.../test_router_beta_reader.py` | B7 | NarrareTesting | ★★☆ |
| **Frontend** | F1 | Create API types + client | `lib/api/analysis.ts` | B1 | NarrareFrontend | ★☆☆ |
| **Frontend** | F2 | Create TanStack Query hooks | `lib/hooks/useBetaReader.ts` | F1 | NarrareFrontend | ★☆☆ |
| **Frontend** | F3 | Add i18n translations (3 locales) | `messages/{en,de,fr}/analysis.json` | — | NarrareDocs | ★☆☆ |
| **Frontend** | F4 | Register i18n namespace | `lib/i18n/request.ts` (modify) | F3 | NarrareFrontend | ★☆☆ |
| **Frontend** | F5 | Create FeedbackCard component | `analysis/FeedbackCard.tsx` | F1 | NarrareFrontend | ★★☆ |
| **Frontend** | F6 | Create ScoreRadar component | `analysis/ScoreRadar.tsx` | F1 | NarrareFrontend | ★★☆ |
| **Frontend** | F7 | Create BetaReaderPanel | `analysis/BetaReaderPanel.tsx` | F1, F2, F5, F6 | NarrareFrontend | ★★★ |
| **Frontend** | F8 | Create BetaReaderTrigger | `analysis/BetaReaderTrigger.tsx` | F2 | NarrareFrontend | ★☆☆ |
| **Frontend** | F9 | Add editor store state | `stores/editorStore.ts` (modify) | F1 | NarrareFrontend | ★☆☆ |
| **Frontend** | F10 | Integrate into EditorView | `EditorView.tsx` (modify) | F7, F8, F9 | NarrareFrontend | ★★☆ |
| **Frontend** | F11 | Write component tests | `analysis/__tests__/BetaReaderPanel.test.tsx` | F7 | NarrareTesting | ★★☆ |

### 13.2 Dependency Graph

```
C1 ──→ C2 ──→ C5
  │            │
  │            ▼
  │         C6 (agent tests)
  │
C3 (Phase 1 prompt) ──┐
C4 (Phase 2 prompt) ──┤
                       ▼
B1 ──→ B2 (init)
  │
  ├──→ B3 (cache) ──→ B10 (cache tests)
  │
  ├──→ B4 (assembler) ──→ B9 (assembler tests)
  │       │
  │       ▼
  │    B5 (service) ──→ B8 (service tests)
  │       │
  │       ▼
  │    B6 (DI) ──→ B7 (router) ──→ B11 (router tests)
  │
  └──→ F1 (API types) ──→ F2 (hooks)
                           │
         F3 + F4 (i18n)    │
         F5 (FeedbackCard) │
         F6 (ScoreRadar)   │
                            ▼
                          F7 (Panel) ──→ F8 (Trigger)
                            │
                            ▼
                          F9 (store) ──→ F10 (EditorView integration)
                            │
                            ▼
                          F11 (component tests)
```

### 13.3 Parallelization Opportunities

| Batch | Tasks | Specialist |
|-------|-------|------------|
| **Batch 1** | C1, C3, C4, B1, B2, B3, F3 | Core types + prompts + contracts + cache + i18n |
| **Batch 2** | C2, C5, C6, B4 | Agent + export + agent tests + context assembler |
| **Batch 3** | B5, B9, B10 | Service + assembler tests + cache tests |
| **Batch 4** | B6, B7, B8, B11, F1, F2, F4 | DI + router + service tests + integration tests + API types + hooks + i18n register |
| **Batch 5** | F5, F6, F8, F9 | Frontend components + store state |
| **Batch 6** | F7, F10, F11 | Panel integration + EditorView + component tests |

### 13.4 Estimated Total Complexity

| Layer | New Files | Modified Files | Est. Lines | Tests | Complexity |
|-------|-----------|----------------|-----------|-------|------------|
| Core | 4 | 1 | ~520 lines | 12 | ★★☆ |
| Backend | 7 | 0 | ~840 lines | 34 | ★★★ |
| Frontend | 11 | 4 | ~990 lines | 13 | ★★★ |
| **Total** | **22 new** | **5 mod** | **~2350 lines** | **59 tests** | |

### 13.5 Definition of Done

- [ ] `BetaReaderDeps`, `BetaReaderPhase1Output`, `BetaReaderPhase2Output` defined in `beta_reader_types.py`
- [ ] `BetaReaderAgent` with `run_phase1()` and `run_phase2()` in `beta_reader_agent.py`
- [ ] Phase 1 system prompt in `analysis/en/beta_reader/system.md`
- [ ] Phase 2 system prompt in `analysis/en/beta_reader_deepdive/system.md`
- [ ] `BetaReaderProtocol` with `analyze()` and `deep_dive()` in `analysis/contracts.py`
- [ ] `BetaReaderRequest`, `BetaReaderResponse`, `BetaReaderDeepDiveRequest`, `BetaReaderDeepDiveResponse` schemas
- [ ] `BetaReaderCache` with 30min TTL, key prefix `analysis:beta:`
- [ ] `ContextAssembler` builds `BetaReaderDeps` from chapters + KB + novel metadata
- [ ] `BetaReaderService.analyze()` orchestrates: validate → cache → assemble → agent → cache → response
- [ ] `BetaReaderService.deep_dive()` retrieves Phase 1 from cache, runs Phase 2 agent
- [ ] `POST /api/v1/analysis/beta-reader` endpoint returns `BetaReaderResponse`
- [ ] `POST /api/v1/analysis/beta-reader/deep-dive` endpoint returns `BetaReaderDeepDiveResponse`
- [ ] Word count validation: min 1000, max 10000 words
- [ ] TypeScript types in `analysis.ts` match Pydantic schemas (RULE-17)
- [ ] TanStack Query hooks: `useBetaReaderAnalyze`, `useBetaReaderDeepDive`
- [ ] `BetaReaderPanel` with tabs: Strengths, Issues, Questions, Overall
- [ ] `FeedbackCard` with severity badge, category badge, collapsible excerpt
- [ ] `ScoreRadar` visualization for overall assessment
- [ ] `BetaReaderTrigger` in editor toolbar
- [ ] `"analysis"` i18n namespace registered in `request.ts` (RULE-16)
- [ ] Translation files in `en`, `de`, `fr` locales
- [ ] 59 tests passing (12 core + 34 backend + 13 frontend)
- [ ] All RULE-XX constraints satisfied (see compliance matrix)
- [ ] No workarounds, no TODOs, no half-implementations

---

## ARCHITECTURE HANDOFF

### Spec
- **Typ**: Feature Spec + ADR (combined)
- **Pfad**: `docs/architecture/implementation-plans/ANAL-001-beta-reader-simulation.md`
- **Status**: Draft — awaiting review and user approval

### Root Cause
Writers lack automated reader-perspective feedback within the tool. The generation-only
infrastructure produces text but cannot evaluate it. ANAL-001 fills this gap by
simulating a beta reader's feedback using the existing LLM agent infrastructure.

### Alternatives Considered
- **Option A** (Extend Writing Service): REJECTED — violates RULE-06, wrong domain
- **Option B** (Direct LLM, No Agent): REJECTED — violates RULE-01b, no structured output
- **Option C** (Two-Phase Hybrid Agent): SELECTED — correct separation, proven pattern

### Implementation Plan

| Step | Layer | Specialist |
|------|-------|------------|
| C1-C6 | Core (types, agent, prompts) | NarrareBackend + NarrareCore |
| B1-B11 | Backend (contracts, service, cache, router, DI, tests) | NarrareBackend + NarrareTesting |
| F1-F11 | Frontend (API, hooks, components, integration, tests) | NarrareFrontend + NarrareTesting |

### Critical Constraints
- **RULE-01b**: All LLM through BetaReaderAgent, model from ModelRegistry
- **RULE-02**: Prompts in `prompts/_bundled/analysis/en/beta_reader/`, composed by PromptComposer
- **RULE-03**: Contracts in `analysis/contracts.py` before any implementation
- **RULE-06**: Service orchestrates, router delegates, cache stores, assembler gathers
- **RULE-19**: `SessionDep` in dependency factories (not bare `AsyncSession`)
- **RULE-16**: `"analysis"` namespace registered + 3 locale files

### Risks & Trade-offs
- **Token budget**: Chapter text + context may exceed model limits for very long chapters.
  Mitigation: 10,000 word cap per analysis. Context assembler truncates KB entries to 200 chars each.
- **Two LLM calls for full experience**: Phase 1 + Phase 2 = 2 calls. Acceptable because
  Phase 2 is optional and user-triggered.
- **Cache staleness**: 30min TTL means feedback may not reflect recent edits.
  Mitigation: `refresh=True` option in UI. Cache key includes chapter IDs for natural invalidation.

### Definition of Done
- [ ] Spec approved by user
- [ ] Contracts in place before implementation
- [ ] All RULE-XX constraints satisfied
- [ ] No workarounds or shortcuts
- [ ] 59 tests passing
- [ ] Frontend renders feedback with i18n in 3 locales

---

> **Specification authored by**: Architecture Specialist
> **Date**: 2026-05-26
> **Next review**: After contracts and agent types are written (Steps C1, B1)
