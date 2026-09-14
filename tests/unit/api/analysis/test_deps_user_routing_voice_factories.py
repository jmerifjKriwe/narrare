"""User-routing migration tests — Task 2b voice factory execution.

Split off ``test_deps_user_routing_factories.py`` (RULE-04 test-file hard
limit) when Task 2b added the four voice factories. Proves that each factory
resolves via the per-user ``ModelRoutingResolver`` cascade with the correct
intent + user_id (+ novel_id where the router provides one) and that the
resolved config + credentials reach the service. ADR-086-migrated factories
(character_voice, coreference, voice_check, author_voice,
author_voice_drift) prove the cascade wiring is LAZY — no resolution at
construction, exactly one resolve at first use:

- ``get_voice_check_service`` (VOICE — chapter-scoped, resolves WITHOUT
  the project tier, per the plan's novel_id threading rule)
- ``get_voice_drift_service`` (VOICE — novel-scoped path param)
- ``get_author_voice_service`` (VOICE — novel-scoped path param)
- ``get_author_voice_drift_service`` (VOICE — novel-scoped path param)

Same conventions as the sibling files: fake resolver, cast-pattern
registry fakes (mirrors ``test_deps_user_routing.py``, Task 1a).
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
# Shared helpers (mirrors test_deps_user_routing_factories.py conventions)
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
# Task 2b — voice factories (voice_check / voice_drift / author_voice /
# author_voice_drift). All resolve LLMIntent.VOICE (each service's prompt
# resolver composes with intent=VOICE, per voice_check_prompt.py et al.)
# ===========================================================================


class TestVoiceCheckFactoryUserRouting:
    """get_voice_check_service wires the VOICE cascade lazily (no novel tier).

    The voice-check router is chapter-scoped — the novel is only known
    after the service loads the chapter — so the cascade resolves WITHOUT
    the project tier (plan's novel_id threading rule; coreference
    precedent from Task 2a) at the service's first ``ensure_resolved()``.
    """

    async def test_resolves_voice_for_user_without_novel_at_first_use(self) -> None:
        from narrare.analysis.dependencies_voice_check import get_voice_check_service
        from narrare.analysis.voice_check_service import CharacterVoiceCheckerService

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.analysis.dependencies_voice_check.get_model_routing_resolver",
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
            service = await get_voice_check_service(
                session=session,
                user_id=user_id,
            )

        # ADR-086 lazy wiring: the factory runs pre-body-validation, so
        # it must NOT resolve — the cascade is deferred to first use.
        assert resolver.resolve.await_args_list == []

        assert isinstance(service, CharacterVoiceCheckerService)
        resolved_model = await service.ensure_resolved()

        # The REAL intent (VOICE), for THIS user, WITHOUT the novel
        # (project) tier — invoked at first use, not at construction:
        assert resolver.resolve.await_args_list == [call(LLMIntent.VOICE, UUID(user_id), None)]

        # The cascade result lands on the service (threaded onwards to
        # the registry.prepare resolution point at consumption time).
        assert resolved_model.config is resolved.config
        assert resolved_model.config.model_id == "glm-4.7"
        assert resolved_model.config.provider_name == "zai"
        assert resolved_model.api_key == _USER_KEY
        assert resolved_model.base_url == _USER_BASE_URL


class TestVoiceDriftFactoryUserRouting:
    """get_voice_drift_service resolves via the cascade (VOICE + novel)."""

    async def test_resolves_voice_for_user_and_novel(self) -> None:
        from narrare.analysis.dependencies_voice_drift import get_voice_drift_service
        from narrare.analysis.voice_drift_service import CharacterVoiceDriftService

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        novel_id = uuid4()
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.analysis.dependencies_voice_drift.get_model_routing_resolver",
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
            service = await get_voice_drift_service(
                novel_id=novel_id,
                session=session,
                user_id=user_id,
            )

        resolver.resolve.assert_awaited_once_with(LLMIntent.VOICE, UUID(user_id), novel_id)
        assert isinstance(service, CharacterVoiceDriftService)
        assert service._config is resolved.config
        assert service._api_key == _USER_KEY
        assert service._base_url == _USER_BASE_URL


class TestAuthorVoiceFactoryUserRouting:
    """get_author_voice_service wires the VOICE cascade lazily (novel tier).

    The author-voice router is novel-scoped — the cascade resolves WITH
    the project tier (plan: "Where not, resolve without it" does not
    apply here) at the service's first ``ensure_resolved()``.
    """

    async def test_resolves_voice_for_user_and_novel_at_first_use(self) -> None:
        from narrare.analysis.author_voice_service import AuthorVoiceService
        from narrare.analysis.dependencies_author_voice import get_author_voice_service

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        novel_id = uuid4()
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.analysis.dependencies_author_voice.get_model_routing_resolver",
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
            service = await get_author_voice_service(
                novel_id=novel_id,
                session=session,
                user_id=user_id,
            )

        # ADR-086 lazy wiring: the factory runs pre-body-validation, so
        # it must NOT resolve — the cascade is deferred to first use.
        assert resolver.resolve.await_args_list == []

        assert isinstance(service, AuthorVoiceService)
        resolved_model = await service.ensure_resolved()

        # The REAL intent (VOICE), for THIS user, WITH the novel
        # (project) tier — invoked at first use, not at construction:
        assert resolver.resolve.await_args_list == [call(LLMIntent.VOICE, UUID(user_id), novel_id)]

        # The cascade result lands on the service (threaded onwards to
        # the registry.prepare resolution point at consumption time).
        assert resolved_model.config is resolved.config
        assert resolved_model.config.model_id == "glm-4.7"
        assert resolved_model.config.provider_name == "zai"
        assert resolved_model.api_key == _USER_KEY
        assert resolved_model.base_url == _USER_BASE_URL


class TestAuthorVoiceDriftFactoryUserRouting:
    """get_author_voice_drift_service wires the VOICE cascade lazily (novel tier).

    The author-voice-drift router is novel-scoped — the cascade resolves
    WITH the project tier at the service's first ``ensure_resolved()``.
    """

    async def test_resolves_voice_for_user_and_novel_at_first_use(self) -> None:
        from narrare.analysis.author_voice_drift_service import AuthorVoiceDriftService
        from narrare.analysis.dependencies_author_voice_drift import (
            get_author_voice_drift_service,
        )

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        novel_id = uuid4()
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.analysis.dependencies_author_voice_drift.get_model_routing_resolver",
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
            service = await get_author_voice_drift_service(
                novel_id=novel_id,
                session=session,
                user_id=user_id,
            )

        # ADR-086 lazy wiring: the factory runs pre-body-validation, so
        # it must NOT resolve — the cascade is deferred to first use.
        assert resolver.resolve.await_args_list == []

        assert isinstance(service, AuthorVoiceDriftService)
        resolved_model = await service.ensure_resolved()

        # The REAL intent (VOICE), for THIS user, WITH the novel
        # (project) tier — invoked at first use, not at construction:
        assert resolver.resolve.await_args_list == [call(LLMIntent.VOICE, UUID(user_id), novel_id)]

        # The cascade result lands on the service (threaded onwards to
        # the registry.prepare resolution point at consumption time).
        assert resolved_model.config is resolved.config
        assert resolved_model.config.model_id == "glm-4.7"
        assert resolved_model.config.provider_name == "zai"
        assert resolved_model.api_key == _USER_KEY
        assert resolved_model.base_url == _USER_BASE_URL
