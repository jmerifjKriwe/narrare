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

CORE BOUNDARY (known gap, NOT patched here — RULE-01b, mirrors the
Task-6c ``WorldbuilderAgent.run_phase2`` finding): the
``WikiGenerationAgent`` run paths (``generate_entity`` /
``generate_chapter`` → ``WikiChapterGenerator``) invoke
``agent.run(...)`` WITHOUT ``model_settings``/``usage_limits`` kwargs,
so the settings half of the prepared triple cannot reach the LLM call
from this API-side factory. Fixing it requires the ~2-line core kwargs
pass-through in ``packages/core/narrare_core/wiki/agent.py`` (+ the
chapter generator) — route to the Core specialist. The resolution point
is migrated here; the run-site gap stays pinned by this boundary note
and swept in Task 7.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
        mock_config = MagicMock(spec=ResolvedModelConfig)

        with (
            patch("narrare._app.dependencies.get_model_registry", return_value=registry),
            patch(
                "narrare._app.dependencies_services.build_system_default_config",
                return_value=mock_config,
            ),
            patch("narrare_core.wiki.agent.WikiGenerationAgent") as mock_agent_cls,
            patch("narrare_core.wiki.service.WikiService"),
        ):
            from narrare.wiki.dependencies_core import build_core_wiki_service

            await build_core_wiki_service()

        assert len(calls) == 1
        assert calls[0]["config"] is mock_config
        assert calls[0]["intent"] is LLMIntent.SUMMARIZE
        prepared = cast("PreparedModelCall", calls[0]["prepared"])
        mock_agent_cls.assert_called_once_with(model=prepared.model)

    @pytest.mark.skip(
        "CORE BOUNDARY (RULE-01b): WikiGenerationAgent.generate_entity/"
        "generate_chapter run agent.run(...) without model_settings/"
        "usage_limits kwargs — the settings half of the prepared triple "
        "cannot flow from the API-side factory. 2-line core pass-through "
        "in packages/core/narrare_core/wiki/agent.py + agent_chapter.py; "
        "same follow-up class as the Task-6c WorldbuilderAgent.run_phase2 "
        "gap. Unskip when the core kwargs pass-through lands."
    )
    async def test_prepared_settings_reach_the_agent_run_site(self) -> None:
        """Placeholder pin: the settings triple must reach the wiki run site."""
        raise NotImplementedError
