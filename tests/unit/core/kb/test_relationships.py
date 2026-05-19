"""Unit tests for KB relationship type definitions.

Tests cover:
- RelationshipType constants exist and are strings
- INVERSE_SUGGESTIONS has entries for common types
- suggested_for returns correct types for known pairs
- suggested_for returns empty list for unknown pairs
"""

from __future__ import annotations

from narrare_core.kb.relationships import (
    INVERSE_SUGGESTIONS,
    RelationshipType,
    suggested_for,
)


class TestRelationshipTypeConstants:
    """Tests for the RelationshipType constants class."""

    def test_all_constants_are_strings(self) -> None:
        """Every constant should be a string value."""
        for attr_name in dir(RelationshipType):
            if attr_name.startswith("_"):
                continue
            value = getattr(RelationshipType, attr_name)
            assert isinstance(value, str), f"{attr_name} is not a string"

    def test_character_character_types(self) -> None:
        """Character→Character should have 9 relationship types."""
        expected = {
            "ally",
            "rival",
            "mentor",
            "mentee",
            "family",
            "romantic",
            "enemy",
            "neutral",
            "colleague",
        }
        actual = {
            RelationshipType.ALLY,
            RelationshipType.RIVAL,
            RelationshipType.MENTOR,
            RelationshipType.MENTEE,
            RelationshipType.FAMILY,
            RelationshipType.ROMANTIC,
            RelationshipType.ENEMY,
            RelationshipType.NEUTRAL,
            RelationshipType.COLLEAGUE,
        }
        assert actual == expected

    def test_character_location_types(self) -> None:
        """Character→Location should have 5 relationship types."""
        expected = {"born_in", "lives_in", "visits", "rules", "guards"}
        actual = {
            RelationshipType.BORN_IN,
            RelationshipType.LIVES_IN,
            RelationshipType.VISITS,
            RelationshipType.RULES,
            RelationshipType.GUARDS,
        }
        assert actual == expected

    def test_character_faction_types(self) -> None:
        """Character→Faction should have 4 relationship types."""
        expected = {"member_of", "leader_of", "opposes", "founded_faction"}
        actual = {
            RelationshipType.MEMBER_OF,
            RelationshipType.LEADER_OF,
            RelationshipType.OPPOSES,
            RelationshipType.FOUNDED_FACTION,
        }
        assert actual == expected

    def test_character_object_types(self) -> None:
        expected = {"owns", "seeks", "created", "destroyed"}
        actual = {
            RelationshipType.OWNS,
            RelationshipType.SEEKS,
            RelationshipType.CREATED,
            RelationshipType.DESTROYED,
        }
        assert actual == expected

    def test_character_system_types(self) -> None:
        expected = {"practitioner_of", "affected_by"}
        actual = {RelationshipType.PRACTITIONER_OF, RelationshipType.AFFECTED_BY}
        assert actual == expected

    def test_location_location_types(self) -> None:
        expected = {"contains", "borders", "connected_to"}
        actual = {
            RelationshipType.CONTAINS,
            RelationshipType.BORDERS,
            RelationshipType.CONNECTED_TO,
        }
        assert actual == expected

    def test_faction_faction_types(self) -> None:
        expected = {"faction_allies", "faction_rivals", "subordinate_of"}
        actual = {
            RelationshipType.FACTION_ALLIES,
            RelationshipType.FACTION_RIVALS,
            RelationshipType.SUBORDINATE_OF,
        }
        assert actual == expected

    def test_faction_location_types(self) -> None:
        expected = {"headquartered_in", "controls", "claims"}
        actual = {
            RelationshipType.HEADQUARTERED_IN,
            RelationshipType.CONTROLS,
            RelationshipType.CLAIMS,
        }
        assert actual == expected

    def test_object_object_types(self) -> None:
        expected = {"part_of", "transforms_into"}
        actual = {RelationshipType.PART_OF, RelationshipType.TRANSFORMS_INTO}
        assert actual == expected

    def test_object_system_types(self) -> None:
        expected = {"powered_by", "channel_for"}
        actual = {RelationshipType.POWERED_BY, RelationshipType.CHANNEL_FOR}
        assert actual == expected

    def test_system_system_types(self) -> None:
        expected = {"counters", "enhances", "subset_of"}
        actual = {
            RelationshipType.COUNTERS,
            RelationshipType.ENHANCES,
            RelationshipType.SUBSET_OF,
        }
        assert actual == expected


