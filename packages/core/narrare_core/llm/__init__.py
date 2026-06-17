"""LLM Gateway — the only path to any LLM provider. See CONSTRAINTS.md RULE-01b."""

from narrare_core.llm.contracts import ModelCatalogProtocol, ModelRegistryProtocol
from narrare_core.llm.cost_rates import (
    ModelLimits,
    get_cached_data,
    get_model_limits,
    get_rates,
    invalidate_cache,
    refresh_models,
)
from narrare_core.llm.gateway import ModelRegistry
from narrare_core.llm.intent_categories import INTENT_CATEGORY_MAP, IntentCategory
from narrare_core.llm.intent_profiles import IntentProfile, get_intent_profile
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_config import CacheSettings, ResolvedModelConfig
from narrare_core.llm.model_listing import (
    ModelCatalogClient,
    ModelCatalogEntry,
    ModelCatalogError,
)
from narrare_core.llm.model_routing import ModelRoutingResolver, ResolvedModel
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
    "CacheSettings",
    "CategoryOverride",
    "IntentCategory",
    "IntentOverride",
    "IntentProfile",
    "LLMIntent",
    "LLMResult",
    "LLMStream",
    "ModelCatalogClient",
    "ModelCatalogEntry",
    "ModelCatalogError",
    "ModelCatalogProtocol",
    "ModelLimits",
    "ModelRegistry",
    "ModelRegistryProtocol",
    "ModelRoutingResolver",
    "ResolvedModel",
    "ResolvedModelConfig",
    "RetryConfig",
    "StreamChunk",
    "TokenLimitOverride",
    "TokenUsage",
    "get_cached_data",
    "get_intent_profile",
    "get_model_limits",
    "get_rates",
    "invalidate_cache",
    "refresh_models",
]
