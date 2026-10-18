"""KB + wiki catalog entries (spec §3: validator-strict AI surfaces).

Wire formats mirror the REAL endpoints (verified 2026-10-12):
- POST /api/v1/novels/{id}/kb/extract/{chapter_id} — ExtractionOutput JSON
  (bulk extract lives at /kb/extract/bulk and the apply sibling at
  /kb/extract/apply; both are excluded so the glob only serves extraction).
- POST /api/v1/novels/{id}/kb/entities/{entry_id}/improve —
  KBImproveAnalysisResponse JSON (…/improve/apply excluded).
- POST /api/v1/novels/{id}/kb/sessions/{session_id}/interview —
  {session, question} aggregate exactly as router_sessions.py answers it
  (session = a KBCreationSession dump, question = KBAssistQuestionResponse).
  The fixture session mirrors a trimmed real character session (the FE's
  requestInterview reads only question.{field_key,question,reasoning}); the
  question's field_key is a REAL character-template field so the FE's
  follow-up answer PATCH hits an existing field.
- POST /api/v1/novels/{id}/wiki/summaries/{entity_id}/refresh —
  WikiRefreshResponse JSON (path param is UUID-typed: real UUID required;
  a successful regeneration answers status="fresh" like the real service).
- POST /api/v1/novels/{id}/kb/consistency-check —
  ConsistencyCheckResponse JSON (JSON endpoint, NOT /stream; category and
  severity literals use the real StrEnum values — the validate() ratchet
  fails loudly if ConsistencyCategory/WorldbuildingSeverity ever drift).
"""

from __future__ import annotations

import json

from tests.e2e.mocks.catalog import RouteSpec

KB_EXTRACTION_HAPPY = json.dumps(
    {
        "results": [
            {
                "item_type": "new_entity",
                "entity_type": "character",
                "name": "Elara Thornwind",
                "confidence": 0.93,
                "source_text": "Elara counted the strikes the way her mother had taught her.",
                "proposed_content": {"summary": "Counts bell strikes; keeps her mother's ring."},
            },
            {
                "item_type": "relationship",
                "name": "Elara → Gatekeeper",
                "confidence": 0.81,
                "source_text": "Elara trades her mother's ring for a forged writ.",
                "relationship_type": "bargains_with",
                "source_entity_name": "Elara Thornwind",
                "target_entity_name": "Gatekeeper",
            },
        ],
        "analysis_notes": "Two clear entities and one transactional relationship.",
    }
)

KB_IMPROVE_HAPPY = json.dumps(
    {
        "suggestions": [
            {
                "type": "expand",
                "target": "body",
                "description": "Anchor Elara's goal in the opening line.",
                "proposed_content": "Elara needs passage before the second bell seals the gate.",
                "related_entity_id": None,
                "related_entity_name": None,
                "confidence": 0.88,
                "reasoning": "The entry states urgency without a deadline.",
                "suggestion_id": 0,
            },
            {
                "type": "connect",
                "target": "Gatekeeper",
                "description": "Link the bargained ring to the Thornwind heirloom.",
                "proposed_content": None,
                "related_entity_id": "00000000-0000-0000-0000-0000000000b2",
                "related_entity_name": "Gatekeeper",
                "confidence": 0.74,
                "reasoning": "The ring trade creates a provenance edge.",
                "suggestion_id": 1,
            },
        ],
        "overall_assessment": "Solid scaffold; the entry needs one concrete goal.",
        "completeness_score": 0.62,
    }
)

KB_INTERVIEW_QUESTION_HAPPY = json.dumps(
    {
        "session": {
            "id": "00000000-0000-0000-0000-0000000000c1",
            "novel_id": "00000000-0000-0000-0000-0000000000a1",
            "user_id": "00000000-0000-0000-0000-0000000000b7",
            "entity_type": "character",
            "name": None,
            "status": "active",
            "fields": [
                {
                    "field_key": "age",
                    "label": "Age",
                    "field_type": "text",
                    "required": False,
                    "options": None,
                    "user_value": "34",
                    "ai_suggested_value": None,
                    "ai_reasoning": None,
                    "source": "user",
                    "final_value": "34",
                },
                {
                    "field_key": "personality.motivations",
                    "label": "Personality Motivations",
                    "field_type": "text",
                    "required": False,
                    "options": None,
                    "user_value": None,
                    "ai_suggested_value": None,
                    "ai_reasoning": None,
                    "source": "user",
                    "final_value": None,
                },
            ],
            "context_entries": [],
            "created_at": "2026-10-15T00:00:00Z",
            "updated_at": "2026-10-15T00:00:00Z",
        },
        "question": {
            "field_key": "personality.motivations",
            "question": "What does Maren want most — and what is she willing to trade for it?",
            "reasoning": (
                "Motivations is still empty; a concrete want anchors the personality group."
            ),
        },
    }
)

WIKI_REFRESH_HAPPY = json.dumps(
    {
        "summary_id": "00000000-0000-0000-0000-0000000000d1",
        "status": "fresh",
        "message": "Summary refreshed successfully.",
    }
)

