"""Static recovery invariants for the writing-session WebSocket route."""

from __future__ import annotations

import inspect

from narrare.writing.router_sessions import interactive_session


def test_interactive_session_accepts_session_id_query_param() -> None:
    """Reconnect can identify the session via ?session_id=... (ADR-052)."""
    assert "session_id" in inspect.signature(interactive_session).parameters


def test_interactive_session_does_not_construct_per_connection_cache() -> None:
    """Route must use shared app.state cache, not a new cache per connection."""
    source = inspect.getsource(interactive_session)
    assert "InMemorySessionCache" not in source
    assert "get_session_manager" in source
