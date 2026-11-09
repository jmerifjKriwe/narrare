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
