from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.capabilities.writing.metadata import (
    InvalidNovelUpdateError,
    normalized_novel_updates,
)
from app.capabilities.writing.schemas import NovelUpdate


def test_absent_fields_are_not_updates() -> None:
    assert normalized_novel_updates(NovelUpdate()) == {}


def test_a_carried_null_is_an_update() -> None:
    assert normalized_novel_updates(NovelUpdate(author=None)) == {"author": None}


def test_title_is_trimmed_and_blank_is_refused() -> None:
    assert normalized_novel_updates(NovelUpdate(title="  Dune  ")) == {"title": "Dune"}
    with pytest.raises(InvalidNovelUpdateError) as refused:
        normalized_novel_updates(NovelUpdate(title="   "))
    assert refused.value.field == "title"


def test_genre_is_trimmed_empty_clears_and_width_is_checked() -> None:
    assert normalized_novel_updates(NovelUpdate(genre="  Sci-Fi  ")) == {"genre": "Sci-Fi"}
    assert normalized_novel_updates(NovelUpdate(genre="   ")) == {"genre": None}
    with pytest.raises(InvalidNovelUpdateError) as refused:
        normalized_novel_updates(NovelUpdate(genre="x" * 81))
    assert refused.value.field == "genre"


def test_author_is_trimmed_empty_clears_and_width_is_checked() -> None:
    assert normalized_novel_updates(NovelUpdate(author="  Frank Herbert  ")) == {
        "author": "Frank Herbert"
    }
    assert normalized_novel_updates(NovelUpdate(author="   ")) == {"author": None}
    with pytest.raises(InvalidNovelUpdateError) as refused:
        normalized_novel_updates(NovelUpdate(author="x" * 201))
    assert refused.value.field == "author"


def test_blurb_is_trimmed_and_empty_clears() -> None:
    assert normalized_novel_updates(NovelUpdate(blurb="  A desert planet.  ")) == {
        "blurb": "A desert planet."
    }
    assert normalized_novel_updates(NovelUpdate(blurb="   ")) == {"blurb": None}


@pytest.mark.parametrize(
    ("given", "expected"),
    [("DE", "de"), ("en-GB", "en-GB"), ("  de  ", "de"), ("   ", None)],
)
def test_language_folds_only_its_primary_subtag(given: str, expected: str | None) -> None:
    assert normalized_novel_updates(NovelUpdate(language=given)) == {"language": expected}


def test_an_invalid_language_is_refused_by_name() -> None:
    for value in ("deutsch", "d", "de_DE", "x" * 17):
        with pytest.raises(InvalidNovelUpdateError) as refused:
            normalized_novel_updates(NovelUpdate(language=value))
        assert refused.value.field == "language"


def test_status_carries_the_vocabulary_and_null_clears() -> None:
    for value in ("draft", "revision", "final"):
        assert normalized_novel_updates(NovelUpdate(status=value)) == {"status": value}
    assert normalized_novel_updates(NovelUpdate(status=None)) == {"status": None}
    assert normalized_novel_updates(NovelUpdate(status="   ")) == {"status": None}


def test_a_status_outside_the_vocabulary_is_refused_by_name() -> None:
    for value in ("published", "Draft", "fertig"):
        with pytest.raises(InvalidNovelUpdateError) as refused:
            normalized_novel_updates(NovelUpdate(status=value))
        assert refused.value.field == "status"


def test_series_id_passes_through_for_the_ownership_check() -> None:
    series_id = uuid4()
    assert normalized_novel_updates(NovelUpdate(series_id=series_id)) == {"series_id": series_id}
    assert normalized_novel_updates(NovelUpdate(series_id=None)) == {"series_id": None}


def test_series_volume_is_positive_or_absent() -> None:
    assert normalized_novel_updates(NovelUpdate(series_volume=3)) == {"series_volume": 3}
    assert normalized_novel_updates(NovelUpdate(series_volume=None)) == {"series_volume": None}
    for value in (0, -1):
        with pytest.raises(InvalidNovelUpdateError) as refused:
            normalized_novel_updates(NovelUpdate(series_volume=value))
        assert refused.value.field == "series_volume"


def test_archived_at_passes_through_as_carried() -> None:
    stamp = datetime(2026, 11, 15, 10, 0, tzinfo=UTC)
    assert normalized_novel_updates(NovelUpdate(archived_at=stamp)) == {"archived_at": stamp}
    assert normalized_novel_updates(NovelUpdate(archived_at=None)) == {"archived_at": None}
