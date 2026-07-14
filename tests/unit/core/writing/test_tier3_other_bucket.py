"""Tests for CR-AUFG-04-04: extensible entity-type classification in Tier-3.

Unknown entity types (anything outside {character, location, faction, system,
timeline}) must be routed to an ``other`` catch-all bucket and surfaced via
``kb_other`` instead of being silently dropped. Known entity types must still
reach their dedicated buckets.

Covers the full producer→consumer chain:
  * ``apply_tier3`` / ``apply_tier3_rendered`` (writing/_tier3_processor.py)
  * ``WritingContext.kb_other`` + ``to_prompt_variables()`` (writing/models.py)
  * ``kb_other`` registration in ``SYSTEM_VARS`` (prompts/variable_registry.py)
"""

from __future__ import annotations

import pytest
from structlog.testing import capture_logs

from narrare_core.prompts.variable_engine import prepare_variables_for_template
from narrare_core.prompts.variable_registry import SYSTEM_VARS
from narrare_core.writing._tier3_processor import (
    apply_tier3,
    apply_tier3_rendered,
)
from narrare_core.writing.context_models import KBEntity
from narrare_core.writing.models import WritingContext


def _entity(
    entity_id: str = "ent-1",
    entity_type: str = "character",
    name: str = "Alice",
    content: str = "A brave warrior.",
) -> KBEntity:
    return KBEntity(
        entity_id=entity_id,
        entity_type=entity_type,
        name=name,
        content=content,
    )


def _count(s: str) -> int:
    """Deterministic token counter used in tier3 tests (whitespace split)."""
    return len(s.split()) if s else 0


# ---------------------------------------------------------------------------
# Unknown entity types routed to the ``other`` bucket (not dropped)
# ---------------------------------------------------------------------------


class TestUnknownEntityRoutedToOther:
    """Unknown entity types are captured in the ``other`` bucket, not dropped."""

    def test_unknown_type_appears_in_other_rendered(self) -> None:
        entity = _entity("o1", entity_type="object", name="The Ring", content="A golden ring.")
        rendered = apply_tier3_rendered([entity], limit=10_000, count_tokens=_count)
        assert rendered.other.text != ""
        assert "The Ring" in rendered.other.text

    def test_unknown_type_appears_in_apply_tier3_other_element(self) -> None:
        entity = _entity("o1", entity_type="concept", name="Mana", content="Magical energy.")
        result = apply_tier3([entity], limit=10_000, count_tokens=_count)
        # 9-tuple: (chars, locs, factions, systems, timelines, other, overflow, fresh, stale)
        other_text = result[5]
        assert "Mana" in other_text

    def test_unknown_type_not_in_named_buckets(self) -> None:
        entity = _entity("o1", entity_type="object", name="The Ring", content="Golden.")
        rendered = apply_tier3_rendered([entity], limit=10_000, count_tokens=_count)
        assert rendered.characters.text == ""
        assert rendered.locations.text == ""
        assert rendered.factions.text == ""
        assert rendered.systems.text == ""
        assert rendered.timelines.text == ""

    def test_multiple_unknown_types_all_captured(self) -> None:
        entities = [
            _entity("o1", entity_type="object", name="Ring", content="Golden."),
            _entity("o2", entity_type="concept", name="Mana", content="Magical."),
            _entity("o3", entity_type="creature", name="Dragon", content="Scaly."),
        ]
        rendered = apply_tier3_rendered(entities, limit=10_000, count_tokens=_count)
        assert "Ring" in rendered.other.text
        assert "Mana" in rendered.other.text
        assert "Dragon" in rendered.other.text


# ---------------------------------------------------------------------------
# Unclassified warning logged (no longer silent)
# ---------------------------------------------------------------------------


class TestUnclassifiedWarningLogged:
    """Unknown entity types emit a structlog warning."""

    def test_unknown_type_logs_tier3_unclassified_entity_type(self) -> None:
        entity = _entity("o1", entity_type="object", name="Ring", content="Golden.")
        with capture_logs() as logs:
            apply_tier3_rendered([entity], limit=10_000, count_tokens=_count)
        matches = [log for log in logs if log["event"] == "tier3_unclassified_entity_type"]
        assert matches, "expected a tier3_unclassified_entity_type warning"
        assert matches[0]["entity_type"] == "object"
        assert matches[0]["count"] == 1

    def test_distinct_unknown_types_logged_once_each_with_counts(self) -> None:
        entities = [
            _entity("o1", entity_type="object", name="Ring", content="Golden."),
            _entity("o2", entity_type="object", name="Sword", content="Sharp."),
            _entity("o3", entity_type="concept", name="Mana", content="Magical."),
        ]
        with capture_logs() as logs:
            apply_tier3_rendered(entities, limit=10_000, count_tokens=_count)
        warnings = {
            log["entity_type"]: log["count"]
            for log in logs
            if log["event"] == "tier3_unclassified_entity_type"
        }
        assert warnings == {"object": 2, "concept": 1}

    def test_no_warning_when_all_types_known(self) -> None:
        entity = _entity("c1", entity_type="character", name="Alice", content="Brave.")
        with capture_logs() as logs:
            apply_tier3_rendered([entity], limit=10_000, count_tokens=_count)
        assert not [log for log in logs if log["event"] == "tier3_unclassified_entity_type"]


