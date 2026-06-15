"""Interview-assisted draft generation.

Extracted from ``ws_handler.py`` for RULE-04 compliance (max 300 lines).
Generates a full chapter draft from collected interview answers via the
standard invocation contract (ADR-045 Decision 6/7).

Transport-agnostic — yields :class:`~narrare_core.llm.result.StreamChunk`
instances so any transport adapter (WebSocket, SSE, MCP) can consume the
same generator (RULE-12/RULE-13). The caller maps chunks to transport
DTOs (e.g. via :func:`~narrare.writing.ws_streaming.send_stream_chunks`)
and handles persistence.

Uses:
- :class:`ModelRegistry` for LLM calls (RULE-01b)
- :class:`PromptComposer` via the invocation adapter (RULE-02)
- :class:`InvocationPipeline` for enrichment, validation, budget, evidence
- :class:`DefaultRunLimitResolver` for output-budget enforcement
  (ADR-045 Decision 4)

See: ADR-045, CONSTRAINTS.md RULE-02/RULE-03/RULE-06/RULE-12/RULE-13.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from narrare_core.shared.errors import WritingError
from narrare_core.writing._invocation_adapter import build_and_validate_prompt
from narrare_core.writing.budget import cap_to_budget

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare_core.ai_invocation.models import PromptInvocationContext
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.llm.result import StreamChunk
    from narrare_core.llm.run_limits import DefaultRunLimitResolver
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.prompts.context import PromptContext
    from narrare_core.writing.session_manager import SessionManager

logger = structlog.get_logger(__name__)

# Maximum token budget for the interview transcript fed into the prompt.
# Prevents "context length exceeded" crashes on long interviews (20+ Q&A pairs).
MAX_TRANSCRIPT_TOKENS: int = 4000

#: Feature identifier for interview-assisted draft generation. Distinct from
#: interactive turns (``writing_interactive_turn``) so adoption evidence can
#: correlate each production path independently (ADR-045 Decision 2).
INTERVIEW_DRAFT_FEATURE_ID: str = "writing_interview_draft"


class InterviewDraftGenerator:
    """Generates a full chapter draft from collected interview answers.

    Formats the conversation history as a transcript and streams a
    complete draft via the standard invocation contract (prepare →
    compose → finalize → enforce limits → stream).

    Transport-agnostic — yields :class:`StreamChunk` instances. The
    caller maps them to transport DTOs and handles persistence
    (RULE-12/RULE-13).

    Dependencies are injected via constructor (DI pattern).
    """

    def __init__(
        self,
        session_manager: SessionManager,
        registry: ModelRegistry,
        composer: PromptComposer,
        config: ResolvedModelConfig,
        invocation_pipeline: InvocationPipeline | None,
        run_limit_resolver: DefaultRunLimitResolver,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._registry = registry
        self._composer = composer
        self._config = config
        self._invocation_pipeline = invocation_pipeline
        self._run_limit_resolver = run_limit_resolver
        self._api_key = api_key
        self._base_url = base_url

    async def stream_draft(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        project_id: UUID,
        chapter_id: UUID,
    ) -> AsyncIterator[StreamChunk]:
        """Yield ``StreamChunk`` instances for a draft from the transcript.

        Runs the full invocation contract:
            1. Look up the session and format the interview transcript.
            2. Build :class:`PromptContext` (mode ``new_chapter``).
            3. Build :class:`PromptInvocationContext` with all identifiers.
            4. ``build_and_validate_prompt`` — prepare → merge → compose
               → finalize (enrichment, budget, validation, evidence).
            5. Resolve run limits with the same ``invocation_id``.
            6. Stream via :meth:`ModelRegistry.stream` with enforced limits.

        Args:
            session_id: The WebSocket session identifier.
            user_id: The authenticated user's identifier (ADR-045).
            project_id: The project identifier for enrichment.
            chapter_id: The chapter being written.

        Yields:
            :class:`StreamChunk` instances. The final chunk has
            ``is_final=True`` with populated ``usage``.

        Raises:
            WritingError: If the session is not found, the transcript is
                empty, or pre/final validation fails.
        """
        from narrare_core.llm.intents import LLMIntent

        transcript = await self._prepare_transcript(session_id)
        invocation_id = uuid4()
        prompt_ctx = self._build_prompt_context(transcript)
        invocation_ctx = self._build_invocation_context(
            intent=LLMIntent.WRITE,
            prompt_ctx=prompt_ctx,
            user_id=user_id,
            project_id=project_id,
            chapter_id=chapter_id,
            session_id=session_id,
            invocation_id=invocation_id,
        )

        prompt = await build_and_validate_prompt(
            self._composer,
            self._invocation_pipeline,
            LLMIntent.WRITE,
            prompt_ctx,
            invocation_ctx,
            user_id=user_id,
            project_id=project_id,
        )

        resolved_limits = self._run_limit_resolver.resolve(
            config=self._config,
            budget=None,
            invocation_id=invocation_id,
        )

        logger.info(
            "interview_draft_stream_start",
            invocation_id=str(invocation_id),
            session_id=str(session_id),
            streaming=True,
        )

        async for chunk in self._registry.stream(
            intent=LLMIntent.WRITE,
            system_prompt=prompt.system,
            user_prompt=prompt.user,
            config=self._config,
            usage_limits=resolved_limits.usage_limits,
            api_key=self._api_key,
            base_url=self._base_url,
        ):
            yield chunk

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _prepare_transcript(self, session_id: UUID) -> str:
        """Look up the session, format, and cap the transcript.

        Args:
            session_id: The session to read.

        Returns:
            The budget-capped transcript string.

        Raises:
            WritingError: If the session is not found or the transcript
                is empty.
        """
        session = await self._session_manager.get_session(session_id)
        if session is None:
            raise WritingError(
                "Session not found or expired.",
                code="SESSION_NOT_FOUND",
            )

        transcript = self._format_transcript(session.conversation_history)
        original_transcript = transcript
        transcript = cap_to_budget(transcript, MAX_TRANSCRIPT_TOKENS)
        if len(transcript) < len(original_transcript):
            logger.warning(
                "interview_transcript_capped",
                original_chars=len(original_transcript),
                capped_chars=len(transcript),
                budget=MAX_TRANSCRIPT_TOKENS,
                messages=len(session.conversation_history),
            )

        if not transcript.strip():
            raise WritingError(
                "No interview answers collected yet. Answer some questions first.",
                code="EMPTY_TRANSCRIPT",
            )
        return transcript

    @staticmethod
    def _build_prompt_context(transcript: str) -> PromptContext:
        """Build the PromptContext for draft generation.

        The transcript becomes ``author_instructions`` — the
        runtime-input channel (RULE-02a). System/task prompts are built
        by the PromptComposer cascade, not here.
        """
        from narrare_core.prompts.context import PromptContext

        return PromptContext(
            language="en",
            mode="new_chapter",
            author_instructions=(
                "Based on the following interview transcript, "
                "write a complete chapter draft:\n\n"
                f"{transcript}"
            ),
        )

    @staticmethod
    def _build_invocation_context(
        *,
        intent: LLMIntent,
        prompt_ctx: PromptContext,
        user_id: UUID,
        project_id: UUID,
        chapter_id: UUID,
        session_id: UUID,
        invocation_id: UUID,
    ) -> PromptInvocationContext:
        """Build the PromptInvocationContext with all identifiers.

        ADR-045 Decision 6: user and project IDs are mandatory in the
        invocation context. Chapter and session IDs are carried as
        dynamic inputs so enrichers and evidence can correlate them.
        """
        from narrare_core.ai_invocation.models import PromptInvocationContext

        return PromptInvocationContext(
            feature_id=INTERVIEW_DRAFT_FEATURE_ID,
            intent=intent,
            mode="new_chapter",
            invocation_id=invocation_id,
            user_id=user_id,
            project_id=project_id,
            language=prompt_ctx.language,
            streaming=True,
            dynamic_inputs={
                "chapter_id": str(chapter_id),
                "session_id": str(session_id),
            },
            prompt_context=prompt_ctx,
        )

    @staticmethod
    def _format_transcript(
        conversation_history: list[dict[str, str]],
    ) -> str:
        """Format conversation history as an interview transcript.

        Args:
            conversation_history: List of message dicts with ``role`` and
                ``content`` keys.

        Returns:
            Formatted transcript string with ``Author:`` and
            ``Interviewer:`` prefixes.
        """
        parts: list[str] = []
        for msg in conversation_history:
            role = msg.get("role", "unknown")
            text = msg.get("content", "")
            if role == "user":
                parts.append(f"Author: {text}")
            elif role == "assistant":
                parts.append(f"Interviewer: {text}")
        return "\n\n".join(parts)
