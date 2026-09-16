"""Per-kind request payload builders for the generation access matrix.

Extracted from ``test_generation_access_matrix.py`` (ADR-086 L31) per
the RULE-04 size limit — the matrix file is the six-surface dispatch
hub and every migrated entry adds a branch; the pure request-mapping
moves here. Behavior is unchanged — only the location moved.
"""

from __future__ import annotations

from typing import Any

_SELECTION = (
    "This is a sufficiently long selection text that demonstrates the "
    "access-gate matrix flow. It needs to exceed fifty characters to "
    "satisfy Pydantic's min_length constraint on the request schemas."
)


def request_for_kind(kind: str) -> Any:
    """Valid request payload per endpoint kind."""
    from narrare.writing.schemas import (
        ExtendRequest,
        GenerateRequest,
        GenerationModeEnum,
        InlineSuggestRequest,
    )
    from narrare.writing.schemas_coauthor import CoAuthorFocus, CoAuthorRequest
    from narrare.writing.schemas_rewrite import RewriteMode, RewriteRequest
    from narrare.writing.schemas_style_variants import StyleVariantRegenerateRequest
    from narrare_core.writing.style_variants import StyleVariant

    match kind:
        case "generate":
            return GenerateRequest(
                mode=GenerationModeEnum.FULL_DRAFT,
                prompt="A storm approaches.",
                word_target=None,
                tone="balanced",
                language="en",
            )
        case "extend":
            return ExtendRequest(text_before="The night was dark. ", tone="balanced", language="en")
        case "rewrite":
            return RewriteRequest(selection_text=_SELECTION, mode=RewriteMode.TONE)
        case "coauthor":
            return CoAuthorRequest(selection_text=_SELECTION, focus=[CoAuthorFocus.SENTENCE])
        case "style_variant":
            return StyleVariantRegenerateRequest(
                source_text=_SELECTION, style_variant=StyleVariant.LEANER
            )
        case "suggest":
            return InlineSuggestRequest(text_before="The old house ")
        case _:
            raise ValueError(kind)
