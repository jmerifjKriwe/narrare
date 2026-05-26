"""Regression tests for INFRA-010: workspace root cascade activation.

Verifies that:
1. DI factory produces PromptRegistry with project_root=BASE_DIR
2. The cascade resolves project-level paths correctly
3. Management fallback uses user_config_dir, not ~/.narrare
"""

from __future__ import annotations

from narrare._app.config import BASE_DIR
from narrare_core.prompts.management import PromptManagementService
from narrare_core.prompts.registry import PromptRegistry


class TestWorkspaceCascade:
    """Verify project-level cascade is active via DI-provided registry."""

    def test_registry_with_project_root_resolves_project_paths(self) -> None:
        """Project-level cascade paths should resolve to workspace root."""
        registry = PromptRegistry(project_root=BASE_DIR)
        paths = registry._build_search_paths(
            category="writing",
            language="en",
            mode="new_chapter",
            genre=None,
        )
        project_paths = [str(p) for p, source in paths if source == "project"]
        assert len(project_paths) > 0, "Should have project-level paths"
        assert str(BASE_DIR) in project_paths[0], "Path should contain BASE_DIR"
        assert ".narrare/prompts/writing/en/new_chapter" in project_paths[0]

    def test_registry_without_project_root_skips_project_paths(self) -> None:
        """When project_root is None, no project-level paths should be generated."""
        registry = PromptRegistry()
        paths = registry._build_search_paths(
            category="writing",
            language="en",
            mode="new_chapter",
            genre=None,
        )
        project_paths = [p for p, source in paths if source == "project"]
        assert len(project_paths) == 0, "Should NOT have project-level paths"

    def test_management_fallback_uses_user_config_dir(self) -> None:
        """_project_override_path fallback should align with cascade user-global path."""
        registry = PromptRegistry()
        service = PromptManagementService(registry=registry)
        path = service._project_override_path("writing", "en", "new_chapter")

        # Should NOT use .narrare in the fallback
        assert ".narrare" not in str(path), "Fallback should not use .narrare"
        # Should use user_config_dir (default ~/.config/narrare/prompts/)
        assert "prompts" in str(path)
        assert "writing/en/new_chapter/system.md" in str(path)
