"""N11 drift seam: raw parser speakers are roster-gated before the union.

``CharacterVoiceDriftService`` unions profile names with parser speakers
(``set(profiles_by_name) | all_speakers``); ungated, garbage action-beat
"speakers" surface as no_stored_profile cards (audit N11). Pinned at the
exact composition the service performs.
"""

from __future__ import annotations

import uuid

from narrare.analysis.schemas_voice_drift import VoiceDriftRequest
from narrare_core.analysis.dialogue_parser import DialogueParser, filter_speaker_names
from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.analysis import _voice_drift_test_helpers as helpers

# The deterministic N11 repro (landed with pt1 — see
# tests/unit/core/analysis/test_dialogue_parser_roster.py): "Elara" is the
# only roster character; the sentence-initial prose words attract garbage
# action-beat attributions ("In", "About").
_N11_TEXT = (
    'Elara pressed her palm against the gate. "Open it," she said.\n\n'
    'In order to be ready, she counted the bells. "Two strikes. The gate, then."\n\n'
    'About an hour later, the guard sighed. "Nobody crosses after dark."'
)


def test_drift_character_union_is_roster_gated() -> None:
    parser = DialogueParser()
    raw_speakers = {u.speaker for u in parser.parse(_N11_TEXT) if u.speaker}
    assert raw_speakers - {"Elara"}, f"repro stale: {raw_speakers}"

    roster = {"Elara"}
    all_speakers = filter_speaker_names(raw_speakers, roster)
    all_names = sorted(set({"Elara": object()}) | all_speakers)  # profiles | speakers

    assert all_names == ["Elara"]


def test_empty_roster_preserves_the_union() -> None:
    parser = DialogueParser()
    raw_speakers = {u.speaker for u in parser.parse(_N11_TEXT) if u.speaker}
    assert filter_speaker_names(raw_speakers, set()) == raw_speakers


async def test_drift_no_profile_events_are_roster_gated() -> None:
    """Service seam: garbage speakers never surface as no_profile cards.

    The fake consumer holds NO stored profiles, so every character in the
    gated union must appear as a ``no_stored_profile`` card — and with the
    roster wired, that union is exactly {"Elara"}. The agent is never
    reached (zero analysable characters), keeping the test TestModel-free.
    """
    novel = helpers.make_novel()
    chapter = helpers.make_chapter(novel_id=novel.id, content=_N11_TEXT)
    consumer = helpers.FakeVoiceProfileConsumer(profiles=[])
    roster_calls: list[uuid.UUID] = []

    async def roster_provider(novel_id: uuid.UUID) -> set[str]:
        roster_calls.append(novel_id)
        return {"Elara"}

    service = helpers.make_service(
        novel=novel,
        chapters=[chapter],
        consumer=consumer,
        config=ResolvedModelConfig(provider_name="test", model_id="test-model"),
        roster_provider=roster_provider,
    )

    events = await helpers.consume(service.run_stream(novel.id, uuid.uuid4(), VoiceDriftRequest()))

    assert roster_calls == [novel.id], "the roster provider must be called per run"
    assert events[-1].event == "done"
    no_profile_names = [
        event.no_profile.character_name
        for event in events
        if event.event == "no_profile" and event.no_profile is not None
    ]
    assert no_profile_names == ["Elara"], (
        f"garbage speakers must not surface as no_profile cards: {no_profile_names}"
    )
    names_in_events = {
        event.no_profile.character_name for event in events if event.no_profile is not None
    } | {event.result.character_name for event in events if event.result is not None}
    assert names_in_events == {"Elara"}


async def test_no_roster_provider_keeps_the_raw_union() -> None:
    """Backwards compatibility: ``roster_provider=None`` gates nothing."""
    novel = helpers.make_novel()
    chapter = helpers.make_chapter(novel_id=novel.id, content=_N11_TEXT)
    consumer = helpers.FakeVoiceProfileConsumer(profiles=[])

    service = helpers.make_service(
        novel=novel,
        chapters=[chapter],
        consumer=consumer,
        config=ResolvedModelConfig(provider_name="test", model_id="test-model"),
    )

    events = await helpers.consume(service.run_stream(novel.id, uuid.uuid4(), VoiceDriftRequest()))

    no_profile_names = {
        event.no_profile.character_name
        for event in events
        if event.event == "no_profile" and event.no_profile is not None
    }
    assert "In" in no_profile_names and "About" in no_profile_names, (
        "without a roster provider the raw parser speakers must still surface"
    )
