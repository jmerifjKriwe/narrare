"""Writing subsystem — generation pipeline, context assembly, session management.

Public API:
    GenerationMode, GenerationStatus, WritingContext,
    GenerationRequest, SessionState, SceneState,
    KBEntity, RecentChapter,
    WritingPipelineProtocol, ContextAssemblerProtocol,
    DraftProcessorProtocol, SessionManagerProtocol,
    WritingContextAssembler, TokenBudgetManager,
    DraftProcessor, WritingPipeline, SessionManager,
"""

from narrare_core.writing._enums import GenerationMode, GenerationStatus
from narrare_core.writing.budget import TokenBudgetManager
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.context_models import KBEntity, RecentChapter
from narrare_core.writing.contracts import (
    ContextAssemblerProtocol,
    DraftProcessorProtocol,
    SessionManagerProtocol,
    WritingPipelineProtocol,
)
from narrare_core.writing.draft_processor import DraftProcessor
from narrare_core.writing.models import (
    GenerationRequest,
    SceneState,
    SessionState,
    WritingContext,
)
from narrare_core.writing.pipeline import WritingPipeline
from narrare_core.writing.session_manager import SessionManager

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
    "TokenBudgetManager",
    "WritingContext",
    "WritingContextAssembler",
    "WritingPipeline",
    "WritingPipelineProtocol",
]
