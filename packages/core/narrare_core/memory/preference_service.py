"""Preference service — derives user preferences from mem0 memories.

Implements the PreferenceProvider protocol. Queries mem0 for
semantic memories and aggregates them into a PreferenceProfile.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from narrare_core.memory.models import PreferenceProfile

if TYPE_CHECKING:
    from uuid import UUID

logger = structlog.get_logger(__name__)

# Queries used to extract different preference dimensions from mem0
_PREFERENCE_QUERIES: list[tuple[str, str]] = [
    ("style", "What writing style does the user prefer?"),
    ("content", "What content preferences does the user have?"),
    ("constraints", "What does the user dislike or want to avoid?"),
]


class PreferenceService:
    """Derives user preferences from mem0 semantic memories.

    Queries mem0 with intent-specific queries and aggregates results
    into a PreferenceProfile suitable for prompt injection.

    Gracefully degrades (D7): returns an empty profile when mem0
    is unavailable or returns no results.

    Implements:
        PreferenceProvider protocol.
    """

    def __init__(
        self,
        mem0_client: Any,
        *,
        confidence_denominator: float = 20.0,
    ) -> None:
        self._mem0 = mem0_client
        self._confidence_denominator = confidence_denominator

    async def get_preferences(
        self,
        user_id: UUID,
        project_id: UUID,
    ) -> PreferenceProfile:
        """Query mem0 and aggregate results into a PreferenceProfile.

        Returns an empty profile if mem0 returns no results or
        encounters errors.
        """
        style: dict[str, str] = {}
        content: dict[str, str] = {}
        constraints: list[str] = []
        total_memories = 0

        for dimension, query in _PREFERENCE_QUERIES:
            try:
                result = await self._mem0.search(
                    query=query,
                    filters={"user_id": str(user_id), "agent_id": str(project_id)},
                )
                memories = result.get("results", [])
                total_memories += len(memories)

                for memory in memories:
                    text = memory.get("memory", "") or memory.get("text", "")
                    if not text:
                        continue

                    if dimension == "style":
                        style[f"preference_{len(style)}"] = text
                    elif dimension == "content":
                        content[f"preference_{len(content)}"] = text
                    elif dimension == "constraints":
                        constraints.append(text)

            except Exception:
                logger.warning(
                    "preference_query_failed",
                    dimension=dimension,
                    user_id=str(user_id),
                )

        confidence = (
            min(1.0, total_memories / self._confidence_denominator) if total_memories > 0 else 0.0
        )

        return PreferenceProfile(
            user_id=user_id,
            project_id=project_id,
            event_count=total_memories,
            confidence=confidence,
            style=style,
            content=content,
            constraints=constraints,
        )

    async def reset(self, user_id: UUID, project_id: UUID) -> None:
        """Clear all mem0 memories for the user+project scope."""
        try:
            await self._mem0.delete_all(
                user_id=str(user_id),
                agent_id=str(project_id),
            )
            logger.info(
                "preferences_reset",
                user_id=str(user_id),
                project_id=str(project_id),
            )
        except Exception:
            logger.warning(
                "preference_reset_failed",
                user_id=str(user_id),
                project_id=str(project_id),
            )
