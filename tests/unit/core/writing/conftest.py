"""Shared fixtures for co-author pipeline tests.

Helper functions live in :mod:`_coauthor_test_helpers` and are imported
here for fixture usage.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.draft_processor import DraftProcessor
from narrare_core.writing.pipeline import WritingPipeline
from tests.unit.core.writing._coauthor_test_helpers import _default_context


@pytest.fixture()
def mock_registry() -> Any:
    """Mock ModelRegistry with a configurable stream."""
    reg = MagicMock(spec=["stream", "run"])
    return reg


@pytest.fixture()
def mock_composer() -> Any:
    """Mock PromptComposer returning a simple composed prompt."""
    comp = MagicMock(spec=PromptComposer)
    comp.build = AsyncMock(
        return_value=ComposedPrompt(system="sys prompt", user="user prompt"),
    )
    return comp


@pytest.fixture()
def mock_assembler() -> Any:
    """Mock WritingContextAssembler returning default context."""
    asm = MagicMock(spec=WritingContextAssembler)
    asm.assemble = AsyncMock(return_value=_default_context())
    return asm


@pytest.fixture()
def mock_processor() -> Any:
    """Mock DraftProcessor that returns text unchanged."""
    proc = MagicMock(spec=DraftProcessor)
    return proc


@pytest.fixture()
def pipeline(
    mock_registry: Any,
    mock_composer: Any,
    mock_assembler: Any,
    mock_processor: Any,
) -> WritingPipeline:
    return WritingPipeline(
        registry=mock_registry,
        composer=mock_composer,
        context_assembler=mock_assembler,
        draft_processor=mock_processor,
    )
