"""User-routing migration tests — analysis factory execution (Tasks 2a/2b).

Companion of ``test_deps_user_routing.py`` (split off for the RULE-04
test-file hard limit). Proves that the RULE-04 split factories resolve via
the per-user ``ModelRoutingResolver`` cascade with the correct intent +
user_id (+ novel_id where the router provides one) and that the resolved
config + credentials reach the service:

- ``get_beta_reader_service`` (BETA_READ — novel-scoped query param)
- ``get_character_voice_service`` (VOICE — novel-scoped path param)
- ``get_coreference_service`` (ANALYSE — chapter-scoped, resolves WITHOUT
  the project tier, per the plan's novel_id threading rule)

Task 2b's four voice factories live in
``test_deps_user_routing_voice_factories.py`` (RULE-04 split when Task 2b
pushed this file past its hard limit).

Same conventions as the sibling files: fake resolver, cast-pattern
registry fakes (mirrors ``test_deps_user_routing.py``, Task 1a).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from narrare._app.dependencies_services import LazyModelResolution
from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_routing import ResolvedModel

# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_deps_user_routing.py, Task 1a conventions)
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
# Factory execution — resolver resolves with intent + user_id (+ novel_id)
# ===========================================================================


class TestBetaReaderFactoryUserRouting:
    """get_beta_reader_service wires the BETA_READ cascade lazily (novel tier)."""

    async def test_resolves_beta_read_for_user_and_novel(self) -> None:
        from narrare._app.config import Settings
        from narrare.analysis.beta_reader_service import BetaReaderService
        from narrare.analysis.dependencies_beta_reader import get_beta_reader_service
        from narrare.settings.token_limits.contracts import TokenLimitOverrides
        from narrare.settings.token_limits.service import TokenLimitsService
        from narrare_core.context.contracts import EffectiveContextBudgets

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        novel_id = uuid4()
        resolver, resolved = _fake_resolver()

        fake_limits = TokenLimitOverrides(context_total_budget=24_000)
        fake_token_service = MagicMock(spec=TokenLimitsService)
        fake_token_service.get_resolved_limits = AsyncMock(return_value=fake_limits)
        canned = EffectiveContextBudgets(
            context_total=24_000,
            series_history=0,
            writing_tier_base=24_000,
            reserve_tokens=4_096,
            context_window=128_000,
            source="cascade:uncapped",
        )

        with (
            patch(
                "narrare.analysis.dependencies_beta_reader.get_model_routing_resolver",
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
            patch(
                "narrare._app.config.get_settings",
                return_value=MagicMock(spec=Settings, name="settings"),
            ),
            patch(
                "narrare.settings.token_limits.service.TokenLimitsService",
                return_value=fake_token_service,
            ),
            patch(
                "narrare.settings.token_limits.context_budgets.resolve_context_budgets",
                return_value=canned,
            ),
        ):
            service = await get_beta_reader_service(
                session=session,
                user_id=user_id,
                novel_id=novel_id,
            )

        # ADR-086 lazy wiring: the factory runs pre-body-validation, so
        # it must NOT resolve — the cascade is deferred to first use.
        assert resolver.resolve.await_args_list == []

        assert isinstance(service, BetaReaderService)
        assert isinstance(service._model_resolution, LazyModelResolution)
        resolved_model = await service._model_resolution.resolve()

        # The REAL intent (BETA_READ), for THIS user, WITH the novel
        # (project) tier — invoked at first use, not at construction:
        assert resolver.resolve.await_args_list == [
            call(LLMIntent.BETA_READ, UUID(user_id), novel_id)
        ]

        # The cascade result lands on the service (threaded onwards to
        # the run-limit resolver + registry.prepare at consumption time).
        assert resolved_model.config is resolved.config
        assert resolved_model.config.model_id == "glm-4.7"
        assert resolved_model.config.provider_name == "zai"
        assert resolved_model.api_key == _USER_KEY
        assert resolved_model.base_url == _USER_BASE_URL

        # RULE-18b: the token-limits cascade is likewise deferred — it
        # composes at first use through the deferred budget assembler.
        assert fake_token_service.get_resolved_limits.await_args_list == []
        budget_assembler = await service._budget_assembler_factory()
        fake_token_service.get_resolved_limits.assert_awaited_once_with(
            user_id=user_id, project_id=str(novel_id)
        )
        assert budget_assembler.total_budget == 24_000


class TestCharacterVoiceFactoryUserRouting:
    """get_character_voice_service resolves via the cascade (VOICE + novel)."""

    async def test_resolves_voice_for_user_and_novel(self) -> None:
        from narrare.analysis.character_voice_service import CharacterVoiceService
        from narrare.analysis.dependencies_character_voice import (
            get_character_voice_service,
        )

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        novel_id = uuid4()
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.analysis.dependencies_character_voice.get_model_routing_resolver",
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
            service = await get_character_voice_service(
                novel_id=novel_id,
                session=session,
                user_id=user_id,
            )

        resolver.resolve.assert_awaited_once_with(LLMIntent.VOICE, UUID(user_id), novel_id)
        assert isinstance(service, CharacterVoiceService)
        assert service._config is resolved.config
        assert service._api_key == _USER_KEY
        assert service._base_url == _USER_BASE_URL


class TestCoreferenceFactoryUserRouting:
    """get_coreference_service resolves via the cascade (ANALYSE, no novel).

    The coreference router is chapter-scoped — the novel is only known after
    the service loads the chapter, so the cascade resolves without the
    project tier (plan: "Where not, resolve without it").
    """

    async def test_resolves_analyse_for_user_without_novel(self) -> None:
        from narrare.analysis.coreference_service import CoreferenceService
        from narrare.analysis.dependencies_coreference import get_coreference_service

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.analysis.dependencies_coreference.get_model_routing_resolver",
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
            service = await get_coreference_service(
                session=session,
                user_id=user_id,
            )

        resolver.resolve.assert_awaited_once_with(LLMIntent.ANALYSE, UUID(user_id), None)
        assert isinstance(service, CoreferenceService)
        assert service._config is resolved.config
        assert service._api_key == _USER_KEY
        assert service._base_url == _USER_BASE_URL
