"""DialogueCoachService Protocol — Backend Service Layer (ADR-069 D17).

Exposes BOTH ``run()`` (non-streaming → ``DialogueCoachResponse``) AND
``stream()`` (``AsyncIterator[DialogueCoachStreamEvent]``) per RULE-13 /
ADR-065. The two methods share one provider/model-settings path: the
service builds one PromptComposer invocation + one DialogueCoachAgent,
and ``run()`` materialises the streamed events into a single response
while ``stream()`` yields them incrementally.

RULE-12: the Service Layer is the only public API. WebUI calls
``stream()`` via the SSE router; future MCP / A2A adapters call ``run()``.

See:
    ADR-069 Decision 17 (run + stream two-method contract),
    ADR-065 (RULE-13 reconciliation),
    CONSTRAINTS.md RULE-03, RULE-12, RULE-13.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.ai_assist.schemas import (
        DialogueCoachRequest,
        DialogueCoachResponse,
        DialogueCoachStreamEvent,
    )


@runtime_checkable
class DialogueCoachServiceProtocol(Protocol):
    """Backend service for the Dialogue Coach (ASSIST-004).

    Two methods, one provider path (ADR-065):
    - ``run()`` — non-streaming. Returns the full ``DialogueCoachResponse``.
      For MCP / A2A / CLI clients.
    - ``stream()`` — streaming. Yields ``DialogueCoachStreamEvent``
      instances (progress / result / done / error). For the WebUI SSE router.
    """

    async def run(
        self,
        chapter_id: UUID,
        user_id: UUID,
        request: DialogueCoachRequest,
    ) -> DialogueCoachResponse:
        """Non-streaming coach invocation — returns the full result."""
        ...

    async def stream(
        self,
        chapter_id: UUID,
        user_id: UUID,
        request: DialogueCoachRequest,
    ) -> AsyncIterator[DialogueCoachStreamEvent]:
        """Streaming coach invocation — yields SSE events."""
        ...
