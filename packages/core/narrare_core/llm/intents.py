"""
LLM Intent definitions and model routing.

Every LLM call carries an intent. The gateway uses the intent to select:
- Which model to use (quality vs cost tradeoff)
- What parameters to apply (temperature, max_tokens)
- Which provider to route to

To change the model for an intent: edit MODEL_ROUTING below.
No service code changes needed.
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

    # Extraction operations
    EXTRACT = "extract"  # General structured extraction
    SUGGEST = "suggest"  # Quick suggestions (inline, KB, titles)

    # Chat
    CHAT = "chat"  # General story assistant chat

    # Research
    RESEARCH = "research"  # Web research synthesis

    # Embeddings (handled separately via embeddings.py)
    EMBED = "embed"  # Text embedding (not routed via gateway)


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """Configuration for a specific intent's model call."""

    model: str
    temperature: float = 0.7
    max_tokens: int = 2000
    # Whether this intent typically streams responses
    streams: bool = False
    # Human-readable reason for this model choice (for debugging)
    reason: str = ""


# ---------------------------------------------------------------------------
# Model routing table
# Change models here — no service code changes needed.
# Environment variables can override: DEFAULT_WRITING_MODEL, etc.
# ---------------------------------------------------------------------------

MODEL_ROUTING: dict[LLMIntent, ModelConfig] = {
    # High-quality generation — use best available model
    LLMIntent.WRITE: ModelConfig(
        model="claude-sonnet-4-5-20251020",
        temperature=0.8,
        max_tokens=4096,
        streams=True,
        reason="Writing quality matters most",
    ),
    LLMIntent.EXTEND: ModelConfig(
        model="claude-sonnet-4-5-20251020",
        temperature=0.8,
        max_tokens=2048,
        streams=True,
        reason="Same quality as new chapter generation",
    ),
    LLMIntent.REWRITE: ModelConfig(
        model="claude-sonnet-4-5-20251020",
        temperature=0.7,
        max_tokens=2048,
        streams=True,
        reason="Rewrite requires nuance",
    ),
    LLMIntent.CO_AUTHOR: ModelConfig(
        model="claude-sonnet-4-5-20251020",
        temperature=0.9,
        max_tokens=1024,
        streams=True,
        reason="Co-author needs creativity",
    ),
    # KB operations — quality matters for world-building
    LLMIntent.KB_CREATE: ModelConfig(
        model="claude-sonnet-4-5-20251020",
        temperature=0.7,
        max_tokens=2000,
        streams=True,
        reason="KB creation needs nuanced world-building",
    ),
    LLMIntent.KB_IMPROVE: ModelConfig(
        model="claude-sonnet-4-5-20251020",
        temperature=0.6,
        max_tokens=2000,
        streams=False,
        reason="KB improvement is analytical",
    ),
    LLMIntent.KB_EXTRACT: ModelConfig(
        model="claude-haiku-3-5-20241022",
        temperature=0.3,
        max_tokens=1000,
        streams=False,
        reason="Extraction is structured — fast model sufficient",
    ),
    # Analysis — fast model sufficient for most
    LLMIntent.ANALYSE: ModelConfig(
        model="claude-haiku-3-5-20241022",
        temperature=0.3,
        max_tokens=1500,
        streams=False,
        reason="Analysis is deterministic — fast model",
    ),
    LLMIntent.SENTIMENT: ModelConfig(
        model="claude-haiku-3-5-20241022",
        temperature=0.2,
        max_tokens=500,
        streams=False,
        reason="Sentiment is low-complexity structured output",
    ),
    LLMIntent.CONSISTENCY: ModelConfig(
        model="claude-haiku-3-5-20241022",
        temperature=0.2,
        max_tokens=1500,
        streams=False,
        reason="Consistency checks run frequently — cost matters",
    ),
    LLMIntent.BETA_READ: ModelConfig(
        model="claude-sonnet-4-5-20251020",
        temperature=0.5,
        max_tokens=2000,
        streams=False,
        reason="Beta reader needs good narrative understanding",
    ),
    LLMIntent.VOICE: ModelConfig(
        model="claude-sonnet-4-5-20251020",
        temperature=0.4,
        max_tokens=1500,
        streams=False,
        reason="Voice analysis needs literary understanding",
    ),
    # Planning
    LLMIntent.PLAN: ModelConfig(
        model="claude-sonnet-4-5-20251020",
        temperature=0.6,
        max_tokens=2000,
        streams=False,
        reason="Planning benefits from coherent structure",
    ),
    LLMIntent.SUMMARIZE: ModelConfig(
        model="claude-haiku-3-5-20241022",
        temperature=0.3,
        max_tokens=500,
        streams=False,
        reason="Summarization runs in background tasks",
    ),
    # Suggestions — must be fast
    LLMIntent.SUGGEST: ModelConfig(
        model="claude-haiku-3-5-20241022",
        temperature=0.7,
        max_tokens=300,
        streams=False,
        reason="Suggestions need low latency",
    ),
    LLMIntent.EXTRACT: ModelConfig(
        model="claude-haiku-3-5-20241022",
        temperature=0.2,
        max_tokens=1000,
        streams=False,
        reason="Extraction is structured output",
    ),
    # Chat and research
    LLMIntent.CHAT: ModelConfig(
        model="claude-sonnet-4-5-20251020",
        temperature=0.7,
        max_tokens=1500,
        streams=True,
        reason="Chat needs good story understanding",
    ),
    LLMIntent.RESEARCH: ModelConfig(
        model="claude-sonnet-4-5-20251020",
        temperature=0.4,
        max_tokens=2000,
        streams=False,
        reason="Research synthesis needs accuracy",
    ),
}


def get_model_config(intent: LLMIntent) -> ModelConfig:
    """
    Get the model configuration for a given intent.

    Args:
        intent: The LLM operation intent.

    Returns:
        ModelConfig with model name and generation parameters.

    Raises:
        KeyError: If intent has no routing entry (should never happen
                  in production — all intents must have a routing entry).
    """
    if intent not in MODEL_ROUTING:
        raise KeyError(
            f"No model routing defined for intent '{intent}'. "
            "Add an entry to MODEL_ROUTING in llm/intents.py."
        )
    return MODEL_ROUTING[intent]
