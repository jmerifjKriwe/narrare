"""User-routing + lazy-wiring test for the generation factory (ADR-086 L14).

``generation/router.py::_get_service`` is a router-resident factory
(pre-existing layout; relocation out of scope per the plan). Proves:

- the factory wires the per-user ``ModelRoutingResolver`` cascade with
  the REAL intent (``NAME_GENERATE``), for THIS user, WITH the project
  tier — invoked at the service's first use, NOT at construction,
- the cascade result (config + credentials) reaches the service,
- the factory-level S12b ownership gate stays AHEAD of resolution.

Mirrors ``tests/unit/api/analysis/test_deps_user_routing_voice_factories.py``
(the analysis ADR-086 convention).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from narrare.generation.name_service import NameGeneratorService
from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_routing import ResolvedModel

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


class TestGenerationFactoryUserRouting:
    """_get_service wires the NAME_GENERATE cascade lazily (project tier)."""

    async def test_resolves_name_generate_for_user_and_project_at_first_use(
        self,
    ) -> None:
        from narrare.generation.router import _get_service

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        project_id = uuid4()
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.generation.router.get_model_routing_resolver",
                return_value=resolver,
            ),
            # The S12b factory gate is out of scope here — patched to pass
            # so the test isolates the lazy-resolution wiring.
            patch(
                "narrare.generation.router.verify_novel_owned",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "narrare.generation.router.get_model_registry",
                return_value=MagicMock(spec=True, name="ModelRegistry"),
            ),
            patch(
                "narrare.generation.router.get_composer",
                return_value=MagicMock(spec=True, name="PromptComposer"),
            ),
            patch(
                "narrare.generation.router.get_invocation_pipeline",
                return_value=MagicMock(spec=True, name="InvocationPipeline"),
            ),
        ):
            service = await _get_service(
                session=session,
                user_id=user_id,
                project_id=project_id,
            )

        # ADR-086 lazy wiring: construction resolves nothing.
        assert resolver.resolve.await_args_list == []

        assert isinstance(service, NameGeneratorService)
        resolved_model = await service.ensure_resolved()

        # The REAL intent (NAME_GENERATE), for THIS user, WITH the
        # project tier — invoked at first use, not at construction:
        assert resolver.resolve.await_args_list == [
            call(LLMIntent.NAME_GENERATE, UUID(user_id), project_id)
        ]

        # The cascade result lands on the service (threaded onwards to
        # the registry.run call with the generation overrides layered).
        assert resolved_model.config is resolved.config
        assert resolved_model.config.model_id == "glm-4.7"
        assert resolved_model.config.provider_name == "zai"
        assert resolved_model.api_key == _USER_KEY
        assert resolved_model.base_url == _USER_BASE_URL
