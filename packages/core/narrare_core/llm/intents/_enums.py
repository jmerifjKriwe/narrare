"""``LLMIntent`` enum — the only public type exported by this package.

Split out of the former monolithic ``intents.py`` (400 lines) per
RULE-04 (modularize, do not compress). This module holds the compact
enum only; the **full verbose documentation** (Scope / Input / Output /
NOT) that used to live in each member's docstring now lives verbatim in
:data:`narrare_core.llm.intents.INTENT_DOCS`.

Each member keeps a concise one-line scope summary as its docstring for
quick IDE introspection. Nothing is lost — the original prose is
preserved word-for-word in ``INTENT_DOCS``.
"""

from __future__ import annotations

from enum import StrEnum


class LLMIntent(StrEnum):
    """All possible LLM operation intents in Narrare.

    Each intent has a defined semantic scope. Full verbose documentation
    (Scope/Input/Output/NOT) for every intent lives in
    :data:`narrare_core.llm.intents.INTENT_DOCS`, split into category
    modules to keep this most-edited file well under the size limit.

    When adding a new intent:

    - Document what it DOES and what it does NOT do (in ``INTENT_DOCS``)
    - Check for scope overlap with existing intents
    - Register in ``_INTENT_TO_CATEGORY`` and ``_INTENT_TO_MODE`` in
      ``composer.py`` / ``route_table.py``
    """

    # ------------------------------------------------------------------
    # Writing operations — chapter-level prose generation
    # ------------------------------------------------------------------

    WRITE = "write"
    """Generate new chapter content from outline."""

    EXTEND = "extend"
    """Extend existing chapter content from a continuation point."""

    REWRITE = "rewrite"
    """Rewrite a specific text selection with author direction."""

    CO_AUTHOR = "co_author"
    """Collaborative writing — targeted improvement of existing text."""

    # ------------------------------------------------------------------
    # Analysis operations — reading, evaluating, checking text
    # ------------------------------------------------------------------

    ANALYSE = "analyse"
    """General-purpose multi-dimension text analysis."""

    SENTIMENT = "sentiment"
    """Sentiment and emotional tone analysis."""

    CONSISTENCY = "consistency"
    """Cross-chapter consistency checking."""

    BETA_READ = "beta_read"
    """Beta reader simulation — reader-perspective feedback."""

    VOICE = "voice"
    """Voice and style analysis."""

    # ------------------------------------------------------------------
    # Knowledge base operations — entity creation, improvement, extraction
    # ------------------------------------------------------------------

    KB_CREATE = "kb_create"
    """Interactive KB entity creation via structured interview."""

    KB_IMPROVE = "kb_improve"
    """KB entry improvement analysis."""

    KB_EXTRACT = "kb_extract"
    """Extract entities from chapter text."""

    KB_INTERVIEW = "kb_interview"
    """Ask the author a single focused question about a KB field."""

    KB_SUGGEST = "kb_suggest"
    """Suggest a well-reasoned value for a specific KB template field."""

    KB_ENHANCE = "kb_enhance"
    """Generate or expand a KB entity entry with multiple fields."""

    KB_WORLDBUILD = "kb_worldbuild"
    """Worldbuilding analysis — gap detection, connections, consistency."""

    KB_CONSISTENCY = "kb_consistency"
    """KB entry-internal consistency checking."""

    # ------------------------------------------------------------------
    # Planning operations — story structure, scene planning
    # ------------------------------------------------------------------

    PLAN = "plan"
    """Scene/structure planning."""

    SUMMARIZE = "summarize"
    """Chapter/section summarization."""

    # ------------------------------------------------------------------
    # Generation operations — structured content generation
    # ------------------------------------------------------------------

    GENERATE = "generate"
    """General structured generation."""

    NAME_GENERATE = "name_generate"
    """Name generation for characters, places, etc."""

    TITLE_GENERATE = "title_generate"
    """Title generation for chapters, novels, etc."""

    # ------------------------------------------------------------------
    # Extraction operations — pull structured data from text
    # ------------------------------------------------------------------

    EXTRACT = "extract"
    """General structured extraction from text."""

    FACT_EXTRACT = "fact_extract"
    """Structured fact extraction with provenance (ADR-044 Stage 1)."""

    SUGGEST = "suggest"
    """Quick inline suggestions."""

    # ------------------------------------------------------------------
    # Chat — conversational writing assistant
    # ------------------------------------------------------------------

    CHAT = "chat"
    """General story assistant chat."""

    RESEARCH = "research"
    """Web research synthesis."""

    # ------------------------------------------------------------------
    # AI assist operations — writer-facing assistance (ASSIST-* features)
    # ------------------------------------------------------------------

    DIALOGUE_COACH = "dialogue_coach"
    """Analyse or improve selected dialogue (ASSIST-004)."""

    # ------------------------------------------------------------------
    # Embeddings (handled separately via embeddings.py)
    # ------------------------------------------------------------------

    EMBED = "embed"
    """Text embedding (not routed via gateway)."""
