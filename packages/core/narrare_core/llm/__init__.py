"""LLM Gateway — the only path to any LLM provider. See CONSTRAINTS.md RULE-01."""

from narrare_core.llm.contracts import ModelRegistryProtocol
from narrare_core.llm.gateway import ModelRegistry
from narrare_core.llm.intents import (
    INTENT_CATEGORY_MAP,
    IntentCategory,
    LLMIntent,
    ResolvedModelConfig,
)
from narrare_core.llm.model_routing import ModelRoutingResolver, ResolvedModel
from narrare_core.llm.observability import LLMObservability
from narrare_core.llm.override_schemas import (
    CategoryOverride,
    IntentOverride,
    TokenLimitOverride,
)
from narrare_core.llm.result import LLMResult, LLMStream, StreamChunk, TokenUsage
from narrare_core.llm.retry import DEFAULT_RETRY, FAST_RETRY, NO_RETRY, PATIENT_RETRY, RetryConfig

__all__ = [
    "DEFAULT_RETRY",
    "FAST_RETRY",
    "INTENT_CATEGORY_MAP",
    "NO_RETRY",
    "PATIENT_RETRY",
    "CategoryOverride",
    "IntentCategory",
    "IntentOverride",
    "LLMIntent",
    "LLMObservability",
    "LLMResult",
    "LLMStream",
    "ModelRegistry",
    "ModelRegistryProtocol",
    "ModelRoutingResolver",
    "ResolvedModel",
    "ResolvedModelConfig",
    "RetryConfig",
    "StreamChunk",
    "TokenLimitOverride",
    "TokenUsage",
]
