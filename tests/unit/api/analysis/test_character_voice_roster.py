"""N11 service seam: character-voice profiles only ROSTER characters.

The service reads the KB character roster and gates parser attributions
before metrics — the progress event must say "Profiling 1 character(s)"
for the N11 repro chapter, not 1 + garbage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from narrare.analysis.character_roster import known_character_names
from narrare.kb.models import KBEntry
from narrare_core.agents.character_voice_types import CharacterVoiceOutput
from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.analysis._character_voice_test_helpers import (
    FakeComposer,
    consume,
    make_chapter,
    make_novel,
    make_service,
    patch_mode1,
)

if TYPE_CHECKING:
    from pytest import MonkeyPatch

    from narrare.kb.contracts import KBRepositoryProtocol

_ROSTER_TEXT = (
    'Elara pressed her palm against the gate. "Open it," she said.\n\n'
    'In order to be ready, she counted the bells. "Two strikes. The gate, then."'
)


class FakeKBRepo:
    """Minimal roster source: implements only the ``list_entries`` read.

    The roster gate's sole KB touchpoint (via ``list_entities``) is
    ``list_entries``, backed by real ``KBEntry`` rows. Passed to the
    protocol-typed seams through ``cast`` — the established fake pattern
    (see ``tests/unit/api/kb/_test_fakes_graph_suggest_consistency.py``).
    """

    def __init__(self, names: list[str]) -> None:
        self._entries = [
            KBEntry(
                id=uuid4(),
                novel_id=uuid4(),
                name=name,
                slug=name.lower(),
                entity_type="character",
            )
            for name in names
        ]

    async def list_entries(
        self,
        novel_id: UUID,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        review_status: str | None = None,
        page: int = 1,
        page_size: int = 50,
        include_deprecated: bool = False,
    ) -> tuple[list[KBEntry], int]:
        return list(self._entries), len(self._entries)


async def test_known_character_names_reads_the_kb_roster() -> None:
    roster = await known_character_names(
        cast("KBRepositoryProtocol", FakeKBRepo(["Elara", "Gatekeeper"])), uuid4()
    )
    assert roster == {"Elara", "Gatekeeper"}


async def test_known_character_names_empty_for_empty_kb() -> None:
    assert (
        await known_character_names(cast("KBRepositoryProtocol", FakeKBRepo([])), uuid4()) == set()
    )


async def test_service_profiles_only_roster_characters(
    monkeypatch: MonkeyPatch,
) -> None:
    """End-to-end seam pin: the agent receives roster-only character names.

    Uses the service's REAL DialogueParser (the ``_make_dialogue_parser``
    default), a KB roster holding only "Elara", and a stubbed
    ``run_character_voice_agent`` that records ``character_names``.
    """
    from typing import Any

    calls: list[dict[str, Any]] = []

    async def _stub_run_character_voice_agent(**kwargs: Any) -> CharacterVoiceOutput:
        calls.append(kwargs)
        return CharacterVoiceOutput(characters=[])

    monkeypatch.setattr(
        "narrare.analysis.character_voice_service.run_character_voice_agent",
        _stub_run_character_voice_agent,
    )

    novel = make_novel()
    chapter = make_chapter(novel_id=novel.id, content=_ROSTER_TEXT)
    service = make_service(
        FakeComposer(),
        ResolvedModelConfig(provider_name="test", model_id="test-model"),
        kb_repo=cast("KBRepositoryProtocol", FakeKBRepo(["Elara"])),
    )
    service._novel_repo.get_by_id = AsyncMock(return_value=novel)
    service._chapter_repo.list_by_novel = AsyncMock(return_value=[chapter])

    with patch_mode1():
        events = await consume(service.analyze(novel.id, None, uuid4()))

    assert calls, "the agent runner must have been called"
    assert calls[0]["character_names"] == ["Elara"]
    progress = [e.progress for e in events if e.event == "progress"]
    assert progress == ["Profiling 1 character(s)."], (
        f"garbage characters must not be profiled, got {progress}"
    )