KB_CONSISTENCY_CHECK_HAPPY = json.dumps(
    {
        "novel_id": "00000000-0000-0000-0000-0000000000a1",
        "entity_count": 2,
        "issues": [
            {
                "finding_index": 0,
                "category": "entry_internal",
                "entity_ids": ["00000000-0000-0000-0000-0000000000b1"],
                "entity_names": ["Elara Thornwind"],
                "description": "Goal stated without its deadline",
                "contradiction": "Urgency claimed but no time pressure exists",
                "suggested_resolution": "Anchor the goal to the second bell",
                "severity": "major",
                "confidence": 0.91,
            }
        ],
        "summary": {"entry_internal": 1, "asymmetry": 0, "cross_entity": 0},
        "suppressed_count": 0,
        "checked_at": "2026-10-15T00:00:00Z",
    }
)

_KB_ERROR_500 = json.dumps({"detail": "e2e-mock: request failed"})

SPECS: tuple[RouteSpec, ...] = (
    RouteSpec(
        capability="kb_extraction",
        variant="happy",
        pattern="**/api/v1/novels/*/kb/extract/*",
        method="POST",
        body=KB_EXTRACTION_HAPPY,
        url_exclude=("/extract/bulk", "/extract/apply"),
    ),
    RouteSpec(
        capability="kb_improve",
        variant="happy",
        pattern="**/api/v1/novels/*/kb/entities/*/improve*",
        method="POST",
        body=KB_IMPROVE_HAPPY,
        url_exclude="/improve/apply",
    ),
    RouteSpec(
        capability="wiki_refresh",
        variant="happy",
        pattern="**/api/v1/novels/*/wiki/summaries/*/refresh",
        method="POST",
        body=WIKI_REFRESH_HAPPY,
    ),
    RouteSpec(
        capability="kb_consistency_check",
        variant="happy",
        pattern="**/api/v1/novels/*/kb/consistency-check*",
        method="POST",
        body=KB_CONSISTENCY_CHECK_HAPPY,
    ),
    RouteSpec(
        capability="kb_assist_question",
        variant="happy",
        # Trailing '*' = query-string safety (Playwright matches the FULL
        # URL); a single '*' never crosses '/', so the sibling session
        # routes (GET session, PATCH fields/{key}, suggest, enhance,
        # complete) stay unmocked — only /interview is intercepted.
        pattern="**/api/v1/novels/*/kb/sessions/*/interview*",
        method="POST",
        body=KB_INTERVIEW_QUESTION_HAPPY,
    ),
    RouteSpec(
        capability="kb_consistency_check",
        variant="error",
        pattern="**/api/v1/novels/*/kb/consistency-check*",
        method="POST",
        status=500,
        body=_KB_ERROR_500,
    ),
    RouteSpec(
        capability="kb_improve",
        variant="error",
        pattern="**/api/v1/novels/*/kb/entities/*/improve*",
        method="POST",
        status=500,
        body=_KB_ERROR_500,
        url_exclude="/improve/apply",
    ),
    RouteSpec(
        capability="kb_extraction",
        variant="error",
        pattern="**/api/v1/novels/*/kb/extract/*",
        method="POST",
        status=500,
        body=_KB_ERROR_500,
        url_exclude=("/extract/bulk", "/extract/apply"),
    ),
    RouteSpec(
        capability="wiki_refresh",
        variant="error",
        pattern="**/api/v1/novels/*/wiki/summaries/*/refresh",
        method="POST",
        status=500,
        body=_KB_ERROR_500,
    ),
    RouteSpec(
        capability="kb_assist_question",
        variant="error",
        pattern="**/api/v1/novels/*/kb/sessions/*/interview*",
        method="POST",
        status=500,
        body=_KB_ERROR_500,
    ),
)


def validate() -> None:
    """Spec §10 ratchet against the real app/core models."""
    from narrare.kb.assist_contracts import KBAssistQuestionResponse
    from narrare.kb.consistency_contracts import ConsistencyCheckResponse
    from narrare.kb.improve_contracts import KBImproveAnalysisResponse
    from narrare.kb.session_models import KBCreationSession
    from narrare.wiki.schemas import WikiRefreshResponse
    from narrare_core.agents.extraction_types import ExtractionOutput

    ExtractionOutput.model_validate_json(KB_EXTRACTION_HAPPY)
    KBImproveAnalysisResponse.model_validate_json(KB_IMPROVE_HAPPY)
    WikiRefreshResponse.model_validate_json(WIKI_REFRESH_HAPPY)
    ConsistencyCheckResponse.model_validate_json(KB_CONSISTENCY_CHECK_HAPPY)

    # The interview aggregate has no single pydantic model (the route
    # handler returns a plain dict) — ratchet both halves separately.
    interview_aggregate = json.loads(KB_INTERVIEW_QUESTION_HAPPY)
    KBCreationSession.model_validate(interview_aggregate["session"])
    KBAssistQuestionResponse.model_validate(interview_aggregate["question"])
