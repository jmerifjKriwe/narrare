"""Regression tests for writing graph prompt builders (CR-AUFG-02-07).

These tests verify the ADR-046 prompt-path-compliance retrofit:

    composer=None must fail-fast with ``ConfigurationError``, NOT silently
    degrade to inline f-string prompt fallbacks.

Before ADR-046:
    Passing ``composer=None`` returned an inline f-string task prompt,
    bypassing the ``NarrareMeta`` Capability.  This was a degraded
    production path reachable when DI failed to wire ``PromptComposer``.

After ADR-046:
    ``composer=None`` raises ``ConfigurationError`` (RULE-11: no silent
    fallbacks). ``WritingDeps.composer`` is required (non-Optional).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from narrare_core.agents.writing_graph_prompts import (
    get_draft_prompt,
    get_outline_prompt,
    get_review_prompt,
    get_revise_prompt,
    get_summary_prompt,
)
from narrare_core.agents.writing_graph_types import WritingDeps, WritingState
from narrare_core.shared.errors import ConfigurationError


def _deps() -> WritingDeps:
    """Build a valid WritingDeps with a (mocked) PromptComposer wired.

    The ``composer`` here is a placeholder for the WritingDeps container
    (which now requires it).  The actual functions under test receive
    ``composer=None`` directly to exercise the fail-fast guard.
    """
    return WritingDeps(
        registry=AsyncMock(),
        composer=AsyncMock(),
        genre="fantasy",
        tone="balanced",
    )


def _state() -> WritingState:
    return WritingState(chapter_id="ch-01")


class TestComposerNoneFailsFast:
    """REGRESSION (CR-AUFG-02-07): ``composer=None`` must raise ConfigurationError.

    Each prompt-builder function previously contained a ``composer is None``
    fallback branch with inline f-string prompts.  These silent fallback
    paths violated RULE-02 (no prompt assembly outside ``core/prompts/``)
    and RULE-11 (no silent fallbacks) and bypassed the ``NarrareMeta``
    Capability.

    After the retrofit, ``composer=None`` is a DI-wiring error that
    fails fast.
    """

    @pytest.mark.asyncio
    async def test_outline_prompt_raises_on_none_composer(self) -> None:
        with pytest.raises(ConfigurationError):
            await get_outline_prompt(
                composer=None,  # type: ignore[arg-type]  # intentionally testing DI failure
                deps=_deps(),
                state=_state(),
            )

    @pytest.mark.asyncio
    async def test_draft_prompt_raises_on_none_composer(self) -> None:
        with pytest.raises(ConfigurationError):
            await get_draft_prompt(
                composer=None,  # type: ignore[arg-type]
                deps=_deps(),
                state=_state(),
            )

    @pytest.mark.asyncio
    async def test_review_prompt_raises_on_none_composer(self) -> None:
        with pytest.raises(ConfigurationError):
            await get_review_prompt(
                composer=None,  # type: ignore[arg-type]
                deps=_deps(),
                state=_state(),
                word_count=0,
            )

    @pytest.mark.asyncio
    async def test_revise_prompt_raises_on_none_composer(self) -> None:
        with pytest.raises(ConfigurationError):
            await get_revise_prompt(
                composer=None,  # type: ignore[arg-type]
                deps=_deps(),
                state=_state(),
            )

    @pytest.mark.asyncio
    async def test_summary_prompt_raises_on_none_composer(self) -> None:
        with pytest.raises(ConfigurationError):
            await get_summary_prompt(
                composer=None,  # type: ignore[arg-type]
                deps=_deps(),
                state=_state(),
            )

    @pytest.mark.asyncio
    async def test_configuration_error_message_mentions_composer(self) -> None:
        """The error message should guide developers to wire the composer."""
        with pytest.raises(ConfigurationError, match=r"(?i)composer|PromptComposer"):
            await get_outline_prompt(
                composer=None,  # type: ignore[arg-type]
                deps=_deps(),
                state=_state(),
            )
