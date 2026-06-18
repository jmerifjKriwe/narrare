"""TypedDict definitions for prompt-surface manifest entries.

Extracted from ``_check_prompt_surface.py`` to keep the checker under
RULE-04 (300 lines).  These types describe the YAML manifest at
``scripts/architecture/prompt-surface-manifest.yaml``.
"""

from __future__ import annotations

from typing import TypedDict

__all__ = ["ManifestContextMode", "ManifestEntry", "ManifestSecurity"]


class ManifestSecurity(TypedDict, total=False):
    """Security constraints for a manifest route entry."""

    xml_required: list[str]
    generated_suggestions_must_be_labelled: list[str]


class ManifestContextMode(TypedDict, total=False):
    """A single ``context_modes`` sub-entry (ADR-049 D11).

    Each context-mode declares its own template, variables, and security
    constraints, parallel to the top-level manifest entry shape.
    """

    mode: str
    template: str
    content_type: str
    required_variables: list[str]
    optional_variables: list[str]
    security: ManifestSecurity
    fallback_policy: str


class ManifestEntry(TypedDict, total=False):
    """A single route entry from the prompt-surface manifest."""

    intent: str
    routeable: bool
    category: str
    mode: str
    template: str
    content_type: str
    output_language_variable: str | None
    required_variables: list[str]
    optional_variables: list[str]
    security: ManifestSecurity
    fallback_policy: str
    rationale: str
    # ADR-049 D11: optional context_modes list for multi-template intents.
    context_modes: list[ManifestContextMode]
