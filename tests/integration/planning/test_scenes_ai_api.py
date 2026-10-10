"""Integration tests for the scene-plan AI endpoints (PLAN-001 T8).

POST ``/planning/scenes/{novel_id}/{chapter_id}/draft`` and ``/refine``:
happy paths through the REAL factory + REAL PromptComposer (governed
T7 templates resolve at the HTTP layer — INFRA-013 runtime evidence),
with the routing-resolver and model-registry seams patched (no provider
seeding, no LLM — RULE-01b). Graceful no-provider degradation is pinned
against the REAL cascade (fresh test user → ``ConfigurationError``).

Split from ``test_scenes_api.py`` for the 400-line test-file limit
(RULE-04). Zero-write proof: the aggregate is unchanged after a draft.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from tests.integration.planning._scenes_api_helpers import (
    _seed_foreign_users_novel,
    _seed_scene,
)

if TYPE_CHECKING:
    import pytest
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

_PROPOSED_SCENE: dict[str, Any] = {
    "title": "The Ambush at the Gate",
    "pov_character_name": "John Smith",
    "location_name": "The Castle",
    "present_characters": [{"name": "John Smith", "goal": "wants to warn the guard"}],
    "purpose": "John must reach the gate before dawn.",
    "conflict": "Mara blocks the path.",
    "resolution": "John talks his way past but at a cost.",
    "beats": ["John reaches the gate", "The horn sounds"],
}


def _tool_response(payload: dict[str, Any]) -> ModelResponse:
    """FunctionModel response carrying a final_result structured tool call."""
    return ModelResponse(parts=[ToolCallPart(tool_name="final_result", args=json.dumps(payload))])


class _FakeRoutingResolver:
    """Stands in for ``ModelRoutingResolverImpl`` — canned PLAN resolution.

    The real cascade raises ``ConfigurationError`` in the test environment
    (no provider rows); the seam proves the post-resolution HTTP contract
    without provider seeding.
    """

    async def resolve(self, intent: Any, user_id: Any, novel_id: Any) -> ResolvedModel:
        del intent, user_id, novel_id  # canned outcome
        return ResolvedModel(
            config=ResolvedModelConfig(provider_name="zai", model_id="test-model", temperature=0.7),
            api_key=None,
            base_url=None,
            source="integration-test",
        )


class _FakeModelRegistry:
    """Async ``prepare()`` seam returning a FunctionModel-backed triple."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    async def prepare(self, _config: Any, **_kw: Any) -> SimpleNamespace:
        model = FunctionModel(lambda _messages, _info: _tool_response(self._payload))
        return SimpleNamespace(model=model, model_settings=None, usage_limits=None)


