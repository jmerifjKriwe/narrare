"""Bundled tone instructions for writing generation.

This module contains the built-in tone definitions used by WritingPipeline.
User-defined tone overrides come through prompt cascade (see ADR-026).

See:
    CONSTRAINTS.md RULE-04 — extracted from pipeline.py to stay under 400 lines.
"""

# -- Tone instructions — injected into prompt extra variables --

TONE_INSTRUCTIONS: dict[str, str] = {
    "dramatic": (
        "Use vivid imagery, heightened emotional stakes, powerful verbs, "
        "and dramatic pacing. Build tension through escalating sentences."
    ),
    "quiet": (
        "Use understated prose, sensory details, internal reflection, "
        "and gentle pacing. Let subtext carry the emotional weight."
    ),
    "suspenseful": (
        "Use short punchy sentences, cliffhangers, sensory details, "
        "and withheld information. Create urgency and uncertainty."
    ),
    "balanced": "",
    "humorous": (
        "Use witty observations, lighthearted tone, playful language, "
        "comedic timing, and unexpected juxtapositions. Maintain levity."
    ),
    "contemplative": (
        "Use reflective prose, philosophical musings, measured pacing, "
        "internal monologue, and layered observations."
    ),
    "romantic": (
        "Use evocative sensory details, emotional language, intimate moments, "
        "lyrical prose, and heightened emotional resonance."
    ),
    "dark": (
        "Use grim imagery, foreboding atmosphere, visceral details, "
        "moral ambiguity, and unsettling tension."
    ),
    "adventurous": (
        "Use dynamic action sequences, energetic pacing, bold descriptive "
        "language, rising stakes, and momentum."
    ),
}


def is_bundled_tone(tone: str) -> bool:
    """Check whether a tone name is one of the bundled built-in tones.

    Args:
        tone: Tone name to check.

    Returns:
        ``True`` if the tone has built-in instructions.
    """
    return tone in TONE_INSTRUCTIONS
