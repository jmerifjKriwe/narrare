"""Generation API service contracts — written before implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from narrare.generation.schemas import NameGenerateRequest, NameGenerateResponse


@runtime_checkable
class NameGeneratorProtocol(Protocol):
    """Protocol for name generation API service."""

    async def generate_names(
        self,
        request: NameGenerateRequest,
    ) -> NameGenerateResponse: ...
