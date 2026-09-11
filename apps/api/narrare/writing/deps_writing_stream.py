"""Writing module dependency injection — request-scoped stream factory.

RULE-04 split from :mod:`narrare.writing.deps_writing` (the module hit
the 200-line hard limit): the stream-path factory is a distinct
responsibility — it recovers the project scope from the generation-
request row instead of a caller-supplied ``project_id``.

Ownership (IDOR remediation S6 + fix-wave N1): the request row is
validated via :func:`narrare.writing._helpers.get_validated_request`
BEFORE ``get_writing_service`` runs, and the shared factory re-checks
novel ownership at entry — so an unknown or foreign novel surfaces as
``NotFoundError`` (404) before the SSE response starts (CR-07).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.writing.service import WritingService


async def get_writing_service_for_stream(
    session: AsyncSession,
    user_id: str,
    request_id: UUID,
) -> WritingService:
    """Request-scoped factory for the SSE stream path (ADR-082, Task 3e).

    The stream route only knows ``request_id`` — the novel is recoverable
    solely from the generation-request row. Resolving it here keeps the one
    factory resolution path project-aware on the real generation path:
    ADR-082 budget carving (series in scope → series-history ceiling +
    tier-base carve-out) and project-level model routing both key on the
    project id. The row is validated via
    :func:`narrare.writing._helpers.get_validated_request`, so ownership is
    enforced before the SSE response starts (CR-07).

    Args:
        session: DB session for repository and settings lookups.
        user_id: Authenticated user identifier (access check).
        request_id: The generation request being streamed.

    Raises:
        NotFoundError: If the request does not exist or belongs to
            another user.

    Returns:
        Configured WritingService with budgets resolved for the
        request's novel.
    """
    from narrare.writing._helpers import get_validated_request
    from narrare.writing.deps_writing import get_writing_service
    from narrare.writing.repository import GenerationRepository

    request_model = await get_validated_request(
        GenerationRepository(session),
        request_id,
        user_id,
    )
    return await get_writing_service(session, user_id, request_model.novel_id)
