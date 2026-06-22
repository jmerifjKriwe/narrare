"""Unit tests for FeedbackSourceType — closed source taxonomy (CR-AUFG-07-24)."""

from __future__ import annotations

import pytest

from narrare_core.memory.source_types import FeedbackSourceType


def test_taxonomy_contains_exactly_the_five_required_sources() -> None:
    members = {m.value for m in FeedbackSourceType}
    assert members == {
        "co_author_change",
        "kb_field_suggest",
        "kb_enhance_field",
        "kb_improve_suggestion",
        "chat_message",
    }


def test_each_member_round_trips_through_its_value() -> None:
    for member in FeedbackSourceType:
        assert FeedbackSourceType(member.value) is member


def test_unknown_source_raises_value_error() -> None:
    with pytest.raises(ValueError):
        FeedbackSourceType("totally_made_up_source")
