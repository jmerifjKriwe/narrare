"""User-routing migration tests — Task 5 series factories.

Mirrors ``tests/unit/api/analysis/test_deps_user_routing_voice_factories.py``
(Task 2b conventions). Proves that each series factory resolves via the
per-user ``ModelRoutingResolver`` cascade with the correct intent + user_id
and that the resolved config + credentials reach the service AND its ACTUAL
``get_model`` resolution points:

- ``get_series_voice_service`` (VOICE — ``author_voice_prompt`` composes with
  ``intent=LLMIntent.VOICE``)
- ``get_series_consistency_service`` (ANALYSE — ``series_consistency_prompt``
  composes with ``intent=LLMIntent.ANALYSE``)
- ``get_series_voice_drift_service`` (VOICE — ``author_voice_drift_prompt``
  composes with ``intent=LLMIntent.VOICE``)

The credentials-reach-the-resolution-point proofs live in the sibling
``test_deps_user_routing_credentials.py`` (split off for the RULE-04
test-file hard limit — analysis-domain precedent).

Tier decision: all three resolve WITHOUT the project tier (``project_id=None``).
The series routes are series-scoped (``/series/{series_id}/...``); the novel id
— the cascade's project tier key — arrives only in the request BODY (voice
profile / consistency check / voice-drift check) or not at all (the remaining
voice + snapshot endpoints), so it is never available at dependency-wiring
time. Passing the SERIES id as the project id would query the
project-routing table with a foreign UUID (series ids are not project/novel
ids). Same documented caveat as ``dependencies_context_preview.py``
(SERIES-002): user/operator-level routing + cascade overrides apply.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_routing import ResolvedModel

# ---------------------------------------------------------------------------
# Shared helpers (mirrors the Task 2b analysis-file conventions)
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


# ===========================================================================
# Factory wiring — resolve() via the cascade, credentials land on the service
# ===========================================================================


class TestSeriesVoiceFactoryUserRouting:
    """get_series_voice_service wires the VOICE cascade lazily."""

    async def test_wires_voice_cascade_lazily_for_user_without_project_tier(self) -> None:
        from narrare.series.dependencies_voice import get_series_voice_service
        from narrare.series.series_voice_service import SeriesVoiceService

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.series.dependencies_voice.get_model_routing_resolver",
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
            service = await get_series_voice_service(
                session=session,
                user_id=user_id,
            )

        # ADR-086 lazy wiring: construction resolves nothing.
        assert resolver.resolve.await_args_list == []

        assert isinstance(service, SeriesVoiceService)
        resolved_model = await service.ensure_resolved()

        # The REAL intent (VOICE), for THIS user, WITHOUT a project tier
        # (the novel id arrives only in the request BODY of the profile
        # endpoint and not at all on get/override/clear) — invoked at
        # first use, not at construction:
        assert resolver.resolve.await_args_list == [call(LLMIntent.VOICE, UUID(user_id), None)]

        # The cascade result lands on the service (threaded onwards to
        # ModelRegistry.prepare with the credentials).
        assert resolved_model.config is resolved.config
        assert resolved_model.config.model_id == "glm-4.7"
        assert resolved_model.api_key == _USER_KEY
        assert resolved_model.base_url == _USER_BASE_URL


class TestSeriesConsistencyFactoryUserRouting:
    """get_series_consistency_service wires the ANALYSE cascade lazily."""

    async def test_wires_analyse_cascade_lazily_for_user_without_project_tier(self) -> None:
        from narrare.series.dependencies_consistency import get_series_consistency_service
        from narrare.series.series_consistency_service import SeriesConsistencyService

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.series.dependencies_consistency.get_model_routing_resolver",
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
            service = await get_series_consistency_service(
                session=session,
                user_id=user_id,
            )

        # ADR-086 lazy wiring: construction resolves nothing.
        assert resolver.resolve.await_args_list == []

        assert isinstance(service, SeriesConsistencyService)
        resolved_model = await service.ensure_resolved()

        # The REAL intent (ANALYSE), for THIS user, WITHOUT a project tier
        # (the novel id arrives only in the request BODY) — invoked at
        # first use, not at construction:
        assert resolver.resolve.await_args_list == [call(LLMIntent.ANALYSE, UUID(user_id), None)]

        # The cascade result lands on the service (threaded onwards to
        # ModelRegistry.prepare with the credentials).
        assert resolved_model.config is resolved.config
        assert resolved_model.config.model_id == "glm-4.7"
        assert resolved_model.api_key == _USER_KEY
        assert resolved_model.base_url == _USER_BASE_URL


class TestSeriesVoiceDriftFactoryUserRouting:
    """get_series_voice_drift_service resolves via the cascade (VOICE)."""

    async def test_resolves_voice_for_user_without_project_tier(self) -> None:
        from narrare.series.dependencies_voice_drift import get_series_voice_drift_service
        from narrare.series.series_voice_drift_service import SeriesVoiceDriftService

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.series.dependencies_voice_drift.get_model_routing_resolver",
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
            service = await get_series_voice_drift_service(
                session=session,
                user_id=user_id,
            )

        resolver.resolve.assert_awaited_once_with(LLMIntent.VOICE, UUID(user_id), None)
        assert isinstance(service, SeriesVoiceDriftService)
        assert service._config is resolved.config
        assert service._api_key == _USER_KEY
        assert service._base_url == _USER_BASE_URL
