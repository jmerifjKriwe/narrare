"""Merge prepared invocation dynamic inputs into PromptContext.

ADR-045 makes ``InvocationPipeline.prepare()`` functionally relevant: dynamic
inputs produced by enrichers must reach the ``PromptContext`` consumed by
``PromptComposer`` unless a declared manual-injection exception applies.
"""

from __future__ import annotations

from collections.abc import Sized
from dataclasses import fields, replace
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from narrare_core.ai_invocation.models import PromptInvocationContext
    from narrare_core.prompts.context import PromptContext


class PromptContextMergeStatus(StrEnum):
    """Outcome for one dynamic input key."""

    MERGED = "merged"
    ALREADY_PROVIDED = "already_provided"
    CONFLICT = "conflict"


class PromptContextMergeEntry(BaseModel):
    """Privacy-safe merge evidence for a single dynamic input."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(min_length=1)
    target: str = Field(min_length=1)
    status: PromptContextMergeStatus
    existing_precedence: str | None = None
    incoming_precedence: str = "generated_suggestion"


class PromptContextMergeResult(BaseModel):
    """Result of merging prepared dynamic inputs into PromptContext."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    context: PromptContext
    entries: dict[str, PromptContextMergeEntry]


def merge_prepared_dynamic_inputs(
    prompt_context: PromptContext,
    prepared_context: PromptInvocationContext,
) -> PromptContextMergeResult:
    """Merge prepared dynamic inputs into a copy of ``prompt_context``.

    Empty dataclass fields are filled. Existing non-empty dataclass fields and
    existing ``extra`` keys are preserved because caller-provided/assembler
    values have higher RULE-22 precedence than generated/enricher suggestions.
    Feature-specific keys are merged into ``PromptContext.extra``.
    """
    dataclass_field_names = {field.name for field in fields(prompt_context)} - {"extra"}
    updates: dict[str, Any] = {}
    extra_updates: dict[str, Any] = dict(prompt_context.extra)
    entries: dict[str, PromptContextMergeEntry] = {}

    for key, value in prepared_context.dynamic_inputs.items():
        if key in dataclass_field_names:
            existing = getattr(prompt_context, key)
            if _is_empty(existing):
                updates[key] = value
                entries[key] = PromptContextMergeEntry(
                    key=key,
                    target=f"field:{key}",
                    status=PromptContextMergeStatus.MERGED,
                )
            else:
                entries[key] = PromptContextMergeEntry(
                    key=key,
                    target=f"field:{key}",
                    status=PromptContextMergeStatus.ALREADY_PROVIDED,
                    existing_precedence="caller_prompt_context",
                )
            continue

        if key not in extra_updates or _is_empty(extra_updates[key]):
            extra_updates[key] = value
            entries[key] = PromptContextMergeEntry(
                key=key,
                target=f"extra:{key}",
                status=PromptContextMergeStatus.MERGED,
            )
        else:
            entries[key] = PromptContextMergeEntry(
                key=key,
                target=f"extra:{key}",
                status=PromptContextMergeStatus.ALREADY_PROVIDED,
                existing_precedence="caller_prompt_context",
            )

    updates["extra"] = extra_updates
    merged_context = replace(prompt_context, **updates)
    return PromptContextMergeResult(context=merged_context, entries=entries)


def _is_empty(value: object) -> bool:
    """Return whether a PromptContext value can be filled by enrichment."""
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    if isinstance(value, Sized):
        return len(value) == 0
    return False


def _rebuild_forward_refs() -> None:
    """Resolve Pydantic forward refs for PromptContextMergeResult."""
    from narrare_core.prompts.context import PromptContext

    PromptContextMergeResult.model_rebuild(
        _types_namespace={"PromptContext": PromptContext},
    )


_rebuild_forward_refs()