# ---------------------------------------------------------------------------
# Known types still routed correctly (regression)
# ---------------------------------------------------------------------------


class TestKnownTypesRoutedCorrectlyRegression:
    """Known entity types still reach their dedicated buckets."""

    @pytest.mark.parametrize(
        ("entity_type", "bucket_attr"),
        [
            ("character", "characters"),
            ("location", "locations"),
            ("faction", "factions"),
            ("system", "systems"),
            ("timeline", "timelines"),
        ],
    )
    def test_known_type_in_correct_bucket(self, entity_type: str, bucket_attr: str) -> None:
        entity = _entity("e1", entity_type=entity_type, name="X", content="Content.")
        rendered = apply_tier3_rendered([entity], limit=10_000, count_tokens=_count)
        assert getattr(rendered, bucket_attr).text != ""
        assert rendered.other.text == ""


# ---------------------------------------------------------------------------
# Truncation priority: kb_other is LOWEST priority (truncated before systems)
# ---------------------------------------------------------------------------


class TestOtherBucketLowestTruncationPriority:
    """Known buckets win budget over unknown ones; kb_other is cut first."""

    def test_other_truncated_before_systems(self) -> None:
        # Two equal-size entities (6 tokens each), budget fits exactly ONE.
        # Priority decides which survives: the known type (system) wins,
        # the unknown type (other) is emptied first.
        entities = [
            _entity("s1", entity_type="system", name="Magic", content="Magic costs mana."),
            _entity("o1", entity_type="object", name="Ring", content="A golden ring."),
        ]
        rendered = apply_tier3_rendered(entities, limit=6, count_tokens=_count)
        assert rendered.systems.text != ""
        assert rendered.other.text == ""

    def test_other_survives_when_budget_plentiful(self) -> None:
        entities = [
            _entity("s1", entity_type="system", name="Magic", content="word word word."),
            _entity("o1", entity_type="object", name="Ring", content="word word word."),
        ]
        rendered = apply_tier3_rendered(entities, limit=10_000, count_tokens=_count)
        assert rendered.systems.text != ""
        assert rendered.other.text != ""


# ---------------------------------------------------------------------------
# apply_tier3 arity grows to a 9-tuple
# ---------------------------------------------------------------------------


class TestApplyTier3Arity:
    """apply_tier3 returns a 9-tuple; the other element is the 6th item."""

    def test_apply_tier3_returns_nine_elements(self) -> None:
        result = apply_tier3([], limit=1000, count_tokens=_count)
        assert len(result) == 9

    def test_apply_tier3_other_is_sixth_element(self) -> None:
        entity = _entity("o1", entity_type="object", name="Ring", content="Golden ring.")
        result = apply_tier3([entity], limit=10_000, count_tokens=_count)
        (
            _chars,
            _locs,
            _facs,
            _systems,
            _timelines,
            other_text,
            _overflow,
            _fresh,
            _stale,
        ) = result
        assert "Ring" in other_text


# ---------------------------------------------------------------------------
# WritingContext exposes kb_other and maps it to prompt variables
# ---------------------------------------------------------------------------


class TestWritingContextKbOther:
    """WritingContext exposes kb_other and maps it to prompt variables."""

    def test_default_kb_other_is_empty_string(self) -> None:
        assert WritingContext().kb_other == ""

    def test_to_prompt_variables_includes_kb_other(self) -> None:
        variables = WritingContext().to_prompt_variables()
        assert variables["kb_other"] == ""

    def test_kb_other_value_propagates_to_variables(self) -> None:
        ctx = WritingContext(kb_other="### Object: Ring\nGolden.")
        assert ctx.to_prompt_variables()["kb_other"] == "### Object: Ring\nGolden."


# ---------------------------------------------------------------------------
# kb_other registered and composable (no PromptVariableError)
# ---------------------------------------------------------------------------


class TestKbOtherRegisteredAndComposable:
    """kb_other is registered in SYSTEM_VARS and composes without error."""

    def test_kb_other_in_system_vars(self) -> None:
        assert "kb_other" in SYSTEM_VARS

    def test_template_with_kb_other_composes_without_prompt_variable_error(self) -> None:
        # prepare_variables_for_template raises PromptVariableError for any
        # placeholder that is neither registered nor provided. kb_other must be
        # both registered (SYSTEM_VARS) and provided (to_prompt_variables).
        variables = WritingContext().to_prompt_variables()
        prepared = prepare_variables_for_template("Header\n{{kb_other}}\nFooter", variables)
        assert "kb_other" in prepared
