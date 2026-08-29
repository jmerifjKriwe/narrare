"""Basic entry-path unit tests for the writing-session WebSocket route.

Tests the success paths (default + explicit ``session_id``) through the
ADR-084 ticket flow: identity is minted via the registry and the route
derives it from the consumed ticket. Guard-clause coverage (ticket gate,
origin, rate limiting) lives in ``test_router_sessions_auth.py`` and
``test_router_sessions_validation.py``.

Coverage target: **≥ 80%** on ``narrare.writing.router_sessions``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from narrare._app.config import Settings as AppSettings
from narrare.writing.router_sessions import interactive_session
from tests.unit.api.writing.ws_test_helpers import mint_ws_ticket

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_websocket() -> AsyncMock:
    """A mock WebSocket with standard headers for localhost origin."""
    ws = AsyncMock()
    ws.app = MagicMock(spec=["state"])
    ws.headers = {"origin": "http://localhost:3000"}
    return ws


@pytest.fixture
def chapter_id() -> UUID:
    """A unique chapter UUID per test."""
    return uuid4()


@pytest.fixture
def project_id() -> UUID:
    """A unique project UUID per test."""
    return uuid4()


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


async def test_success_path_calls_handler_handle(
    mock_websocket: AsyncMock,
    chapter_id: UUID,
    project_id: UUID,
) -> None:
    """The full success path wires dependencies and calls handler.handle().

    Validates the entire dependency chain is correctly assembled:
    - Ticket consumed → identity DERIVED from the registry record
    - Origin check passes
    - Rate limit check passes
    - All app.state services are resolved
    - Token limits are resolved from DB
    - Model routing resolves a ResolvedModelConfig
    - A handler is built and invoked with the correct arguments
    """
    # Create a realistic ResolvedModelConfig for the resolver to return
    from narrare.settings.token_limits.contracts import TokenLimitOverrides
    from narrare_core.llm.model_config import ResolvedModelConfig
    from narrare_core.llm.model_routing import ResolvedModel

    resolved_config = ResolvedModelConfig(
        provider_name="test-provider",
        model_id="test-model",
        temperature=0.7,
        max_tokens=4096,
    )
    resolved_model = ResolvedModel(
        config=resolved_config,
        api_key="test-key",
        source="user_default",
    )

    mock_token_limits = TokenLimitOverrides(
        output_limit=2048,
        ws_timeout=900,
    )

    # Set up all mocks
    mock_handler = AsyncMock()
    mock_db_session = AsyncMock()

    # Plain AsyncMock — no spec so __anext__ and aclose can be set directly
    mock_async_gen = AsyncMock()
    mock_async_gen.__anext__ = AsyncMock(return_value=mock_db_session)
    mock_async_gen.aclose = AsyncMock()

    mock_resolver = AsyncMock()
    mock_resolver.resolve = AsyncMock(return_value=resolved_model)

    mock_token_limits_instance = AsyncMock()
    mock_token_limits_instance.get_resolved_limits = AsyncMock(
        return_value=mock_token_limits,
    )

    with (
        patch("narrare._app.config.get_settings") as mock_get_settings,
        patch("narrare.writing.deps_ws.get_session_manager") as mock_get_session_manager,
        patch("narrare.writing.deps_ws.get_active_turn_registry") as mock_get_registry,
        patch("narrare.writing.deps_ws.get_turn_state") as mock_get_turn_state,
        patch("narrare.writing.deps_ws.get_session_control_service") as mock_get_control,
        patch("narrare._app.dependencies.get_model_registry") as mock_get_model_registry,
        patch("narrare._app.dependencies.get_composer") as mock_get_composer,
        patch("narrare._app.database.get_async_session") as mock_get_async_session,
        patch("narrare._app.dependencies_pipeline.get_invocation_pipeline") as mock_get_pipeline,
        patch(
            "narrare.settings.token_limits.service.TokenLimitsService",
        ) as mock_token_limits_cls,
        patch(
            "narrare._app.dependencies_services.get_model_routing_resolver",
        ) as mock_get_resolver,
        patch(
            "narrare.writing.ws_factory.build_writing_session_handler",
        ) as mock_build_handler,
        patch(
            "narrare_core.llm.run_limits.DefaultRunLimitResolver",
        ) as mock_run_limit_cls,
        # Ensure rate limit check passes
        patch(
            "narrare._app.rate_limits.AI_WS_LIMITER.try_acquire",
            return_value=True,
        ),
    ):
        # Configure the settings mock with all needed attributes
        mock_settings = MagicMock(spec=AppSettings)
        mock_settings.csrf_trusted_origins = ["http://localhost:3000"]
        mock_settings.default_max_tokens = 4096
        mock_settings.ws_idle_timeout_seconds = 900
        mock_settings.consistency_max_chapter_tokens = 2000
        mock_settings.consistency_max_kb_entries = 100
        mock_settings.default_max_selection_words = 2000
        mock_get_settings.return_value = mock_settings

        # Wire the function-call mocks (opaque DI return values)
        mock_get_session_manager.return_value = MagicMock(spec=[])
        mock_get_registry.return_value = MagicMock(spec=[])
        mock_get_turn_state.return_value = MagicMock(spec=[])
        mock_get_control.return_value = MagicMock(spec=[])
        mock_get_model_registry.return_value = MagicMock(spec=[])
        mock_get_composer.return_value = MagicMock(spec=[])
        mock_get_async_session.return_value = mock_async_gen

        # Wire the pipeline
        mock_get_pipeline.return_value = MagicMock(spec=[])

        # Wire the TokenLimitsService constructor
        mock_token_limits_cls.return_value = mock_token_limits_instance

        # Wire the model routing resolver
        mock_get_resolver.return_value = mock_resolver

        # Wire the handler factory
        mock_build_handler.return_value = mock_handler

        # Wire the RunLimitResolver constructor
        mock_run_limit_cls.return_value = MagicMock(spec=[])

        # Mint the ticket for the identity the DB mocks are wired for —
        # the route must DERIVE this id from the ticket (ADR-084).
        user_id = "00000000-0000-0000-0000-000000000001"
        token = mint_ws_ticket(user_id)
        await interactive_session(
            mock_websocket,
            chapter_id,
            token=token,
            project_id=project_id,
        )

    # Assert the handler was built with correct key collaborators
    mock_build_handler.assert_called_once()
    _call_kwargs = mock_build_handler.call_args.kwargs
    assert _call_kwargs["mode"] == "interactive_session"
    assert _call_kwargs["ws_idle_timeout"] == 900

    # Assert handler.handle() was invoked with the DERIVED identity
    mock_handler.handle.assert_awaited_once_with(
        mock_websocket,
        chapter_id,
        user_id,
        project_id,
        session_id=None,
    )

    # Assert the DB session was cleaned up
    mock_async_gen.aclose.assert_awaited_once()

    # Assert the function never sent an error or closed the socket
    mock_websocket.send_json.assert_not_called()
    mock_websocket.close.assert_not_called()


async def test_success_path_with_explicit_session_id(
    mock_websocket: AsyncMock,
    chapter_id: UUID,
    project_id: UUID,
) -> None:
    """When session_id is provided, it is forwarded to handler.handle().

    Covers the reconnect path (ADR-052): the reconnect presents a FRESH
    single-use ticket (the old one died with the previous connection).
    """
    from narrare.settings.token_limits.contracts import TokenLimitOverrides
    from narrare_core.llm.model_config import ResolvedModelConfig
    from narrare_core.llm.model_routing import ResolvedModel

    session_id = uuid4()
    resolved_model = ResolvedModel(
        config=ResolvedModelConfig(provider_name="test", model_id="test"),
    )

    mock_handler = AsyncMock()
    mock_db_session = AsyncMock()
    mock_async_gen = AsyncMock()
    mock_async_gen.__anext__ = AsyncMock(return_value=mock_db_session)
    mock_async_gen.aclose = AsyncMock()

    mock_resolver = AsyncMock()
    mock_resolver.resolve = AsyncMock(return_value=resolved_model)

    mock_token_instance = AsyncMock()
    mock_token_instance.get_resolved_limits = AsyncMock(
        return_value=TokenLimitOverrides(),
    )

    with (
        patch("narrare._app.config.get_settings") as mock_get_settings,
        patch("narrare.writing.deps_ws.get_session_manager"),
        patch("narrare.writing.deps_ws.get_active_turn_registry"),
        patch("narrare.writing.deps_ws.get_turn_state"),
        patch("narrare.writing.deps_ws.get_session_control_service"),
        patch("narrare._app.dependencies.get_model_registry"),
        patch("narrare._app.dependencies.get_composer"),
        patch("narrare._app.database.get_async_session", return_value=mock_async_gen),
        patch("narrare._app.dependencies_pipeline.get_invocation_pipeline"),
        patch(
            "narrare.settings.token_limits.service.TokenLimitsService",
            return_value=mock_token_instance,
        ),
        patch(
            "narrare._app.dependencies_services.get_model_routing_resolver",
            return_value=mock_resolver,
        ),
        patch(
            "narrare.writing.ws_factory.build_writing_session_handler",
            return_value=mock_handler,
        ),
        patch("narrare_core.llm.run_limits.DefaultRunLimitResolver"),
        patch(
            "narrare._app.rate_limits.AI_WS_LIMITER.try_acquire",
            return_value=True,
        ),
    ):
        mock_settings = MagicMock(spec=AppSettings)
        mock_settings.csrf_trusted_origins = ["http://localhost:3000"]
        mock_settings.default_max_tokens = 4096
        mock_settings.ws_idle_timeout_seconds = 1800
        mock_settings.consistency_max_chapter_tokens = 2000
        mock_settings.consistency_max_kb_entries = 100
        mock_settings.default_max_selection_words = 2000
        mock_get_settings.return_value = mock_settings

        user_id = str(uuid4())
        await interactive_session(
            mock_websocket,
            chapter_id,
            token=mint_ws_ticket(user_id),
            project_id=project_id,
            session_id=session_id,
        )

    mock_handler.handle.assert_awaited_once_with(
        mock_websocket,
        chapter_id,
        user_id,
        project_id,
        session_id=session_id,
    )
