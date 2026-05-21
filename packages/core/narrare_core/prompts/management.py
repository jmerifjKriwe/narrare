"""Prompt management service — CRUD for prompt overrides.

Handles listing, reading, saving, and resetting prompt overrides
at the project level. Delegates update detection and diff generation
to _override_helpers.

See CONSTRAINTS.md RULE-02 (prompts only in core/prompts/).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from narrare_core.prompts._management_types import (
    CascadePath,
    PromptDetail,
    PromptInfo,
    UpdateInfo,
)
from narrare_core.prompts._override_helpers import (
    detect_override_updates,
    get_bundled_version,
    inject_override_version,
    read_override_and_bundled,
)
from narrare_core.prompts.variable_engine import extract_variables
from narrare_core.shared.file_utils import (
    delete_file,
    find_files,
    read_text_or_none,
    write_text,
)
from narrare_core.shared.frontmatter import parse_frontmatter

if TYPE_CHECKING:
    from narrare_core.prompts.registry import PromptRegistry

logger = structlog.get_logger(__name__)

_SYSTEM_FILE = "system.md"


class PromptManagementService:
    """Manages prompt overrides, update detection, and diff comparison.

    Provides CRUD operations on project-level prompt overrides
    with cascade resolution and version tracking.
    """

    def __init__(self, registry: PromptRegistry) -> None:
        self._registry = registry

    async def list_prompts(
        self,
        *,
        category: str | None = None,
    ) -> list[PromptInfo]:
        """List all available bundled prompts with metadata.

        Scans the bundled prompts directory and checks for overrides
        at the project level.
        """
        bundled_root = self._registry.bundled_root
        if not bundled_root.exists():
            return []

        results: list[PromptInfo] = []
        seen_ids: set[str] = set()

        for md_path in find_files(bundled_root, "*.md"):
            rel = md_path.relative_to(bundled_root)
            parts = rel.parts

            if parts[-1] != _SYSTEM_FILE or len(parts) < 4:
                continue

            prompt_category = parts[0]
            if category and prompt_category != category:
                continue
            if len(parts) >= 3 and parts[1] == "name-styles":
                continue

            prompt_language = parts[1]
            prompt_mode = parts[2]
            prompt_id = f"{prompt_category}/{prompt_language}/{prompt_mode}"

            if prompt_id in seen_ids:
                continue
            seen_ids.add(prompt_id)

            content = await read_text_or_none(md_path)
            if content is None:
                continue
            parsed = parse_frontmatter(content)
            version = str(parsed.metadata.get("prompt_version", "0.0.0"))

            has_override = self._project_override_path(
                prompt_category,
                prompt_language,
                prompt_mode,
            ).exists()

            results.append(
                PromptInfo(
                    prompt_id=prompt_id,
                    name=f"{prompt_category}/{prompt_mode} ({prompt_language})",
                    category=prompt_category,
                    language=prompt_language,
                    mode=prompt_mode,
                    source="bundled",
                    has_override=has_override,
                    prompt_version=version,
                    is_overridden=has_override,
                ),
            )

        return results

    async def get_prompt(self, prompt_id: str) -> PromptDetail | None:
        """Get a prompt's resolved content with cascade info."""
        parts = prompt_id.split("/")
        if len(parts) != 3:
            return None
        category, language, mode = parts

        bundled_path = self._registry.bundled_root / category / language / mode / _SYSTEM_FILE
        base_content = await read_text_or_none(bundled_path)
        if base_content is None:
            return None

        override_content = await read_text_or_none(
            self._project_override_path(category, language, mode),
        )
        is_overridden = override_content is not None
        active_content = override_content if is_overridden else base_content

        parsed = parse_frontmatter(active_content)
        variables = [v.name for v in extract_variables(parsed.content)]

        return PromptDetail(
            prompt_id=prompt_id,
            content=active_content,
            base_content=base_content,
            source="project" if is_overridden else "bundled",
            is_overridden=is_overridden,
            variables=variables,
            metadata=parsed.metadata,
        )

    async def save_override(self, prompt_id: str, content: str) -> None:
        """Save a project-level prompt override.

        Injects ``override_of_version`` into frontmatter matching
        the current bundled prompt version.
        """
        parts = prompt_id.split("/")
        if len(parts) != 3:
            raise ValueError(f"Invalid prompt_id format: {prompt_id}")
        category, language, mode = parts

        bundled_version = await get_bundled_version(
            self._registry.bundled_root,
            category,
            language,
            mode,
        )
        content_with_version = inject_override_version(content, bundled_version)

        path = self._project_override_path(category, language, mode)
        await write_text(path, content_with_version, create_parents=True)
        logger.info(
            "prompt_override_saved",
            prompt_id=prompt_id,
            override_of_version=bundled_version,
        )

    async def reset_override(self, prompt_id: str) -> bool:
        """Delete a project-level override, restoring bundled default.

        Returns True if an override was deleted, False if none existed.
        """
        parts = prompt_id.split("/")
        if len(parts) != 3:
            return False
        category, language, mode = parts

        path = self._project_override_path(category, language, mode)
        deleted = await delete_file(path, missing_ok=True)
        if deleted:
            logger.info("prompt_override_reset", prompt_id=prompt_id)
        return deleted

    async def cascade_info(self, prompt_id: str) -> list[CascadePath]:
        """Return all cascade paths for a prompt with existence status."""
        parts = prompt_id.split("/")
        if len(parts) != 3:
            return []
        category, language, mode = parts

        mode_path = Path(category) / language / mode / _SYSTEM_FILE
        en_mode_path = Path(category) / "en" / mode / _SYSTEM_FILE
        entries: list[CascadePath] = []

        if self._registry.project_root is not None:
            p = self._registry.project_root / ".narrare" / "prompts" / mode_path
            entries.append(CascadePath(level="project", path=p, exists=p.exists()))

        user_path = self._registry.user_config_dir / "prompts" / mode_path
        entries.append(CascadePath(level="user", path=user_path, exists=user_path.exists()))

        bundled_path = self._registry.bundled_root / mode_path
        entries.append(
            CascadePath(level="bundled", path=bundled_path, exists=bundled_path.exists()),
        )

        if language != "en":
            bundled_en = self._registry.bundled_root / en_mode_path
            entries.append(
                CascadePath(level="bundled_en", path=bundled_en, exists=bundled_en.exists()),
            )

        return entries

    async def detect_updates(self) -> list[UpdateInfo]:
        """Find overrides where the bundled version has changed."""
        project_root = self._registry.project_root
        if project_root is None:
            return []
        return await detect_override_updates(project_root, self._registry.bundled_root)

    async def get_diff(self, prompt_id: str) -> tuple[str, str] | None:
        """Return (override_content, bundled_content) for diff comparison."""
        parts = prompt_id.split("/")
        if len(parts) != 3:
            return None
        category, language, mode = parts

        override_path = self._project_override_path(category, language, mode)
        return await read_override_and_bundled(
            override_path,
            self._registry.bundled_root,
            category,
            language,
            mode,
        )

    def _project_override_path(self, category: str, language: str, mode: str) -> Path:
        """Build the project-level override file path."""
        if self._registry.project_root is None:
            return Path.home() / ".narrare" / "prompts" / category / language / mode / _SYSTEM_FILE
        return (
            self._registry.project_root
            / ".narrare"
            / "prompts"
            / category
            / language
            / mode
            / _SYSTEM_FILE
        )
