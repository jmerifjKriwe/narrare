"""Regression tests for the ``WikiEventPublisherDep`` FastAPI dependency.

CI Action #495: every route that injects ``WikiEventPublisherDep`` answered
``422 {"loc": ["query", "request"], "msg": "Field required"}`` because the
dependency factory was declared as ``get_wiki_event_publisher(request: Any)``.
FastAPI resolves dependency parameters by TYPE, not by name: ``Any`` is not a
known injection type, so FastAPI treated ``request`` as a REQUIRED QUERY
PARAMETER — breaking every consumer route (chapters/router.py:30,
kb/dependencies_core.py:69, kb/dependencies_improve.py:18,
kb/dependencies_session.py:18, prompts/router.py:113, prompts/deps.py:82,
prompts/router_prompt_history.py:42/64/87/108).

These tests use a minimal FastAPI app + ``TestClient`` (no DB, no auth, no
LLM) to pin the DI contract: the dependency must resolve from ``app.state``
without demanding a ``request`` query parameter.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from narrare.events.publisher import EventPublisher, WikiEventPublisherDep


def _make_app() -> FastAPI:
    """Minimal app whose route injects ``WikiEventPublisherDep``."""
    app = FastAPI()

    @app.get("/probe")
    def probe(event_publisher: WikiEventPublisherDep) -> dict[str, bool]:
        return {"publisher_bound": event_publisher is not None}

    return app


class TestWikiEventPublisherDep:
    def test_wiki_event_publisher_dep_without_request_query_param_returns_200(
        self,
    ) -> None:
        """Route using the dependency works without a ``request`` query param.

        Regression for CI Action #495: before the fix FastAPI treated the
        ``Any``-annotated ``request`` parameter as a required query parameter
        and answered ``422`` with ``Field required``.
        """
        app = _make_app()

        with TestClient(app) as client:
            response = client.get("/probe")

        assert response.status_code == 200

    def test_wiki_event_publisher_dep_when_app_state_bound_returns_publisher(
        self,
    ) -> None:
        """A publisher bound on ``app.state`` is injected into the route."""
        app = _make_app()
        app.state.wiki_event_publisher = EventPublisher()

        with TestClient(app) as client:
            response = client.get("/probe")

        assert response.status_code == 200
        assert response.json() == {"publisher_bound": True}

    def test_wiki_event_publisher_dep_when_app_state_unbound_returns_none(
        self,
    ) -> None:
        """Unbound ``app.state`` degrades gracefully (RULE-11): dep is ``None``."""
        app = _make_app()

        with TestClient(app) as client:
            response = client.get("/probe")

        assert response.status_code == 200
        assert response.json() == {"publisher_bound": False}
