"""Unit tests for the OUT-direction read/assist drivers (plan Task 9).

Covers CAP-OUT-05..10: series canon read, wiki read (prose recorded-
not-scored), timeline read, proactive suggestions (API-mounted, no
frontend client — inventory 02-out Finding), reference resolution, and
templates. Shared fixtures in ``out_direction_helpers.py``; the
CAP-OUT-01..02 tests live in ``test_out_direction.py``, the
CAP-OUT-03/04 tests in ``test_out_kb_detail.py``.
"""

from __future__ import annotations

from benchmark.drivers.out_direction_assist import (
    SUGGESTIONS_MAX_RESULTS,
    ProactiveSuggestionsDriver,
    ReferenceResolutionDriver,
    TemplatesDriver,
    probe_name,
)
from benchmark.drivers.out_direction_surfaces import (
    SeriesCanonReadDriver,
    TimelineReadDriver,
    WikiReadDriver,
)
from benchmark.drivers.out_records import (
    CanonEntryRef,
    CanonReadRecord,
    CharacterAge,
    ReferenceResolutionRecord,
    ResolvedRef,
    Suggestion,
    SuggestionsRecord,
    TemplateInfo,
    TemplatesRecord,
    TimelineEventRef,
    TimelineReadRecord,
    WikiReadRecord,
)
from benchmark.tests.client_helpers import ScriptedApi, make_client
from benchmark.tests.out_direction_helpers import (
    AGES_BODY,
    CANON,
    CANON_ENTRY,
    CANON_ENTRY_PATH,
    CANON_LIST_BODY,
    CHAPTER_SUMMARY_BODY,
    CHARACTER_AGES,
    EVENT_PATH,
    EVENTS,
    EVENTS_BODY,
    KB_RESOLVE,
    KB_SUGGESTIONS,
    KB_TEMPLATES,
    RESOLVE_BODY,
    SUGGESTIONS_BODY,
    TEMPLATE_DETAIL_BODY,
    TEMPLATE_LIST_BODY,
    WIKI,
    WIKI_INDEX_BODY,
    WIKI_LIST_BODY,
    WIKI_SUMMARY_A,
    context,
    corpus_with,
    invoke,
)

EMPTY_CANON_LIST: list[object] = []
EMPTY_EVENTS_BODY: list[object] = []
EMPTY_TEMPLATE_LIST: list[object] = []


# ---------------------------------------------------------------------------
# CAP-OUT-05 — SeriesCanonReadDriver: canon list + single read-back
# ---------------------------------------------------------------------------


def test_canon_driver_lists_canon_and_reads_first_entry_back() -> None:
    routes = {
        f"GET {CANON}": CANON_LIST_BODY,
        f"GET {CANON_ENTRY_PATH}": CANON_ENTRY,
    }

    api, events, parsed = invoke(SeriesCanonReadDriver, routes, targets={"series_id": "series-1"})

    assert api.paths() == [f"GET {CANON}", f"GET {CANON_ENTRY_PATH}"]
    assert isinstance(parsed, CanonReadRecord)
    assert parsed == CanonReadRecord(
        series_id="series-1",
        entries=(
            CanonEntryRef(
                id="entry-1",
                name="Anna Meyer",
                entity_type="character",
                slug="anna-meyer",
                scope="series",
            ),
        ),
        single=CanonEntryRef(
            id="entry-1",
            name="Anna Meyer",
            entity_type="character",
            slug="anna-meyer",
            scope="series",
        ),
    )
    assert [event.step for event in events] == ["CAP-OUT-05:list", "CAP-OUT-05:entry"]


def test_canon_driver_skips_single_read_when_canon_is_empty() -> None:
    routes = {f"GET {CANON}": EMPTY_CANON_LIST}

    api, _events, parsed = invoke(SeriesCanonReadDriver, routes, targets={"series_id": "series-1"})

    assert api.paths() == [f"GET {CANON}"]
    assert isinstance(parsed, CanonReadRecord)
    assert parsed.entries == ()
    assert parsed.single is None


def test_canon_driver_without_series_target_is_skipped_structural() -> None:
    api = ScriptedApi()

    result = SeriesCanonReadDriver().invoke(context(make_client(api)))

    assert result.status.name == "SKIPPED"
    assert result.reason is not None and "series_id" in result.reason
    assert api.calls == []


# ---------------------------------------------------------------------------
# CAP-OUT-06 — WikiReadDriver: index + summaries; prose recorded-not-scored
# ---------------------------------------------------------------------------


