"""
Prompt Registry — the single cascade resolver for all prompt files.

Replaces three competing implementations from the previous codebase
(PromptManagementService, KBPromptResolver, WritingPromptResolver).

Cascade order (highest to lowest priority):
1. DB template (user-saved override) — checked by caller via UserPromptTemplateService
2. Project-level file: {project_root}/.narrare/prompts/{category}/{language}/{mode}/system.md
3. User-global file:   ~/.config/narrare/prompts/{category}/{language}/{mode}/system.md
4. Bundled default:    narrare_core/prompts/_bundled/{category}/{language}/{mode}/system.md
5. Bundled fallback:   narrare_core/prompts/_bundled/{category}/en/{mode}/system.md

See: ADR-002 (unified prompt system)
See: CONSTRAINTS.md RULE-02
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path

import structlog

from narrare_core.shared.errors import PromptNotFoundError
from narrare_core.shared.file_utils import read_text_or_none
from narrare_core.shared.frontmatter import extract_section, parse_frontmatter

logger = structlog.get_logger(__name__)

# Standard prompt file names within a mode directory
_SYSTEM_FILE = "system.md"
_SYSTEM_GENRE_PATTERN = "system_{genre}.md"


class PromptRegistry:
    """
    Resolves prompt files via the standard cascade.

    One instance is shared across the application (singleton via DI).
    """

    def __init__(
        self,
        project_root: Path | None = None,
        user_config_dir: Path | None = None,
    ) -> None:
        self._project_root = project_root
        self._user_config_dir = user_config_dir or Path.home() / ".config" / "narrare"
        self._bundled_root = self._find_bundled_root()

    def _find_bundled_root(self) -> Path:
        """Locate the bundled prompts directory."""
        try:
            ref = importlib.resources.files("narrare_core") / "prompts" / "_bundled"
            return Path(str(ref))
        except Exception:
            # Fallback for development (running from source)
            here = Path(__file__).parent
            return here / "_bundled"

    async def resolve(
        self,
        *,
        category: str,
        language: str,
        mode: str,
        genre: str | None = None,
        db_content: str | None = None,
    ) -> ResolvedPrompt:
        """
        Resolve a prompt file for the given parameters via cascade.

        Args:
            category: Prompt category (writing, kb, analysis).
            language: ISO 639-1 language code (en, de, fr).
            mode: Prompt mode/action (new_chapter, character, etc.).
            genre: Optional genre for genre-specific prompts.
            db_content: Pre-fetched DB template content (highest priority).

        Returns:
            ResolvedPrompt with system prompt and optional first message.

        Raises:
            PromptNotFoundError: If no prompt found in any cascade level.
        """
        # Level 1: DB template (passed in from service layer)
        if db_content:
            return self._parse_prompt(
                db_content,
                source="db",
                category=category,
                language=language,
                mode=mode,
            )

        # Build search paths in priority order
        search_paths = self._build_search_paths(
            category=category,
            language=language,
            mode=mode,
            genre=genre,
        )

        for path, source in search_paths:
            content = await read_text_or_none(path)
            if content is not None:
                logger.debug(
                    "prompt_resolved",
                    category=category,
                    language=language,
                    mode=mode,
                    source=source,
                    path=str(path),
                )
                return self._parse_prompt(
                    content,
                    source=source,
                    category=category,
                    language=language,
                    mode=mode,
                )

        raise PromptNotFoundError(category, language, mode)

    def _build_search_paths(
        self,
        *,
        category: str,
        language: str,
        mode: str,
        genre: str | None,
    ) -> list[tuple[Path, str]]:
        """Build ordered list of (path, source_label) to search."""
        paths: list[tuple[Path, str]] = []

        mode_path = Path(category) / language / mode

        # Project-level override
        if self._project_root:
            base = self._project_root / ".narrare" / "prompts"
            if genre:
                paths.append((base / mode_path / f"system_{genre}.md", "project_genre"))
            paths.append((base / mode_path / _SYSTEM_FILE, "project"))

        # User-global override
        base = self._user_config_dir / "prompts"
        if genre:
            paths.append((base / mode_path / f"system_{genre}.md", "user_genre"))
        paths.append((base / mode_path / _SYSTEM_FILE, "user"))

        # Bundled defaults
        base = self._bundled_root
        if genre:
            paths.append((base / mode_path / f"system_{genre}.md", "bundled_genre"))
        paths.append((base / mode_path / _SYSTEM_FILE, "bundled"))

        # Bundled fallback to English
        if language != "en":
            en_path = Path(category) / "en" / mode
            if genre:
                paths.append((base / en_path / f"system_{genre}.md", "bundled_en_genre"))
            paths.append((base / en_path / _SYSTEM_FILE, "bundled_en"))

        return paths

    def _parse_prompt(
        self,
        content: str,
        *,
        source: str,
        category: str,
        language: str,
        mode: str,
    ) -> ResolvedPrompt:
        """Parse a prompt file into its components."""
        parsed = parse_frontmatter(content)
        body = parsed.content

        system = extract_section(body, "System Prompt") or body.strip()
        first_message = extract_section(body, "First Message")

        return ResolvedPrompt(
            system_prompt=system,
            first_message=first_message,
            source=source,
            category=category,
            language=language,
            mode=mode,
            metadata=parsed.metadata,
        )


class ResolvedPrompt:
    """A resolved and parsed prompt ready for variable substitution."""

    __slots__ = (
        "category",
        "first_message",
        "language",
        "metadata",
        "mode",
        "source",
        "system_prompt",
    )

    def __init__(
        self,
        system_prompt: str,
        first_message: str | None,
        source: str,
        category: str,
        language: str,
        mode: str,
        metadata: dict[str, object],
    ) -> None:
        self.system_prompt = system_prompt
        self.first_message = first_message
        self.source = source
        self.category = category
        self.language = language
        self.mode = mode
        self.metadata = metadata
