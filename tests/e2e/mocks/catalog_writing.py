"""Writing-surface catalog entries: generation SSE + scene draft/refine.

Wire formats mirror the REAL endpoints (verified 2026-10-12):
- GET  /api/v1/writing/generation/{request_id}/stream — SSE:
  ``context_meta`` first (real ``ContextMetadata.to_dict()`` shape), then
  ``{"text": ...}`` chunks, final chunk carries ``is_final`` + ``usage``,
  terminated by ``data: [DONE]`` (apps/api/narrare/writing/router.py).
  The START POST is NOT mocked — the real backend creates the request row
  so accept/reject keep working; only the stream is deterministic.
  Variant ``truncated`` models the audit-M06 silent death: the stream ends
  WITHOUT ``is_final`` and WITHOUT an error event (Task 3's guard E2E).
- POST /api/v1/writing/chapters/{chapter_id}/rewrite — SSE (router_rewrite.py):
  ``context_meta`` event first (CR-07), ``<alternative label="…">…</alternative>``
  text chunks, final chunk ``is_final`` + ``usage``
  (frontend: ``packages/web/lib/api/generation-streams.ts`` ``streamRewrite``).
- POST /api/v1/writing/story-suggest/{novel_id} — SSE (router_story_suggest.py):
  one ``{"event": "suggestions", "suggestions": [...]}`` event,
  ``{"event": "done", "is_final": true}`` (frontend: story-suggest-stream.ts).
- POST /api/v1/writing/chapters/{chapter_id}/co-author — SSE (router_coauthor.py):
  ``context_meta`` event, ``{"text": ...}`` chunks, final event ``is_final``
  + ``usage`` + ``changes`` + ``total_changes`` + ``has_changes`` +
  ``reasoning`` + ``request_id`` (frontend: coauthor.ts ``streamCoAuthor``).
  The pattern ends at ``/co-author*`` — the trailing ``*`` eats the query
  string the frontend appends (``?novel_id=…``), while a single ``*`` cannot
  cross ``/``, so ``/co-author/apply`` and ``/co-author/feedback`` stay on
  the real backend (pinned by a unit test).
- POST /api/v1/planning/scenes/{novel_id}/{chapter_id}/draft|refine — JSON
  (apps/api/narrare/planning/schemas_scenes.py).
"""

from __future__ import annotations

import json

from tests.e2e.mocks.catalog import RouteSpec, assert_sse_body_wellformed


def _sse(*events: str) -> str:
    return "".join(f"data: {event}\n\n" for event in events) + "data: [DONE]\n\n"


# Real context_meta wire shape (CR-07): narrare_core.writing.context_models
# ContextMetadata.to_dict() — empty-KB values. The frontend ContextInspector
# reads character_names/location_names with .slice() during streaming, so a
# minimal/fabricated payload crashes the page (Task 7 live-run finding).
_CONTEXT_META: str = json.dumps(
    {
        "type": "context_meta",
        "kb_characters_count": 0,
        "kb_locations_count": 0,
        "kb_factions_count": 0,
        "kb_systems_count": 0,
        "kb_timelines_count": 0,
        "kb_relationships_count": 0,
        "kb_suggested_count": 0,
        "kb_pinned_count": 0,
        "recent_chapter_count": 1,
        "character_names": [],
        "location_names": [],
        "faction_names": [],
        "is_first_chapter": True,
        "has_user_preferences": False,
        "has_cross_session_context": False,
        "tone": "balanced",
        "story_structure": "",
        "timeline_position": "",
        "wiki_summaries_count": 0,
        "wiki_summaries_stale": 0,
        "total_budget_tokens": 120_000,
    }
)


