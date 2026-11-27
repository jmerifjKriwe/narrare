"""The language tag's one home: its grammar, its width and its fold."""

from app.kernel.language_tag import (
    LANGUAGE_TAG,
    LANGUAGE_TAG_MAX_LENGTH,
    fold_language_tag,
    is_language_tag,
)


def test_the_grammar_is_two_or_three_lowercase_letters_then_subtags() -> None:
    assert LANGUAGE_TAG.pattern == r"[a-z]{2,3}(-[A-Za-z0-9]{1,8})*"
    for tag in ("de", "yue", "en-GB", "zh-Hans-CN", "de-CH-1906", "hy-Latn-IT-arevela"):
        assert is_language_tag(tag), tag


def test_a_value_that_is_no_language_tag_is_refused() -> None:
    for value in ("deutsch", "German", "d", "de-", "en_GB", "", "  "):
        assert not is_language_tag(value), value


def test_a_tag_of_exactly_the_width_is_accepted_and_one_more_is_refused() -> None:
    tag = f"de-{'-'.join(['abcdefgh'] * 6)}-abcdefg"
    assert len(tag) == LANGUAGE_TAG_MAX_LENGTH == 64
    assert is_language_tag(tag)
    wider = f"{tag}g"
    assert len(wider) == 65
    assert not is_language_tag(wider)


def test_folding_drops_the_whitespace_and_lowercases_only_the_primary_subtag() -> None:
    assert fold_language_tag("  DE-CH-1906  ") == "de-CH-1906"
    assert fold_language_tag("de") == "de"
    assert fold_language_tag(" en-GB ") == "en-GB"
