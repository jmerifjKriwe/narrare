"""Memory subsystem — feedback collection, preference derivation, and mem0 adapter.

Public API:
    FeedbackAction, FeedbackEvent, FeedbackCollector, PreferenceProvider,
    PreferenceProfile, MemoryFacade, FeedbackService, PreferenceService,
    EmbeddingConfig, EmbeddingCascadeResolver, MemoryClientCache,
    ProviderEnvConfig, is_mem0_available, detect_provider_from_env

The mem0 client factories (``create_memory_client``,
``create_memory_client_sync``) are intentionally excluded from public
exports — they are internal implementation details used only during
service wiring.
"""

from narrare_core.memory._null_client import NullMemoryClient
from narrare_core.memory.availability import (
    ProviderEnvConfig,
    detect_provider_from_env,
    is_mem0_available,
)
from narrare_core.memory.embedding_cascade import (
    EmbeddingCascadeResolver,
    EmbeddingConfig,
)
from narrare_core.memory.feedback_service import FeedbackService
from narrare_core.memory.memory_client_cache import MemoryClientCache
from narrare_core.memory.models import (
    FeedbackAction,
    FeedbackEvent,
    PreferenceProfile,
)
from narrare_core.memory.preference_service import PreferenceService
from narrare_core.memory.protocols import (
    FeedbackCollector,
    MemoryFacade,
    PreferenceProvider,
)

__all__ = [
    "EmbeddingCascadeResolver",
    "EmbeddingConfig",
    "FeedbackAction",
    "FeedbackCollector",
    "FeedbackEvent",
    "FeedbackService",
    "MemoryClientCache",
    "MemoryFacade",
    "NullMemoryClient",
    "PreferenceProfile",
    "PreferenceProvider",
    "PreferenceService",
    "ProviderEnvConfig",
    "detect_provider_from_env",
    "is_mem0_available",
]
