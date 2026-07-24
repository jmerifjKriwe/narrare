"""Tests that build_invocation_evidence threads context.project_id → evidence.novel_id (ADR-070).

``PromptInvocationContext.project_id`` is deliberately typed ``object | None``:
production callers supply it as a ``UUID`` (services), a *string-form* UUID
(``writing_graph`` carries ``state.novel_id`` as ``str``), or occasionally a
non-uuid string (``wiki`` reuses ``entity_name``). The evidence ``novel_id``
column, however, is a strict ``UUID | None``. These tests pin the write-path
bridging contract: UUIDs and string-form UUIDs are coerced to ``UUID``;
``None`` and non-uuid values yield ``None`` (fail-safe, never a crash).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from narrare_core.ai_invocation._enums import ValidationStatus
from narrare_core.ai_invocation._evidence import build_invocation_evidence
from narrare_core.ai_invocation.models import PromptInvocationContext, ValidationResult
from narrare_core.llm.intents import LLMIntent


def _context(*, project_id: object | None) -> PromptInvocationContext:
    return PromptInvocationContext(
        feature_id="dialogue_coach",
        intent=LLMIntent.DIALOGUE_COACH,
        mode="dialogue_coach",
        project_id=project_id,
    )


def _build(project_id: object | None) -> UUID | None:
    return build_invocation_evidence(
        context=_context(project_id=project_id),
        prepared=None,
        final_validation=ValidationResult(status=ValidationStatus.PASS),
        final_validator_ran=True,
    ).novel_id


class TestNovelIdThreading:
    def test_project_id_flows_to_novel_id(self) -> None:
        novel = uuid4()
        assert _build(project_id=novel) == novel

    def test_none_project_id_yields_none_novel_id(self) -> None:
        assert _build(project_id=None) is None

    def test_string_form_uuid_is_coerced(self) -> None:
        # writing_graph carries state.novel_id as str (see writing_graph_prompts.py
        # doing UUID(state.novel_id)). Evidence must still carry the novel UUID.
        novel = uuid4()
        assert _build(project_id=str(novel)) == novel

    def test_non_uuid_string_yields_none(self) -> None:
        # wiki reuses entity_name as project_id (wiki/service.py). A non-uuid
        # string must degrade to None rather than crash the evidence build.
        assert _build(project_id="gandalf-the-grey") is None