def test_wiki_read_driver_drives_index_list_single_and_chapter_summary() -> None:
    routes = {
        f"GET {WIKI}/index": WIKI_INDEX_BODY,
        f"GET {WIKI}/summaries": WIKI_LIST_BODY,
        f"GET {WIKI}/summaries/entry-9": WIKI_SUMMARY_A,
        f"GET {WIKI}/chapters/chapter-1/summary": CHAPTER_SUMMARY_BODY,
    }

    api, events, parsed = invoke(
        WikiReadDriver,
        routes,
        chapter_ids={"ch-01": "chapter-1"},
        targets={"entry_id": "entry-9"},
    )

    assert api.paths() == [
        f"GET {WIKI}/index",
        f"GET {WIKI}/summaries",
        f"GET {WIKI}/summaries/entry-9",
        f"GET {WIKI}/chapters/chapter-1/summary",
    ]
    assert isinstance(parsed, WikiReadRecord)
    assert parsed.total_summaries == 2
    assert parsed.fresh_count == 1
    assert parsed.stale_count == 1
    assert parsed.pending_count == 0
    # The narrative PROSE is carried raw (recorded-not-scored, plan Task 13):
    assert parsed.summaries[0].narrative_summary == "Anna kam aus der HafenCity."
    assert parsed.summaries[0].role_in_story == "Protagonistin"
    assert parsed.summaries[1].status == "STALE"
    assert parsed.single is not None and parsed.single.entity_id == "entry-9"
    assert parsed.chapter_summary == "Anna kam am Hafen an."
    assert parsed.chapter_summary_status == "FRESH"
    assert [event.step for event in events] == [
        "CAP-OUT-06:index",
        "CAP-OUT-06:summaries",
        "CAP-OUT-06:summary",
        "CAP-OUT-06:chapter-summary",
    ]


def test_wiki_read_driver_without_targets_fetches_only_index_and_list() -> None:
    routes = {
        f"GET {WIKI}/index": WIKI_INDEX_BODY,
        f"GET {WIKI}/summaries": WIKI_LIST_BODY,
    }

    api, _events, parsed = invoke(WikiReadDriver, routes)

    assert api.paths() == [f"GET {WIKI}/index", f"GET {WIKI}/summaries"]
    assert isinstance(parsed, WikiReadRecord)
    assert parsed.single is None
    assert parsed.chapter_summary is None
    assert parsed.chapter_summary_status is None


# ---------------------------------------------------------------------------
# CAP-OUT-07 — TimelineReadDriver: events + single read-back + age report
# ---------------------------------------------------------------------------


def test_timeline_read_driver_lists_reads_back_and_reports_ages() -> None:
    routes = {
        f"GET {EVENTS}": EVENTS_BODY,
        f"GET {EVENT_PATH}": EVENTS_BODY[0],
        f"GET {CHARACTER_AGES}": AGES_BODY,
    }

    api, events, parsed = invoke(TimelineReadDriver, routes)

    assert api.paths() == [f"GET {EVENTS}", f"GET {EVENT_PATH}", f"GET {CHARACTER_AGES}"]
    assert isinstance(parsed, TimelineReadRecord)
    assert parsed.events == (
        TimelineEventRef(
            id="event-1",
            event_name="Ritt nach Hamburg",
            event_type="plot_point",
            timestamp_raw="am dritten Tag",
            source="ai_extraction",
            confidence=0.9,
            is_confirmed=True,
            chapter_id=None,
        ),
    )
    assert parsed.single is not None and parsed.single.id == "event-1"
    assert parsed.ages == (
        CharacterAge(
            character_name="Anna Meyer",
            character_id="entry-9",
            birth_date="1990-03-12",
            birth_date_narrative="Frühjahr 1990",
            age_available=True,
        ),
        CharacterAge(
            character_name="Ben",
            character_id=None,
            birth_date=None,
            birth_date_narrative=None,
            age_available=False,
        ),
    )
    assert parsed.characters_with_age == 1
    assert parsed.characters_without_age == 1
    assert [event.step for event in events] == [
        "CAP-OUT-07:events",
        "CAP-OUT-07:event",
        "CAP-OUT-07:character-ages",
    ]


def test_timeline_read_driver_skips_single_read_when_no_events() -> None:
    routes = {
        f"GET {EVENTS}": EMPTY_EVENTS_BODY,
        f"GET {CHARACTER_AGES}": AGES_BODY,
    }

    api, _events, parsed = invoke(TimelineReadDriver, routes)

    assert api.paths() == [f"GET {EVENTS}", f"GET {CHARACTER_AGES}"]
    assert isinstance(parsed, TimelineReadRecord)
    assert parsed.events == ()
    assert parsed.single is None


