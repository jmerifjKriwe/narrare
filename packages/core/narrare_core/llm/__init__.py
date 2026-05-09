"""LLM Gateway — the only path to any LLM provider. See CONSTRAINTS.md RULE-01."""

from narrare_core.llm.gateway import LLMGateway
from narrare_core.llm.intents import LLMIntent, ModelConfig, get_model_config
from narrare_core.llm.result import LLMResult, StreamChunk, TokenUsage, LLMStream
from narrare_core.llm.retry import DEFAULT_RETRY, FAST_RETRY, PATIENT_RETRY, NO_RETRY, RetryConfig

__all__ = [
    "LLMGateway",
    "LLMIntent",
    "ModelConfig",
    "get_model_config",
    "LLMResult",
    "StreamChunk",
    "TokenUsage",
    "LLMStream",
    "DEFAULT_RETRY",
    "FAST_RETRY",
    "PATIENT_RETRY",
    "NO_RETRY",
    "RetryConfig",
]
