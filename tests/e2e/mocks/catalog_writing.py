"""Writing-surface catalog entries: generation SSE + scene draft/refine.

Wire formats mirror the REAL endpoints (verified 2026-10-12):
- GET  /api/v1/writing/generation/{request_id}/stream — SSE:
  optional ``{"type": "context_meta", ...}`` first, then
  ``{"text": ...}`` chunks, final chunk carries ``is_final`` + ``usage``,
  terminated by ``data: [DONE]`` (apps/api/narrare/writing/router.py).
  The START POST is NOT mocked — the real backend creates the request row
  so accept/reject keep working; only the stream is deterministic.
- POST /api/v1/planning/scenes/{novel_id}/{chapter_id}/draft|refine — JSON
  (apps/api/narrare/planning/schemas_scenes.py).
"""

from __future__ import annotations

import json

from tests.e2e.mocks.catalog import RouteSpec, assert_sse_body_wellformed


def _sse(*events: str) -> str:
    return "".join(f"data: {event}\n\n" for event in events) + "data: [DONE]\n\n"


GENERATION_HAPPY_SSE = _sse(
    json.dumps({"type": "context_meta", "source": "e2e-mock", "word_count": 1420}),
    json.dumps({"text": "The harbour bell rang twice before dawn, "}),
    json.dumps({"text": "and Elara counted the strikes the way her mother had taught her."}),
    json.dumps(
        {
            "text": "Two strikes meant the tide gate would seal within the hour.",
            "is_final": True,
            "usage": {"prompt_tokens": 210, "completion_tokens": 48, "total_tokens": 258},
        }
    ),
)

GENERATION_ERROR_BODY = json.dumps({"detail": "e2e-mock: generation provider stream died"})

_SCENE_PROPOSAL = {
    "title": "Arrival at the Harbour Gate",
    "pov_character_ref": None,
    "location_ref": None,
    "present_characters": [],
    "purpose": "Establish Elara's deadline and the sealed gate.",
    "conflict": "The gatekeeper refuses passage without a writ.",
    "resolution": "Elara trades her mother's ring for a forged writ.",
    "beats": [
        "Elara arrives at dawn",
        "The gatekeeper bars the way",
        "The ring changes hands",
    ],
}

SCENE_DRAFT_HAPPY = json.dumps(
    {
        "proposals": [
            _SCENE_PROPOSAL,
            {
                "title": "The Forged Writ",
                "pov_character_ref": None,
                "location_ref": None,
                "present_characters": [],
                "purpose": "Show the cost of Elara's bargain.",
                "conflict": "The forgery names an authority the chapter never introduces.",
                "resolution": "Elara pockets the writ unanswered.",
                "beats": ["The gatekeeper studies the seal", "Elara lies about the seal's origin"],
            },
        ],
        "ai_unavailable": False,
    }
)

SCENE_REFINE_HAPPY = json.dumps({"proposal": _SCENE_PROPOSAL, "ai_unavailable": False})


SPECS: tuple[RouteSpec, ...] = (
    RouteSpec(
        capability="generation_stream",
        variant="happy",
        pattern="**/api/v1/writing/generation/*/stream",
        method="GET",
        content_type="text/event-stream",
        body=GENERATION_HAPPY_SSE,
    ),
    RouteSpec(
        capability="generation_stream",
        variant="error",
        pattern="**/api/v1/writing/generation/*/stream",
        method="GET",
        status=500,
        body=GENERATION_ERROR_BODY,
    ),
    RouteSpec(
        capability="scene_draft",
        variant="happy",
        pattern="**/api/v1/planning/scenes/*/*/draft",
        method="POST",
        body=SCENE_DRAFT_HAPPY,
    ),
    RouteSpec(
        capability="scene_refine",
        variant="happy",
        pattern="**/api/v1/planning/scenes/*/*/refine",
        method="POST",
        body=SCENE_REFINE_HAPPY,
    ),
)


def validate() -> None:
    """Spec §10 ratchet: scene JSONs validate against the real models; SSE is well-formed."""
    from narrare.planning.schemas_scenes import SceneDraftResponse, SceneRefineResponse

    SceneDraftResponse.model_validate_json(SCENE_DRAFT_HAPPY)
    SceneRefineResponse.model_validate_json(SCENE_REFINE_HAPPY)

    happy = SPECS[0]
    events = assert_sse_body_wellformed(happy.body)
    assert events[0]["type"] == "context_meta", "generation SSE must open with context_meta"
    assert any(e.get("is_final") is True for e in events), "missing is_final chunk"