class TestScenePlanAiGenerators:
    """POST draft/refine — zero-write generators, graceful degradation.

    Happy paths patch the factory's resolver/registry seams (both are
    imported into the factory's namespace) and keep the REAL
    PromptComposer, so the governed ``scene_plan_draft`` /
    ``scene_plan_refine`` templates resolve through the real cascade at
    the HTTP layer (INFRA-013 runtime-adoption evidence). FunctionModel
    fakes only the LLM boundary; the agent → structured-output path is
    unit-tested in ``tests/unit/api/planning/test_scene_ai_service.py``.
    """

    async def test_draft_returns_proposals_without_ids_and_writes_nothing(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_and_chapter: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        novel_id = novel_and_chapter["novel_id"]
        chapter_id = novel_and_chapter["chapter_id"]
        aggregate_url = f"/api/v1/planning/scenes/{novel_id}/{chapter_id}"
        monkeypatch.setattr(
            "narrare.planning._scene_ai_factory.get_model_routing_resolver",
            lambda _session: _FakeRoutingResolver(),
        )
        monkeypatch.setattr(
            "narrare.planning._scene_ai_factory.get_model_registry",
            lambda: _FakeModelRegistry({"scenes": [_PROPOSED_SCENE]}),
        )
        before = (await client.get(aggregate_url, headers=auth_headers)).json()

        resp = await client.post(
            f"{aggregate_url}/draft",
            json={
                "structure_type": "three_act",
                "outline_notes": "Escape sequence.",
                "chapter_summary": "John races to the gate.",
                "neighbor_summaries": "Prev: John flees.",
                "instruction": "Plan 3 tense scenes.",
                "scene_count": 3,
            },
            headers=auth_headers,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["ai_unavailable"] is False
        assert len(body["proposals"]) == 1
        proposal = body["proposals"][0]
        # Proposals carry NO id — the client assigns UUIDs on insert.
        assert "id" not in proposal
        assert proposal["title"] == "The Ambush at the Gate"
        assert proposal["pov_character_ref"]["name"] == "John Smith"
        assert proposal["pov_character_ref"]["id"] is None
        assert proposal["beats"] == ["John reaches the gate", "The horn sounds"]
        # ZERO DB writes: no scene rows were created or mutated by the
        # draft (version_updated_at is a per-request derived value on an
        # empty aggregate, so the envelope is not comparable).
        after = (await client.get(aggregate_url, headers=auth_headers)).json()
        assert after["scenes"] == before["scenes"]

    async def test_refine_returns_single_proposal(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_and_chapter: dict[str, str],
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        novel_id = novel_and_chapter["novel_id"]
        chapter_id = novel_and_chapter["chapter_id"]
        await _seed_scene(db_session, chapter_id, 1, title="The Ambush at the Gate")
        monkeypatch.setattr(
            "narrare.planning._scene_ai_factory.get_model_routing_resolver",
            lambda _session: _FakeRoutingResolver(),
        )
        monkeypatch.setattr(
            "narrare.planning._scene_ai_factory.get_model_registry",
            lambda: _FakeModelRegistry({"scene": _PROPOSED_SCENE}),
        )
        url = f"/api/v1/planning/scenes/{novel_id}/{chapter_id}"
        # Carried scene ROUND-TRIPS a fetched aggregate (client timestamps).
        carried = (await client.get(url, headers=auth_headers)).json()["scenes"][0]

        resp = await client.post(
            f"{url}/refine",
            json={
                "scene": carried,
                "prev_scene_summary": "John flees the city.",
                "next_scene_summary": "The gate falls.",
                "chapter_summary": "John races to the gate.",
                "instruction": "Make the conflict sharper.",
            },
            headers=auth_headers,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["ai_unavailable"] is False
        assert body["proposal"] is not None
        assert "id" not in body["proposal"]
        assert body["proposal"]["title"] == "The Ambush at the Gate"

    async def test_draft_without_provider_degrades_gracefully_http_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_and_chapter: dict[str, str],
    ) -> None:
        """Real cascade, no provider rows → 200 + ``ai_unavailable`` (never 5xx)."""
        novel_id = novel_and_chapter["novel_id"]
        chapter_id = novel_and_chapter["chapter_id"]

        resp = await client.post(
            f"/api/v1/planning/scenes/{novel_id}/{chapter_id}/draft",
            json={"instruction": "Plan 3 tense scenes."},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["ai_unavailable"] is True
        assert body["proposals"] == []

    async def test_refine_without_provider_degrades_gracefully_http_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_and_chapter: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        novel_id = novel_and_chapter["novel_id"]
        chapter_id = novel_and_chapter["chapter_id"]
        await _seed_scene(db_session, chapter_id, 1, title="Scene A")
        url = f"/api/v1/planning/scenes/{novel_id}/{chapter_id}"
        carried = (await client.get(url, headers=auth_headers)).json()["scenes"][0]

        resp = await client.post(
            f"{url}/refine",
            json={"scene": carried, "instruction": "Make it sharper."},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["ai_unavailable"] is True
        assert body["proposal"] is None

    async def test_draft_foreign_users_novel_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
    ) -> None:
        foreign_novel_id, foreign_chapter_id = await _seed_foreign_users_novel(db_session)

        resp = await client.post(
            f"/api/v1/planning/scenes/{foreign_novel_id}/{foreign_chapter_id}/draft",
            json={"instruction": "Plan scenes."},
            headers=auth_headers,
        )

        assert resp.status_code == 404

    async def test_draft_invalid_body_returns_422_before_routing(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Lazy wiring pin: body validation precedes any routing/novel work."""
        resp = await client.post(
            f"/api/v1/planning/scenes/{uuid.uuid4()}/{uuid.uuid4()}/draft",
            json={"scene_count": "many"},
            headers=auth_headers,
        )

        assert resp.status_code == 422
