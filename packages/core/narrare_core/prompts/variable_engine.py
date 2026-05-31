"""
Prompt variable substitution engine.

Replaces {{variable_name}} placeholders in prompt text with values
from a PromptContext. Validates that required variables are present.

Single implementation — replaces three competing implementations
from the previous codebase.

Security: User-authored content variables are wrapped in XML tags
directly in the prompt templates (e.g., ``<user_provided_text>``).
The meta-prompt instructs the LLM to never follow instructions
within those tags. This template-level approach is the primary
defense; ``wrap_user_content()`` remains available as a programmatic
utility but is no longer called automatically during substitution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from narrare_core.shared.errors import PromptVariableError

_VARIABLE_RE = re.compile(r"\{\{(\w+)\}\}")

# User-authored content variables that require XML encapsulation
# in prompt templates for prompt injection defense.
#
# These variables contain text written by the end user (chapter prose,
# interview answers, instructions, etc.) and MUST be wrapped in XML
# tags in the template files:
#   - <user_provided_text> for prose/content (existing_content, chapter_text, etc.)
#   - <user_provided_data> for structured data (existing_answers)
#   - <user_instructions> for author instructions
#   - <conversation_history> for conversation logs
#
# System-generated variables (kb_characters, recent_chapters, etc.)
# are intentionally excluded — they are assembled by the backend,
# not authored by the user, and are not an injection vector.
_USER_CONTENT_VARS: frozenset[str] = frozenset(
    {
        # Prose / text content
        "existing_content",
        "chapter_text",
        "chapter_texts",
        "entry_content",
        "selection_text",
        "context_before",
        "context_after",
        "text_before",
        "text_after",
        # Structured data
        "existing_answers",
        # Author instructions
        "author_instructions",
        # Conversation history
        "conversation_history",
    }
)

# System-generated variables that are NOT user content and should
# NOT be wrapped. Listed here for clarity — these are assembled by
# the backend from the KB, project config, or other system sources.
_SYSTEM_VARS: frozenset[str] = frozenset(
    {
        "recent_chapters",
        "chapter_content",
        "chapter_outline",
        "chapter_context",
        "kb_characters",
        "kb_locations",
        "kb_factions",
        "kb_systems",
        "kb_timelines",
        "kb_objects",
        "kb_concepts",
        "kb_settings",
        "kb_relationships",
        "kb_entities",
        "existing_names",
        "existing_relationships",
        "existing_entity_names",
        "user_preferences",
        "avoidance_patterns",
        "style_constraints",
        "character_voice_profiles",
        "feedback_text",
        "template_structure",
        "world_context",
        "entity_type",
        "target_field",
        "target_field_description",
        "project_title",
        "genre",
        "language",
        "tone",
        "tone_instructions",
        "story_structure",
        "author_name",
        "culture_guidelines",
        "word_target",
        "word_count",
        "extend_length",
        "chapter_title",
        "chapter_titles",
        "count",
        "focus_categories",
        "check_types",
        "co_author_focus_instructions",
        "rewrite_mode_instructions",
        "deepdive_category",
        "phase1_strengths_summary",
        "phase1_feedback_summary",
        "category_focus_instructions",
        "mode",
    }
)


@dataclass(frozen=True, slots=True)
class VariableInfo:
    """Metadata about a variable found in a prompt template."""

    name: str
    required: bool = True


def extract_variables(template: str) -> list[VariableInfo]:
    """
    Find all {{variable}} placeholders in a template string.

    Args:
        template: Prompt template text.

    Returns:
        List of VariableInfo for each unique variable found.
    """
    names = dict.fromkeys(_VARIABLE_RE.findall(template))
    return [VariableInfo(name=name) for name in names]


def wrap_user_content(name: str, value: str) -> str:
    """Wrap user-provided content in XML tags for prompt injection defense.

    .. deprecated::
        XML wrapping is now handled in prompt templates via explicit
        ``<user_provided_text>``, ``<user_provided_data>`, etc. tags.
        This function is retained as a programmatic utility for ad-hoc
        use but is no longer called automatically by :func:`substitute`.

    Variables listed in ``_USER_CONTENT_VARS`` are wrapped in
    ``<user_content type="...">...</user_content>`` tags so that LLMs
    can distinguish user data from system instructions.  Other variables
    pass through unchanged.

    Args:
        name: The variable name (e.g., ``"author_instructions"``).
        value: The resolved value.

    Returns:
        The value, wrapped in XML tags if it is user-provided content.
    """
    if name not in _USER_CONTENT_VARS:
        return value
    if not value.strip():
        return value  # Don't wrap empty values
    return f'<user_content type="{name}">\n{value}\n</user_content>'


def substitute(
    template: str,
    variables: dict[str, str],
    *,
    strict: bool = True,
) -> str:
    """
    Replace {{variable}} placeholders with values from the variables dict.

    Security note: User-content variables are wrapped in XML tags in the
    prompt templates themselves (e.g., ``<user_provided_text>``).  The
    meta-prompt instructs the LLM to treat tagged content as data.
    Values are substituted as-is — no automatic XML wrapping is applied.

    Args:
        template: Prompt template text with {{variable}} placeholders.
        variables: Dict of variable name → value.
        strict: If True, raise PromptVariableError for missing variables.
                If False, leave missing placeholders unchanged.

    Returns:
        Template with all found variables substituted.

    Raises:
        PromptVariableError: If strict=True and a variable is missing.
    """

    def replacer(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in variables:
            return variables[name]
        if strict:
            raise PromptVariableError(name)
        return match.group(0)  # Leave {{name}} unchanged

    return _VARIABLE_RE.sub(replacer, template)


def validate_variables(
    template: str,
    variables: dict[str, str],
) -> list[str]:
    """
    Check which required variables are missing from the variables dict.

    Args:
        template: Prompt template text.
        variables: Available variables.

    Returns:
        List of missing variable names. Empty list if all present.
    """
    required = {info.name for info in extract_variables(template)}
    provided = set(variables.keys())
    return sorted(required - provided)
