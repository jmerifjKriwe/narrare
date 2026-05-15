"""Override detection and diff utilities for prompt management.

Extracted from management.py per RULE-04 (modularize, don't compress).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from narrare_core.prompts._management_types import UpdateInfo

if TYPE_CHECKING:
    from pathlib import Path
from narrare_core.shared.file_utils import find_files, read_text_or_none
from narrare_core.shared.frontmatter import parse_frontmatter

_SYSTEM_FILE = "system.md"


async def detect_override_updates(
    project_root: Path,
    bundled_root: Path,
) -> list[UpdateInfo]:
    """Find project overrides where the bundled version has changed.

    Scans all project-level override files, parses their
    ``override_of_version`` frontmatter field, and compares it
    with the current bundled prompt's ``prompt_version``.
    """
    prompts_dir = project_root / ".narrare" / "prompts"
    if not prompts_dir.exists():
        return []

    results: list[UpdateInfo] = []

    for md_path in find_files(prompts_dir, "*.md"):
        rel = md_path.relative_to(prompts_dir)
        parts = rel.parts

        if parts[-1] != _SYSTEM_FILE:
            continue
        if len(parts) < 4:
            continue

        category = parts[0]
        # Skip culture directories
        if len(parts) >= 3 and parts[1] == "cultures":
            continue
        language = parts[1]
        mode = parts[2]
        prompt_id = f"{category}/{language}/{mode}"

        override_content = await read_text_or_none(md_path)
        if override_content is None:
            continue
        parsed = parse_frontmatter(override_content)
        override_version = str(
            parsed.metadata.get("override_of_version", "unknown"),
        )

        bundled_version = await get_bundled_version(
            bundled_root,
            category,
            language,
            mode,
        )

        if override_version != bundled_version:
            results.append(
                UpdateInfo(
                    prompt_id=prompt_id,
                    override_version=override_version,
                    current_bundled_version=bundled_version,
                ),
            )

    return results


async def get_bundled_version(
    bundled_root: Path,
    category: str,
    language: str,
    mode: str,
) -> str:
    """Extract prompt_version from bundled prompt frontmatter."""
    bundled_path = bundled_root / category / language / mode / _SYSTEM_FILE
    content = await read_text_or_none(bundled_path)
    if content is None:
        return "0.0.0"
    parsed = parse_frontmatter(content)
    return str(parsed.metadata.get("prompt_version", "0.0.0"))


async def read_override_and_bundled(
    override_path: Path,
    bundled_root: Path,
    category: str,
    language: str,
    mode: str,
) -> tuple[str, str] | None:
    """Read both override and bundled content for diff comparison.

    Returns None if the override file does not exist.
    """
    override_content = await read_text_or_none(override_path)
    if override_content is None:
        return None

    bundled_path = bundled_root / category / language / mode / _SYSTEM_FILE
    bundled_content = await read_text_or_none(bundled_path)

    return (override_content, bundled_content or "")


def inject_override_version(content: str, bundled_version: str) -> str:
    """Add or update override_of_version in frontmatter.

    If content already has frontmatter, inject the field.
    If not, wrap content in frontmatter.
    """
    parsed = parse_frontmatter(content)

    if parsed.has_frontmatter:
        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if fm_match:
            raw_yaml = fm_match.group(1)
            if "override_of_version" not in raw_yaml:
                raw_yaml += f'\noverride_of_version: "{bundled_version}"'
            return f"---\n{raw_yaml}\n---\n\n{parsed.content}"
        return content

    return f'---\noverride_of_version: "{bundled_version}"\n---\n\n{content}'
