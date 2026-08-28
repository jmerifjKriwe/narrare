"""Generation API service contracts — written before implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.generation.schemas import NameGenerateRequest, NameGenerateResponse


@runtime_checkable
class NameGeneratorProtocol(Protocol):
    """Protocol for name generation API service.

    Ownership (IDOR remediation S12b): ``generate_names`` gates the request's
    project on the caller BEFORE any KB read or LLM call — foreign and unknown
    projects are indistinguishable (``NotFoundError`` → 404).
    """

    async def generate_names(
        self,
        request: NameGenerateRequest,
        user_id: UUID,
    ) -> NameGenerateResponse: ...
