"""Provider-free prompt preview view models.

These dataclasses are the Core contract surface for PROMPT-003. They carry
resolved prompt text plus variable provenance/security metadata without
calling an LLM, instantiating an agent, or importing provider SDKs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare_core.prompts.variable_taxonomy import VariableProvenance, VariableSecurity


@dataclass(frozen=True, slots=True)
class PromptVariableMetadata:
    """Per-variable preview metadata for UI provenance/security rendering."""

    name: str
    description: str
    variable_type: str
    required: bool
    provenance: VariableProvenance
    security: VariableSecurity


class PreviewDiagnosticKind:
    """String constants for provider-free preview diagnostics."""

    MISSING_VARIABLE = "missing_variable"
    UNUSED_VARIABLE = "unused_variable"
    VALIDATION_NOTE = "validation_note"


@dataclass(frozen=True, slots=True)
class PreviewDiagnostic:
    """A single typed diagnostic emitted during provider-free preview."""

    kind: str
    variable_name: str | None
    message: str


@dataclass(frozen=True, slots=True)
class PromptPreview:
    """Fully resolved provider-free prompt preview."""

    system_prompt: str
    user_prompt: str
    first_message: str | None
    cascade_source: str
    variables: list[PromptVariableMetadata]
    diagnostics: list[PreviewDiagnostic]
