"""Tests for WikiPromptLoader — prompt loading, Jinja2 conditionals, variable substitution.

Test-Strategie:
- Testet die statischen Methoden von WikiPromptLoader direkt
- Verwendet reale Bundle-Dateien für read_bundled_prompt-Tests
- Jinja2 conditionals mit verschiedenen entity_types
- Variable substitution mit echten Dependencies
"""

from __future__ import annotations

import pytest

from narrare_core.wiki.prompt_loader import WikiPromptLoader
from narrare_core.wiki.types import WikiGenerationDeps

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def deps() -> WikiGenerationDeps:
    """Default generation deps for a character entity."""
    return WikiGenerationDeps(
        language="en",
        genre="Fantasy",
        entity_type="character",
        entity_name="Eldrin the Wise",
        entity_body="Eldrin is an ancient wizard who guards the Crystal of Eternity.",
        entity_metadata={"age": "immortal", "alignment": "neutral good"},
        relationships=[
            {"name": "Lyra", "type": "apprentice", "context": "Chapter 3"},
            {"name": "Morgath", "type": "rival", "context": "Chapter 5"},
        ],
        chapter_context=["Chapter 3: Eldrin teaches Lyra about the crystal."],
    )


@pytest.fixture()
def deps_location() -> WikiGenerationDeps:
    """Generation deps for a location entity."""
    return WikiGenerationDeps(
        language="en",
        genre="Fantasy",
        entity_type="location",
        entity_name="The Whispering Woods",
        entity_body="An ancient forest where the trees communicate telepathically.",
        entity_metadata={"size": "vast", "danger_level": "moderate"},
        relationships=[
            {"name": "Eldrin", "type": "protector", "context": "Chapter 2"},
        ],
        chapter_context=["Chapter 2: The party enters the woods."],
    )


# ---------------------------------------------------------------------------
# A. Jinja2 Conditional Handling
# ---------------------------------------------------------------------------


class TestProcessJinjaConditionals:
    """Jinja2 conditional processing in bundled prompts."""

    def test_character_keeps_arc(self) -> None:
        """Character entity_type keeps the character_arc section."""
        text = (
            "Some text.\n"
            '{% if entity_type == "character" %}\n'
            "5. **Character Arc** — Include arc.\n"
            "{% endif %}\n"
            "More text."
        )
        deps = WikiGenerationDeps(
            language="en",
            genre="Fantasy",
            entity_type="character",
            entity_name="Test",
            entity_body="Body",
        )
        result = WikiPromptLoader.process_jinja_conditionals(text, deps)
        assert "Character Arc" in result
        assert "{% if" not in result
        assert "{% endif" not in result

    def test_location_removes_arc(self) -> None:
        """Non-character entity_type removes the character_arc section."""
        text = (
            "Some text.\n"
            '{% if entity_type == "character" %}\n'
            "5. **Character Arc** — Include arc.\n"
            "{% endif %}\n"
            "More text."
        )
        deps = WikiGenerationDeps(
            language="en",
            genre="Fantasy",
            entity_type="location",
            entity_name="Forest",
            entity_body="A forest.",
        )
        result = WikiPromptLoader.process_jinja_conditionals(text, deps)
        assert "Character Arc" not in result
        assert "{% if" not in result
        assert "{% endif" not in result


# ---------------------------------------------------------------------------
# B. Variable Building
# ---------------------------------------------------------------------------


class TestBuildVariables:
    """Variable substitution dict construction from WikiGenerationDeps."""

    def test_contains_all_keys(self, deps: WikiGenerationDeps) -> None:
        variables = WikiPromptLoader.build_variables(deps)
        assert "entity_type" in variables
        assert "entity_name" in variables
        assert "entity_body" in variables
        assert "entity_metadata" in variables
        assert "relationships" in variables
        assert "chapter_context" in variables
        assert "language" in variables
        assert "genre" in variables


# ---------------------------------------------------------------------------
# C. Bundled Prompt Reading
# ---------------------------------------------------------------------------


class TestReadBundledPrompt:
    """Reading prompt files from the bundled prompts directory."""

    def test_entity_prompt(self) -> None:
        """Entity prompt can be read from bundled prompts."""
        text = WikiPromptLoader.read_bundled_prompt("wiki", "en", "entity_summary")
        assert isinstance(text, str)
        assert len(text) > 0
        assert "narrative_summary" in text

    def test_chapter_prompt(self) -> None:
        """Chapter prompt can be read from bundled prompts."""
        text = WikiPromptLoader.read_bundled_prompt("wiki", "en", "chapter_summary")
        assert isinstance(text, str)
        assert len(text) > 0
        assert "narrative_summary" in text

    def test_fallback_to_en(self) -> None:
        """Unknown language falls back to English."""
        text = WikiPromptLoader.read_bundled_prompt("wiki", "xx", "entity_summary")
        assert isinstance(text, str)
        assert len(text) > 0
        # Should be the English version
        assert "You are a narrative wiki generator" in text


# ---------------------------------------------------------------------------
# D. Full Prompt Rendering
# ---------------------------------------------------------------------------


class TestRenderPrompt:
    """Full prompt rendering: frontmatter + conditionals + substitution."""

    def test_substitutes_variables(self, deps: WikiGenerationDeps) -> None:
        """Rendered prompt has variables substituted."""
        raw = WikiPromptLoader.read_bundled_prompt("wiki", "en", "entity_summary")
        rendered = WikiPromptLoader.render_prompt(raw, deps)
        assert "{{entity_type}}" not in rendered
        assert "{{entity_name}}" not in rendered
        assert deps.entity_name in rendered
        assert deps.entity_type in rendered

    def test_handles_character_conditional(self, deps: WikiGenerationDeps) -> None:
        """Character conditional is kept for character entities."""
        raw = WikiPromptLoader.read_bundled_prompt("wiki", "en", "entity_summary")
        rendered = WikiPromptLoader.render_prompt(raw, deps)
        # Character arc instruction should be in the rendered prompt
        assert "Character Arc" in rendered or "character_arc" in rendered

    def test_removes_character_conditional_for_location(
        self, deps_location: WikiGenerationDeps
    ) -> None:
        """Character conditional is removed for non-character entities."""
        raw = WikiPromptLoader.read_bundled_prompt("wiki", "en", "entity_summary")
        rendered = WikiPromptLoader.render_prompt(raw, deps_location)
        # Character arc instruction should NOT be in the rendered prompt
        assert "Character Arc" not in rendered
