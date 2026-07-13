"""Session memory service — records and retrieves cross-session writing context.

Implements the SessionMemoryCollector protocol. Stores structural writing-
session summaries (mode, chapter title, word count) to mem0 so later
sessions can recall past writing decisions, and reads them back as
formatted context text for prompt injection.

Privacy (ADR-045 Decision 8, RULE-22): only structural metadata is ever
recorded — never raw chapter prose. The method has no content parameter,
so chapter body cannot reach mem0.

Graceful degradation (RULE-11): mem0 failures are logged as warnings and
never raised, ensuring the writing path never crashes on a memory outage.

See: ADR-045 Decision 8, CONSTRAINTS.md RULE-08/RULE-11/RULE-22.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Query used to retrieve past writing-session memories from mem0. Scoped to
# the user+project via filters so cross-project bleed is impossible.
_SESSION_QUERY = "writing sessions and chapter decisions"

# Maximum number of memories surfaced as cross-session context. Keeps the
# injected context bounded and the bullet list readable.
_MAX_CONTEXT_MEMORIES = 5


class SessionMemoryService:
    """Records and retrieves cross-session writing context via mem0.

    Stores a structural summary per writing session (no extra LLM call —
    the summary is pure string formatting) and reads past sessions back as
    a newline-joined bullet list for context assembly.

    Gracefully degrades (RULE-11): mem0 failures are warnings, not errors.

    Implements:
        SessionMemoryCollector protocol.
    """

    def __init__(self, mem0_client: Any) -> None:
        """Inject the mem0 client (AsyncMemory or NullMemoryClient)."""
        self._mem0 = mem0_client

    async def record_writing_session(
        self,
        user_id: object,
        project_id: object,
        *,
        mode: str,
        chapter_title: str,
        word_count: int,
    ) -> None:
        """Record a writing-session summary to mem0 (best-effort).

        Builds a structural summary from the inputs — no extra LLM call —
        and forwards it to mem0 scoped to the user+project. Never raises:
        mem0 failures are logged as warnings.
        """
        summary = (
            f"Writing session: user wrote '{chapter_title}' in {mode} mode ({word_count} words)"
        )
        try:
            await self._mem0.add(
                messages=summary,
                user_id=str(user_id),
                agent_id=str(project_id),
                metadata={
                    "type": "writing_session",
                    "mode": mode,
                    "chapter_title": chapter_title,
                    "word_count": word_count,
                },
            )
        except Exception:
            logger.warning(
                "session_memory_record_failed",
                user_id=str(user_id),
                project_id=str(project_id),
            )

    async def get_cross_session_context(
        self,
        user_id: object,
        project_id: object,
    ) -> str:
        """Retrieve past writing-session memories as formatted context text.

        Queries mem0 scoped to the user+project, takes the top results, and
        formats them as a newline-joined bullet list (``"- text\\n- text"``).

        Returns an empty string when mem0 returns no results or encounters
        errors (graceful degradation).
        """
        try:
            result = await self._mem0.search(
                query=_SESSION_QUERY,
                filters={
                    "user_id": str(user_id),
                    "agent_id": str(project_id),
                },
            )
        except Exception:
            logger.warning(
                "session_memory_query_failed",
                user_id=str(user_id),
                project_id=str(project_id),
            )
            return ""

        memories = result.get("results", [])
        bullets: list[str] = []
        for memory in memories[:_MAX_CONTEXT_MEMORIES]:
            text = memory.get("memory", "") or memory.get("text", "")
            if not text:
                continue
            bullets.append(f"- {text}")

        return "\n".join(bullets)
