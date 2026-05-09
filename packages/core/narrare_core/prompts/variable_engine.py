"""
Prompt variable substitution engine.

Replaces {{variable_name}} placeholders in prompt text with values
from a PromptContext. Validates that required variables are present.

Single implementation — replaces three competing implementations
from the previous codebase.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from narrare_core.shared.errors import PromptVariableError

_VARIABLE_RE = re.compile(r"\{\{(\w+)\}\}")


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


def substitute(
    template: str,
    variables: dict[str, str],
    *,
    strict: bool = True,
) -> str:
    """
    Replace {{variable}} placeholders with values from the variables dict.

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
