"""ADR-086 L21 integration pins — storyboard endpoints vs. the cascade.

Real-chain proofs for the lazy ``get_storyboard_service`` wiring
(planning routers call their factories INSIDE the endpoint body, so the
real factory runs on every request — no fake override involved):

- invalid body → 422 before any routing/novel work,
- valid body + nonexistent novel → 404 (the uid-scoped novel guard,
  relocated from the eager factory into the service's first-use path —
  same status as the eager world; the guard is preserved, not dropped,
  per the ADR-086 planning guard ruling).

Scope note (honest baseline): the storyboard factory is invoked inside
the endpoint body (post body-validation), so the 422 ordering pre-exists
for these REST endpoints — the pins document the contract under the
production lazy wiring; the resolution-timing proof lives in the unit
deferral tests (``tests/unit/api/planning/test_service_factory_wiring.py``
+ ``test_storyboard_lazy_resolution.py``). The preserved graceful
remap outcome (valid body + existing novel + unconfigured provider →
200 with heuristic stages) stays pinned by the pre-existing
``test_planning_api.py`` preview/confirm nodes running the real chain.
Mirrors ``tests/integration/planning/test_character_arc_lazy_resolution.py``
(ADR-086 L20 convention). New file: the pin belongs to the slice.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestStoryboardLazyResolutionIntegration:
    """ADR-086 L21: invalid body → 422; relocated guard → 404 for valid bodies."""

    async def test_remap_422_with_invalid_body_and_real_lazy_factory(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Invalid body → 422 under the real lazy wiring.

        The PLAN cascade is wired lazily, so body validation precedes any
        routing/novel work on the request path.
        """
        response = await client.post(
            f"/api/v1/planning/storyboard/{uuid4()}/remap",
            json={},  # new_structure missing → invalid body
            headers=auth_headers,
        )

        assert response.status_code == 422

    async def test_remap_404_guard_for_valid_body_nonexistent_novel(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Valid body + nonexistent novel → 404 (guard preserved).

        The uid-scoped novel guard relocated into the service's
        first-use path still raises ``NotFoundError("Novel")`` for valid
        bodies against nonexistent novels — before the routing cascade
        runs (gate-before-resolution ordering).
        """
        response = await client.post(
            f"/api/v1/planning/storyboard/{uuid4()}/remap",
            json={"new_structure": "five_act"},
            headers=auth_headers,
        )

        assert response.status_code == 404
