"""PROMPT-003 (CR-AUFG-07-16) — preview / reset / live-test Pydantic schemas.

Split out of ``schemas.py`` per RULE-04 (file-size limit).  These schemas back
the provider-free preview, reset-with-metadata, and optional live-test
endpoints under the ``/api/v1/prompts/{prompt_id}`` route tree.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_PreviewLanguage = Literal["en", "de", "fr"]
_DiagnosticKind = Literal["missing_variable", "unused_variable", "validation_note"]


class PreviewRequest(BaseModel):
    """Request body for ``POST /prompts/{prompt_id}/preview``.

    Variables carry raw resolved values; the preview service builds a
    :class:`ContextSnapshot` from them. No LLM is invoked.
    """

    variables: dict[str, str] = Field(default_factory=dict)
    language: _PreviewLanguage = "en"
    genre: str | None = None
    mode: str | None = None
    edited_override: str | None = None


class PreviewVariableMetadataResponse(BaseModel):
    """Per-variable metadata for the preview response.

    Mirrors :class:`narrare_core.prompts.preview_types.PromptVariableMetadata`.
    ``provenance``/``security`` are surfaced as their enum string values so
    the frontend can render governance labels without importing Core types.
    """

    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str
    variable_type: str
    required: bool
    provenance: str
    security: str


class PreviewDiagnosticResponse(BaseModel):
    """A single diagnostic surfaced by the provider-free preview.

    ``kind`` is a closed Literal matching
    :class:`narrare_core.prompts.preview_types.PreviewDiagnosticKind`.
    """

    model_config = ConfigDict(from_attributes=True)

    kind: _DiagnosticKind
    variable_name: str | None
    message: str


class PreviewResponse(BaseModel):
    """Provider-free resolved prompt preview.

    Mirrors :class:`narrare_core.prompts.preview_types.PromptPreview`.
    """

    model_config = ConfigDict(from_attributes=True)

    system_prompt: str
    user_prompt: str
    first_message: str | None
    cascade_source: str
    variables: list[PreviewVariableMetadataResponse]
    diagnostics: list[PreviewDiagnosticResponse]


class ResetResponse(BaseModel):
    """Response from ``POST /prompts/{prompt_id}/reset`` — metadata, not bool.

    ``effective_source``/``effective_content`` describe the post-reset state
    so the UI can render the restored prompt without a follow-up GET.
    """

    model_config = ConfigDict(from_attributes=True)

    reset: bool
    effective_source: str
    effective_content: str


class LiveTestRequest(BaseModel):
    """Request body for ``POST /prompts/{prompt_id}/live-test``.

    ``acknowledge_token_cost`` must be true — the client confirms the
    token/privacy warning before any provider call is made.
    """

    variables: dict[str, str] = Field(default_factory=dict)
    language: _PreviewLanguage = "en"
    genre: str | None = None
    mode: str | None = None
    edited_override: str | None = None
    user_prompt: str = ""
    acknowledge_token_cost: bool = Field(
        default=False,
        description="Must be true — client confirms the token/privacy warning.",
    )


class LiveTestStartedResponse(BaseModel):
    """Validation metadata returned before SSE streaming begins.

    Surfaces the resolved model id, intent label, and remaining rate-limit
    budget so the client can render a pre-stream confirmation UI.
    """

    model_config = ConfigDict(from_attributes=True)

    prompt_id: str
    intent: str
    model_id: str
    rate_limit_remaining: int
