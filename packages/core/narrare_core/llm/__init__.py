"""LLM Gateway — the only path to any LLM provider. See CONSTRAINTS.md RULE-01b."""

from narrare_core.llm.contracts import ModelCatalogProtocol, ModelRegistryProtocol
from narrare_core.llm.cost_rates import (
    ModelLimits,
    get_cached_data,
    get_model_limit_calibration,
    get_model_limits,
    get_rates,
    invalidate_cache,
    refresh_models,
)
from narrare_core.llm.gateway import ModelRegistry
from narrare_core.llm.intent_categories import INTENT_CATEGORY_MAP, IntentCategory
from narrare_core.llm.intent_profiles import IntentProfile, get_intent_profile
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_calibration import ModelLimitCalibration, ModelLimitCalibrationStatus
from narrare_core.llm.model_config import CacheSettings, ResolvedModelConfig
from narrare_core.llm.model_listing import (
    ModelCatalogClient,
    ModelCatalogEntry,
    ModelCatalogError,
)
from narrare_core.llm.model_routing import ModelRoutingResolver, ResolvedModel
from narrare_core.llm.model_suitability import (
    ModelSuitabilityIssue,
    ModelSuitabilityResult,
    SuitabilitySeverity,
    evaluate_model_suitability,
)
from narrare_core.llm.override_schemas import (
    CategoryOverride,
    IntentOverride,
    TokenLimitOverride,
)
from narrare_core.llm.result import LLMResult, LLMStream, StreamChunk, TokenUsage
from narrare_core.llm.retry import DEFAULT_RETRY, FAST_RETRY, NO_RETRY, PATIENT_RETRY, RetryConfig
from narrare_core.llm.run_limits import SUGGEST_MAX_TOKENS
from narrare_core.llm.token_profiles import (
    PROFILE_OUTPUT_LIMITS,
    TOKEN_OUTPUT_ABSOLUTE_MAX,
    TOKEN_OUTPUT_UX_RECOMMENDED_MAX,
    TokenLimitProfile,
    public_token_profile_values,
)

__all__ = [
    "DEFAULT_RETRY",
    "FAST_RETRY",
    "INTENT_CATEGORY_MAP",
    "NO_RETRY",
    "PATIENT_RETRY",
    "PROFILE_OUTPUT_LIMITS",
    "SUGGEST_MAX_TOKENS",
    "TOKEN_OUTPUT_ABSOLUTE_MAX",
    "TOKEN_OUTPUT_UX_RECOMMENDED_MAX",
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
    "ModelLimitCalibration",
    "ModelLimitCalibrationStatus",
    "ModelLimits",
    "ModelRegistry",
    "ModelRegistryProtocol",
    "ModelRoutingResolver",
    "ModelSuitabilityIssue",
    "ModelSuitabilityResult",
    "ResolvedModel",
    "ResolvedModelConfig",
    "RetryConfig",
    "StreamChunk",
    "SuitabilitySeverity",
    "TokenLimitOverride",
    "TokenLimitProfile",
    "TokenUsage",
    "evaluate_model_suitability",
    "get_cached_data",
    "get_intent_profile",
    "get_model_limit_calibration",
    "get_model_limits",
    "get_rates",
    "invalidate_cache",
    "public_token_profile_values",
    "refresh_models",
]
