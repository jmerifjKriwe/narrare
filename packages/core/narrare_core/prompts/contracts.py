"""Contracts for provider-free prompt preview (PROMPT-003).

The preview protocol is the boundary consumed by API/MCP/CLI adapters. It is
intentionally free of LLM, provider, agent, HTTP, auth, and persistence imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from narrare_core.prompts.preview_types import PromptPreview


def _empty_variables() -> dict[str, str]:
    """Return an empty preview variable mapping."""
    return {}


@dataclass(frozen=True, slots=True)
class ContextSnapshot:
    """Raw variable values for provider-free preview resolution."""

    variables: dict[str, str] = field(default_factory=_empty_variables)
    language: str = "en"
    genre: str | None = None
    mode: str | None = None


@runtime_checkable
class PromptPreviewProtocol(Protocol):
    """Provider-free prompt preview resolver contract."""

    async def preview(
        self,
        *,
        prompt_id: str,
        snapshot: ContextSnapshot,
        edited_override: str | None = None,
    ) -> PromptPreview:
        """Resolve a prompt preview without invoking any model provider."""
        ...