# ---------------------------------------------------------------------------
# CAP-OUT-08 — ProactiveSuggestionsDriver (API-mounted, no frontend client)
# ---------------------------------------------------------------------------


def test_suggestions_driver_requires_chapter_target() -> None:
    api = ScriptedApi()

    result = ProactiveSuggestionsDriver().invoke(context(make_client(api)))

    assert result.status.name == "SKIPPED"
    assert result.reason is not None and "chapter_id" in result.reason
    assert api.calls == []


def test_suggestions_driver_pins_max_results_and_parses_ranking() -> None:
    routes = {f"GET {KB_SUGGESTIONS}": SUGGESTIONS_BODY}

    api, events, parsed = invoke(
        ProactiveSuggestionsDriver, routes, targets={"chapter_id": "chapter-1"}
    )

    assert api.paths() == [f"GET {KB_SUGGESTIONS}"]
    assert api.calls[0].params == {"max_results": str(SUGGESTIONS_MAX_RESULTS)}
    assert isinstance(parsed, SuggestionsRecord)
    assert parsed == SuggestionsRecord(
        chapter_id="chapter-1",
        suggestions=(
            Suggestion(
                entry_id="entry-2",
                entry_type="location",
                name="HafenCity",
                relevance_score=0.9,
                similarity=0.8,
                usage_count=4,
                reason="Aehnlicher Kontext",
            ),
        ),
    )
    assert [event.step for event in events] == ["CAP-OUT-08"]


# ---------------------------------------------------------------------------
# CAP-OUT-09 — ReferenceResolutionDriver: probe text from the corpus reference
# ---------------------------------------------------------------------------


def test_probe_name_prefers_reference_persons_then_falls_back() -> None:
    api = ScriptedApi()

    named = probe_name(context(make_client(api), corpus=corpus_with(("Anna Meyer",))))
    fallback = probe_name(context(make_client(api)))

    assert named == "Anna Meyer"
    assert fallback == "Benchmark"


def test_resolve_references_driver_posts_probe_text_and_parses_links() -> None:
    routes = {f"POST {KB_RESOLVE}": RESOLVE_BODY}

    api, events, parsed = invoke(
        ReferenceResolutionDriver, routes, corpus=corpus_with(("Anna Meyer",))
    )

    assert api.paths() == [f"POST {KB_RESOLVE}"]
    assert api.calls[0].body == {"text": "@Anna Meyer trifft @Benchmark."}
    assert isinstance(parsed, ReferenceResolutionRecord)
    assert parsed.resolved == (
        ResolvedRef(
            mention="Anna Meyer",
            entry_id="entry-9",
            entry_name="Anna Meyer",
            entity_type="character",
            slug="anna-meyer",
        ),
        ResolvedRef(
            mention="Benchmark",
            entry_id=None,
            entry_name=None,
            entity_type=None,
            slug=None,
        ),
    )
    assert parsed.html == "<a>Anna Meyer</a> trifft Benchmark."
    assert [event.step for event in events] == ["CAP-OUT-09"]


# ---------------------------------------------------------------------------
# CAP-OUT-10 — TemplatesDriver: type listing + one detail read-back
# ---------------------------------------------------------------------------


def test_templates_driver_lists_and_reads_first_detail() -> None:
    routes = {
        f"GET {KB_TEMPLATES}": TEMPLATE_LIST_BODY,
        f"GET {KB_TEMPLATES}/character": TEMPLATE_DETAIL_BODY,
    }

    api, events, parsed = invoke(TemplatesDriver, routes)

    assert api.paths() == [f"GET {KB_TEMPLATES}", f"GET {KB_TEMPLATES}/character"]
    assert isinstance(parsed, TemplatesRecord)
    assert parsed.templates == (
        TemplateInfo(
            entity_type="character",
            scope="user",
            schema_version="2.0.0",
            has_override=False,
            has_update=True,
        ),
    )
    assert parsed.detail is not None
    assert parsed.detail.entity_type == "character"
    assert parsed.detail.scope == "user"
    assert parsed.detail.schema_version == "2.0.0"
    assert parsed.detail.based_on_version is None
    assert parsed.detail.is_overridden is False
    assert [event.step for event in events] == ["CAP-OUT-10:list", "CAP-OUT-10:detail"]


def test_templates_driver_skips_detail_without_templates() -> None:
    routes = {f"GET {KB_TEMPLATES}": EMPTY_TEMPLATE_LIST}

    api, _events, parsed = invoke(TemplatesDriver, routes)

    assert api.paths() == [f"GET {KB_TEMPLATES}"]
    assert isinstance(parsed, TemplatesRecord)
    assert parsed.templates == ()
    assert parsed.detail is None
