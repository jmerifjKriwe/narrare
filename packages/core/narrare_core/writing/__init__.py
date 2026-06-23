"""Writing subsystem — generation pipeline, context assembly, session management.

Public API:
    GenerationMode, GenerationStatus, WritingContext,
    GenerationRequest, SessionState, SceneState,
    KBEntity, RecentChapter,
    WritingPipelineProtocol, ContextAssemblerProtocol,
    DraftProcessorProtocol, SessionManagerProtocol,
    WritingContextAssembler, TokenBudgetManager, cap_to_budget,
    DraftProcessor, WritingPipeline, SessionManager,
"""

from narrare_core.writing._enums import GenerationMode, GenerationStatus
from narrare_core.writing.budget import TokenBudgetManager, cap_to_budget
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.context_models import KBEntity, RecentChapter
from narrare_core.writing.contracts import (
    ContextAssemblerProtocol,
    DraftProcessorProtocol,
    SessionManagerProtocol,
    WritingPipelineProtocol,
)
from narrare_core.writing.draft_processor import DraftProcessor
from narrare_core.writing.models import WritingContext
from narrare_core.writing.pipeline import WritingPipeline
from narrare_core.writing.requests import GenerationRequest, SceneState, SessionState
from narrare_core.writing.session_manager import SessionManager
from narrare_core.writing.style_variants import (
    StyleVariant,
    get_style_variant_instructions,
)

__all__ = [
    "ContextAssemblerProtocol",
    "DraftProcessor",
    "DraftProcessorProtocol",
    "GenerationMode",
    "GenerationRequest",
    "GenerationStatus",
    "KBEntity",
    "RecentChapter",
    "SceneState",
    "SessionManager",
    "SessionManagerProtocol",
    "SessionState",
    "StyleVariant",
    "TokenBudgetManager",
    "WritingContext",
    "WritingContextAssembler",
    "WritingPipeline",
    "WritingPipelineProtocol",
    "cap_to_budget",
    "get_style_variant_instructions",
]
