"""Style-variant taxonomy for creative regeneration (CR-AUFG-07-22).

A finite set of author-facing creative directions that can be applied when
regenerating an AI output.  These are NOT model-routing shortcuts and do not
bypass prompt customisation or the settings cascade — they inject additional
creative-direction text into the existing ``rewrite_selection`` prompt via the
``{{style_variant_instructions}}`` template variable.

Design notes:
- The instruction mapping is module-private (``_STYLE_VARIANT_INSTRUCTIONS``),
  matching the ``_REWRITE_MODE_INSTRUCTIONS`` convention in
  :mod:`narrare_core.writing.pipeline_rewrite`.  Callers resolve instructions
  through :func:`get_style_variant_instructions`, which returns ``""`` for
  ``None`` so the template variable renders as nothing (backward compatible for
  non-variant rewrites).
- RULE-02 / RULE-02a / RULE-02b: the variant direction is a Cascade variable,
  not an inline f-string.  This module only produces the *content* of that
  variable; the prompt itself is assembled exclusively in ``core/prompts/``.

See: docs/features/ai-ux/CR-AUFG-07-22-style-variants-regeneration.md
"""

from __future__ import annotations

from enum import StrEnum


class StyleVariant(StrEnum):
    """Finite creative-direction taxonomy for style-variant regeneration.

    Each value flows from the API schema → pipeline → prompt template as
    ``{{style_variant_instructions}}``.  The original output remains visible
    and unchanged until a variant is accepted.
    """

    LEANER = "leaner"
    MORE_LYRICAL = "more_lyrical"
    MORE_TENSE = "more_tense"
    MORE_INTIMATE = "more_intimate"
    MORE_DIALOGUE = "more_dialogue"
    MORE_SENSORY = "more_sensory"


# Module-private by convention (see ``_REWRITE_MODE_INSTRUCTIONS``).
# Resolved publicly via :func:`get_style_variant_instructions`.
_STYLE_VARIANT_INSTRUCTIONS: dict[StyleVariant, str] = {
    StyleVariant.LEANER: (
        "Make the prose leaner and more economical. Cut adjectives, tighten "
        "sentences, and let strong verbs carry the weight. Remove anything "
        "that does not earn its place on the page."
    ),
    StyleVariant.MORE_LYRICAL: (
        "Make the prose more lyrical and flowing. Use rhythm, assonance, and "
        "evocative imagery to create a musical quality. Let sentences breathe "
        "with longer, more ornamented phrasing."
    ),
    StyleVariant.MORE_TENSE: (
        "Make the prose tenser and more urgent. Use short, punchy sentences "
        "and increase the sense of immediacy and pressure. Cut anything that "
        "slows the momentum."
    ),
    StyleVariant.MORE_INTIMATE: (
        "Make the prose more intimate and emotionally close. Draw the reader "
        "into the character's inner world using smaller, more personal details "
        "and a confessional, vulnerable tone."
    ),
    StyleVariant.MORE_DIALOGUE: (
        "Shift toward more dialogue. Convert narration and description into "
        "spoken exchanges where possible, letting characters reveal information "
        "and emotion through conversation."
    ),
    StyleVariant.MORE_SENSORY: (
        "Make the prose more sensory and immersive. Ground the reader in "
        "physical sensation — smell, texture, sound, taste, and temperature. "
        "Let the body perceive the scene."
    ),
}


def get_style_variant_instructions(variant: StyleVariant | None) -> str:
    """Return the creative-direction instruction text for a style variant.

    Args:
        variant: The style variant to resolve, or ``None`` when no variant
            is requested (e.g. a plain rewrite without style-variant direction).

    Returns:
        The instruction string for the variant, or an empty string when
        ``variant is None`` (the template variable renders as nothing,
        preserving backward compatibility for non-variant rewrites).
    """
    if variant is None:
        return ""
    return _STYLE_VARIANT_INSTRUCTIONS.get(variant, "")
