"""Inline suggest service — lightweight ghost-text suggestion engine.

This service provides inline suggestions (ghost text) for the TipTap editor.
Unlike the main :class:`WritingService`, it has no pipeline, no graph, no
multi-step generation.  It directly:
- Uses :class:`PromptComposer` to build a ``SUGGEST`` prompt
- Uses :class:`ModelRegistry` to stream a short completion (max 60 tokens)

Implements :class:`SuggestServiceProtocol` from ``contracts.py`` (RULE-03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.context import PromptContext

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.writing.schemas import InlineSuggestRequest
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.intents import ResolvedModelConfig
    from narrare_core.llm.result import StreamChunk
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


class InlineSuggestService:
    """Lightweight ghost-text suggestion service (DI, RULE-07).

    Provides inline completions for the TipTap editor.  Uses composer
    and registry directly — no pipeline, no graph overhead.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        composer: PromptComposer,
        config: ResolvedModelConfig,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._registry = registry
        self._composer = composer
        self._config = config
        self._api_key = api_key
        self._base_url = base_url

    async def suggest_inline(
        self,
        chapter_id: UUID,
        user_id: str,
        request: InlineSuggestRequest,
    ) -> AsyncIterator[StreamChunk]:
        """Stream an inline suggestion for ghost text (Phase 3).

        Lightweight endpoint: no graph, no multi-step pipeline, no context
        assembly.  Uses ``LLMIntent.SUGGEST`` → ``writing/inline_suggest``
        prompt mode.  Max ~60 tokens per suggestion for low latency.

        The prompt context includes the user's ``text_before`` as the
        primary completion trigger and ``text_after`` for forward context.

        Args:
            chapter_id: Chapter the user is editing (for routing context).
            user_id: Authenticated user identifier.
            request: Inline suggestion request with text_before/text_after.

        Yields:
            StreamChunk instances with incremental text.  The final chunk
            has ``is_final=True`` and populated ``usage``.

        Raises:
            narrare_core.shared.errors.PromptNotFoundError: If no prompt
                file exists for ``LLMIntent.SUGGEST``.
        """
        ctx = PromptContext(
            language="en",  # TODO: resolve from project settings
            mode="inline_suggest",
            author_instructions=request.text_before,
            extra={
                "user_id": str(user_id),
                "chapter_id": str(chapter_id),
                "text_after": request.text_after or "",
            },
        )

        prompt = await self._composer.build(
            LLMIntent.SUGGEST,
            ctx,
        )

        async for chunk in self._registry.stream(
            intent=LLMIntent.SUGGEST,
            system_prompt=prompt.system,
            user_prompt=prompt.user,
            config=self._config,
            api_key=self._api_key,
            base_url=self._base_url,
        ):
            yield chunk
