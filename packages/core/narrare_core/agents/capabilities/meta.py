"""NarrareMeta — Capability for the Narrare meta-prompt identity.

The meta-prompt defines who Narrare is, their approach to creative writing,
role flexibility, and conversation guardrails. This is distinct from universal
rules (NarrareUniversalRules) which cover fiction guidelines, conflict
resolution, and content security.

Architecturally guaranteed: every NarrareAgent always has the meta-prompt.

See ADR-026 Phase 3 (Capability-Based Prompt Injection Pattern).
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

_DEFAULT_LANGUAGE = "en"


def _find_bundled_root() -> Path:
    """Locate the bundled prompts directory."""
    try:
        import importlib.resources

        ref = importlib.resources.files("narrare_core") / "prompts" / "_bundled"
        return Path(str(ref))
    except Exception:
        return Path(__file__).parent.parent.parent / "prompts" / "_bundled"


def _load_meta_prompt(language: str, variables: dict[str, str] | None = None) -> str:
    """Load the meta-prompt from bundled templates synchronously.

    Reads the bundled meta-prompt file for the given language, with
    English fallback. Does NOT support project/user cascade — custom
    meta-prompts are not supported via this path.

    Falls back to empty string on any error (graceful degradation).

    Args:
        language: ISO 639-1 language code (e.g., 'en', 'de', 'fr').
        variables: Optional variables to substitute into the prompt.

    Returns:
        The meta-prompt text, or empty string if unavailable.
    """
    bundled_root = _find_bundled_root()
    filename = "system.md"

    for lang in [language, "en"] if language != "en" else ["en"]:
        path = bundled_root / "meta" / lang / filename
        try:
            content = path.read_text(encoding="utf-8")
            parsed = parse_frontmatter(content)
            meta = parsed.content.strip()
            if meta:
                if variables:
                    from narrare_core.prompts.variable_engine import substitute

                    meta = substitute(meta, variables, strict=False)
                return meta
        except FileNotFoundError:
            continue
        except Exception:
            logger.exception("Unexpected error reading meta prompt path: %s", path)
            continue

    return ""


@dataclass
class NarrareMeta(AbstractCapability):
    """Injects the Narrare meta-prompt identity.

    The meta-prompt defines Narrare's persona: identity, approach to
    creative writing, role flexibility, and conversation guardrails.

    Loaded from ``core/prompts/_bundled/meta/`` with English fallback.
    Attached automatically by ``NarrareAgent.__init__``.

    Uses the same pattern as ``NarrareUniversalRules``: synchronous file
    loading in ``__post_init__``, language resolution from deps in
    ``for_run()``.
    """

    language: str = _DEFAULT_LANGUAGE
    variables: dict[str, str] | None = None
    _meta_prompt: str = ""

    def __post_init__(self) -> None:
        """Load meta-prompt from bundled templates."""
        self._meta_prompt = _load_meta_prompt(self.language, self.variables)

    async def for_run(self, ctx: RunContext[Any]) -> NarrareMeta:
        """Resolve language and variables from deps before instructions extraction.

        Uses getattr() with fallback to support any deps type — not all
        deps types implement the full PromptDeps protocol. This follows
        the same pattern as NarrareObservability and NarrareUniversalRules.
        """
        language = _DEFAULT_LANGUAGE
        variables = None

        if ctx.deps is not None:
            language = getattr(ctx.deps, "language", _DEFAULT_LANGUAGE) or _DEFAULT_LANGUAGE
            variables = _extract_variables(ctx.deps)

        return NarrareMeta(language=language, variables=variables)

    def get_instructions(self) -> str | None:
        """Return the meta-prompt as instructions.

        Returns None if the meta-prompt is empty (graceful degradation).
        """
        return self._meta_prompt or None


def _extract_variables(deps: Any) -> dict[str, str] | None:
    """Extract meta-prompt variables from Deps via getattr() with fallbacks.

    Follows the same pattern as NarrareObservability._extract_variables.
    """
    if deps is None:
        return None
    vars_map: dict[str, str] = {}
    for attr in (
        "author_name",
        "genre",
        "project_title",
        "tone",
        "story_structure",
        "writing_language",
        "avoidance_patterns",
        "language",
    ):
        val = getattr(deps, attr, None)
        if val is not None:
            vars_map[attr] = str(val)
    return vars_map or None
