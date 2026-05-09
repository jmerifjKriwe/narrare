"""LLM Gateway — the only path to any LLM provider. See CONSTRAINTS.md RULE-01."""

from narrare_core.llm.gateway import LLMGateway
from narrare_core.llm.intents import LLMIntent, ModelConfig, get_model_config
from narrare_core.llm.result import LLMResult, LLMStream, StreamChunk, TokenUsage
from narrare_core.llm.retry import DEFAULT_RETRY, FAST_RETRY, NO_RETRY, PATIENT_RETRY, RetryConfig

__all__ = [
    "DEFAULT_RETRY",
    "FAST_RETRY",
    "NO_RETRY",
    "PATIENT_RETRY",
    "LLMGateway",
    "LLMIntent",
    "LLMResult",
    "LLMStream",
    "ModelConfig",
    "RetryConfig",
    "StreamChunk",
    "TokenUsage",
    "get_model_config",
]
