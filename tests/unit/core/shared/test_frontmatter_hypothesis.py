"""
Property-based tests for shared/frontmatter.py using Hypothesis.

Verifies that frontmatter parsing handles arbitrary input robustly,
is deterministic, and correctly round-trips valid YAML frontmatter.
"""

from __future__ import annotations

from typing import Any

import yaml
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from narrare_core.shared.frontmatter import (
    ParsedFrontmatter,
    extract_section,
    parse_frontmatter,
    strip_frontmatter,
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Safe YAML values that yaml.safe_load can round-trip reliably
_yaml_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**53), max_value=2**53),  # YAML safe range
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(min_size=0, max_size=80),
)

# Small dictionaries of string keys → primitive YAML values
_yaml_dicts = st.dictionaries(
    keys=st.text(min_size=1, max_size=40, alphabet=st.characters(whitelist_categories=("L", "N"))),
    values=_yaml_primitives,
    max_size=10,
)


# Build a valid frontmatter string from a dictionary
@st.composite
def frontmatter_text(draw: st.DrawFn) -> tuple[str, dict[str, Any]]:
    """Generate a valid frontmatter document and return (text, metadata)."""
    metadata = draw(_yaml_dicts)
    content = draw(st.text(min_size=0, max_size=200))
    yaml_str = yaml.safe_dump(metadata, allow_unicode=True, default_flow_style=False)
    text = f"---\n{yaml_str}---\n{content}"
    return text, metadata


# Any string — for no-crash properties
any_string = st.text()


# ---------------------------------------------------------------------------
# Tests: parse_frontmatter — no-crash property
# ---------------------------------------------------------------------------


class TestParseFrontmatterNoCrash:
    @given(any_string)
    @settings(max_examples=200, deadline=None)
    def test_parse_frontmatter_never_crashes(self, text: str) -> None:
        """parse_frontmatter should handle any arbitrary string without raising."""
        result = parse_frontmatter(text)
        assert isinstance(result, ParsedFrontmatter)
        assert isinstance(result.metadata, dict)
        assert isinstance(result.content, str)
        assert isinstance(result.has_frontmatter, bool)

    @given(any_string)
    @settings(max_examples=200, deadline=None)
    def test_strip_frontmatter_never_crashes(self, text: str) -> None:
        """strip_frontmatter should handle any arbitrary string without raising."""
        result = strip_frontmatter(text)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Tests: parse_frontmatter — deterministic property
# ---------------------------------------------------------------------------


class TestParseFrontmatterDeterministic:
    @given(any_string)
    @settings(max_examples=200, deadline=None)
    def test_parsing_twice_gives_same_result(self, text: str) -> None:
        """Parsing the same input twice yields identical results."""
        first = parse_frontmatter(text)
        second = parse_frontmatter(text)
        assert first == second


# ---------------------------------------------------------------------------
# Tests: parse_frontmatter — round-trip property
# ---------------------------------------------------------------------------


class TestParseFrontmatterRoundTrip:
    @given(frontmatter_text())
    @settings(max_examples=200, deadline=None)
    def test_round_trip_preserves_metadata(self, data: tuple[str, dict[str, Any]]) -> None:
        """Valid frontmatter parsed metadata should contain the original keys.

        Note: We only check key presence, not exact value equality,
        because YAML safe_load may coerce or normalize certain values
        (e.g. Unicode whitespace, booleans, numeric strings).
        """
        text, original_metadata = data
        result = parse_frontmatter(text)
        assert result.has_frontmatter is True

        for key in original_metadata:
            assert key in result.metadata, f"Key {key!r} missing from parsed metadata"


# ---------------------------------------------------------------------------
# Tests: parse_frontmatter — structural properties
# ---------------------------------------------------------------------------


class TestParseFrontmatterStructural:
    @given(any_string)
    @settings(max_examples=200, deadline=None)
    def test_content_is_always_a_string(self, text: str) -> None:
        """The .content field is always a string, never None."""
        result = parse_frontmatter(text)
        assert isinstance(result.content, str)

    @given(any_string)
    @settings(max_examples=200, deadline=None)
    def test_metadata_is_always_a_dict(self, text: str) -> None:
        """The .metadata field is always a dict, never None."""
        result = parse_frontmatter(text)
        assert isinstance(result.metadata, dict)

    @given(any_string)
    @settings(max_examples=200, deadline=None)
    def test_has_frontmatter_is_boolean(self, text: str) -> None:
        """The .has_frontmatter field is always a boolean."""
        result = parse_frontmatter(text)
        assert isinstance(result.has_frontmatter, bool)


# ---------------------------------------------------------------------------
# Tests: strip_frontmatter — identity property
# ---------------------------------------------------------------------------


class TestStripFrontmatterIdentity:
    @given(st.text(min_size=1))
    @settings(max_examples=200, deadline=None)
    def test_plain_text_unchanged(self, text: str) -> None:
        """Text without frontmatter delimiters is returned unchanged."""
        # Assume text does not start with "---\n"
        assume(not text.startswith("---\n"))
        result = strip_frontmatter(text)
        assert result == text

    @given(any_string)
    @settings(max_examples=200, deadline=None)
    def test_strip_result_is_content_field(self, text: str) -> None:
        """strip_frontmatter(text) == parse_frontmatter(text).content"""
        assert strip_frontmatter(text) == parse_frontmatter(text).content


# ---------------------------------------------------------------------------
# Tests: extract_section — no-crash property
# ---------------------------------------------------------------------------


class TestExtractSectionNoCrash:
    @given(any_string, st.text(min_size=0, max_size=50))
    @settings(max_examples=200, deadline=None)
    def test_extract_section_never_crashes(self, text: str, section: str) -> None:
        """extract_section should handle any input pair without raising."""
        result = extract_section(text, section)
        assert result is None or isinstance(result, str)

    @given(any_string, st.text(min_size=1, max_size=30))
    @settings(max_examples=200, deadline=None)
    def test_extract_section_result_is_none_or_content(self, text: str, section: str) -> None:
        """Result is None (section not found) or a non-negative-length string."""
        result = extract_section(text, section)
        if result is not None:
            assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Tests: ParsedFrontmatter.get — default value property
# ---------------------------------------------------------------------------


class TestParsedFrontmatterGet:
    @given(any_string, st.text(min_size=1, max_size=30))
    @settings(max_examples=200, deadline=None)
    def test_get_missing_key_returns_default(self, text: str, key: str) -> None:
        """get() with a missing key always returns the provided default."""
        sentinel = object()
        result = parse_frontmatter(text)
        # We can't guarantee 'key' is missing, but the method should never raise
        value = result.get(key, sentinel)
        # If key exists, value comes from metadata; otherwise it's the sentinel
        if key in result.metadata:
            assert value == result.metadata[key]
        else:
            assert value is sentinel
