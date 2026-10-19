"""KB character-roster reads + roster gating for the voice services (N11).

One responsibility (RULE-06): turn the novel's KB character entries into
the name set that gates parser speaker attributions, and apply that gate.
Reuses ``worldbuilding_entity_assembly.list_entities`` — the same
name-source helper the wiki and consistency services use (no second roster
SSOT).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from uuid import UUID

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare_core.analysis.voice_types import AttributedUtterance


async def known_character_names(kb_repo: KBRepositoryProtocol, novel_id: UUID) -> set[str]:
    """All character-entry names for *novel_id* (empty set for an empty KB).

    The empty set is meaningful: callers treat it as "no roster to gate
    against" and keep the parser's raw attributions (RULE-11 degradation).
    """
    from narrare.kb.worldbuilding_entity_assembly import list_entities

    entries = await list_entities(kb_repo, novel_id, ["character"])
    return {entry.name for entry in entries}


async def gate_speakers_to_roster(
    kb_repo: KBRepositoryProtocol,
    novel_id: UUID,
    utterances: list[AttributedUtterance],
) -> list[AttributedUtterance]:
    """Gate parser *utterances* against the novel's KB character roster.

    Reads the roster (see :func:`known_character_names`) and demotes every
    attribution whose speaker is not on it via
    :func:`narrare_core.analysis.dialogue_parser.restrict_speakers_to_roster`
    — sentence-initial prose words otherwise become garbage "characters"
    via the action-beat heuristic (audit N11). Demoted quotes keep their
    text/position at ``speaker=None``/low confidence: the ADR-055 Decision 3
    handoff (the agent resolves them inline, rendered ``?`` in the prompt).
    An empty roster (KB-less novel) leaves the utterances unchanged.
    """
    from narrare_core.analysis.dialogue_parser import restrict_speakers_to_roster

    roster = await known_character_names(kb_repo, novel_id)
    return restrict_speakers_to_roster(utterances, roster)


async def gate_speaker_names(
    speakers: set[str],
    roster_provider: Callable[[UUID], Awaitable[set[str]]] | None,
    novel_id: UUID,
) -> set[str]:
    """Provider-form name-set gate (drift seam, N11 half 2).

    ``CharacterVoiceDriftService`` unions parser speakers into the character
    set (``set(profiles_by_name) | all_speakers``), so every garbage
    action-beat "speaker" would surface as a ``no_stored_profile`` card
    (audit N11). When *roster_provider* is wired and returns a non-empty
    roster, *speakers* are filtered through
    :func:`narrare_core.analysis.dialogue_parser.filter_speaker_names`;
    a ``None`` provider or an empty roster keeps the raw set (RULE-11
    degradation — the service's default ``None`` keeps every existing
    construction backwards compatible).

    Extracted here for RULE-04: the drift service sits at its line limit, so
    the gate composition lives with the other roster gates (pt1 precedent).
    """
    if roster_provider is None:
        return speakers
    roster = await roster_provider(novel_id)
    if not roster:
        return speakers
    from narrare_core.analysis.dialogue_parser import filter_speaker_names

    return filter_speaker_names(speakers, roster)
