"""Prompt loader utility — reads bundled prompt files via importlib.resources.

Extracted from ``timeline_consistency_service.py`` to keep service files
under the 300-line limit (RULE-04). Centralises the logic for reading
language-specific prompts from the ``narrare_core.prompts._bundled``
package with automatic fallback to English.
"""

from __future__ import annotations

from importlib import resources as impresources

import structlog

logger = structlog.get_logger(__name__)


def load_temporal_consistency_prompt(
    language: str,
    novel_title: str,
    genre: str,
    language_code: str,
) -> str:
    """Load the temporal consistency system prompt from bundled prompts.

    Reads the prompt file via ``importlib.resources`` and fills template
    variables with novel-specific context. The ``{{event_context}}``
    variable is left empty as it is provided as the user prompt to the
    agent at runtime.

    Args:
        language: Writing language code (e.g. "en", "de", "fr").
        novel_title: Title of the novel.
        genre: Genre of the novel.
        language_code: Same as language — for prompt template.

    Returns:
        The filled system prompt string, or empty string if the bundled
        prompt cannot be found.
    """
    try:
        prompt_path = (
            impresources.files("narrare_core.prompts._bundled.planning")
            / language
            / "temporal_consistency"
            / "system.md"
        )
        text = prompt_path.read_text(encoding="utf-8")
    except FileNotFoundError, ModuleNotFoundError, TypeError:
        # Fall back to English if the language-specific prompt is missing
        try:
            prompt_path = (
                impresources.files("narrare_core.prompts._bundled.planning")
                / "en"
                / "temporal_consistency"
                / "system.md"
            )
            text = prompt_path.read_text(encoding="utf-8")
        except FileNotFoundError, ModuleNotFoundError, TypeError:
            logger.warning(
                "bundled_prompt_not_found",
                language=language,
                exc_info=True,
            )
            return ""

    # Fill template variables
    text = text.replace("{{project_title}}", novel_title)
    text = text.replace("{{genre}}", genre)
    text = text.replace("{{language}}", language_code)
    text = text.replace("{{writing_language}}", language_code)
    text = text.replace("{{event_context}}", "")
    text = text.replace("{{user_preferences}}", "")
    text = text.replace("{{avoidance_patterns}}", "")

    return text
