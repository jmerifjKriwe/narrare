"""PROMPT-003 backend preview service tests (CR-AUFG-07-16).

Tests the API-layer adapter that builds a :class:`ContextSnapshot` from the
request, delegates to the Core ``PromptPreviewProtocol``, and maps the Core
dataclass result to a Pydantic :class:`PreviewResponse`. The Core protocol
is faked — no LLM, no composer, no filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from narrare.prompts.preview_service import PromptPreviewApiService
from narrare.prompts.schemas import PreviewRequest
from narrare_core.prompts.preview_types import (
    PreviewDiagnostic,
    PreviewDiagnosticKind,
    PromptPreview,
    PromptVariableMetadata,
)
from narrare_core.prompts.variable_taxonomy import (
    VariableProvenance,
    VariableSecurity,
)

if TYPE_CHECKING:
    from narrare_core.prompts.contracts import ContextSnapshot


@dataclass
class FakeCorePreview:
    """Fake Core ``PromptPreviewProtocol`` — records calls, returns canned result."""

    system: str = "resolved system"
    user: str = "resolved user"
    first: str | None = None
    cascade_source: str = "bundled"
    variables: list[PromptVariableMetadata] = field(default_factory=list)
    diagnostics: list[PreviewDiagnostic] = field(default_factory=list)
    calls: list[tuple[str, ContextSnapshot, str | None]] = field(default_factory=list)

    async def preview(
        self,
        *,
        prompt_id: str,
        snapshot: ContextSnapshot,
        edited_override: str | None = None,
    ) -> PromptPreview:
        self.calls.append((prompt_id, snapshot, edited_override))
        return PromptPreview(
            system_prompt=self.system,
            user_prompt=self.user,
            first_message=self.first,
            cascade_source=self.cascade_source,
            variables=list(self.variables),
            diagnostics=list(self.diagnostics),
        )


def _var(name: str = "language") -> PromptVariableMetadata:
    return PromptVariableMetadata(
        name=name,
        description=f"desc for {name}",
        variable_type="text",
        required=True,
        provenance=VariableProvenance.SYSTEM_GENERATED,
        security=VariableSecurity.SYSTEM_ONLY,
    )


async def test_preview_service_maps_core_to_schema() -> None:
    """Happy path: Core dataclass fields land on the Pydantic response."""
    fake = FakeCorePreview(variables=[_var("language")])
    service = PromptPreviewApiService(core=fake)

    resp = await service.preview(
        "writing/en/new_chapter",
        PreviewRequest(variables={"language": "en"}),
    )

    assert resp.system_prompt == "resolved system"
    assert resp.user_prompt == "resolved user"
    assert resp.first_message is None
    assert resp.cascade_source == "bundled"
    assert resp.variables[0].name == "language"
    # Enum values are serialized to their string form.
    assert resp.variables[0].provenance == "system_generated"
    assert resp.variables[0].security == "system_only"
    assert len(fake.calls) == 1


async def test_preview_service_forwards_edited_override_and_mode() -> None:
    """edited_override + mode/genre are forwarded to the Core snapshot."""
    fake = FakeCorePreview()
    service = PromptPreviewApiService(core=fake)

    await service.preview(
        "writing/en/new_chapter",
        PreviewRequest(
            variables={"language": "en"},
            language="en",
            mode="new_chapter",
            genre="Fantasy",
            edited_override="custom prompt body",
        ),
    )

    prompt_id, snapshot, edited_override = fake.calls[0]
    assert prompt_id == "writing/en/new_chapter"
    assert snapshot.language == "en"
    assert snapshot.mode == "new_chapter"
    assert snapshot.genre == "Fantasy"
    assert snapshot.variables == {"language": "en"}
    assert edited_override == "custom prompt body"


async def test_preview_service_maps_diagnostics() -> None:
    """Diagnostics are forwarded 1:1 from Core to the response."""
    fake = FakeCorePreview(
        diagnostics=[
            PreviewDiagnostic(
                kind=PreviewDiagnosticKind.MISSING_VARIABLE,
                variable_name="project_title",
                message="missing_required_variable:project_title",
            ),
        ],
    )
    service = PromptPreviewApiService(core=fake)

    resp = await service.preview("writing/en/new_chapter", PreviewRequest())

    assert len(resp.diagnostics) == 1
    assert resp.diagnostics[0].kind == "missing_variable"
    assert resp.diagnostics[0].variable_name == "project_title"


async def test_preview_service_handles_empty_result() -> None:
    """Edge case: empty system prompt + no variables + no diagnostics."""
    fake = FakeCorePreview(system="", user="", variables=[], diagnostics=[])
    service = PromptPreviewApiService(core=fake)

    resp = await service.preview("writing/en/new_chapter", PreviewRequest())

    assert resp.system_prompt == ""
    assert resp.variables == []
    assert resp.diagnostics == []
