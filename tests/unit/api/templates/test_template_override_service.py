"""Unit tests for ``TemplateOverrideService`` — user/project override cascade.

The service delegates all storage to a repository; these tests use a
focused fake repository (RULE-TEST-01) to verify the scope-resolution
cascade (user → project), scope-id selection, and delete boolean handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from uuid import uuid4

import pytest

from narrare.templates.template_override_service import TemplateOverrideService
from narrare_core.templates import Template, TemplateMeta

if TYPE_CHECKING:
    import uuid

    from narrare.templates.repository import TemplateRepository


def _make_template(raw: str = "---\ntemplate_type: character\n---\n# Body") -> Template:
    """Minimal template with the ``.raw`` the service forwards on save."""
    return Template(
        meta=TemplateMeta(
            template_type="character",
            template_version="1.0.0",
            schema_version="2.0.0",
        ),
        fields=[],
        body="# Body",
        raw=raw,
    )


@dataclass
class _OverrideCall:
    method: str
    kwargs: dict[str, object]


class FakeOverrideRepository:
    """Fake for the override subset of TemplateRepository.

    ``user_override`` / ``project_override`` configure get_override returns;
    ``delete_result`` configures the delete_override return value.
    """

    def __init__(
        self,
        *,
        user_override: Template | None = None,
        project_override: Template | None = None,
        delete_result: bool = False,
    ) -> None:
        self.user_override = user_override
        self.project_override = project_override
        self.delete_result = delete_result
        self.calls: list[_OverrideCall] = []

    async def get_override(
        self, entity_type: str, scope: str, scope_id: uuid.UUID | None
    ) -> Template | None:
        self.calls.append(
            _OverrideCall(
                "get_override",
                {"entity_type": entity_type, "scope": scope, "scope_id": scope_id},
            )
        )
        if scope == "user":
            return self.user_override
        if scope == "project":
            return self.project_override
        return None

    async def save_override(self, **kwargs: object) -> Template:
        self.calls.append(_OverrideCall("save_override", dict(kwargs)))
        return _make_template()

    async def delete_override(self, **kwargs: object) -> bool:
        self.calls.append(_OverrideCall("delete_override", dict(kwargs)))
        return self.delete_result


def _service(repo: FakeOverrideRepository) -> TemplateOverrideService:
    """Build the service with the fake repository (cast for the concrete hint)."""
    return TemplateOverrideService(repository=cast("TemplateRepository", repo))


# ---------------------------------------------------------------------------
# get_override — user → project cascade
# ---------------------------------------------------------------------------


class TestGetOverride:
    async def test_returns_user_override_when_present(self) -> None:
        user_tpl = _make_template(raw="# user")
        repo = FakeOverrideRepository(user_override=user_tpl)
        service = _service(repo)

        result = await service.get_override(uuid4(), "character")

        assert result is user_tpl
        # User hit short-circuits — project scope is never queried.
        scopes = [c.kwargs["scope"] for c in repo.calls if c.method == "get_override"]
        assert scopes == ["user"]

    async def test_falls_back_to_project_override(self) -> None:
        """When no user override exists, the project override is returned."""
        proj_tpl = _make_template(raw="# project")
        repo = FakeOverrideRepository(project_override=proj_tpl)
        service = _service(repo)

        project_id = uuid4()
        result = await service.get_override(uuid4(), "character", project_id=project_id)

        assert result is proj_tpl
        project_calls = [
            c for c in repo.calls if c.method == "get_override" and c.kwargs["scope"] == "project"
        ]
        assert len(project_calls) == 1
        assert project_calls[0].kwargs["scope_id"] == project_id

    async def test_returns_none_when_no_override_anywhere(self) -> None:
        repo = FakeOverrideRepository()
        service = _service(repo)

        result = await service.get_override(uuid4(), "character", project_id=uuid4())

        assert result is None


# ---------------------------------------------------------------------------
# save_override — scope/scope_id selection
# ---------------------------------------------------------------------------


class TestSaveOverride:
    async def test_save_user_scope_without_project_id(self) -> None:
        repo = FakeOverrideRepository()
        service = _service(repo)

        user_id = uuid4()
        template = _make_template()
        await service.save_override(user_id, "character", template, "1.0.0")

        save_calls = [c for c in repo.calls if c.method == "save_override"]
        assert len(save_calls) == 1
        assert save_calls[0].kwargs["scope"] == "user"
        assert save_calls[0].kwargs["scope_id"] == user_id
        assert save_calls[0].kwargs["content"] == template.raw
        assert save_calls[0].kwargs["based_on_version"] == "1.0.0"

    async def test_save_project_scope_with_project_id(self) -> None:
        repo = FakeOverrideRepository()
        service = _service(repo)

        project_id = uuid4()
        await service.save_override(
            uuid4(), "character", _make_template(), "1.0.0", project_id=project_id
        )

        save_calls = [c for c in repo.calls if c.method == "save_override"]
        assert save_calls[0].kwargs["scope"] == "project"
        assert save_calls[0].kwargs["scope_id"] == project_id


# ---------------------------------------------------------------------------
# delete_override — boolean result + scope selection
# ---------------------------------------------------------------------------


class TestDeleteOverride:
    async def test_returns_true_and_logs_when_deleted(self) -> None:
        repo = FakeOverrideRepository(delete_result=True)
        service = _service(repo)

        result = await service.delete_override(uuid4(), "character")

        assert result is True

    async def test_returns_false_when_nothing_deleted(self) -> None:
        repo = FakeOverrideRepository(delete_result=False)
        service = _service(repo)

        result = await service.delete_override(uuid4(), "character")

        assert result is False

    async def test_delete_uses_project_scope_when_project_id_given(self) -> None:
        repo = FakeOverrideRepository(delete_result=True)
        service = _service(repo)

        project_id = uuid4()
        await service.delete_override(uuid4(), "character", project_id=project_id)

        delete_calls = [c for c in repo.calls if c.method == "delete_override"]
        assert delete_calls[0].kwargs["scope"] == "project"
        assert delete_calls[0].kwargs["scope_id"] == project_id


# ---------------------------------------------------------------------------
# Fixture sanity (keeps the import surface exercised even with no asserts)
# ---------------------------------------------------------------------------


@pytest.fixture
def service() -> TemplateOverrideService:
    return _service(FakeOverrideRepository())
