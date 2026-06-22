"""Prompts Pydantic schemas — maps core dataclasses to API responses.

Includes PROMPT-003 (CR-AUFG-07-16) schemas for the provider-free preview,
reset-with-metadata, and optional live-test endpoints. All new models use
Pydantic v2 with ``from_attributes=True`` so Core dataclasses can be mapped
via ``model_validate``.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PromptInfoResponse(BaseModel):
    """Metadata summary for a single prompt."""

    model_config = ConfigDict(from_attributes=True)

    prompt_id: str = Field(..., description="Prompt ID: {category}/{language}/{mode}")
    name: str
    category: str
    language: str
    source: str
    has_override: bool
    prompt_version: str


class PromptDetailResponse(BaseModel):
    """Full prompt content with metadata and variable info."""

    model_config = ConfigDict(from_attributes=True)

    prompt_id: str
    content: str
    base_content: str
    source: str
    is_overridden: bool
    variables: list[str]
    metadata: dict[str, Any]


class CascadePathResponse(BaseModel):
    """A single level in the prompt cascade."""

    model_config = ConfigDict(from_attributes=True)

    level: str
    path: str
    exists: bool


class UpdateInfoResponse(BaseModel):
    """Information about a prompt with available bundled updates."""

    model_config = ConfigDict(from_attributes=True)

    prompt_id: str
    override_version: str
    current_bundled_version: str


class DiffResponse(BaseModel):
    """Side-by-side content for diff comparison."""

    model_config = ConfigDict(from_attributes=True)

    prompt_id: str
    override_content: str
    bundled_content: str


class SaveOverrideRequest(BaseModel):
    """Request body for saving a prompt override."""

    content: str = Field(..., min_length=1, description="Override prompt content")


# ---------------------------------------------------------------------------
# PROMPT-003 (CR-AUFG-07-16) — preview / reset / live-test schemas
# ---------------------------------------------------------------------------

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
