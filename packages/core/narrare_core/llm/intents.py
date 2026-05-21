"""
LLM Intent definitions and model routing types.

Every LLM call carries an intent. Intents are grouped into categories
for user-configurable model routing. The actual model resolution is
handled by ``ModelRoutingResolver`` implementations — this module
defines the types only.

Removed (configurable-model-routing):
    - ``MODEL_ROUTING`` dict — hardcoded routing replaced by runtime resolution
    - ``get_model_config()`` — replaced by ``ModelRoutingResolver.resolve()``
    - ``ModelConfig`` — replaced by ``ResolvedModelConfig``

See: openspec/changes/configurable-model-routing/design.md (D7)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LLMIntent(StrEnum):
    """All possible LLM operation intents in Narrare."""

    # Writing operations
    WRITE = "write"  # Generate new chapter content
    EXTEND = "extend"  # Extend existing content
    REWRITE = "rewrite"  # Rewrite a selection
    CO_AUTHOR = "co_author"  # Collaborative writing turn

    # Analysis operations
    ANALYSE = "analyse"  # General analysis (readability, POV, etc.)
    SENTIMENT = "sentiment"  # Sentiment analysis
    CONSISTENCY = "consistency"  # Consistency checking
    BETA_READ = "beta_read"  # Beta reader simulation
    VOICE = "voice"  # Voice/style analysis

    # Knowledge base operations
    KB_CREATE = "kb_create"  # Interactive KB entity creation
    KB_IMPROVE = "kb_improve"  # KB entry improvement
    KB_EXTRACT = "kb_extract"  # Extract entities from text

    # Planning operations
    PLAN = "plan"  # Scene/structure planning
    SUMMARIZE = "summarize"  # Chapter/section summarization

    # Generation operations
    GENERATE = "generate"  # General structured generation
    NAME_GENERATE = "name_generate"  # Name generation (characters, places)
    TITLE_GENERATE = "title_generate"  # Title generation (chapters, novels)

    # Extraction operations
    EXTRACT = "extract"  # General structured extraction
    SUGGEST = "suggest"  # Quick suggestions (inline, KB, titles)

    # Chat
    CHAT = "chat"  # General story assistant chat

    # Research
    RESEARCH = "research"  # Web research synthesis

    # Embeddings (handled separately via embeddings.py)
    EMBED = "embed"  # Text embedding (not routed via gateway)


class IntentCategory(StrEnum):
    """Categories grouping related LLM intents for manageable UX.

    Users configure model overrides per category. Intent-level overrides
    are optional (expand-on-demand in the UI).

    See: design.md D4
    """

    WRITING = "writing"
    ANALYSIS = "analysis"
    KB = "kb"
    PLANNING = "planning"
    GENERATION = "generation"
    EXTRACTION = "extraction"
    CHAT = "chat"
    RESEARCH = "research"


INTENT_CATEGORY_MAP: dict[LLMIntent, IntentCategory] = {
    # Writing
    LLMIntent.WRITE: IntentCategory.WRITING,
    LLMIntent.EXTEND: IntentCategory.WRITING,
    LLMIntent.REWRITE: IntentCategory.WRITING,
    LLMIntent.CO_AUTHOR: IntentCategory.WRITING,
    # Analysis
    LLMIntent.ANALYSE: IntentCategory.ANALYSIS,
    LLMIntent.SENTIMENT: IntentCategory.ANALYSIS,
    LLMIntent.CONSISTENCY: IntentCategory.ANALYSIS,
    LLMIntent.BETA_READ: IntentCategory.ANALYSIS,
    LLMIntent.VOICE: IntentCategory.ANALYSIS,
    # Knowledge base
    LLMIntent.KB_CREATE: IntentCategory.KB,
    LLMIntent.KB_IMPROVE: IntentCategory.KB,
    LLMIntent.KB_EXTRACT: IntentCategory.KB,
    # Planning
    LLMIntent.PLAN: IntentCategory.PLANNING,
    LLMIntent.SUMMARIZE: IntentCategory.PLANNING,
    # Generation
    LLMIntent.GENERATE: IntentCategory.GENERATION,
    LLMIntent.NAME_GENERATE: IntentCategory.GENERATION,
    LLMIntent.TITLE_GENERATE: IntentCategory.GENERATION,
    # Extraction
    LLMIntent.EXTRACT: IntentCategory.EXTRACTION,
    LLMIntent.SUGGEST: IntentCategory.EXTRACTION,
    # Chat
    LLMIntent.CHAT: IntentCategory.CHAT,
    # Research
    LLMIntent.RESEARCH: IntentCategory.RESEARCH,
}
"""Maps every routeable ``LLMIntent`` to its ``IntentCategory``.

Note: ``LLMIntent.EMBED`` is intentionally excluded — embeddings are
handled separately via ``core/embeddings/`` and do not go through the
model routing cascade.
"""


@dataclass(frozen=True, slots=True)
class ResolvedModelConfig:
    """Fully resolved model configuration ready for the gateway.

    Contains everything the gateway needs to make an LLM call:
    which provider, which model, and generation parameters.

    This is the output of ``ModelRoutingResolver.resolve()`` and the
    input to ``ModelRegistry.run()`` / ``ModelRegistry.stream()``.

    Replaces the old ``ModelConfig`` which had no ``provider_name``
    and relied on ``infer_provider()`` heuristics.

    See: design.md D7
    """

    provider_name: str
    model_id: str
    temperature: float = 0.7
    max_tokens: int = 2000
    streams: bool = False
    token_limit_profile: str | None = None
