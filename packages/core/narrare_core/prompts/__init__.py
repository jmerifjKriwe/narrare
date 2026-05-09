"""Prompt system — the only place prompts are assembled. See CONSTRAINTS.md RULE-02."""

from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.prompts.context import KBContextEntry, PromptContext
from narrare_core.prompts.meta import MetaPromptLoader
from narrare_core.prompts.registry import PromptRegistry, ResolvedPrompt
from narrare_core.prompts.variable_engine import (
    extract_variables,
    substitute,
    validate_variables,
)

__all__ = [
    "ComposedPrompt",
    "KBContextEntry",
    "MetaPromptLoader",
    "PromptComposer",
    "PromptContext",
    "PromptRegistry",
    "ResolvedPrompt",
    "extract_variables",
    "substitute",
    "validate_variables",
]
