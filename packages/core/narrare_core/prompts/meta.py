"""
Meta-prompt loader.

The meta-prompt is a global persona/system prompt prepended to all
feature-specific prompts. It defines the AI's overall writing philosophy
and character. One implementation used by all features.

.. deprecated:: CR-AUFG-02-07
    ``MetaPromptLoader`` is the **pre-ADR-026** mechanism for loading
    meta-prompt content. ADR-026 Phase 3 replaced it with the
    ``NarrareMeta`` Capability (auto-injected by every ``NarrareAgent``).
    ADR-046 removed the last production caller (``_get_fallback_meta``
    in ``writing_graph_prompts.py``). The class is retained solely for
    test-only usage and will be removed in a future release.

Cascade:
1. {project}/.narrare/prompts/meta/{language}/system.md
2. ~/.config/narrare/prompts/meta/{language}/system.md
3. Bundled: narrare_core/prompts/_bundled/meta/{language}/system.md
4. Bundled English fallback
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path
from warnings import deprecated

import structlog

from narrare_core.prompts.variable_engine import substitute
from narrare_core.shared.file_utils import read_text_or_none
from narrare_core.shared.frontmatter import strip_frontmatter

logger = structlog.get_logger(__name__)


@deprecated(
    "MetaPromptLoader is deprecated per ADR-046 (CR-AUFG-02-07). "
    "Use the NarrareMeta Capability instead. "
    "Removal target: post-ADR-046 full rollout."
)
class MetaPromptLoader:
    """Loads and caches the meta-prompt for a given language."""

    def __init__(
        self,
        project_root: Path | None = None,
        user_config_dir: Path | None = None,
        *,
        lite_threshold: int = 2000,
    ) -> None:
        self._project_root = project_root
        self._user_config_dir = user_config_dir or Path.home() / ".config" / "narrare"
        self._bundled_root = self._find_bundled_root()
        self._lite_threshold = lite_threshold
        self._cache: dict[str, str] = {}

    def _find_bundled_root(self) -> Path:
        try:
            ref = importlib.resources.files("narrare_core") / "prompts" / "_bundled"
            return Path(str(ref))
        except Exception:
            return Path(__file__).parent / "_bundled"

    async def load(
        self,
        language: str = "en",
        *,
        variables: dict[str, str] | None = None,
        use_lite: bool = False,
    ) -> str:
        """
        Load the meta-prompt for a given language.

        Args:
            language: ISO 639-1 language code.
            variables: Variables to substitute into the meta-prompt
                       (project_title, genre, tone, language).
            use_lite: Load the shorter lite variant (for tight token budgets).

        Returns:
            Meta-prompt text with variables substituted.
            Empty string if no meta-prompt exists.
        """
        filename = "system.lite.md" if use_lite else "system.md"
        cache_key = f"{language}/{filename}"

        if cache_key not in self._cache:
            content = await self._resolve(language, filename)
            self._cache[cache_key] = content

        content = self._cache[cache_key]
        if not content:
            return ""

        if variables:
            content = substitute(content, variables, strict=False)

        return content

    async def _resolve(self, language: str, filename: str) -> str:
        """Find the meta-prompt file via cascade."""
        search_paths: list[Path] = []

        if self._project_root:
            search_paths.append(
                self._project_root / ".narrare" / "prompts" / "meta" / language / filename
            )

        search_paths.append(self._user_config_dir / "prompts" / "meta" / language / filename)
        search_paths.append(self._bundled_root / "meta" / language / filename)

        if language != "en":
            search_paths.append(self._bundled_root / "meta" / "en" / filename)

        for path in search_paths:
            content = await read_text_or_none(path)
            if content is not None:
                logger.debug("meta_prompt_resolved", language=language, path=str(path))
                return strip_frontmatter(content)

        logger.debug("meta_prompt_not_found", language=language)
        return ""

    def should_use_lite(self, remaining_budget: int) -> bool:
        """Determine if the lite meta-prompt variant should be used."""
        return remaining_budget < self._lite_threshold

    def invalidate_cache(self) -> None:
        """Clear the cache (e.g. after a meta-prompt file is updated)."""
        self._cache.clear()
