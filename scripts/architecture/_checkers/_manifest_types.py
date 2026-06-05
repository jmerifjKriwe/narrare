"""TypedDict definitions for prompt-surface manifest entries.

Extracted from ``_check_prompt_surface.py`` to keep the checker under
RULE-04 (300 lines).  These types describe the YAML manifest at
``scripts/architecture/prompt-surface-manifest.yaml``.
"""

from __future__ import annotations

from typing import TypedDict

__all__ = ["ManifestEntry", "ManifestSecurity"]


class ManifestSecurity(TypedDict, total=False):
    """Security constraints for a manifest route entry."""

    xml_required: list[str]
    generated_suggestions_must_be_labelled: list[str]


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
