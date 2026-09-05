"""Task 6d-3 wiring tests — wiki resolves via ModelRegistry.prepare().

Pins the Task-6a/6b/6c structural contract for the bare ``get_model``
wiki factory site — the model is resolved via the SINGLE assembly point
(``ModelRegistry.prepare``, Task 4) with the site intent + per-user
credentials, and ``prepared.model`` reaches ``WikiGenerationAgent``:

- ``build_core_wiki_service`` (SUMMARIZE — both planes)

Root cause pinned here (structural audit, "Pipeline 3 — nothing at
all"): the factory resolved the model via bare ``get_model`` on both
the user plane and the operator plane, bypassing the intent-aware
assembly point entirely.

CORE BOUNDARY RESOLUTION (Task 1 core kwargs pass-through + Task 2
factory-side wiring, RULE-01b): ``WikiGenerationAgent.generate_entity``
/ ``generate_chapter`` (via ``WikiChapterGenerator``) forward
``model_settings``/``usage_limits`` to the internal agent runs, and the
factory binds the prepared halves into the agent path via the API-side
``PreparedWikiAgent`` adapter (the core ``WikiAgentProtocol`` surface
has no settings/limits parameters — the binding happens where the
triple is resolved, pinned in
``test_factory_binds_prepared_settings_into_the_agent_path`` below).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.gateway import ModelRegistry
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from pydantic_ai.settings import ModelSettings

_USER_KEY = "sk-user-key"
_USER_BASE_URL = "https://user.example/v1"

_SENTINEL_SETTINGS: ModelSettings = {"max_tokens": 12_345}


def _user_config() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider_name="zai",
        model_id="glm-4.7",
        temperature=0.7,
        max_tokens=4096,
    )


def _recording_registry(model: Any) -> tuple[MagicMock, list[dict[str, object]]]:
    """Mock ModelRegistry whose prepare mirrors the Task-4 assembly point."""
    calls: list[dict[str, object]] = []

    async def _prepare(
        config: ResolvedModelConfig,
        *,
        intent: LLMIntent | None = None,
        usage_limits: Any = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> PreparedModelCall:
        prepared = PreparedModelCall(
            model=model,
            model_settings=_SENTINEL_SETTINGS,
            usage_limits=usage_limits,
        )
        calls.append(
            {
                "config": config,
                "intent": intent,
                "usage_limits": usage_limits,
                "api_key": api_key,
                "base_url": base_url,
                "prepared": prepared,
            }
        )
        return prepared

    registry = MagicMock(spec=ModelRegistry)
    cast("Any", registry).prepare = AsyncMock(side_effect=_prepare)
    return registry, calls


class TestBuildCoreWikiServicePrepareWiring:
    """build_core_wiki_service resolves via prepare(SUMMARIZE) on both planes."""

    async def test_user_plane_resolves_via_prepare_with_credentials(self) -> None:
        """User plane: config + credentials + intent reach prepare() once."""
        mock_model = AsyncMock()
        registry, calls = _recording_registry(mock_model)
        config = _user_config()

        with (
            patch("narrare._app.dependencies.get_model_registry", return_value=registry),
            patch(
                "narrare._app.dependencies_services.build_system_default_config"
            ) as mock_system_config,
            patch("narrare_core.wiki.agent.WikiGenerationAgent") as mock_agent_cls,
            patch("narrare_core.wiki.service.WikiService"),
        ):
            from narrare.wiki.dependencies_core import build_core_wiki_service

            await build_core_wiki_service(config=config, api_key=_USER_KEY, base_url=_USER_BASE_URL)

        # Single assembly point with the site intent + user credentials.
        assert len(calls) == 1
        assert calls[0]["config"] is config
        assert calls[0]["intent"] is LLMIntent.SUMMARIZE
        assert calls[0]["api_key"] == _USER_KEY
        assert calls[0]["base_url"] == _USER_BASE_URL
        # One prepare() → exactly one model resolution (no duplicate).
        registry.get_model.assert_not_awaited()
        # The prepared model reaches the agent boundary.
        prepared = cast("PreparedModelCall", calls[0]["prepared"])
        mock_agent_cls.assert_called_once_with(model=prepared.model)
        mock_system_config.assert_not_called()

    async def test_operator_plane_resolves_via_prepare_with_system_config(self) -> None:
        """Operator plane (startup listener): system config + intent reach prepare()."""
        mock_model = AsyncMock()
        registry, calls = _recording_registry(mock_model)
        # Real config value object — the ADR-045 run-limit resolver (Task 3)
        # reads resolve_output_limit()/token_limit_profile from it.
        system_config = ResolvedModelConfig(
            provider_name="default",
            model_id="default",
            temperature=0.7,
            max_tokens=4096,
        )

        with (
            patch("narrare._app.dependencies.get_model_registry", return_value=registry),
            patch(
                "narrare._app.dependencies_services.build_system_default_config",
                return_value=system_config,
            ),
            patch("narrare_core.wiki.agent.WikiGenerationAgent") as mock_agent_cls,
            patch("narrare_core.wiki.service.WikiService"),
        ):
            from narrare.wiki.dependencies_core import build_core_wiki_service

            await build_core_wiki_service()

        assert len(calls) == 1
        assert calls[0]["config"] is system_config
        assert calls[0]["intent"] is LLMIntent.SUMMARIZE
        prepared = cast("PreparedModelCall", calls[0]["prepared"])
        mock_agent_cls.assert_called_once_with(model=prepared.model)

    async def test_factory_binds_prepared_settings_into_the_agent_path(self) -> None:
        """Task 2 wiring: the prepared settings/limits halves reach the
        agent run path. The factory wraps the concrete agent in the
        API-side ``PreparedWikiAgent`` binding adapter, so every
        ``generate_entity``/``generate_chapter`` call (driven by the core
        ``WikiService`` through ``WikiAgentProtocol``) forwards the
        prepared halves into the concrete agent calls."""
        mock_model = AsyncMock()
        registry, calls = _recording_registry(mock_model)
        config = _user_config()

        with (
            patch("narrare._app.dependencies.get_model_registry", return_value=registry),
            patch("narrare_core.wiki.agent.WikiGenerationAgent") as mock_agent_cls,
            patch("narrare_core.wiki.service.WikiService") as mock_svc_cls,
        ):
            # The behavioral half awaits the concrete agent's generate
            # methods through the adapter — make them awaitable.
            mock_agent_cls.return_value.generate_entity = AsyncMock()
            mock_agent_cls.return_value.generate_chapter = AsyncMock()

            from narrare.wiki.dependencies_core import build_core_wiki_service
            from narrare.wiki.prepared_wiki_agent import PreparedWikiAgent

            await build_core_wiki_service(config=config, api_key=_USER_KEY, base_url=_USER_BASE_URL)

        prepared = cast("PreparedModelCall", calls[0]["prepared"])
        # The factory hands the core service the binding adapter...
        bound_agent = mock_svc_cls.call_args.kwargs["agent"]
        assert isinstance(bound_agent, PreparedWikiAgent)
        # ...which wraps the concrete agent constructed with prepared.model.
        mock_agent_cls.assert_called_once_with(model=prepared.model)

        # Behavioral: generate calls through the adapter forward the
        # prepared halves into the concrete agent.
        from narrare_core.wiki.types import WikiGenerationDeps

        deps = WikiGenerationDeps(
            language="en",
            genre="Fantasy",
            entity_type="character",
            entity_name="Eldrin the Wise",
            entity_body="An ancient wizard.",
        )
        await bound_agent.generate_entity(deps)
        entity_call = mock_agent_cls.return_value.generate_entity.call_args
        assert entity_call.kwargs["model_settings"] is _SENTINEL_SETTINGS
        assert entity_call.kwargs["usage_limits"] is prepared.usage_limits
        await bound_agent.generate_chapter(deps)
        chapter_call = mock_agent_cls.return_value.generate_chapter.call_args
        assert chapter_call.kwargs["model_settings"] is _SENTINEL_SETTINGS
        assert chapter_call.kwargs["usage_limits"] is prepared.usage_limits

    async def test_prepared_settings_reach_the_agent_run_site(self) -> None:
        """Core pass-through landed (Task 1): the wiki run paths forward
        ``model_settings``/``usage_limits`` to the internal agent runs.

        Former CORE BOUNDARY pin: ``generate_entity`` /
        ``generate_chapter`` ran the internal agents without the kwargs.
        They now flow through; the factory-side wiring that passes the
        ``prepared`` triple halves is Task 2 (Backend).
        """
        from types import SimpleNamespace

        from pydantic_ai.models.test import TestModel
        from pydantic_ai.usage import UsageLimits

        from narrare_core.wiki.agent import WikiGenerationAgent
        from narrare_core.wiki.types import (
            WikiChapterOutput,
            WikiEntityOutput,
            WikiGenerationDeps,
        )

        deps = WikiGenerationDeps(
            language="en",
            genre="Fantasy",
            entity_type="character",
            entity_name="Eldrin the Wise",
            entity_body="An ancient wizard.",
        )
        sentinel_limits = UsageLimits(request_limit=7)

        # --- generate_entity: kwargs reach the internal NarrareAgent run ---
        agent = WikiGenerationAgent(model=TestModel())
        expected_entity = WikiEntityOutput(
            narrative_summary="Summary.", key_attributes=[], relationships=[]
        )
        stub_inner = AsyncMock(name="inner_agent")
        stub_inner.run = AsyncMock(return_value=SimpleNamespace(output=expected_entity))
        cast("Any", agent)._agent = stub_inner

        result = await agent.generate_entity(
            deps=deps,
            model_settings=_SENTINEL_SETTINGS,
            usage_limits=sentinel_limits,
        )

        assert result is expected_entity
        entity_call = stub_inner.run.call_args
        assert entity_call is not None
        assert entity_call.kwargs["model_settings"] is _SENTINEL_SETTINGS
        assert entity_call.kwargs["usage_limits"] is sentinel_limits

        # --- generate_chapter: kwargs reach WikiChapterGenerator.generate ---
        expected_chapter = WikiChapterOutput(
            narrative_summary="Summary.", key_events=[], entities_involved=[], themes=[]
        )
        with patch("narrare_core.wiki.agent.WikiChapterGenerator") as MockGenerator:
            chapter_agent = WikiGenerationAgent(model=TestModel())
            MockGenerator.return_value.generate = AsyncMock(return_value=expected_chapter)

            chapter_result = await chapter_agent.generate_chapter(
                deps=deps,
                model_settings=_SENTINEL_SETTINGS,
                usage_limits=sentinel_limits,
            )

        assert chapter_result is expected_chapter
        chapter_call = MockGenerator.return_value.generate.call_args
        assert chapter_call is not None
        assert chapter_call.kwargs["model_settings"] is _SENTINEL_SETTINGS
        assert chapter_call.kwargs["usage_limits"] is sentinel_limits
