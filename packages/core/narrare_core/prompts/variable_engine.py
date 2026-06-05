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

from narrare_core.prompts.variable_registry import (
    FEATURE_DYNAMIC_VARS,
    SYSTEM_VARS,
    USER_CONTENT_VARS,
    is_registered_variable,
)
from narrare_core.shared.errors import PromptVariableError

_VARIABLE_RE = re.compile(r"\{\{(\w+)\}\}")

_USER_CONTENT_VARS = USER_CONTENT_VARS
_SYSTEM_VARS = SYSTEM_VARS
_FEATURE_DYNAMIC_VARS = FEATURE_DYNAMIC_VARS


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


def prepare_variables_for_template(
    template: str,
    variables: dict[str, str],
    *,
    optional_variables: frozenset[str] = frozenset(),
    prompt_id: str = "",
) -> dict[str, str]:
    """Validate template variables and add empty defaults for optional context.

    This is strict preflight for PromptComposer routes: every placeholder must be
    registered in the taxonomy, required placeholders must be present in the
    provided context, and optional placeholders are rendered as empty strings when
    absent. XML/label boundaries remain the template author's responsibility; this
    function never auto-wraps values.
    """
    prepared = dict(variables)
    for info in extract_variables(template):
        name = info.name
        if not is_registered_variable(name):
            raise PromptVariableError(name, prompt_id)
        if name in prepared:
            continue
        if name in optional_variables:
            prepared[name] = ""
            continue
        raise PromptVariableError(name, prompt_id)
    return prepared
