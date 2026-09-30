"""ChatService dynamic tiering pilot — DI wiring (ADR-089, default-off).

Pins the ``chat/dependencies.py`` side of the opt-in dynamic tier
escalation pilot (ADR-089 Decision 7):

- Flag off (default): the DI factory constructs ``ChatService`` exactly as
  before the pilot — no escalation resolution is wired, and no cascade
  work happens at DI time (ADR-086).
- Flag on: a lazy ``LazyModelResolution`` over the SAME routing resolver
  instance and user (ANALYSE intent, no project tier — chat has no novel
  path parameter) is wired alongside the CHAT resolution; resolution
  stays lazy — first use in ``ChatService.ensure_resolved``, never DI.

The service-level seam behavior (flag-off invariance, capability attach,
degradation) lives in ``test_chat_dynamic_tiering.py``; the fixtures for
the ``CoreSettings`` flag live in this package's ``conftest.py``.

Mirrors ``test_chat_dependencies.py`` (patched app-level factories +
spec'd routing-resolver fake).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from tests.fakes.fake_db_session import FakeDbSession

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.chat.chat_service import ChatService


def _base_resolved_model() -> object:
    """The base CHAT cascade result the fake resolver returns."""
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.model_routing import ResolvedModel

    return ResolvedModel(
        config=ResolvedModelConfig(
            provider_name="zai", model_id="glm-4.7", temperature=0.7, max_tokens=4096
        ),
        api_key="sk-user-key",
        base_url=None,
    )


async def _wired_service() -> tuple[ChatService, MagicMock]:
    """Build the production DI wiring (``get_chat_service``) with fakes.

    The four app-level factories are patched; the routing resolver is a
    spec'd fake so tests can assert the cascade was NOT touched at DI time
    (ADR-086).
    """
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl

    resolver = MagicMock(spec=ModelRoutingResolverImpl, name="ModelRoutingResolver")
    resolver.resolve = AsyncMock(return_value=_base_resolved_model())
    with (
        patch(
            "narrare.chat.dependencies.get_model_routing_resolver",
            return_value=resolver,
        ),
        patch(
            "narrare.chat.dependencies.get_model_registry",
            return_value=MagicMock(spec=True, name="ModelRegistry"),
        ),
        patch(
            "narrare.chat.dependencies.get_composer",
            return_value=MagicMock(spec=True, name="PromptComposer"),
        ),
        patch(
            "narrare.chat.dependencies.get_invocation_pipeline",
            return_value=None,
        ),
    ):
        from narrare.chat.dependencies import get_chat_service

        service = await get_chat_service(
            session=cast("AsyncSession", FakeDbSession()),
            user_id=str(uuid4()),
        )
    return service, resolver


class TestDynamicTieringDIWiring:
    """ADR-089 D7: the escalation resolution is wired only when flag on."""

    async def test_flag_disabled_wires_no_escalation_resolution(
        self,
        tiering_off: None,
    ) -> None:
        """Flag off: the DI factory constructs ChatService exactly as today."""
        service, resolver = await _wired_service()

        escalation_resolution = vars(service)["_escalation_resolution"]
        assert escalation_resolution is None
        # ADR-086: no cascade work at DI time either way.
        resolver.resolve.assert_not_awaited()

    async def test_flag_enabled_wires_lazy_escalation_resolution_at_di(
        self,
        tiering_on: None,
    ) -> None:
        """Flag on: a lazy ANALYSE resolution is wired, nothing resolves yet."""
        service, resolver = await _wired_service()

        from narrare._app.dependencies_services import LazyModelResolution

        escalation_resolution = vars(service)["_escalation_resolution"]
        assert isinstance(escalation_resolution, LazyModelResolution)
        # ADR-086/ADR-089 D7: resolution stays lazy — first use, not DI.
        resolver.resolve.assert_not_awaited()
