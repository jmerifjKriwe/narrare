"""Output types for CoreferenceAgent.

See ADR-015 Phase 2.1 — Output Types.
ANAL-005 — Coreference Analysis (LLM-based).

Resolves pronoun references to character names, flags ambiguous pronouns,
tracks character mentions, and scores overall referential clarity.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PronounResolution(BaseModel):
    """A single pronoun resolved to its referent.

    Attributes:
        pronoun: The pronoun token as it appears in the text
            (e.g. ``"he"``, ``"she"``, ``"they"``, ``"his"``, ``"her"``,
            ``"their"``, ``"it"``).
        position: Character offset of the pronoun within the analysed text.
        referent: The character name the pronoun refers to, or ``""`` when
            the referent could not be determined (ambiguous / unresolved).
        confidence: Resolution confidence (0.0-1.0).
        is_ambiguous: ``True`` when multiple referents are plausible for this
            pronoun (the reader cannot determine the referent with certainty).
    """

    pronoun: str = ""
    position: int = 0
    referent: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    is_ambiguous: bool = False


class CharacterMention(BaseModel):
    """A character and the positions where it is mentioned.

    Attributes:
        character_name: The character's name (or most common reference form).
        mentions: Character offsets within the analysed text where the
            character is referred to by name or pronoun.
        is_pov: ``True`` when this character appears to be the POV character
            for the analysed passage.
    """

    character_name: str = ""
    mentions: list[int] = []
    is_pov: bool = False


class CoreferenceOutput(BaseModel):
    """Structured output from the CoreferenceAgent.

    Attributes:
        resolutions: Per-pronoun resolutions to their referents.
        character_mentions: Per-character mention tracking.
        clarity_score: Overall referential clarity of the passage (0-100).
            Higher is clearer; ambiguous pronouns and unresolved references
            lower the score.
        summary: A brief free-text assessment of referential clarity
            (1-3 sentences).
    """

    resolutions: list[PronounResolution] = []
    character_mentions: list[CharacterMention] = []
    clarity_score: float = Field(default=0.0, ge=0.0, le=100.0)
    summary: str = ""


class CoreferenceDeps:
    """Dependencies for CoreferenceAgent.

    This is a plain class (not Pydantic) — follows the existing pattern
    used by POVDeps, ReadabilityDeps, and ConsistencyDeps.

    Attributes:
        text: The passage / chapter text to analyse.
        project_title: The project title (for prompt context).
        genre: The project genre (for prompt context).
        writing_language: Language code (``"en"``, ``"de"``, ``"fr"``).
        chapter_title: The chapter title (for prompt context).
    """

    def __init__(
        self,
        text: str = "",
        project_title: str = "",
        genre: str = "",
        writing_language: str = "en",
        chapter_title: str = "",
    ) -> None:
        self.text = text
        self.project_title = project_title
        self.genre = genre
        self.writing_language = writing_language
        self.chapter_title = chapter_title
