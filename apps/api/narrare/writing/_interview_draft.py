"""Interview-assisted draft generation.

Extracted from ``ws_handler.py`` for RULE-04 compliance (max 300 lines).
Handles building the interview transcript and streaming the final draft.

Uses:
- :class:`LLMGateway` for LLM calls (RULE-01)
- :class:`PromptComposer` for prompt assembly (RULE-02)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from uuid import UUID

    from fastapi import WebSocket

    from narrare_core.llm.gateway import LLMGateway
    from narrare_core.llm.intents import ResolvedModelConfig
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.writing.session_manager import SessionManager

logger = structlog.get_logger(__name__)


class InterviewDraftGenerator:
    """Generates a full chapter draft from collected interview answers.

    Formats the conversation history as a transcript and streams a
    complete draft via the LLM gateway.

    Dependencies are injected via constructor (DI pattern).
    """

    def __init__(
        self,
        session_manager: SessionManager,
        gateway: LLMGateway,
        composer: PromptComposer,
        config: ResolvedModelConfig,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._gateway = gateway
        self._composer = composer
        self._config = config
        self._api_key = api_key
        self._base_url = base_url

    async def generate(
        self,
        websocket: WebSocket,
        session_id: UUID,
    ) -> None:
        """Generate a full draft from the interview transcript.

        Collects all messages from the session (user answers and
        assistant questions), formats them as a transcript, and
        streams a complete draft via the LLM gateway.

        Sends ``text_chunk`` messages during streaming and a final
        ``draft_done`` or ``error`` message when complete.
        """
        session = await self._session_manager.get_session(session_id)
        if session is None:
            await websocket.send_json({"type": "error", "message": "Session not found or expired."})
            return

        transcript = self._format_transcript(session.conversation_history)

        if not transcript.strip():
            await websocket.send_json(
                {
                    "type": "error",
                    "message": "No interview answers collected yet. Answer some questions first.",
                }
            )
            return

        logger.info(
            "interview_draft_start",
            session_id=str(session_id),
            transcript_messages=len(session.conversation_history),
        )

        accumulated = await self._stream_draft(websocket, session_id, transcript)
        if accumulated is None:
            return  # error already sent

        await self._finalize(websocket, session_id, accumulated)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

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

    async def _stream_draft(
        self,
        websocket: WebSocket,
        session_id: UUID,
        transcript: str,
    ) -> list[str] | None:
        """Stream the draft generation via the LLM gateway.

        Returns:
            List of accumulated text chunks, or ``None`` on error.
        """
        accumulated: list[str] = []
        try:
            from narrare_core.llm.intents import LLMIntent
            from narrare_core.prompts.context import PromptContext

            ctx = PromptContext(
                language="en",
                mode="new_chapter",
                author_instructions=(
                    "Based on the following interview transcript, "
                    "write a complete chapter draft:\n\n"
                    f"{transcript}"
                ),
            )
            prompt = await self._composer.build(LLMIntent.WRITE, ctx)

            async for chunk in self._gateway.stream(
                intent=LLMIntent.WRITE,
                system_prompt=prompt.system,
                user_prompt=prompt.user,
                config=self._config,
                api_key=self._api_key,
                base_url=self._base_url,
            ):
                if chunk.is_final:
                    break
                accumulated.append(chunk.text)
                await websocket.send_json({"type": "text_chunk", "text": chunk.text})

        except Exception as e:
            logger.error(
                "interview_draft_failed",
                session_id=str(session_id),
                error=str(e),
            )
            await websocket.send_json({"type": "error", "message": f"Draft generation failed: {e}"})
            return None

        return accumulated

    async def _finalize(
        self,
        websocket: WebSocket,
        session_id: UUID,
        accumulated: list[str],
    ) -> None:
        """Persist the draft to the session and send completion message."""
        full_text = "".join(accumulated)
        if not full_text:
            return

        word_count = len(full_text.split())
        await self._session_manager.add_message(session_id, "assistant", full_text)
        await self._session_manager.append_prose(session_id, full_text)
        await websocket.send_json(
            {
                "type": "draft_done",
                "text": full_text,
                "word_count": word_count,
            }
        )
