"""PROMPT-003 backend preview + reset services (CR-AUFG-07-16).

This module hosts two API-layer adapters over Core Protocols:

* :class:`PromptPreviewApiService` — wraps the provider-free Core
  :class:`PromptPreviewProtocol`. Builds a :class:`ContextSnapshot` from the
  request, delegates to Core, and maps the Core dataclass result to a
  Pydantic :class:`PreviewResponse`. Contains NO LLM/agent/provider code.
* :class:`PromptResetApiService` — wraps the Core management service and
  returns post-reset metadata (:class:`ResetResponse`) instead of a bare
  boolean, so the UI can render the restored prompt without a follow-up GET.

Both adapters stay well under the 300-line service hard limit (RULE-04).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, cast, get_args, runtime_checkable

import structlog

from narrare.prompts.schemas import (
    PreviewDiagnosticResponse,
    PreviewRequest,
    PreviewResponse,
    PreviewVariableMetadataResponse,
    ResetResponse,
)
from narrare_core.prompts.contracts import ContextSnapshot

if TYPE_CHECKING:
    from collections.abc import Iterable

    from narrare_core.prompts._management_types import PromptDetail
    from narrare_core.prompts.contracts import PromptPreviewProtocol
    from narrare_core.prompts.preview_types import PreviewDiagnostic

logger = structlog.get_logger(__name__)

_DiagnosticKind = Literal["missing_variable", "unused_variable", "validation_note"]
_VALID_DIAGNOSTIC_KINDS: frozenset[str] = frozenset(get_args(_DiagnosticKind))


@runtime_checkable
class _ResetDataSource(Protocol):
    """Minimal Core surface needed by :class:`PromptResetApiService`.

    Declared locally (not in Core) because this is an API-layer consumer's
    view of the Core management service — only the two methods the reset
    service actually needs (ISP). The real Core
    :class:`PromptManagementService` satisfies this Protocol structurally.
    """

    async def reset_override(self, prompt_id: str) -> bool: ...

    async def get_prompt(self, prompt_id: str) -> PromptDetail | None: ...


def _coerce_diagnostic_kind(kind: str) -> _DiagnosticKind:
    """Coerce a Core diagnostic kind to the wire Literal, with safe fallback.

    Core's ``PreviewDiagnostic.kind`` is typed as ``str``; the wire schema
    constrains it to a closed Literal. Unknown values (e.g. a future Core
    kind this adapter does not know yet) map to ``validation_note`` so the
    API never crashes on a forward-compat Core bump.
    """
    if kind in _VALID_DIAGNOSTIC_KINDS:
        return cast("_DiagnosticKind", kind)
    return "validation_note"


def _map_diagnostics(
    diagnostics: Iterable[PreviewDiagnostic],
) -> list[PreviewDiagnosticResponse]:
    """Map Core diagnostics to Pydantic diagnostic responses."""
    return [
        PreviewDiagnosticResponse(
            kind=_coerce_diagnostic_kind(d.kind),
            variable_name=d.variable_name,
            message=d.message,
        )
        for d in diagnostics
    ]


class PromptPreviewApiService:
    """Backend adapter over the Core provider-free preview Protocol.

    Args:
        core: Core ``PromptPreviewProtocol`` implementation (typically
            :class:`narrare_core.prompts.preview.PromptPreviewService`).
    """

    def __init__(self, *, core: PromptPreviewProtocol) -> None:
        self._core = core

    async def preview(self, prompt_id: str, request: PreviewRequest) -> PreviewResponse:
        """Resolve a provider-free prompt preview.

        Args:
            prompt_id: Prompt identifier in ``{category}/{language}/{mode}`` form.
            request: Variables + locale + optional edited override.

        Returns:
            Pydantic ``PreviewResponse`` with resolved text, per-variable
            metadata, and diagnostics. Resolution failures surface as typed
            diagnostics on the Core side (never raw exceptions).
        """
        snapshot = ContextSnapshot(
            variables=dict(request.variables),
            language=request.language,
            genre=request.genre,
            mode=request.mode,
        )
        result = await self._core.preview(
            prompt_id=prompt_id,
            snapshot=snapshot,
            edited_override=request.edited_override,
        )
        return PreviewResponse(
            system_prompt=result.system_prompt,
            user_prompt=result.user_prompt,
            first_message=result.first_message,
            cascade_source=result.cascade_source,
            variables=[
                PreviewVariableMetadataResponse(
                    name=v.name,
                    description=v.description,
                    variable_type=v.variable_type,
                    required=v.required,
                    # StrEnum → str: keep the wire form stable for the frontend.
                    provenance=str(v.provenance),
                    security=str(v.security),
                )
                for v in result.variables
            ],
            diagnostics=_map_diagnostics(result.diagnostics),
        )


class PromptResetApiService:
    """Reset service — ``POST /reset`` returns metadata, not bool.

    Calls the existing Core ``reset_override`` and then re-fetches the prompt
    detail to surface the effective (post-reset) content + source. This lets
    the UI render the restored state without a follow-up GET.

    Args:
        core: Core management service (or any :class:`_ResetDataSource`
            implementor). Typed against the minimal Protocol so tests can
            supply a Fake without ``type: ignore`` (RULE-23).
    """

    def __init__(self, *, core: _ResetDataSource) -> None:
        self._core = core

    async def reset_with_metadata(self, prompt_id: str) -> ResetResponse:
        """Reset an override and return the effective post-reset prompt state.

        Args:
            prompt_id: Prompt identifier in ``{category}/{language}/{mode}`` form.

        Returns:
            ``ResetResponse`` carrying ``reset`` (True iff an override was
            deleted), plus ``effective_source``/``effective_content``
            describing the now-active prompt.
        """
        did_reset = await self._core.reset_override(prompt_id)
        detail = await self._core.get_prompt(prompt_id)
        effective_source = detail.source if detail else ""
        effective_content = detail.content if detail else ""
        logger.info(
            "prompt_override_reset_api",
            prompt_id=prompt_id,
            reset=did_reset,
            effective_source=effective_source,
        )
        return ResetResponse(
            reset=did_reset,
            effective_source=effective_source,
            effective_content=effective_content,
        )