GENERATION_HAPPY_SSE = _sse(
    _CONTEXT_META,
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

GENERATION_TRUNCATED_SSE = _sse(
    _CONTEXT_META,
)
# No text chunks, no is_final — the audit-M06 silent stream death.

REWRITE_HAPPY_SSE = _sse(
    _CONTEXT_META,
    json.dumps(
        {
            "text": '<alternative label="Tighter">The harbour bell rang twice; '
            "Elara counted each strike the way her mother had taught her.</alternative>"
        }
    ),
    json.dumps(
        {
            "text": '<alternative label="More sensory">Two strikes, iron on iron, '
            "and the taste of salt: the tide gate would seal within the hour.</alternative>"
        }
    ),
    json.dumps(
        {
            "text": "",
            "is_final": True,
            "usage": {"prompt_tokens": 150, "completion_tokens": 40, "total_tokens": 190},
        }
    ),
)

REWRITE_ERROR_BODY = json.dumps({"detail": "e2e-mock: rewrite provider stream died"})

_STORY_SUGGESTIONS = [
    {
        "type": "plot_development",
        "title": "The writ names a rival house",
        "description": "The forged writ Elara bought carries the seal of the house "
        "that ruined her family.",
        "connection": "Explains why she hesitates at the gate she fought to reach.",
    },
    {
        "type": "character_moment",
        "title": "Elara counts strikes",
        "description": "Her mother's counting habit becomes the beat that calms her "
        "before the bargain.",
        "connection": "Pays off the opening line about the harbour bell.",
    },
    {
        "type": "world_detail",
        "title": "The tide gate law",
        "description": "City law seals the gate for the first hour after the bell; "
        "no writ can override it.",
        "connection": "Raises the stakes of the deadline established in chapter one.",
    },
]

STORY_SUGGEST_HAPPY_SSE = _sse(
    json.dumps({"event": "suggestions", "suggestions": _STORY_SUGGESTIONS}),
    json.dumps({"event": "done", "is_final": True}),
)

STORY_SUGGEST_ERROR_BODY = json.dumps({"detail": "e2e-mock: story-suggest provider died"})

_COAUTHOR_CHANGE = {
    # ChangeDetail.id is uuid.UUID (schemas_coauthor.py) — a real UUID string.
    "id": "00000000-0000-0000-0000-00000000c0a1",
    "change_type": "word_choice",
    "original_text": "counted the strikes",
    "revised_text": "counted each strike",
    "index": 0,
}

COAUTHOR_HAPPY_SSE = _sse(
    _CONTEXT_META,
    json.dumps({"text": "The harbour bell rang twice before dawn. "}),
    json.dumps({"text": "Elara counted each strike, tasting salt on the wind."}),
    json.dumps(
        {
            "text": "",
            "is_final": True,
            "usage": {"prompt_tokens": 180, "completion_tokens": 52, "total_tokens": 232},
            "changes": [_COAUTHOR_CHANGE],
            "total_changes": 1,
            "has_changes": True,
            "reasoning": "Tightens the image and adds a sensory anchor.",
            "request_id": "e2e-mock-coauthor-1",
        }
    ),
)

COAUTHOR_ERROR_BODY = json.dumps({"detail": "e2e-mock: co-author provider stream died"})


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
    RouteSpec(
        capability="generation_stream",
        variant="truncated",
        pattern="**/api/v1/writing/generation/*/stream",
        method="GET",
        content_type="text/event-stream",
        body=GENERATION_TRUNCATED_SSE,
    ),
    RouteSpec(
        capability="rewrite_stream",
        variant="happy",
        pattern="**/api/v1/writing/chapters/*/rewrite*",
        method="POST",
        content_type="text/event-stream",
        body=REWRITE_HAPPY_SSE,
    ),
    RouteSpec(
        capability="rewrite_stream",
        variant="error",
        pattern="**/api/v1/writing/chapters/*/rewrite*",
        method="POST",
        status=500,
        body=REWRITE_ERROR_BODY,
    ),
    RouteSpec(
        capability="story_suggest",
        variant="happy",
        pattern="**/api/v1/writing/story-suggest/*",
        method="POST",
        content_type="text/event-stream",
        body=STORY_SUGGEST_HAPPY_SSE,
    ),
    RouteSpec(
        capability="story_suggest",
        variant="error",
        pattern="**/api/v1/writing/story-suggest/*",
        method="POST",
        status=500,
        body=STORY_SUGGEST_ERROR_BODY,
    ),
    RouteSpec(
        capability="coauthor_stream",
        variant="happy",
        pattern="**/api/v1/writing/chapters/*/co-author*",
        method="POST",
        content_type="text/event-stream",
        body=COAUTHOR_HAPPY_SSE,
    ),
    RouteSpec(
        capability="coauthor_stream",
        variant="error",
        pattern="**/api/v1/writing/chapters/*/co-author*",
        method="POST",
        status=500,
        body=COAUTHOR_ERROR_BODY,
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

    # Drift ratchet: the context_meta payload must be exactly the real
    # ContextMetadata wire shape (unknown/missing keys fail) — the FE
    # ContextInspector slices its name arrays during streaming (Task 7).
    from narrare_core.writing.context_models import ContextMetadata

    ContextMetadata(**{k: v for k, v in events[0].items() if k != "type"})

    truncated = next(
        s for s in SPECS if s.capability == "generation_stream" and s.variant == "truncated"
    )
    truncated_events = assert_sse_body_wellformed(truncated.body)
    assert truncated_events[0]["type"] == "context_meta", (
        "truncated SSE must open with context_meta"
    )
    assert not any(e.get("is_final") for e in truncated_events), "truncated must lack is_final"

    rewrite = next(s for s in SPECS if s.capability == "rewrite_stream" and s.variant == "happy")
    rewrite_events = assert_sse_body_wellformed(rewrite.body)
    rewrite_text = "".join(str(e.get("text") or "") for e in rewrite_events)
    assert rewrite_text.count("<alternative label=") == rewrite_text.count("</alternative>") >= 1

    from narrare_core.agents.story_suggest_types import StorySuggestOutput

    suggest = next(s for s in SPECS if s.capability == "story_suggest" and s.variant == "happy")
    suggest_events = assert_sse_body_wellformed(suggest.body)
    suggestions_event = next(e for e in suggest_events if e.get("event") == "suggestions")
    StorySuggestOutput.model_validate({"suggestions": suggestions_event["suggestions"]})

    from narrare.writing.schemas_coauthor import ChangeDetail

    coauthor = next(s for s in SPECS if s.capability == "coauthor_stream" and s.variant == "happy")
    coauthor_events = assert_sse_body_wellformed(coauthor.body)
    assert coauthor_events[0]["type"] == "context_meta", "co-author SSE must open with context_meta"
    coauthor_final = coauthor_events[-1]
    assert coauthor_final.get("is_final") is True and coauthor_final.get("has_changes") is True
    for change in coauthor_final["changes"]:
        ChangeDetail.model_validate(change)
