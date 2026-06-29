"""Character-voice pipeline helpers — chapter loading + KB write + formatting.

Extracted from ``character_voice_service.py`` for RULE-04 compliance
(service < 300 lines). This module owns three distinct pipeline-helper
responsibilities that would bloat the orchestration service:

1. **Chapter loading** (:func:`load_selected_chapters`) — resolves the
   selected chapter ids (or all chapters) and validates they belong to the
   novel.
2. **KB write** (:func:`persist_voice_analysis`) — writes the merged
   :class:`VoiceAnalysis` to a character's KB ``metadata["speech"]
   ["voice_analysis"]``, preserving the 4 human-authored speech fields and
   bumping ``updated_at`` (ADR-055 Consequences / Decision 1).
3. **Runtime-content formatting** — builds the attributed-dialogue +
   per-character metrics strings that flow as user-channel runtime content
   to the :class:`CharacterVoiceAgent` (RULE-02a category 3), plus the
   agent run prompt assembled from them.

See:
    ADR-055 — Character voice storage contract (Decision 1 persistence scope).
    RULE-04 — Modularise, never compress.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from narrare.chapters.models import Chapter
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.repository import KBRepository
    from narrare_core.analysis.voice_types import AttributedUtterance
    from narrare_core.kb.schemas.character import VoiceAnalysis, VoiceMetrics


async def load_selected_chapters(
    chapter_repo: ChapterRepository,
    novel_id: UUID,
    chapter_ids: list[UUID] | None,
) -> list[Chapter]:
    """Load the selected chapters, or all chapters when none specified.

    Raises NotFoundError when a requested chapter is missing or does not
    belong to the novel.
    """
    if not chapter_ids:
        return list(await chapter_repo.list_by_novel(novel_id))

    chapters: list[Chapter] = []
    for cid in chapter_ids:
        chapter = await chapter_repo.get_by_id(cid, novel_id)
        if chapter is None:
            raise NotFoundError("Chapter", identifier=str(cid))
        chapters.append(chapter)
    return chapters


async def persist_voice_analysis(
    kb_repo: KBRepository,
    *,
    novel_id: UUID,
    character_name: str,
    voice_analysis: VoiceAnalysis,
) -> UUID | None:
    """Write ``voice_analysis`` to the character's KB ``speech`` block.

    Preserves the 4 human-authored speech fields (typical_phrases, dialect,
    vocabulary_quirks, body_language) — only ``voice_analysis`` is set.
    Bumps ``updated_at`` so ``profiles/_freshness.py::is_stale()`` keeps
    working (ADR-055 Consequences).

    Args:
        kb_repo: KB repository for finding the character entry + persisting.
        novel_id: The novel the character belongs to.
        character_name: The character's canonical name (matched case-insensitively).
        voice_analysis: The merged voice analysis to persist.

    Returns:
        The KB entry id persisted onto, or ``None`` when no matching
        character KB entry exists (the result is still surfaced to the UI).
    """
    from datetime import UTC, datetime
    from typing import cast

    entry = await kb_repo.get_by_name(novel_id, character_name)
    if entry is None or getattr(entry, "entity_type", "character") != "character":
        return None

    metadata: dict[str, object] = dict(entry.metadata_ or {})
    speech_raw = metadata.get("speech")
    speech: dict[str, object] = (
        dict(cast("dict[str, object]", speech_raw)) if isinstance(speech_raw, dict) else {}
    )
    # Only set voice_analysis — the 4 human-authored fields are preserved.
    speech["voice_analysis"] = voice_analysis.model_dump(mode="json")
    metadata["speech"] = speech

    await kb_repo.update(
        entry,
        {"metadata_": metadata, "updated_at": datetime.now(UTC)},
    )
    return entry.id


def format_attributed_dialogue(utterances: Sequence[AttributedUtterance]) -> str:
    """Format attributed utterances as speaker-tagged dialogue text.

    Utterances with no deterministic speaker (``speaker=None``) are tagged
    ``"?"`` so the agent can resolve them inline (ADR-055 Decision 3).
    """
    lines: list[str] = []
    for utt in utterances:
        speaker = utt.speaker or "?"
        lines.append(f'{speaker}: "{utt.text}"')
    return "\n".join(lines)


def format_metrics_summary(metrics: dict[str, VoiceMetrics]) -> str:
    """Format per-character deterministic metrics for the model.

    The agent interprets these (never recomputes them — ADR-055 Decision 2).
    """
    if not metrics:
        return ""
    lines: list[str] = []
    for name, m in metrics.items():
        lines.append(
            f"{name}: avg_sent_len={m.avg_sentence_length}, "
            f"sent_len_std={m.sentence_length_std}, "
            f"ttr={m.type_token_ratio}, "
            f"avg_syllables={m.avg_syllables_per_word}, "
            f"contraction_rate={m.contraction_rate}"
        )
    return "\n".join(lines)


def build_run_prompt(attributed_dialogue: str, metrics_summary: str) -> str:
    """Build the agent run prompt (user channel) from runtime content.

    The attributed dialogue + per-character metrics are category-3 runtime
    content (RULE-02a) — never feature-task framing.
    """
    parts = [f"Dialogue:\n{attributed_dialogue}"]
    if metrics_summary:
        parts.append(f"\nMetrics:\n{metrics_summary}")
    return "\n".join(parts)
