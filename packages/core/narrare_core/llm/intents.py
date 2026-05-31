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

# ---------------------------------------------------------------------------
# Output token limit profiles
# ---------------------------------------------------------------------------

_PROFILE_OUTPUT_LIMITS: dict[str, int] = {
    "quick": 500,
    "balanced": 2000,
    "long_texts": 8000,
}
"""Token limit presets referenced by :meth:`ResolvedModelConfig.resolve_output_limit`.

The final output limit is determined by ``resolve_output_limit(profile)``.
If a ``token_limit_profile`` is set on the config, it takes precedence
over ``max_tokens`` when no explicit profile argument is supplied.
"""


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
    KB_INTERVIEW = "kb_interview"  # Ask questions about a KB template field
    KB_SUGGEST = "kb_suggest"  # Suggest a value for a KB template field
    KB_ENHANCE = "kb_enhance"  # Generate/expand a KB entity entry
    KB_WORLDBUILD = (
        "kb_worldbuild"  # Worldbuilding analysis (gap detection, connections, consistency)
    )
    KB_CONSISTENCY = "kb_consistency"  # KB entry consistency checking

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


_INTENT_PROFILE_DEFAULTS: dict[LLMIntent, str] = {
    LLMIntent.BETA_READ: "long_texts",
    LLMIntent.NAME_GENERATE: "quick",
}
"""Default token-limit profiles per intent.

When the model routing resolver builds a ``ResolvedModelConfig``, it
should consult this mapping to set ``token_limit_profile`` unless the
user/project already provides one.  Intents not listed here fall back
to the global default (``"balanced"``).
"""


def get_default_profile_for_intent(intent: LLMIntent) -> str | None:
    """Return the default token-limit profile for *intent*, or ``None``.

    Callers (typically the model routing resolver) use this to seed
    ``ResolvedModelConfig.token_limit_profile`` when no user/project
    override exists.

    Parameters
    ----------
    intent:
        The LLM intent to look up.

    Returns
    -------
    str | None
        Profile name (e.g. ``"long_texts"``) if a default is defined,
        otherwise ``None``.
    """
    return _INTENT_PROFILE_DEFAULTS.get(intent)


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
    LLMIntent.KB_INTERVIEW: IntentCategory.KB,
    LLMIntent.KB_SUGGEST: IntentCategory.KB,
    LLMIntent.KB_ENHANCE: IntentCategory.KB,
    LLMIntent.KB_WORLDBUILD: IntentCategory.KB,
    LLMIntent.KB_CONSISTENCY: IntentCategory.KB,
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
class CacheSettings:
    """Prompt caching configuration for a resolved model.

    Provider-specific behavior:
    - Anthropic: Enables cache_control blocks on system prompt + tools.
    - OpenAI / Z.AI / Groq: Ignored (automatic server-side caching).
    - Google: Triggers explicit cached_contents creation.
    - Ollama: Ignored (no caching support).
    """

    enabled: bool = True
    ttl_seconds: int = 300  # Anthropic minimum: 300 (5min)
    max_cache_points: int = 4  # Anthropic limit: 4


@dataclass(frozen=True, slots=True)
class ResolvedModelConfig:
    """Fully resolved model configuration ready for the gateway.

    Contains everything the gateway needs to make an LLM call:
    which provider, which model, and generation parameters.

    This is the output of ``ModelRoutingResolver.resolve()`` and the
    input to ``ModelRegistry.run()`` / ``ModelRegistry.stream()``.

    Replaces the old ``ModelConfig`` which had no ``provider_name``
    and relied on ``infer_provider()`` heuristics.

    The final output token limit is determined by
    :meth:`resolve_output_limit` — it delegates to the profile system
    if ``token_limit_profile`` is set.
    """

    provider_name: str
    model_id: str
    temperature: float = 0.7
    max_tokens: int = 4096
    streams: bool = False
    token_limit_profile: str | None = None
    cache: CacheSettings | None = None

    def resolve_output_limit(self, profile: str | None = None) -> int:
        """Return the output token limit, optionally overridden by *profile*.

        Resolution order:
        1. If *profile* is a known key in ``_PROFILE_OUTPUT_LIMITS``,
           return that limit.
        2. If ``self.token_limit_profile`` is a known key, return its
           limit.
        3. Otherwise return ``self.max_tokens``.

        Parameters
        ----------
        profile:
            Optional explicit profile name (takes highest priority).

        Returns
        -------
        int
            The resolved output token limit.
        """
        effective = profile or self.token_limit_profile
        if effective and effective in _PROFILE_OUTPUT_LIMITS:
            return _PROFILE_OUTPUT_LIMITS[effective]
        return self.max_tokens
