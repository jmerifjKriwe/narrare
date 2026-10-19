"""N11 check seam: only roster characters reach the checker's metrics.

``CharacterVoiceCheckerService`` derives ``speaking`` from raw parser
metrics; ungated, garbage action-beat "speakers" flow into ``checkable``
and the progress text (audit N11). The roster gate restricts the parsed
utterances before ``analyzer.analyze``.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.analysis import _voice_check_test_helpers as helpers

if TYPE_CHECKING:
    from pytest import MonkeyPatch

# The deterministic N11 repro (landed with pt1 — see
# tests/unit/core/analysis/test_dialogue_parser_roster.py): "Elara" is the
# only roster character; the sentence-initial prose words attract garbage
# action-beat attributions ("In", "About").
_N11_TEXT = (
    'Elara pressed her palm against the gate. "Open it," she said.\n\n'
    'In order to be ready, she counted the bells. "Two strikes. The gate, then."\n\n'
    'About an hour later, the guard sighed. "Nobody crosses after dark."'
)


async def test_check_checker_receives_only_roster_characters(
    monkeypatch: MonkeyPatch,
) -> None:
    """Service seam: the checker agent runner sees roster-only checkables."""
    calls: list[dict[str, Any]] = []

    async def _stub_run_voice_checker_agent(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {}

    monkeypatch.setattr(
        "narrare.analysis.voice_check_service.run_voice_checker_agent",
        _stub_run_voice_checker_agent,
    )

    novel = helpers.make_novel()
    chapter = helpers.make_chapter(novel_id=novel.id, content=_N11_TEXT)
    consumer = helpers.FakeVoiceProfileConsumer([helpers.make_profile("Elara")])

    async def roster_provider(novel_id: uuid.UUID) -> set[str]:
        return {"Elara"}

    service = helpers.make_service(
        novel=novel,
        chapter=chapter,
        consumer=consumer,
        config=ResolvedModelConfig(provider_name="test", model_id="test-model"),
        roster_provider=roster_provider,
    )

    events = await helpers.consume(service.check(chapter.id, uuid.uuid4()))

    assert calls, "the checker agent runner must have been called"
    assert list(calls[0]["checkable"]) == ["Elara"], (
        f"garbage names must not be checkable: {calls[0]['checkable']}"
    )
    progress = [e.progress for e in events if e.event == "progress" and e.progress]
    assert progress == [
        "Checking voice consistency for 1 speaking character(s) (1 with stored profiles)."
    ], f"garbage names must not appear in the progress text: {progress}"
    result_names = [
        e.result.character_name for e in events if e.event == "result" and e.result is not None
    ]
    assert result_names == ["Elara"]


async def test_check_no_roster_provider_keeps_raw_speakers(
    monkeypatch: MonkeyPatch,
) -> None:
    """Backwards compatibility: ``roster_provider=None`` gates nothing.

    Ungated, the garbage attributions stay in the metrics: 3 speaking
    characters in the progress text and result events (the garbage cards
    render as ``has_profile=False``).
    """
    calls: list[dict[str, Any]] = []

    async def _stub_run_voice_checker_agent(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {}

    monkeypatch.setattr(
        "narrare.analysis.voice_check_service.run_voice_checker_agent",
        _stub_run_voice_checker_agent,
    )

    novel = helpers.make_novel()
    chapter = helpers.make_chapter(novel_id=novel.id, content=_N11_TEXT)
    consumer = helpers.FakeVoiceProfileConsumer([helpers.make_profile("Elara")])

    service = helpers.make_service(
        novel=novel,
        chapter=chapter,
        consumer=consumer,
        config=ResolvedModelConfig(provider_name="test", model_id="test-model"),
    )

    events = await helpers.consume(service.check(chapter.id, uuid.uuid4()))

    progress = [e.progress for e in events if e.event == "progress" and e.progress]
    assert progress == [
        "Checking voice consistency for 3 speaking character(s) (1 with stored profiles)."
    ], "without a roster provider the raw parser speakers must stay in the metrics"
    result_names = {
        e.result.character_name for e in events if e.event == "result" and e.result is not None
    }
    assert {"In", "About"} <= result_names, (
        "without a roster provider the raw parser speakers must keep result events"
    )
