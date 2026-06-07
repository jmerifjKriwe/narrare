"""Prompt system — the only place prompts are assembled. See CONSTRAINTS.md RULE-02."""

from narrare_core.prompts._management_types import (
    CascadePath,
    PromptDetail,
    PromptInfo,
    UpdateInfo,
)
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.prompts.context import KBContextEntry, PromptContext, validate_world_context
from narrare_core.prompts.management import PromptManagementService
from narrare_core.prompts.meta import MetaPromptLoader
from narrare_core.prompts.registry import PromptRegistry, ResolvedPrompt
from narrare_core.prompts.variable_engine import (
    extract_variables,
    substitute,
    validate_variables,
)
from narrare_core.prompts.variable_metadata import (
    VARIABLE_REGISTRY,
    VariableMeta,
    get_variable_info,
    get_variables_for_names,
)

__all__ = [
    "VARIABLE_REGISTRY",
    "CascadePath",
    "ComposedPrompt",
    "KBContextEntry",
    "MetaPromptLoader",
    "PromptComposer",
    "PromptContext",
    "PromptDetail",
    "PromptInfo",
    "PromptManagementService",
    "PromptRegistry",
    "ResolvedPrompt",
    "UpdateInfo",
    "VariableMeta",
    "extract_variables",
    "get_variable_info",
    "get_variables_for_names",
    "substitute",
    "validate_variables",
    "validate_world_context",
]
