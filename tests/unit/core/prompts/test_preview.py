"""Tests for provider-free prompt preview contracts and service."""

from __future__ import annotations

from dataclasses import fields
from typing import Any, cast

import pytest

from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.contracts import ContextSnapshot, PromptPreviewProtocol
from narrare_core.prompts.preview import PromptPreviewService
from narrare_core.prompts.preview_types import (
    PreviewDiagnosticKind,
    PromptPreview,
    PromptVariableMetadata,
)
from narrare_core.prompts.registry import ResolvedPrompt


def _make_resolved(
    system: str,
    first: str | None = "First message.",
    source: str = "bundled",
) -> ResolvedPrompt:
    return ResolvedPrompt(
        system_prompt=system,
        first_message=first,
        source=source,
        category="writing",
        language="en",
        mode="new_chapter",
        metadata={},
    )


class FakePromptRegistry:
    """Minimal fake for prompt preview tests."""

    def __init__(self, resolved: ResolvedPrompt) -> None:
        self._resolved = resolved
        self.calls: list[dict[str, str | None]] = []

    async def resolve(
        self,
        *,
        category: str,
        language: str,
        mode: str,
        genre: str | None = None,
        db_content: str | None = None,
    ) -> ResolvedPrompt:
        """Return the configured prompt and record cascade parameters."""
        self.calls.append(
            {
                "category": category,
                "language": language,
                "mode": mode,
                "genre": genre,
                "db_content": db_content,
            }
        )
        if db_content:
            return _make_resolved(db_content, source="db")
        return self._resolved


def test_prompt_preview_dataclass_shape() -> None:
    field_names = {field.name for field in fields(PromptPreview)}
    assert {
        "system_prompt",
        "user_prompt",
        "first_message",
        "cascade_source",
        "variables",
        "diagnostics",
    } <= field_names


def test_prompt_variable_metadata_includes_provenance_and_security() -> None:
    field_names = {field.name for field in fields(PromptVariableMetadata)}
    assert {
        "name",
        "description",
        "variable_type",
        "required",
        "provenance",
        "security",
    } <= field_names


def test_prompt_preview_protocol_methods() -> None:
    assert hasattr(PromptPreviewProtocol, "preview")
    assert fields(ContextSnapshot)


@pytest.fixture
def preview_service() -> PromptPreviewService:
    registry = FakePromptRegistry(
        _make_resolved(
            "Write {{writing_language}} prose for {{project_title}}. "
            "Instruction: <user_provided_text>{{author_instructions}}</user_provided_text>"
        )
    )
    composer = PromptComposer(cast("Any", registry))
    return PromptPreviewService(composer=composer, registry=cast("Any", registry))


async def test_preview_resolves_variables_without_provider(
    preview_service: PromptPreviewService,
) -> None:
    snapshot = ContextSnapshot(
        variables={
            "writing_language": "English",
            "project_title": "Demo",
            "author_instructions": "Keep it lyrical.",
        },
        language="en",
        mode="new_chapter",
    )

    result = await preview_service.preview(
        prompt_id="writing/en/new_chapter",
        snapshot=snapshot,
    )

    assert result.system_prompt == (
        "Write English prose for Demo. "
        "Instruction: <user_provided_text>Keep it lyrical.</user_provided_text>"
    )
    assert result.user_prompt == "First message."
    assert result.cascade_source == "bundled"
    by_name = {variable.name: variable for variable in result.variables}
    assert by_name["project_title"].provenance == "system_generated"
    assert by_name["author_instructions"].security == "xml_required"
    assert result.diagnostics == []


async def test_preview_surfaces_missing_variable_diagnostic() -> None:
    registry = FakePromptRegistry(
        _make_resolved("Outline: {{chapter_outline}} for {{project_title}}")
    )
    composer = PromptComposer(cast("Any", registry))
    service = PromptPreviewService(composer=composer, registry=cast("Any", registry))

    result = await service.preview(
        prompt_id="writing/en/new_chapter",
        snapshot=ContextSnapshot(variables={"project_title": "Demo"}, language="en"),
    )

    assert result.system_prompt == ""
    assert result.diagnostics
    assert result.diagnostics[0].kind == PreviewDiagnosticKind.MISSING_VARIABLE
    assert result.diagnostics[0].variable_name == "chapter_outline"


async def test_preview_uses_edited_override_as_db_cascade_source() -> None:
    registry = FakePromptRegistry(_make_resolved("Bundled {{project_title}}"))
    composer = PromptComposer(cast("Any", registry))
    service = PromptPreviewService(composer=composer, registry=cast("Any", registry))

    result = await service.preview(
        prompt_id="writing/en/new_chapter",
        snapshot=ContextSnapshot(variables={"project_title": "Demo"}, language="en"),
        edited_override="Override {{project_title}}",
    )

    assert result.system_prompt == "Override Demo"
    assert result.cascade_source == "db"
