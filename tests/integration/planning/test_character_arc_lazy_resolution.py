"""ADR-086 L20 integration pins — character-arc endpoint vs. the cascade.

Real-chain proofs for the lazy ``get_character_arc_service`` wiring
(planning routers call their factories INSIDE the endpoint body, so the
real factory runs on every request — no fake override involved):

- invalid body → 422 before any routing/novel work,
- valid body + nonexistent novel → 404 (the uid-scoped novel guard,
  relocated from the eager factory into the service's first-use path —
  same status as the eager world; the guard is preserved, not dropped,
  per the ADR-086 planning guard ruling).

Scope note (honest baseline): the character-arc factory is invoked
inside the endpoint body (post body-validation), so the 422 ordering
pre-exists for this REST endpoint — the pin documents the contract under
the production lazy wiring; the resolution-timing proof lives in the
unit deferral tests
(``tests/unit/api/planning/test_character_arc_lazy_resolution.py``).
The 404 pin proves the relocated guard still fires for valid bodies
against nonexistent novels. Mirrors
``tests/integration/writing/test_style_variant_lazy_resolution.py``
(ADR-086 L35 convention). New file: the pin belongs to the slice.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestCharacterArcLazyResolutionIntegration:
    """ADR-086 L20: invalid body → 422; relocated guard → 404 for valid bodies."""

    async def test_character_arc_422_with_invalid_body_and_real_lazy_factory(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Invalid body → 422 under the real lazy wiring.

        The PLAN cascade is wired lazily and the novel guard moved into
        the service's first-use path, so body validation precedes any
        routing/novel work on the request path.
        """
        response = await client.post(
            f"/api/v1/planning/character-arc/{uuid4()}",
            json={},  # character_name missing (min_length=1) → invalid body
            headers=auth_headers,
        )

        assert response.status_code == 422

    async def test_character_arc_404_guard_for_valid_body_nonexistent_novel(
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
            f"/api/v1/planning/character-arc/{uuid4()}",
            json={
                "character_name": "Lyra",
                "character_current_state": "A timid orphan",
                "character_goal_state": "A confident leader",
            },
            headers=auth_headers,
        )

        assert response.status_code == 404
