"""S12b — IDOR regression tests: ownership gate on name generation.

Before the S12b fix, ``NameGeneratorService.generate_names`` resolved access
by bare ``request.project_id``: a foreign caller's request loaded the VICTIM's
KB entity names (``_fetch_existing_names`` → ``kb_repo.list_entries``) into
the LLM prompt, and the router factory resolved model routing against the
foreign project's AI settings before the service even ran.

The fix (plan S12b, Pattern B) gates the project on the caller:
- service entry: ``generate_names(request, user_id)`` — FIRST statement is
  ``novel_repo.get_by_id(project_id, user_id)`` → ``NotFoundError`` BEFORE
  ``_fetch_existing_names`` and any LLM call;
- router factory ``_get_service``: the same gate BEFORE the model-routing
  resolver touches the project (foreign ≡ unknown → 404, no settings read).

Foreign and unknown projects are indistinguishable (anti-enumeration).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from narrare.generation.name_service import NameGeneratorService
from narrare.generation.schemas import (
    GenderEnum,
    NameGenerateRequest,
    NameType,
)
from narrare_core.llm import ResolvedModelConfig
from narrare_core.shared.errors import NotFoundError
from tests.fakes.fake_llm_gateway import FakeModelRegistry

from ._ownership_fakes import RecordingNovelRepo

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol

USER_A = uuid4()  # rightful owner of PROJECT_ID (the victim)
USER_B = uuid4()  # foreign caller

PROJECT_ID = uuid4()  # owned by USER_A
FOREIGN_PROJECT_ID = uuid4()  # owned by USER_B (a real project — not the caller's)

_OWNERSHIP = {PROJECT_ID: USER_A, FOREIGN_PROJECT_ID: USER_B}


class RecordingKBRepo:
    """KB repo stub — records ``list_entries`` (the exfiltration vector)."""

    def __init__(self) -> None:
        self.list_entries_calls: list[UUID] = []

    async def list_entries(
        self,
        novel_id: UUID,
        entity_type: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[object], int]:
        self.list_entries_calls.append(novel_id)
        return [], 0


def _make_request(project_id: UUID) -> NameGenerateRequest:
    return NameGenerateRequest(
        project_id=project_id,
        name_type=NameType.CHARACTER,
        name_style="fantasy",
        count=3,
        gender=GenderEnum.ANY,
        explanation_language="en",
    )


def _make_service(
    ownership: dict[UUID, UUID] | None = None,
) -> tuple[
    NameGeneratorService,
    FakeModelRegistry,
    RecordingKBRepo,
    RecordingNovelRepo,
]:
    """NameGeneratorService over recording fakes + ownership map."""
    registry = FakeModelRegistry()
    registry.returns('{"names": [{"name": "Aelindra", "meaning": "starlight"}]}')
    kb_repo = RecordingKBRepo()
    novel_repo = RecordingNovelRepo(ownership)
    from unittest.mock import AsyncMock

    from narrare_core.prompts.composer import ComposedPrompt

    composer = AsyncMock()
    composer.build = AsyncMock(return_value=ComposedPrompt(system="sys", user="user"))
    service = NameGeneratorService(
        registry=registry,
        composer=composer,
        config=ResolvedModelConfig(
            provider_name="test", model_id="test", temperature=0.8, max_tokens=2000
        ),
        # Minimal recording fakes — cast at the construction seam asserts
        # they stand in for the full repository protocols (house pattern).
        novel_repo=cast("NovelRepositoryProtocol", novel_repo),
        kb_repo=cast("KBRepositoryProtocol", kb_repo),
    )
    return service, registry, kb_repo, novel_repo


# ---------------------------------------------------------------------------
# Service gate — before _fetch_existing_names and any LLM call
# ---------------------------------------------------------------------------


class TestGenerateNamesOwnership:
    """``generate_names`` gates project ownership before any KB read or LLM."""

    async def test_owner_generates_names_unchanged(self) -> None:
        """Matrix case (1): the rightful owner's flow is unchanged — KB names
        are still fetched for dedup, the LLM still runs."""
        service, registry, kb_repo, novel_repo = _make_service(_OWNERSHIP)

        result = await service.generate_names(_make_request(PROJECT_ID), user_id=USER_A)

        assert result.count == 1
        assert novel_repo.get_by_id_calls == [(PROJECT_ID, USER_A)]
        assert kb_repo.list_entries_calls == [PROJECT_ID]
        assert len(registry.calls) == 1

    async def test_foreign_project_denied_before_kb_read_and_llm(self) -> None:
        """Matrix case (2)+(4): foreign project → NotFoundError BEFORE the
        victim's KB entity names are read (zero exfiltration) and before any
        LLM call."""
        service, registry, kb_repo, novel_repo = _make_service(_OWNERSHIP)

        with pytest.raises(NotFoundError, match="Novel"):
            await service.generate_names(_make_request(PROJECT_ID), user_id=USER_B)

        assert novel_repo.get_by_id_calls == [(PROJECT_ID, USER_B)]
        assert kb_repo.list_entries_calls == []
        assert registry.calls == []

    async def test_unknown_project_indistinguishable_from_foreign(self) -> None:
        """Matrix case (3): unknown project ≡ foreign project."""
        service, _, kb_repo, _ = _make_service(_OWNERSHIP)
        unknown_project_id = uuid4()

        with pytest.raises(NotFoundError) as foreign_exc:
            await service.generate_names(_make_request(PROJECT_ID), user_id=USER_B)
        with pytest.raises(NotFoundError) as unknown_exc:
            await service.generate_names(_make_request(unknown_project_id), user_id=USER_B)

        assert type(foreign_exc.value) is type(unknown_exc.value) is NotFoundError
        assert str(foreign_exc.value) == f"Novel ({PROJECT_ID}) not found"
        assert str(unknown_exc.value) == f"Novel ({unknown_project_id}) not found"
        assert kb_repo.list_entries_calls == []


# ---------------------------------------------------------------------------
# Router factory gate — before model-routing resolution
# ---------------------------------------------------------------------------


class TestRouterFactoryOwnership:
    """``_get_service`` gates the project BEFORE the model-routing resolver
    reads the foreign project's AI settings."""

    @pytest.mark.parametrize(
        ("project_id", "label"),
        # USER_B requesting USER_A's project (foreign) / a random id (unknown)
        [(PROJECT_ID, "foreign"), (uuid4(), "unknown")],
    )
    async def test_gate_runs_before_model_routing_resolver(
        self, project_id: UUID, label: str
    ) -> None:
        from narrare.generation.router import _get_service

        with (
            patch(
                "narrare.novels.repository.NovelRepository",
                return_value=RecordingNovelRepo(_OWNERSHIP),
            ),
            patch(
                "narrare._app.dependencies_services.get_model_routing_resolver"
            ) as resolver_getter,
            pytest.raises(NotFoundError, match="Novel"),
        ):
            # session is never touched — the gate is the FIRST statement.
            await _get_service(
                session=cast("AsyncSession", None),
                user_id=str(USER_B),
                project_id=project_id,
            )

        assert not resolver_getter.called, (
            f"{label} project must 404 before the model-routing resolver "
            "reads the project's AI settings"
        )
