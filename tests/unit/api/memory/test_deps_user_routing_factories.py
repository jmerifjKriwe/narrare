"""User-routing migration tests — Task 6 memory factory.

Mirrors ``tests/unit/api/series/test_deps_user_routing_factories.py``
(Task 5 conventions). Proves that the memory analysis factory wires the
per-user ``ModelRoutingResolver`` cascade with the correct intent
+ user_id and that the resolved config + credentials reach the service's
ACTUAL ``get_model`` resolution point. Since ADR-086 the factory wires
the cascade LAZILY (``LazyModelResolution``) — no resolution at
construction (FastAPI solves sub-dependencies pre-body-validation); the
assertions therefore pin both the deferral and the first-use cascade
call:

- ``_get_analysis_service`` (EXTRACT — ``_run_agent`` composes the
  preference-analysis invocation with ``intent=LLMIntent.EXTRACT`` at
  both ``build_invocation_context`` and ``compose_invocation``)

Tier decision: resolves WITHOUT the project tier (``project_id=None``).
The analyze route (``POST /memory/analyze``) has no novel_id path
parameter — ``project_id`` arrives only in the request BODY, which is
unavailable at dependency-wiring time. Same documented caveat as the
Task 5 series factories: user/operator-level routing + cascade overrides
apply.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare._app.dependencies_services import LazyModelResolution, StaticModelResolution
from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_routing import ResolvedModel

if TYPE_CHECKING:
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

# ---------------------------------------------------------------------------
# Shared helpers (mirrors the Task 5 series-file conventions)
# ---------------------------------------------------------------------------

_USER_KEY = "sk-user-key"
_USER_BASE_URL = "https://user.example/v1"


def _user_config() -> ResolvedModelConfig:
    """The config a wired-up user's resolver would return (wizard provider)."""
    return ResolvedModelConfig(
        provider_name="zai",
        model_id="glm-4.7",
        temperature=0.7,
        max_tokens=4096,
    )


def _fake_resolver() -> tuple[MagicMock, ResolvedModel]:
    """A spec'd fake resolver whose resolve() returns the user's model."""
    resolved = ResolvedModel(
        config=_user_config(),
        api_key=_USER_KEY,
        base_url=_USER_BASE_URL,
    )
    resolver = MagicMock(spec=ModelRoutingResolverImpl, name="ModelRoutingResolver")
    resolver.resolve = AsyncMock(return_value=resolved)
    return resolver, resolved


class _StopResolution(BaseException):
    """Sentinel raised after get_model recorded its call (short-circuits run).

    ``BaseException`` (not ``Exception``) so the service's broad
    ``except Exception`` error wrapper (RULE-11 graceful degradation)
    cannot swallow it into the fallback output.
    """


class _RecordingRegistry:
    """Fake ModelRegistry — records ``get_model`` calls for assertions."""

    def __init__(self, stop_after_record: BaseException | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self._stop = stop_after_record

    async def get_model(
        self,
        config: ResolvedModelConfig,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        usage_limits: object = None,
    ) -> object:
        self.calls.append({"config": config, "api_key": api_key, "base_url": base_url})
        if self._stop is not None:
            raise self._stop
        return SimpleNamespace(sentinel_model=True)

    async def prepare(
        self,
        config: ResolvedModelConfig,
        *,
        intent: object = None,
        usage_limits: object = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> object:
        """Task-6d bridge: resolution flows through prepare → get_model.

        Delegates to the SAME recording ``get_model`` call so the
        credential assertions (``registry.calls`` shape) hold for the
        migrated (prepare) path under test.
        """
        return SimpleNamespace(
            model=await self.get_model(config, api_key=api_key, base_url=base_url),
            model_settings=None,
            usage_limits=usage_limits,
        )


# ===========================================================================
# Factory wiring — resolve() via the cascade, credentials land on the service
# ===========================================================================


class TestMemoryAnalysisFactoryUserRouting:
    """_get_analysis_service wires the EXTRACT cascade lazily (no project)."""

    async def test_resolves_extract_for_user_without_project_tier(self) -> None:
        from narrare.memory.analysis_service import PreferenceAnalysisService
        from narrare.memory.router_analysis import _get_analysis_service

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.memory.router_analysis.get_model_routing_resolver",
                return_value=resolver,
            ),
            patch(
                "narrare._app.dependencies.get_model_registry",
                return_value=MagicMock(spec=True, name="ModelRegistry"),
            ),
            patch(
                "narrare._app.dependencies.get_composer",
                return_value=MagicMock(spec=True, name="PromptComposer"),
            ),
            patch(
                "narrare._app.dependencies.get_invocation_pipeline",
                return_value=MagicMock(spec=True, name="InvocationPipeline"),
            ),
        ):
            service = await _get_analysis_service(session=session, user_id=user_id)

        # ADR-086 lazy wiring: the factory runs pre-body-validation, so
        # it must NOT resolve — the cascade is deferred to first use.
        assert resolver.resolve.await_args_list == []

        assert isinstance(service, PreferenceAnalysisService)
        assert isinstance(service._model_resolution, LazyModelResolution)
        resolved_model = await service._model_resolution.resolve()

        # The REAL intent (EXTRACT), for THIS user, WITHOUT the project
        # tier (project_id arrives only in the request BODY) — invoked
        # at first use, not at construction:
        assert resolver.resolve.await_args_list == [call(LLMIntent.EXTRACT, UUID(user_id), None)]

        # The cascade result lands on the service (threaded onwards to
        # the agent-runner get_model resolution point at consumption time).
        assert resolved_model.config is resolved.config
        assert resolved_model.config.model_id == "glm-4.7"
        assert resolved_model.config.provider_name == "zai"
        assert resolved_model.api_key == _USER_KEY
        assert resolved_model.base_url == _USER_BASE_URL


# ===========================================================================
# Resolution point — credentials reach the service's ACTUAL get_model call
# ===========================================================================


class TestMemoryCredentialsReachResolutionPoint:
    """The resolved key must flow into the service's ACTUAL get_model call."""

    async def test_analysis_service_threads_credentials_into_get_model(self) -> None:
        from narrare.memory.analysis_service import PreferenceAnalysisService
        from tests.fakes import FakeFeedbackRepository, FakePreferenceProfileRepository

        user_id, project_id = uuid4(), uuid4()
        feedback_repo = FakeFeedbackRepository()
        config = _user_config()

        from narrare.memory.models import FeedbackEventModel

        for _ in range(5):
            feedback_repo.seed(
                FeedbackEventModel(
                    user_id=user_id,
                    project_id=project_id,
                    suggestion_id=uuid4(),
                    action="accept",
                    intent="write",
                    suggestion_text="Seeded event.",
                )
            )

        registry = _RecordingRegistry(stop_after_record=_StopResolution())
        service = PreferenceAnalysisService(
            registry=cast("ModelRegistry", registry),
            feedback_repo=feedback_repo,
            profile_repo=FakePreferenceProfileRepository(),
            composer=cast("PromptComposer", MagicMock(spec=["build"], name="PromptComposer")),
            model_resolution=StaticModelResolution(
                ResolvedModel(config=config, api_key=_USER_KEY, base_url=_USER_BASE_URL)
            ),
        )

        # The sentinel escapes the service's broad RULE-11 error wrapper
        # (BaseException) — proving the credentials reach the real get_model.
        with pytest.raises(_StopResolution):
            await service.analyze(user_id, project_id)

        assert registry.calls == [
            {"config": config, "api_key": _USER_KEY, "base_url": _USER_BASE_URL}
        ]
