"""Prompt system — the only place prompts are assembled. See CONSTRAINTS.md RULE-02."""

from narrare_core.prompts.composer import PromptComposer, ComposedPrompt
from narrare_core.prompts.context import PromptContext, KBContextEntry
from narrare_core.prompts.registry import PromptRegistry, ResolvedPrompt
from narrare_core.prompts.meta import MetaPromptLoader
from narrare_core.prompts.variable_engine import (
    substitute,
    extract_variables,
    validate_variables,
)

__all__ = [
    "PromptComposer",
    "ComposedPrompt",
    "PromptContext",
    "KBContextEntry",
    "PromptRegistry",
    "ResolvedPrompt",
    "MetaPromptLoader",
    "substitute",
    "extract_variables",
    "validate_variables",
]
