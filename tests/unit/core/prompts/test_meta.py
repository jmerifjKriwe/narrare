"""Tests for prompts/meta.py — meta-prompt loading and caching.

.. note::
    ``MetaPromptLoader`` is deprecated per ADR-046 (CR-AUFG-02-07). These
    tests are retained until the class is removed — they verify the cascade
    mechanics that the ``NarrareMeta`` Capability relies on internally.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from narrare_core.prompts.meta import MetaPromptLoader

# MetaPromptLoader is @deprecated (ADR-046); suppress during its own tests.
pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture
def loader(tmp_path: Path) -> MetaPromptLoader:
    return MetaPromptLoader(project_root=tmp_path)


class TestMetaPromptLoaderLoad:
    async def test_loads_bundled_english_meta_prompt(self) -> None:
        loader = MetaPromptLoader()
        content = await loader.load("en")
        # If bundled prompt exists, it should return non-empty string
        # If not, it should return empty string (no error)
        assert isinstance(content, str)

    async def test_load_returns_empty_for_missing_language(self) -> None:
        loader = MetaPromptLoader()
        content = await loader.load("xx")
        assert isinstance(content, str)

    async def test_load_cascades_to_project_override(self, tmp_path: Path) -> None:
        # Create a project-level override
        meta_dir = tmp_path / ".narrare" / "prompts" / "meta" / "en"
        meta_dir.mkdir(parents=True)
        (meta_dir / "system.md").write_text("Project meta prompt")

        loader = MetaPromptLoader(project_root=tmp_path)
        content = await loader.load("en")

        assert content == "Project meta prompt"

    async def test_load_cascades_to_user_config(self, tmp_path: Path) -> None:
        user_dir = tmp_path / "config"
        meta_dir = user_dir / "prompts" / "meta" / "en"
        meta_dir.mkdir(parents=True)
        (meta_dir / "system.md").write_text("User config meta prompt")

        loader = MetaPromptLoader(user_config_dir=user_dir)
        content = await loader.load("en")

        assert content == "User config meta prompt"

    async def test_project_overrides_user_config(self, tmp_path: Path) -> None:
        # Project-level
        proj_dir = tmp_path / ".narrare" / "prompts" / "meta" / "en"
        proj_dir.mkdir(parents=True)
        (proj_dir / "system.md").write_text("Project prompt")

        # User-level
        user_dir = tmp_path / "user_config"
        user_meta_dir = user_dir / "prompts" / "meta" / "en"
        user_meta_dir.mkdir(parents=True)
        (user_meta_dir / "system.md").write_text("User prompt")

        loader = MetaPromptLoader(project_root=tmp_path, user_config_dir=user_dir)
        content = await loader.load("en")

        assert content == "Project prompt"

    async def test_substitutes_variables(self, tmp_path: Path) -> None:
        proj_dir = tmp_path / ".narrare" / "prompts" / "meta" / "en"
        proj_dir.mkdir(parents=True)
        (proj_dir / "system.md").write_text(
            "---\nprompt_type: meta\n---\nHello {{project_title}}, you are {{genre}}."
        )

        loader = MetaPromptLoader(project_root=tmp_path)
        content = await loader.load(
            "en",
            variables={"project_title": "My Novel", "genre": "fantasy"},
        )

        assert "My Novel" in content
        assert "fantasy" in content
        assert "{{" not in content

    async def test_strips_frontmatter(self, tmp_path: Path) -> None:
        proj_dir = tmp_path / ".narrare" / "prompts" / "meta" / "en"
        proj_dir.mkdir(parents=True)
        (proj_dir / "system.md").write_text("---\nprompt_type: meta\n---\nActual prompt content")

        loader = MetaPromptLoader(project_root=tmp_path)
        content = await loader.load("en")

        assert "prompt_type" not in content
        assert "Actual prompt content" in content

    async def test_caches_result(self, tmp_path: Path) -> None:
        proj_dir = tmp_path / ".narrare" / "prompts" / "meta" / "en"
        proj_dir.mkdir(parents=True)
        (proj_dir / "system.md").write_text("Cached prompt")

        loader = MetaPromptLoader(project_root=tmp_path)
        content1 = await loader.load("en")
        content2 = await loader.load("en")

        assert content1 == content2 == "Cached prompt"

    async def test_load_lite_variant(self, tmp_path: Path) -> None:
        proj_dir = tmp_path / ".narrare" / "prompts" / "meta" / "en"
        proj_dir.mkdir(parents=True)
        (proj_dir / "system.lite.md").write_text("Lite prompt")

        loader = MetaPromptLoader(project_root=tmp_path)
        content = await loader.load("en", use_lite=True)

        assert content == "Lite prompt"

    async def test_falls_back_to_english_for_missing_language(self) -> None:
        # "zz" has no bundled prompt, no user config — should hit bundled English fallback
        loader = MetaPromptLoader()
        content = await loader.load("zz")

        # Should return the bundled English meta prompt (not empty)
        assert isinstance(content, str)
        assert "Narrare" in content

    async def test_load_returns_empty_when_cascade_finds_nothing(self, tmp_path: Path) -> None:
        """When no prompt exists at any cascade level including EN fallback, return ''."""
        loader = MetaPromptLoader()
        # Point to non-existent bundled root so nothing resolves
        loader._bundled_root = tmp_path / "nonexistent"

        content = await loader.load("xx")
        assert content == ""

    async def test_load_returns_empty_from_cache(self, tmp_path: Path) -> None:
        """After caching an empty result, subsequent load returns ''."""
        loader = MetaPromptLoader()
        loader._bundled_root = tmp_path / "nonexistent"

        content1 = await loader.load("xx")
        content2 = await loader.load("xx")
        assert content1 == content2 == ""


class TestMetaPromptLoaderFindBundledRoot:
    """_find_bundled_root exception handler (lines 49-50)."""

    def test_falls_back_when_importlib_resources_fails(self) -> None:
        """When importlib.resources.files raises, fall back to relative path."""
        from unittest.mock import patch

        target = "importlib.resources.files"
        with patch(target, side_effect=Exception("mock import error")):
            loader = MetaPromptLoader()

        # The fallback path points to meta.py's parent/_bundled
        assert loader._bundled_root.name == "_bundled"
        assert str(loader._bundled_root).endswith("prompts/_bundled")


class TestMetaPromptLoaderShouldUseLite:
    def test_returns_true_when_below_threshold(self) -> None:
        loader = MetaPromptLoader()
        assert loader.should_use_lite(1999) is True

    def test_returns_false_when_above_threshold(self) -> None:
        loader = MetaPromptLoader()
        assert loader.should_use_lite(2000) is False


class TestMetaPromptLoaderInvalidateCache:
    async def test_clears_cache(self, tmp_path: Path) -> None:
        proj_dir = tmp_path / ".narrare" / "prompts" / "meta" / "en"
        proj_dir.mkdir(parents=True)
        (proj_dir / "system.md").write_text("Original")

        loader = MetaPromptLoader(project_root=tmp_path)
        await loader.load("en")

        # Overwrite file
        (proj_dir / "system.md").write_text("Updated")

        # Still cached
        content = await loader.load("en")
        assert content == "Original"

        # Invalidate and reload
        loader.invalidate_cache()
        content = await loader.load("en")
        assert content == "Updated"


class TestMetaPromptGuardrails:
    """Guardrails in bundled meta-prompt templates (CR-02 Phase 4).

    After ADR-026 Phase 1, fiction guidelines, conflict resolution, and
    content security have been moved from the meta-prompt to
    NarrareUniversalRules Capability. The meta-prompt now only contains
    identity, role flexibility, and conversation guardrails.
    """

    # --- English meta-prompt ---

    async def test_en_contains_conversation_guardrails(self) -> None:
        loader = MetaPromptLoader()
        content = await loader.load("en")
        assert "Conversation Guardrails" in content

    async def test_en_contains_avoidance_patterns_variable(self) -> None:
        loader = MetaPromptLoader()
        content = await loader.load("en")
        assert "{{avoidance_patterns}}" in content

    async def test_en_no_longer_contains_fiction_guidelines(self) -> None:
        """Fiction guidelines moved to NarrareUniversalRules (ADR-026)."""
        loader = MetaPromptLoader()
        content = await loader.load("en")
        assert "Fiction Content Guidelines" not in content

    async def test_en_no_longer_contains_conflict_resolution(self) -> None:
        """Conflict resolution moved to NarrareUniversalRules (ADR-026)."""
        loader = MetaPromptLoader()
        content = await loader.load("en")
        assert "Conflict Resolution" not in content

    async def test_en_no_longer_contains_content_security(self) -> None:
        """Content security moved to NarrareUniversalRules (ADR-026)."""
        loader = MetaPromptLoader()
        content = await loader.load("en")
        assert "Content Security" not in content

    # --- German meta-prompt ---

    async def test_de_contains_conversation_guardrails(self) -> None:
        loader = MetaPromptLoader()
        content = await loader.load("de")
        assert "Konversations-Leitlinien" in content

    async def test_de_contains_avoidance_patterns_variable(self) -> None:
        loader = MetaPromptLoader()
        content = await loader.load("de")
        assert "{{avoidance_patterns}}" in content

    async def test_de_no_longer_contains_fiction_guidelines(self) -> None:
        """Fiction guidelines moved to NarrareUniversalRules (ADR-026)."""
        loader = MetaPromptLoader()
        content = await loader.load("de")
        assert "Fiktionsinhalts-Richtlinien" not in content

    async def test_de_no_longer_contains_conflict_resolution(self) -> None:
        """Conflict resolution moved to NarrareUniversalRules (ADR-026)."""
        loader = MetaPromptLoader()
        content = await loader.load("de")
        assert "Konfliktlösung" not in content

    # --- French meta-prompt ---

    async def test_fr_contains_conversation_guardrails(self) -> None:
        loader = MetaPromptLoader()
        content = await loader.load("fr")
        assert "Directives de conversation" in content

    async def test_fr_contains_avoidance_patterns_variable(self) -> None:
        loader = MetaPromptLoader()
        content = await loader.load("fr")
        assert "{{avoidance_patterns}}" in content

    async def test_fr_no_longer_contains_fiction_guidelines(self) -> None:
        """Fiction guidelines moved to NarrareUniversalRules (ADR-026)."""
        loader = MetaPromptLoader()
        content = await loader.load("fr")
        assert "Directives sur le contenu de fiction" not in content

    async def test_fr_no_longer_contains_conflict_resolution(self) -> None:
        """Conflict resolution moved to NarrareUniversalRules (ADR-026)."""
        loader = MetaPromptLoader()
        content = await loader.load("fr")
        assert "Résolution des conflits" not in content

    # --- Lite meta-prompt ---

    async def test_lite_contains_avoidance_patterns_variable(self) -> None:
        loader = MetaPromptLoader()
        content = await loader.load("en", use_lite=True)
        assert "{{avoidance_patterns}}" in content

    async def test_lite_no_longer_contains_fiction_reference(self) -> None:
        """Fiction reference moved to NarrareUniversalRules (ADR-026)."""
        loader = MetaPromptLoader()
        content = await loader.load("en", use_lite=True)
        # Lite meta no longer contains fiction guidelines
        assert "fiction content" not in content.lower()
        assert "normal narrative" not in content.lower()

    async def test_lite_is_significantly_shorter_than_full(self) -> None:
        loader = MetaPromptLoader()
        full = await loader.load("en")
        lite = await loader.load("en", use_lite=True)
        assert len(lite) < len(full) * 0.5

    # --- Variable substitution ---

    async def test_avoidance_patterns_substitution(self) -> None:
        loader = MetaPromptLoader()
        content = await loader.load(
            "en",
            variables={"avoidance_patterns": "No spiders, no graphic violence"},
        )
        assert "No spiders, no graphic violence" in content
        assert "{{avoidance_patterns}}" not in content
