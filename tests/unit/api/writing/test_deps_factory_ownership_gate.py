"""Factory-entry ownership gate tests for the writing LLM factories.

Batch-review follow-up N1 (2026-08-29): the five writing service
factories resolve model routing and token limits BEFORE the
service-layer ownership gate. Both resolutions read project-keyed
settings through auto-creating repositories
(``ProjectAiSettingsRepository.get`` / ``ProjectTokenLimitsRepository.get``
flush a new row on first read), so:

- an UNKNOWN ``project_id`` surfaced as an FK ``IntegrityError`` →
  HTTP 500 — a novel-existence oracle (foreign ≢ unknown);
- a FOREIGN ``project_id`` materialized a transient settings row.

The factories must therefore gate the project scope at entry —
``ensure_novel_owned`` (deps_ownership.py, mirroring the committed
S12b pattern from ``generation/router.py``) — BEFORE the resolver or
token-limit service is ever consulted.

These tests pin the gate's presence and ordering for ALL five
factories via targeted assertions (resolver must not run when the
project is unknown/foreign). The deep behavioral proof (404 over the
wire, no ``project_settings`` row materialized) lives in
``tests/integration/writing/test_error_scenarios.py`` on the co-author
route — the one writing surface whose factory the integration
conftest does NOT replace.

Uses ``MagicMock(spec=...)`` / ``AsyncMock`` per RULE-TEST-01 (see
test_deps_factories.py for the established pattern).
"""

from __future__ import annotations

import importlib
from typing import NoReturn
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare_core.shared.errors import NotFoundError

# (module, factory) pairs for the six gated factories.
_FACTORIES: list[tuple[str, str]] = [
    ("narrare.writing.deps_writing", "get_writing_service"),
    ("narrare.writing.deps_extend", "get_extend_service"),
    ("narrare.writing.deps_rewrite", "get_rewrite_service"),
    ("narrare.writing.deps_coauthor", "get_coauthor_service"),
    ("narrare.writing.deps_style_variants", "get_style_variant_service"),
    ("narrare.writing.deps_suggest", "get_suggest_service"),
]


class TestFactoryOwnershipGate:
    """Every writing LLM factory gates the project scope before resolution."""

    @pytest.mark.parametrize(("module_name", "factory_name"), _FACTORIES)
    async def test_unknown_project_raises_404_error_before_resolver(
        self,
        module_name: str,
        factory_name: str,
    ) -> None:
        """Unknown project → NotFoundError at entry; resolver never runs.

        If the gate were missing (or ordered after the resolver), the
        auto-creating project-settings read would flush a row for the
        unknown novel → FK IntegrityError → 500 (existence oracle).
        """
        module = importlib.import_module(module_name)
        factory = getattr(module, factory_name)

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        project_id = uuid4()

        resolver_calls: list[str] = []

        async def _forbidden_resolve(*args: object, **kwargs: object) -> NoReturn:
            resolver_calls.append("resolve")
            raise AssertionError("model-routing resolver ran before the ownership gate")

        fake_resolver = MagicMock(spec=["resolve"], name="resolver")
        fake_resolver.resolve = AsyncMock(side_effect=_forbidden_resolve)

        # Ownership lookup misses: unknown and foreign novels are
        # indistinguishable (both → None → NotFoundError).
        fake_novel_repo = MagicMock(spec=["get_by_id"], name="NovelRepository")
        fake_novel_repo.get_by_id = AsyncMock(return_value=None)

        with (
            patch.object(module, "get_model_routing_resolver", return_value=fake_resolver),
            patch(
                "narrare.novels.repository.NovelRepository",
                return_value=fake_novel_repo,
            ),
            pytest.raises(NotFoundError, match=str(project_id)),
        ):
            await factory(session=session, user_id=user_id, project_id=project_id)

        # The resolver must not have been consulted for the gated project.
        assert resolver_calls == []
        # The gate lookup is ownership-scoped (user-filtered), not a bare get.
        fake_novel_repo.get_by_id.assert_awaited_once_with(project_id, UUID(user_id))
