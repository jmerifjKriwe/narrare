"""Integration tests for INFRA-010: project-level prompt cascade activation.

Verifies that PromptRegistry.resolve() picks up files from the
project-level .narrare/prompts/ directory when project_root is set,
and falls back to bundled prompts when no override exists.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from narrare_core.prompts.registry import PromptRegistry


class TestProjectLevelCascadeIntegration:
    """Verify project-level .narrare/prompts/ files are picked up by resolve()."""

    async def test_project_override_is_resolved(self) -> None:
        """Create a .narrare/prompts/ file, verify resolve() finds it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Create project-level prompt file
            prompt_dir = project_root / ".narrare" / "prompts" / "writing" / "en" / "new_chapter"
            prompt_dir.mkdir(parents=True)
            prompt_file = prompt_dir / "system.md"
            prompt_file.write_text(
                "---\nprompt_version: 1.0.0\n---\n\n## System Prompt\n\nTest override content"
            )

            registry = PromptRegistry(project_root=project_root)
            resolved = await registry.resolve(
                category="writing",
                language="en",
                mode="new_chapter",
            )

            assert resolved.source == "project", f"Expected 'project' source, got {resolved.source}"
            assert "Test override content" in resolved.system_prompt

    async def test_bundled_prompt_when_no_project_override(self) -> None:
        """Without project-level file, bundled prompt is resolved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            registry = PromptRegistry(project_root=project_root)

            # Try to resolve a prompt that exists in bundled
            resolved = await registry.resolve(
                category="writing",
                language="en",
                mode="interview",
            )

            assert resolved.source in ("bundled", "bundled_en"), (
                f"Expected bundled source, got {resolved.source}"
            )
            assert len(resolved.system_prompt) > 0
