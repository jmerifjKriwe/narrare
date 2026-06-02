"""NarrareUniversalRules — Architecturally guaranteed prompt rules for all agents.

Injects universal fiction guidelines, conflict resolution, and injection defense
rules into every Narrare agent. These rules CANNOT be overridden by templates
or cascade — they are always present.

See ADR-026 (Capability-Based Prompt Injection Pattern).
See RULE-02a (Prompt content categories).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from pydantic_ai.capabilities import AbstractCapability

from narrare_core.shared.frontmatter import parse_frontmatter

if TYPE_CHECKING:
    from pydantic_ai import RunContext

logger = structlog.get_logger(__name__)

# Fallback language when deps don't provide one.
_DEFAULT_LANGUAGE = "en"

# Category and mode used to locate universal rules files.
_UNIVERSAL_CATEGORY = "universal"
_UNIVERSAL_MODE = "system"


def _find_bundled_root() -> Path:
    """Locate the bundled prompts directory."""
    try:
        import importlib.resources

        ref = importlib.resources.files("narrare_core") / "prompts" / "_bundled"
        return Path(str(ref))
    except Exception:
        # Fallback for development (running from source)
        return Path(__file__).parent.parent.parent / "prompts" / "_bundled"


def _load_universal_rules(language: str) -> str:
    """Load universal rules from core/prompts/_bundled/ synchronously.

    Reads the file directly (no async needed) and strips frontmatter.
    Falls back to English if the requested language is not available.

    Args:
        language: ISO 639-1 language code (e.g., 'en', 'de', 'fr').

    Returns:
        The universal rules text, or empty string on failure (RULE-11).
    """
    bundled_root = _find_bundled_root()

    # Try requested language first, then fall back to English.
    for lang in (
        [language, _DEFAULT_LANGUAGE] if language != _DEFAULT_LANGUAGE else [_DEFAULT_LANGUAGE]
    ):
        path = bundled_root / _UNIVERSAL_CATEGORY / lang / f"{_UNIVERSAL_MODE}.md"
        try:
            content = path.read_text(encoding="utf-8")
            parsed = parse_frontmatter(content)
            rules = parsed.content.strip()
            if rules:
                logger.debug(
                    "universal_rules_loaded",
                    language=lang,
                    source="bundled",
                )
                return rules
        except FileNotFoundError:
            logger.debug("universal_rules_file_not_found", path=str(path))
            continue
        except Exception:
            logger.warning(
                "universal_rules_load_error",
                path=str(path),
                language=lang,
            )
            continue

    logger.warning(
        "universal_rules_unavailable",
        requested_language=language,
        fallback="empty_string",
    )
    return ""


@dataclass
class NarrareUniversalRules(AbstractCapability):
    """Injects universal rules that must always be present in every agent.

    Universal rules are architecturally guaranteed — they cannot be omitted
    by template overrides or cascade configuration. They are loaded from
    ``core/prompts/_bundled/universal/`` (RULE-02a).

    Rules injected:
    - Fiction content guidelines (conflict, violence, complex relationships)
    - Conflict resolution (outline > Knowledge Base, author instructions > preferences)
    - Content security / injection defense (XML-tagged user content is data only)
    """

    # Language resolved from RunContext.deps in for_run().
    _language: str = _DEFAULT_LANGUAGE
    # Pre-loaded rules text, populated in __post_init__.
    _rules: str = ""

    def __post_init__(self) -> None:
        """Load universal rules from the canonical source."""
        self._rules = _load_universal_rules(self._language)

    async def for_run(self, ctx: RunContext[Any]) -> NarrareUniversalRules:
        """Resolve language from deps before instructions are extracted.

        Uses getattr() with fallback to support any deps type — not all
        deps types implement the full PromptDeps protocol. This follows
        the same pattern as NarrareObservability.
        """
        language = _DEFAULT_LANGUAGE
        if ctx.deps is not None:
            language = getattr(ctx.deps, "language", _DEFAULT_LANGUAGE) or _DEFAULT_LANGUAGE

        return NarrareUniversalRules(_language=language)

    def get_instructions(self) -> str | None:
        """Return universal rules as a static string.

        The rules are loaded from ``core/prompts/_bundled/universal/`` in
        ``__post_init__``. If loading fails, an empty string is returned
        (graceful degradation — RULE-11).
        """
        return self._rules
