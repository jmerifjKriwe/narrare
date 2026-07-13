"""Unit tests for ContextMetadata and WritingContext.to_metadata()."""

from narrare_core.writing.context_models import ContextMetadata
from narrare_core.writing.models import WritingContext


class TestContextMetadata:
    """Tests for the ContextMetadata dataclass."""

    def test_defaults(self):
        meta = ContextMetadata()
        assert meta.kb_characters_count == 0
        assert meta.kb_locations_count == 0
        assert meta.kb_factions_count == 0
        assert meta.kb_suggested_count == 0
        assert meta.kb_pinned_count == 0
        assert meta.recent_chapter_count == 0
        assert meta.character_names == []
        assert meta.location_names == []
        assert meta.faction_names == []
        assert meta.is_first_chapter is False
        assert meta.has_user_preferences is False
        assert meta.tone == "balanced"
        assert meta.total_budget_tokens == 0

    def test_custom_values(self):
        meta = ContextMetadata(
            kb_characters_count=3,
            character_names=["Anna", "Johann", "Waldgeist"],
            kb_locations_count=2,
            location_names=["Försterhaus", "Stiller Wald"],
            tone="dramatic",
            total_budget_tokens=8000,
        )
        assert meta.kb_characters_count == 3
        assert meta.character_names == ["Anna", "Johann", "Waldgeist"]
        assert meta.kb_locations_count == 2
        assert meta.tone == "dramatic"
        assert meta.total_budget_tokens == 8000


class TestWritingContextToMetadata:
    """Tests for WritingContext.to_metadata()."""

    def test_empty_context(self):
        ctx = WritingContext()
        meta = ctx.to_metadata()
        assert meta.kb_characters_count == 0
        assert meta.kb_locations_count == 0
        assert meta.character_names == []
        assert meta.is_first_chapter is False
        assert meta.has_user_preferences is False

    def test_entity_count_extraction(self):
        """Entity text uses '### Type: Name' format — count '### ' occurrences."""
        characters = "### Character: Anna\nA brave girl.\n\n### Character: Johann\nA forester."
        factions = (
            "### Faction: Waldfreunde\nForest friends.\n\n### Faction: Dorfrat\nVillage council."
        )
        ctx = WritingContext(
            kb_characters=characters,
            kb_locations="### Location: Försterhaus\nA cozy cabin.",
            kb_factions=factions,
        )
        meta = ctx.to_metadata()
        assert meta.kb_characters_count == 2
        assert meta.kb_locations_count == 1
        assert meta.kb_factions_count == 2

    def test_entity_count_with_suggested_and_pinned(self):
        ctx = WritingContext(
            kb_suggested="### Character: Minor NPC\nBackground.",
            kb_pinned="### Location: Important Place\nAlways included.",
        )
        meta = ctx.to_metadata()
        assert meta.kb_suggested_count == 1
        assert meta.kb_pinned_count == 1

    def test_names_forwarded(self):
        """character_names/location_names/faction_names are populated by the assembler."""
        ctx = WritingContext(
            character_names=["Anna", "Johann"],
            location_names=["Försterhaus"],
            faction_names=["Waldfreunde"],
        )
        meta = ctx.to_metadata()
        assert meta.character_names == ["Anna", "Johann"]
        assert meta.location_names == ["Försterhaus"]
        assert meta.faction_names == ["Waldfreunde"]

    def test_first_chapter_flag(self):
        ctx = WritingContext(is_first_chapter=True)
        meta = ctx.to_metadata()
        assert meta.is_first_chapter is True

    def test_user_preferences_present(self):
        ctx = WritingContext(user_preferences="Avoid purple prose")
        meta = ctx.to_metadata()
        assert meta.has_user_preferences is True

    def test_user_preferences_absent(self):
        ctx = WritingContext(user_preferences="")
        meta = ctx.to_metadata()
        assert meta.has_user_preferences is False

    def test_user_preferences_whitespace_only(self):
        ctx = WritingContext(user_preferences="   \n  ")
        meta = ctx.to_metadata()
        assert meta.has_user_preferences is False

    def test_tone_forwarded(self):
        ctx = WritingContext(tone="dramatic")
        meta = ctx.to_metadata()
        assert meta.tone == "dramatic"

    def test_total_budget_forwarded(self):
        ctx = WritingContext(total_budget_tokens=8000)
        meta = ctx.to_metadata()
        assert meta.total_budget_tokens == 8000

    def test_recent_chapter_count_forwarded(self):
        ctx = WritingContext(recent_chapter_count=3)
        meta = ctx.to_metadata()
        assert meta.recent_chapter_count == 3

    # ------------------------------------------------------------------
    # CR-04: New fields forwarded through to_metadata()
    # ------------------------------------------------------------------

    def test_story_structure_forwarded(self):
        ctx = WritingContext(story_structure="Hero's Journey")
        meta = ctx.to_metadata()
        assert meta.story_structure == "Hero's Journey"

    def test_timeline_position_forwarded(self):
        ctx = WritingContext(timeline_position="Day 5")
        meta = ctx.to_metadata()
        assert meta.timeline_position == "Day 5"

    def test_kb_systems_count_from_text(self):
        ctx = WritingContext(
            kb_systems="### System: Magic Rules\nMana costs 10.\n\n### System: Combat\nTurn-based."
        )
        meta = ctx.to_metadata()
        assert meta.kb_systems_count == 2

    def test_kb_timelines_count_from_text(self):
        ctx = WritingContext(
            kb_timelines="### Timeline: War of Ashes\nYear 1042.\n\n### Timeline: Founding\nYear 1."
        )
        meta = ctx.to_metadata()
        assert meta.kb_timelines_count == 2

    # ------------------------------------------------------------------
    # Cross-session context (mem0) — mirrors has_user_preferences
    # ------------------------------------------------------------------

    def test_has_cross_session_context_present(self):
        ctx = WritingContext(cross_session_context="- Author likes short chapters.")
        meta = ctx.to_metadata()
        assert meta.has_cross_session_context is True

    def test_has_cross_session_context_absent(self):
        ctx = WritingContext(cross_session_context="")
        meta = ctx.to_metadata()
        assert meta.has_cross_session_context is False

    def test_has_cross_session_context_whitespace_only(self):
        ctx = WritingContext(cross_session_context="   \n  ")
        meta = ctx.to_metadata()
        assert meta.has_cross_session_context is False

    def test_has_cross_session_context_in_to_dict(self):
        meta = ContextMetadata(has_cross_session_context=True)
        d = meta.to_dict()
        assert d["has_cross_session_context"] is True