class TestInverseSuggestions:
    """Tests for the INVERSE_SUGGESTIONS mapping."""

    def test_mentor_inverse_is_mentee(self) -> None:
        assert INVERSE_SUGGESTIONS[RelationshipType.MENTOR] == RelationshipType.MENTEE

    def test_mentee_inverse_is_mentor(self) -> None:
        assert INVERSE_SUGGESTIONS[RelationshipType.MENTEE] == RelationshipType.MENTOR

    def test_symmetric_relationships_self_inverse(self) -> None:
        """Symmetric types (ally, rival, enemy, family) should map to themselves."""
        assert INVERSE_SUGGESTIONS[RelationshipType.ALLY] == RelationshipType.ALLY
        assert INVERSE_SUGGESTIONS[RelationshipType.RIVAL] == RelationshipType.RIVAL
        assert INVERSE_SUGGESTIONS[RelationshipType.ENEMY] == RelationshipType.ENEMY
        assert INVERSE_SUGGESTIONS[RelationshipType.FAMILY] == RelationshipType.FAMILY

    def test_born_in_inverse(self) -> None:
        assert INVERSE_SUGGESTIONS[RelationshipType.BORN_IN] == "birthplace_of"

    def test_lives_in_inverse(self) -> None:
        assert INVERSE_SUGGESTIONS[RelationshipType.LIVES_IN] == "home_of"

    def test_member_of_inverse(self) -> None:
        assert INVERSE_SUGGESTIONS[RelationshipType.MEMBER_OF] == "has_member"

    def test_leader_of_inverse(self) -> None:
        assert INVERSE_SUGGESTIONS[RelationshipType.LEADER_OF] == "led_by"

    def test_owns_inverse(self) -> None:
        assert INVERSE_SUGGESTIONS[RelationshipType.OWNS] == "owned_by"

    def test_all_values_are_strings_or_none(self) -> None:
        """Every value should be a string or None."""
        for key, value in INVERSE_SUGGESTIONS.items():
            assert isinstance(key, str)
            assert value is None or isinstance(value, str)

    def test_all_keys_are_string_constants(self) -> None:
        """Every key should be a string from RelationshipType constants."""
        for key in INVERSE_SUGGESTIONS:
            assert isinstance(key, str)


class TestSuggestedFor:
    """Tests for the suggested_for helper function."""

    def test_character_character(self) -> None:
        result = suggested_for("character", "character")
        assert "ally" in result
        assert "rival" in result
        assert "mentor" in result
        assert len(result) == 9

    def test_character_location(self) -> None:
        result = suggested_for("character", "location")
        assert "born_in" in result
        assert "lives_in" in result
        assert len(result) == 5

    def test_character_faction(self) -> None:
        result = suggested_for("character", "faction")
        assert "member_of" in result
        assert "leader_of" in result
        assert len(result) == 4

    def test_character_object(self) -> None:
        result = suggested_for("character", "object")
        assert "owns" in result
        assert len(result) == 4

    def test_character_system(self) -> None:
        result = suggested_for("character", "system")
        assert "practitioner_of" in result
        assert len(result) == 2

    def test_location_location(self) -> None:
        result = suggested_for("location", "location")
        assert "contains" in result
        assert "borders" in result
        assert len(result) == 3

    def test_faction_faction(self) -> None:
        result = suggested_for("faction", "faction")
        assert "faction_allies" in result
        assert len(result) == 3

    def test_faction_location(self) -> None:
        result = suggested_for("faction", "location")
        assert "headquartered_in" in result
        assert len(result) == 3

    def test_object_object(self) -> None:
        result = suggested_for("object", "object")
        assert "part_of" in result
        assert len(result) == 2

    def test_object_system(self) -> None:
        result = suggested_for("object", "system")
        assert "powered_by" in result
        assert len(result) == 2

    def test_system_system(self) -> None:
        result = suggested_for("system", "system")
        assert "counters" in result
        assert len(result) == 3

    def test_unknown_pair_returns_empty(self) -> None:
        """Unknown source→target pairs should return an empty list."""
        assert suggested_for("character", "unknown") == []
        assert suggested_for("unknown", "character") == []
        assert suggested_for("foo", "bar") == []

    def test_returns_new_list_each_call(self) -> None:
        """Each call should return a fresh list (not a shared reference)."""
        result1 = suggested_for("character", "character")
        result2 = suggested_for("character", "character")
        assert result1 == result2
        assert result1 is not result2
