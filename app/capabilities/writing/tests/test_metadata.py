from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.capabilities.writing.metadata import (
    InvalidNovelUpdateError,
    duplicated_title,
    normalized_novel_updates,
)
from app.capabilities.writing.schemas import NovelUpdate
from app.kernel.contracts.models import AI_ROLES, AUTHOR_TYPOLOGIES


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
    [
        ("DE", "de"),
        ("en-GB", "en-GB"),
        ("  de  ", "de"),
        ("   ", None),
        ("zh-Hans-CN", "zh-Hans-CN"),
        ("de-CH-1906", "de-CH-1906"),
        ("hy-Latn-IT-arevela", "hy-Latn-IT-arevela"),
        ("yue", "yue"),
    ],
)
def test_language_folds_only_its_primary_subtag(given: str, expected: str | None) -> None:
    assert normalized_novel_updates(NovelUpdate(language=given)) == {"language": expected}


def test_an_invalid_language_is_refused_by_name() -> None:
    for value in ("deutsch", "d", "de_DE", "x" * 17, "de-" + "-".join(["abcdefgh"] * 8)):
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


def test_series_volume_is_positive_bounded_or_clears() -> None:
    assert normalized_novel_updates(NovelUpdate(series_volume=3)) == {"series_volume": 3}
    assert normalized_novel_updates(NovelUpdate(series_volume=2_147_483_647)) == {
        "series_volume": 2_147_483_647
    }
    assert normalized_novel_updates(NovelUpdate(series_volume=None)) == {"series_volume": None}
    # The ceiling is the Integer column's own — the target's bound — so an
    # over-long volume is a 422 here, not an overflow at the flush.
    for value in (0, -1, 2_147_483_648):
        with pytest.raises(InvalidNovelUpdateError) as refused:
            normalized_novel_updates(NovelUpdate(series_volume=value))
        assert refused.value.field == "series_volume"


def test_archived_at_passes_through_as_carried() -> None:
    stamp = datetime(2026, 11, 15, 10, 0, tzinfo=UTC)
    assert normalized_novel_updates(NovelUpdate(archived_at=stamp)) == {"archived_at": stamp}
    assert normalized_novel_updates(NovelUpdate(archived_at=None)) == {"archived_at": None}


def test_target_words_is_positive_bounded_or_clears() -> None:
    assert normalized_novel_updates(NovelUpdate(target_words=65000)) == {"target_words": 65000}
    assert normalized_novel_updates(NovelUpdate(target_words=2_147_483_647)) == {
        "target_words": 2_147_483_647
    }
    assert normalized_novel_updates(NovelUpdate(target_words=None)) == {"target_words": None}
    for value in (0, -1, 2_147_483_648):
        with pytest.raises(InvalidNovelUpdateError) as refused:
            normalized_novel_updates(NovelUpdate(target_words=value))
        assert refused.value.field == "target_words"


def test_author_typology_carries_the_shared_vocabulary_and_null_clears() -> None:
    for value in AUTHOR_TYPOLOGIES:
        assert normalized_novel_updates(NovelUpdate(author_typology=value)) == {
            "author_typology": value
        }
    assert normalized_novel_updates(NovelUpdate(author_typology=None)) == {"author_typology": None}
    assert normalized_novel_updates(NovelUpdate(author_typology="   ")) == {"author_typology": None}
    # Trimmed like the status: the door normalizes before it checks the set.
    assert normalized_novel_updates(NovelUpdate(author_typology="  plotter  ")) == {
        "author_typology": "plotter"
    }


def test_an_author_typology_outside_the_vocabulary_is_refused_by_name() -> None:
    for value in ("bogus", "Plotter", "dreamer"):
        with pytest.raises(InvalidNovelUpdateError) as refused:
            normalized_novel_updates(NovelUpdate(author_typology=value))
        assert refused.value.field == "author_typology"


def test_ai_role_carries_the_shared_vocabulary_and_null_clears() -> None:
    for value in AI_ROLES:
        assert normalized_novel_updates(NovelUpdate(ai_role=value)) == {"ai_role": value}
    assert normalized_novel_updates(NovelUpdate(ai_role=None)) == {"ai_role": None}
    assert normalized_novel_updates(NovelUpdate(ai_role="   ")) == {"ai_role": None}


def test_an_ai_role_outside_the_vocabulary_is_refused_by_name() -> None:
    for value in ("bogus", "Lektor", "autor"):
        with pytest.raises(InvalidNovelUpdateError) as refused:
            normalized_novel_updates(NovelUpdate(ai_role=value))
        assert refused.value.field == "ai_role"


def test_dramatic_form_is_trimmed_empty_clears_and_width_is_checked() -> None:
    assert normalized_novel_updates(NovelUpdate(dramatic_form="  three-act  ")) == {
        "dramatic_form": "three-act"
    }
    assert normalized_novel_updates(NovelUpdate(dramatic_form="   ")) == {"dramatic_form": None}
    assert normalized_novel_updates(NovelUpdate(dramatic_form="x" * 80)) == {
        "dramatic_form": "x" * 80
    }
    with pytest.raises(InvalidNovelUpdateError) as refused:
        normalized_novel_updates(NovelUpdate(dramatic_form="x" * 81))
    assert refused.value.field == "dramatic_form"


def test_canon_strictness_is_one_to_five_or_clears() -> None:
    for value in (1, 2, 3, 4, 5):
        assert normalized_novel_updates(NovelUpdate(canon_strictness=value)) == {
            "canon_strictness": value
        }
    assert normalized_novel_updates(NovelUpdate(canon_strictness=None)) == {
        "canon_strictness": None
    }
    for value in (0, -1, 6):
        with pytest.raises(InvalidNovelUpdateError) as refused:
            normalized_novel_updates(NovelUpdate(canon_strictness=value))
        assert refused.value.field == "canon_strictness"


def test_the_copy_title_wraps_the_original_in_quotes_and_suffix() -> None:
    assert duplicated_title("Der Nebel") == '„Der Nebel (Kopie)"'


def test_a_long_original_keeps_as_much_of_itself_as_fits_the_column() -> None:
    # The quotes and suffix take ten of the column's 200 characters.
    title = duplicated_title("x" * 200)
    assert len(title) == 200
    assert title == f'„{"x" * 190} (Kopie)"'
