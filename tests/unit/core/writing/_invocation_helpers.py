"""Shared helpers for invocation wiring tests.

Provides constants, fakes, and wiring utilities used by both
``test_invocation_wiring.py`` and ``test_invocation_wiring_extra.py``.

See: ADR-040 Decision 4, INFRA-013, CONSTRAINTS.md RULE-10/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.writing import GenerationMode
from narrare_core.writing.models import GenerationRequest, WritingContext
from narrare_core.writing.pipeline import WritingPipeline

if TYPE_CHECKING:
    from narrare_core.ai_invocation.models import FeatureInvocationEvidence

__all__ = [
    "CONFIG",
    "USAGE",
    "FakeEvidenceSink",
    "_collect",
    "_ctx",
    "_make_pipeline",
    "_mock_pipeline_with_sink",
    "_req",
    "_setup_run",
    "_setup_stream",
    "_stream",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIG = ResolvedModelConfig(
    provider_name="test",
    model_id="test-model",
    max_tokens=2000,
)
USAGE = TokenUsage(prompt_tokens=10, completion_tokens=50, total_tokens=60)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeEvidenceSink:
    """In-memory evidence sink for testing."""

    def __init__(self) -> None:
        self.records: list[FeatureInvocationEvidence] = []

    async def record(self, evidence: FeatureInvocationEvidence) -> None:
        self.records.append(evidence)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _req(mode: GenerationMode = GenerationMode.EXTEND, **kw: Any) -> GenerationRequest:
    defaults: dict[str, Any] = {
        "chapter_id": uuid4(),
        "project_id": uuid4(),
        "user_id": uuid4(),
        "mode": mode,
        "writing_language": "en",
    }
    defaults.update(kw)
    return GenerationRequest(**defaults)


def _ctx(**kw: Any) -> WritingContext:
    defaults: dict[str, Any] = {
        "chapter_content": "Some existing chapter text.",
        "project_title": "Test Novel",
        "genre": "fantasy",
        "language": "en",
        "tone": "balanced",
        "writing_language": "English",
    }
    defaults.update(kw)
    return WritingContext(**defaults)


async def _collect(gen: Any) -> list[StreamChunk]:
    out: list[StreamChunk] = []
    async for c in gen:
        out.append(c)
    return out


async def _stream(*chunks: StreamChunk):  # type: ignore[no-untyped-def]
    for c in chunks:
        yield c


def _setup_stream(mock_registry: Any, *texts: str) -> None:
    """Wire mock_registry.stream to yield text chunks + final chunk."""
    chunks = [StreamChunk(text=t) for t in texts]
    chunks.append(StreamChunk(text="", is_final=True, usage=USAGE))
    mock_registry.stream = MagicMock(spec=[], return_value=_stream(*chunks))


def _setup_run(mock_registry: Any, text: str = "Interview result.") -> None:
    """Wire mock_registry.run to return a string result.

    Note: After AUFG-03-01, the interview path no longer calls
    ``registry.run()`` — it goes through ``InterviewQuestionAgent``.
    Tests that exercise the interview path should patch the agent
    directly (see ``test_invocation_wiring_extra.py`` for the pattern).
    ``_setup_run`` is retained for any non-interview callers that still
    use ``registry.run()``.
    """
    mock_registry.run = AsyncMock(return_value=text)


def setup_interview_registry(mock_registry: Any) -> None:
    """Wire a registry mock for the AUFG-03-01 agent-based interview path.

    Adds ``get_model`` (returning a fake Model) so the interview path
    can resolve the model. The mock must already be a ``MagicMock`` —
    this helper only attaches ``get_model``. ``InterviewQuestionAgent.run``
    itself is patched separately at the test level (its return value is
    the question text).
    """
    mock_registry.get_model = AsyncMock(
        return_value=MagicMock(spec=["_model_response"], name="fake_model")
    )


def _make_pipeline(
    mock_registry: Any,
    mock_composer: Any,
    mock_assembler: Any,
    mock_processor: Any,
    invocation_pipeline: InvocationPipeline | None = None,
) -> WritingPipeline:
    return WritingPipeline(
        registry=mock_registry,
        composer=mock_composer,
        context_assembler=mock_assembler,
        draft_processor=mock_processor,
        invocation_pipeline=invocation_pipeline,
    )


def _mock_pipeline_with_sink(sink: FakeEvidenceSink) -> InvocationPipeline:
    """Create a real InvocationPipeline with only the evidence sink wired."""
    return InvocationPipeline(evidence_sink=sink)
