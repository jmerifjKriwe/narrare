"""Unit tests for ``benchmark.ingest`` — build-path orchestration.

Fake-client orchestration over the scripted MockTransport backend
(``ingest_helpers``) behind the real ``BenchmarkClient`` — no network.
Pinned here: the exact call sequence (novel once, then per chapter
create → content → extract → endorse), the documented novel payload,
endorse-all candidate mapping (``confidence``/``conflict_description``
dropped — not ApplyExtractionItem fields, map §4.3.2), pacing
(``PACING_SECONDS`` only on inter-chapter boundaries, incremental only),
import mode = identical sequence without waits (map §7: no bulk import
endpoint exists), caller-error validation before any HTTP traffic, and
``IngestError`` fail-fast behavior + contents. Sink behavior (recording,
sanitization) is pinned in ``test_ingest_events.py``. Sequence truth:
benchmark/docs/api-surface.md §4.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from benchmark.ingest import (
    PACING_SECONDS,
    ChapterIngest,
    IngestError,
    IngestResult,
    ingest,
)
from benchmark.tests.client_helpers import Responder, ScriptedApi, make_client
from benchmark.tests.ingest_helpers import (
    CANDIDATES,
    CHAPTERS,
    NOVEL_ID,
    NOVELS_PATH,
    VARIANT,
    apply_path,
    chapter_id,
    chapters_path,
    content_path,
    extract_path,
    ingest_responder,
    run_ingest,
)

if TYPE_CHECKING:
    from benchmark.ingest_events import IngestEvent


def _run_failing(responder: Responder) -> tuple[ScriptedApi, list[IngestEvent], IngestError]:
    """Run ``ingest`` expecting a fail-fast ``IngestError``; return evidence."""
    api = ScriptedApi()
    api.respond_with(responder)
    client = make_client(api, access_token="acc-1")
    events: list[IngestEvent] = []
    with pytest.raises(IngestError) as excinfo:
        ingest(
            client,
            CHAPTERS,
            variant=VARIANT,
            mode="incremental",
            events=events,
            sleeper=lambda _seconds: None,
        )
    return api, events, excinfo.value


def test_incremental_sequence_is_novel_then_per_chapter_cycles() -> None:
    api, _events, result = run_ingest("incremental")

    expected = [f"POST {NOVELS_PATH}"]
    for index in range(len(CHAPTERS)):
        expected += [
            f"POST {chapters_path()}",
            f"PUT {content_path(index)}",
            f"POST {extract_path(index)}",
            f"POST {apply_path()}",
        ]
    assert api.paths() == expected
    assert result.novel_id == NOVEL_ID


def test_novel_created_exactly_once_with_documented_payload() -> None:
    api, _events, _result = run_ingest("incremental")

    novel_calls = [call for call in api.calls if call.path == NOVELS_PATH]
    assert len(novel_calls) == 1
    assert novel_calls[0].body == {
        "title": "KB Benchmark [light/incremental]",
        "author": "",
        "genre": "",
        "writing_language": "de",
        "tone": "",
        "story_structure": "three_act",
        "logline": "",
        "synopsis": "",
    }
    assert novel_calls[0].authorization == "Bearer acc-1"


def test_chapter_is_created_empty_then_receives_full_content() -> None:
    api, _events, _result = run_ingest("incremental")

    create_call = api.calls[1]
    assert create_call.path == chapters_path()
    assert create_call.body == {
        "title": "Kapitel Eins",
        "content": "",
        "position": None,
        "volume_id": None,
    }
    put_call = api.calls[2]
    assert put_call.path == content_path(0)
    assert put_call.body == {"content": CHAPTERS[0].text, "word_count": None}


def test_endorse_all_maps_every_candidate_dropping_non_apply_fields() -> None:
    api, _events, _result = run_ingest("incremental")

    apply_calls = [call for call in api.calls if call.path == apply_path()]
    assert len(apply_calls) == len(CHAPTERS)
    raw_body = apply_calls[0].body
    assert isinstance(raw_body, dict)
    items = cast("list[dict[str, object]]", cast("dict[str, object]", raw_body)["items"])
    assert len(items) == len(CANDIDATES)
    first = items[0]
    assert first == {
        "item_type": "new_entity",
        "entity_type": "person",
        "name": "Anna Meyer",
        "source_text": "Anna kam aus der HafenCity.",
        "proposed_content": {"description": "Architektin aus Hamburg"},
    }
    second = items[1]
    assert second == {
        "item_type": "relationship",
        "name": "Anna Meyer",
        "relationship_type": "partner_of",
        "related_entity_name": "Peter Meyer",
        "source_text": "Peter kam abends von einem Hafen.",
    }
    assert all("confidence" not in item and "conflict_description" not in item for item in items)


def test_result_reports_novel_and_per_chapter_counts() -> None:
    _api, _events, result = run_ingest("incremental")

    assert result == IngestResult(
        novel_id=NOVEL_ID,
        chapters=(
            ChapterIngest(
                stem="ch-01",
                chapter_id=chapter_id(0),
                candidates=3,
                endorsed=3,
                created_entries=1,
                updated_entries=0,
            ),
            ChapterIngest(
                stem="ch-02",
                chapter_id=chapter_id(1),
                candidates=3,
                endorsed=3,
                created_entries=1,
                updated_entries=0,
            ),
        ),
    )


def test_incremental_paces_only_between_chapters() -> None:
    waits: list[float] = []

    _api, _events, _result = run_ingest("incremental", ingest_responder(), sleeper=waits.append)

    assert waits == [PACING_SECONDS]  # one inter-chapter boundary for two chapters
    assert PACING_SECONDS == 12.0  # map §1: AI analysis default 5/min


def test_import_mode_is_same_sequence_without_waits() -> None:
    incremental_api, _events, _result = run_ingest("incremental")
    waits: list[float] = []
    import_api, _events, import_result = run_ingest(
        "import", ingest_responder(), sleeper=waits.append
    )

    assert import_api.paths() == incremental_api.paths()  # fallback: identical build path
    assert waits == []  # import = incremental WITHOUT inter-chapter waits
    assert import_result.novel_id == NOVEL_ID


def test_unknown_mode_is_rejected() -> None:
    api = ScriptedApi()
    api.respond_with(ingest_responder())
    events: list[IngestEvent] = []

    with pytest.raises(ValueError, match="mode"):
        ingest(
            make_client(api, access_token="acc-1"),
            CHAPTERS,
            variant=VARIANT,
            mode="fast",
            events=events,
        )

    assert api.calls == []  # rejected before any HTTP traffic


def test_empty_chapter_list_is_rejected() -> None:
    api = ScriptedApi()
    api.respond_with(ingest_responder())
    events: list[IngestEvent] = []

    with pytest.raises(ValueError, match="chapter"):
        ingest(
            make_client(api, access_token="acc-1"),
            (),
            variant=VARIANT,
            mode="incremental",
            events=events,
        )

    assert api.calls == []  # rejected before any HTTP traffic


def test_extract_failure_raises_ingest_error_fail_fast() -> None:
    api, events, _error = _run_failing(
        ingest_responder(extract_status=500, extract_body={"detail": "LLM down"})
    )

    assert api.paths() == [
        f"POST {NOVELS_PATH}",
        f"POST {chapters_path()}",
        f"PUT {content_path(0)}",
        f"POST {extract_path(0)}",
    ]
    assert events[-1].step == "extract"
    assert events[-1].status == 500


def test_ingest_error_carries_chapter_id_step_and_summary() -> None:
    _api, _events, error = _run_failing(
        ingest_responder(extract_status=500, extract_body={"detail": "LLM down"})
    )

    assert error.step == "extract"
    assert error.chapter_id == chapter_id(0)
    assert "HTTP 500" in str(error)
    assert "LLM down" in str(error)


def test_apply_failure_reports_endorse_step() -> None:
    api, events, error = _run_failing(ingest_responder(apply_status=400))

    assert error.step == "endorse"
    assert error.chapter_id == chapter_id(0)
    assert "apply rejected" in str(error)
    assert api.paths()[-1] == f"POST {apply_path()}"
    assert events[-1].step == "endorse"
    assert events[-1].status == 400


def test_novel_failure_reports_create_novel_step() -> None:
    api, events, error = _run_failing(ingest_responder(novel_status=409))

    assert error.step == "create_novel"
    assert error.chapter_id is None
    assert "novel rejected" in str(error)
    assert len(api.calls) == 1
    assert api.calls[0].path == NOVELS_PATH
    assert events[-1].step == "create_novel"
    assert events[-1].status == 409


def test_malformed_extract_shape_is_rejected() -> None:
    _api, events, error = _run_failing(
        ingest_responder(extract_status=200, extract_body={"results": "not-a-list"})
    )

    assert error.step == "extract"
    assert error.chapter_id == chapter_id(0)
    assert "results" in str(error)
    assert events[-1].step == "extract"
    assert events[-1].status == 200  # shape violation, not an HTTP failure


def test_empty_candidate_set_still_records_empty_endorsement() -> None:
    api, _events, result = run_ingest(
        "incremental", ingest_responder(extract_body={"results": [], "analysis_notes": "none"})
    )

    apply_calls = [call for call in api.calls if call.path == apply_path()]
    assert len(apply_calls) == len(CHAPTERS)
    assert apply_calls[0].body == {"items": []}
    assert result.chapters[0].candidates == 0
    assert result.chapters[0].endorsed == 0
    assert result.chapters[0].created_entries == 1  # scripted apply still returns entry-1
