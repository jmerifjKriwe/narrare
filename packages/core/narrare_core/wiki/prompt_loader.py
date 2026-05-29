"""Prompt loading utilities for WikiGenerationAgent.

Handles reading bundled prompts from the package, parsing frontmatter,
processing Jinja2-style conditionals, building variable substitution
dicts, and rendering final prompt text.
"""

from __future__ import annotations

import importlib.resources
import re
from pathlib import Path
from typing import TYPE_CHECKING

from narrare_core.prompts.variable_engine import substitute
from narrare_core.shared.frontmatter import parse_frontmatter

if TYPE_CHECKING:
    from narrare_core.wiki.types import WikiGenerationDeps

# Regex for Jinja2-style conditionals
# Matches {% if condition %}content{% endif %} blocks across multiple lines.
_JINJA_IF_RE = re.compile(r"{%\s*if\s+(.+?)\s*%}(.*?){%\s*endif\s*%}", re.DOTALL)


class WikiPromptLoader:
    """Utility class for loading and rendering bundled wiki prompts.

    Provides static methods for reading prompt files from the bundled
    prompts directory, processing Jinja2-style conditionals, building
    variable substitution dicts from WikiGenerationDeps, and rendering
    the final prompt text.

    Usage:
        raw = WikiPromptLoader.read_bundled_prompt("wiki", "en", "entity_summary")
        rendered = WikiPromptLoader.render_prompt(raw, deps)
    """

    @staticmethod
    def read_bundled_prompt(category: str, language: str, mode: str) -> str:
        """Read a prompt file from the bundled prompts directory.

        Falls back to English if the requested language is not available.

        Args:
            category: Prompt category directory (e.g., "wiki", "writing").
            language: ISO language code (e.g., "en", "de", "fr").
            mode: Prompt mode/subdirectory (e.g., "entity_summary", "chapter_summary").

        Returns:
            Raw prompt text read from the system.md file.

        Raises:
            FileNotFoundError: If neither the requested language nor English
                fallback can be found.
        """
        # Try requested language
        try:
            ref = (
                importlib.resources.files("narrare_core")
                / "prompts"
                / "_bundled"
                / category
                / language
                / mode
                / "system.md"
            )
            path = Path(str(ref))
            if path.exists():
                return path.read_text(encoding="utf-8")
        except ModuleNotFoundError, FileNotFoundError, OSError:
            pass

        # Fallback to English
        try:
            ref = (
                importlib.resources.files("narrare_core")
                / "prompts"
                / "_bundled"
                / category
                / "en"
                / mode
                / "system.md"
            )
            path = Path(str(ref))
            return path.read_text(encoding="utf-8")
        except (ModuleNotFoundError, FileNotFoundError, OSError) as exc:
            msg = (
                f"Bundled prompt not found: {category}/{language}/{mode} (EN fallback also failed)"
            )
            raise FileNotFoundError(msg) from exc

    @staticmethod
    def render_prompt(raw_prompt: str, deps: WikiGenerationDeps) -> str:
        """Parse frontmatter, process conditionals, and substitute variables.

        Uses the full body (after frontmatter stripping) as the prompt text.
        Variables like ``{{entity_type}}`` appear in the ``## Context`` and
        ``## Instructions`` sections, not just ``## System Prompt``.

        Args:
            raw_prompt: Raw prompt text with YAML frontmatter.
            deps: Generation dependencies providing context and variables.

        Returns:
            Rendered prompt text with conditionals processed and variables
            substituted.
        """
        # Strip frontmatter only — keep all sections
        parsed = parse_frontmatter(raw_prompt)
        body = parsed.content.strip()

        # Handle Jinja2-style conditionals in the full body
        body = WikiPromptLoader.process_jinja_conditionals(body, deps)

        # Build variables dict and substitute
        variables = WikiPromptLoader.build_variables(deps)
        return substitute(body, variables, strict=False)

    @staticmethod
    def process_jinja_conditionals(text: str, deps: WikiGenerationDeps) -> str:
        """Strip or keep Jinja2-style ``{% if ... %}`` blocks based on deps.

        Currently handles the ``{% if entity_type == "character" %}`` conditional
        used in entity_summary prompts. The block is kept when the condition
        matches and removed otherwise.

        Args:
            text: Prompt text containing ``{% if ... %}`` blocks.
            deps: Generation dependencies providing entity_type for evaluation.

        Returns:
            Text with conditionals resolved — matching blocks kept,
            non-matching blocks removed.
        """

        def _replacer(match: re.Match[str]) -> str:
            condition = match.group(1).strip()
            content = match.group(2)
            # Evaluate simple conditions: entity_type == "character"
            if condition.startswith("entity_type == "):
                expected = condition.split('"')[1] if '"' in condition else ""
                if deps.entity_type == expected:
                    return content
            return ""

        return _JINJA_IF_RE.sub(_replacer, text)

    @staticmethod
    def build_variables(deps: WikiGenerationDeps) -> dict[str, str]:
        """Build variable substitution dict from generation deps.

        Args:
            deps: Generation dependencies with entity context, language, etc.

        Returns:
            Dict mapping template variable names to their string values.
            ``chapter_title`` and ``entities_in_chapter`` are aliased from
            ``entity_name`` and ``relationships`` respectively for the
            chapter_summary prompt.
        """
        return {
            "entity_type": deps.entity_type,
            "entity_name": deps.entity_name,
            "entity_body": deps.entity_body,
            "entity_metadata": str(deps.entity_metadata),
            "relationships": str(deps.relationships),
            "chapter_context": "\n".join(deps.chapter_context),
            "language": deps.language,
            "genre": deps.genre,
            # Chapter-specific
            "chapter_title": deps.entity_name,
            "entities_in_chapter": str(deps.relationships),
        }
