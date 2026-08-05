"""Voice-block resolution helper for :meth:`WritingContextAssembler.assemble`.

Extracted from :mod:`narrare_core.writing.context_assembler` (RULE-04 — the
assembler exceeded the 400-line hard limit once Spec 3 / ADR-078 threaded
``series_id`` into the author-voice resolution). Voice resolution is a single,
cohesive responsibility (project the two voice contracts → prompt strings)
distinct from tier budgeting, so it earns its own module (RULE-06).

Two blocks are resolved here, both ADR-050 / ADR-074 / ADR-078 consumers:

* **Character voices** — :meth:`VoiceProfileConsumer.assemble_for_generation`
  → ``formatted_voice_profiles`` + freshness warnings (per-character).
* **Author voice** — :meth:`AuthorVoiceConsumer.resolve_for_generation`
  → the ``{{author_voice}}`` Delta-model content (series foundation + novel
  nuances, Spec 3 / ADR-078).

RULE-11 graceful degradation: when a consumer is ``None`` or no ``project_id``
is supplied the corresponding block renders empty (generation proceeds
without it).

See:
    ADR-050 — Voice Profile SSOT (producer/consumer split).
    ADR-074 — Author Voice Storage Contract.
    ADR-078 — Series Voice Hierarchy (Delta model).
    CONSTRAINTS.md RULE-04 / RULE-06 / RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.profiles.author_voice_consumer import AuthorVoiceConsumer
    from narrare_core.profiles.contracts import VoiceProfileConsumer


async def resolve_voice_blocks(
    voice_profile_consumer: VoiceProfileConsumer | None,
    author_voice_consumer: AuthorVoiceConsumer | None,
    project_id: UUID | None,
    series_id: UUID | None,
) -> tuple[str, list[str], str]:
    """Resolve the character-voice + author-voice prompt blocks.

    Args:
        voice_profile_consumer: Optional character-voice consumer (ADR-050).
            When ``None`` or no project, the character-voice block is empty.
        author_voice_consumer: Optional author-voice consumer (ADR-074 /
            ADR-078). When ``None`` or no project, the author-voice block is
            empty.
        project_id: The novel whose voice blocks are assembled. When ``None``
            both blocks render empty (RULE-11).
        series_id: The novel's series, or ``None`` for a standalone novel.
            Forwarded to :meth:`AuthorVoiceConsumer.resolve_for_generation`
            so the author-voice Delta composition is applied for series novels.

    Returns:
        A ``(character_voice_profiles, voice_profile_warnings, author_voice)``
        triple ready to thread into :class:`WritingContext`.
    """
    # Character voices (ADR-050 SSOT consumer): per-character profiles +
    # freshness warnings. Empty when no consumer / no project (RULE-11).
    character_voice_profiles = ""
    voice_profile_warnings: list[str] = []
    if voice_profile_consumer is not None and project_id is not None:
        voice_profile = await voice_profile_consumer.assemble_for_generation(project_id)
        character_voice_profiles = voice_profile.formatted_voice_profiles
        voice_profile_warnings = list(voice_profile.freshness_warnings)

    # Author voice (ADR-074 / ANAL-007 + Spec 3 / ADR-078 Delta model): the
    # narrator's prose voice. Resolved via the consumer's generation API,
    # which composes the series foundation + novel nuances (Delta) when
    # ``series_id`` is set, and falls back to the novel-only render for
    # standalone novels. Descriptive-only by construction (the consumer
    # delegates to the Core renderer — NEVER raw metrics, ADR-074 binding).
    # RULE-11 graceful: no consumer / no project → "".
    author_voice = ""
    if author_voice_consumer is not None and project_id is not None:
        author_voice = await author_voice_consumer.resolve_for_generation(
            project_id,
            series_id,
        )

    return character_voice_profiles, voice_profile_warnings, author_voice
