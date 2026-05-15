"""Memory subsystem — feedback collection, preference derivation, and mem0 adapter.

Public API:
    FeedbackAction, FeedbackEvent, FeedbackCollector, PreferenceProvider,
    PreferenceProfile, MemoryFacade, FeedbackService, PreferenceService

The mem0 client factory (``create_memory_client``) is intentionally
excluded from public exports — it is an internal implementation detail
used only during service wiring.
"""

from narrare_core.memory.feedback_service import FeedbackService
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
    "FeedbackAction",
    "FeedbackCollector",
    "FeedbackEvent",
    "FeedbackService",
    "MemoryFacade",
    "PreferenceProfile",
    "PreferenceProvider",
    "PreferenceService",
]
