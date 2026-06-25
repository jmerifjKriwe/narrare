"""Style-variant regeneration schemas — request model for CR-AUFG-07-22.

Split from schemas.py per RULE-04 (file-size limit).

A finite :class:`StyleVariant` taxonomy flows from this request through the
rewrite pipeline into the ``{{style_variant_instructions}}`` template variable.
Model/provider/token settings resolve through the existing cascade — the
variant never changes providers.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from narrare_core.writing.style_variants import (
    StyleVariant,  # noqa: TC001 — needed at runtime for Pydantic model resolution
)

#: The source operation a style-variant regeneration builds on.
SourceMode = Literal["rewrite", "co_author"]


class StyleVariantRegenerateRequest(BaseModel):
    """Request to regenerate an AI output in a specific style variant.

    The source text is the existing AI output (or selection) that the writer
    wants regenerated in a controlled creative direction.  Context markers
    provide surrounding text for register matching.  Model/provider/token
    settings resolve through the existing cascade — the variant never changes
    providers.
    """

    source_text: str = Field(
        ...,
        min_length=50,
        max_length=2000,
        description="The existing AI output text to regenerate in the variant style",
    )
    context_before: str | None = Field(
        default=None,
        max_length=500,
        description="Text immediately before the source output (up to 500 chars)",
    )
    context_after: str | None = Field(
        default=None,
        max_length=500,
        description="Text immediately after the source output (up to 500 chars)",
    )
    style_variant: StyleVariant = Field(
        ...,
        description="Creative direction: leaner, more_lyrical, more_tense, "
        "more_intimate, more_dialogue, more_sensory",
    )
    tone: str = Field(
        default="balanced",
        min_length=1,
        max_length=100,
        description="Tone preference (resolved through the settings cascade)",
    )
    language: str = Field(
        default="en",
        min_length=2,
        max_length=5,
        description="Output language",
    )
    source_mode: SourceMode = Field(
        default="rewrite",
        description=(
            "Source operation mode the variant builds on: "
            "'rewrite' (REWRITE pipeline, rewrite_mode='style') or "
            "'co_author' (CO_AUTHOR pipeline with co_author_focus)."
        ),
    )
