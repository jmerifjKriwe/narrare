"""ADR-086 L18 integration pins — session endpoints vs. the routing cascade.

Real-chain proofs for the lazy `get_kb_session_service` wiring (no service
override). Two structural facts are pinned here:

- pre-migration the eager factory's routing cascade raised at dependency
  time — BEFORE body validation — so an invalid body never yielded 422;
  with lazy wiring the same request yields 422 (validation first).
- non-AI session endpoints no longer require a provider at all: the
  cascade only resolves at the assist service's first use, so creating a
  session without any configured provider succeeds (eager world: 400
  NO_AI_PROVIDER from the factory).

The loud-400 on the AI-mediated assist endpoints (suggest/interview/
enhance) is NOT reachable over HTTP in a real-chain test: the factory
builds a per-request ``InMemorySessionCache`` (pre-existing wiring, eager
and lazy alike), so a session created in one request is unreachable in
the next — the session-ownership gate 404s before the cascade could run.
The loud-400 semantics are pinned at unit level
(``test_assist_service_lazy_resolution.py`` — un-swallowed
``ConfigurationError``) and at the handler level by the L16 extraction
pin (same global NarrareError handler, same error type).

Mirrors ``tests/integration/kb/test_kb_extraction_lazy_resolution.py``
(L16 convention).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestSessionLazyResolutionIntegration:
    """ADR-086 L18: validation → 422 first; non-AI endpoints never resolve."""

    async def test_create_session_422_with_invalid_body_and_real_lazy_factory(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Malformed body → 422 with the REAL factory (no override).

        The cascade is wired lazily, so ``entity_type: ""`` surfaces as
        422 regardless of provider/DB state — the dependency no longer
        preempts body validation. (Probed against a temporarily
        re-eagered factory: the same request then yields 404 — the
        cascade's novel guard raising at dependency time — body
        validation never ran. That dependency-time preemption is the
        ADR-086 defect class this node pins shut.)
        """
        resp = await client.post(
            f"/api/v1/novels/{uuid4()}/kb/sessions",
            json={"entity_type": ""},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_create_session_201_without_provider_and_real_lazy_factory(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Valid non-AI request + NO provider configured → 201.

        Real chain, NO factory patch: the cascade resolves nothing for
        session creation — the dependency-scope 400 of the eager world
        (NO_AI_PROVIDER before body validation) is gone, and the novel
        ownership gate is what now decides (a fresh user's owned novel
        passes it). (Probed against a temporarily re-eagered factory:
        the same request then yields 400 NO_AI_PROVIDER at dependency
        time — the eager behavior this node pins shut.)
        """
        novel_resp = await client.post(
            "/api/v1/novels",
            json={"title": "KB Session Lazy Novel", "writing_language": "en"},
            headers=auth_headers,
        )
        assert novel_resp.status_code == 201
        novel_id = novel_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/kb/sessions",
            json={"entity_type": "character"},
            headers=auth_headers,
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["entity_type"] == "character"
        assert body["novel_id"] == novel_id
