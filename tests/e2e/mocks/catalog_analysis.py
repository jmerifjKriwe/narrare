"""Analysis-surface catalog entries (spec §3: validator-strict AI surfaces).

Wire formats mirror the REAL endpoints (verified 2026-10-12):
- POST /api/v1/analysis/beta-reader?novel_id=… — JSON BetaReaderResponse
  (deep-dive is a sibling route and explicitly excluded here).
- POST /api/v1/analysis/coreference/{chapter_id} — SSE envelope events
  ``{"event": "result"|"done"|"error", …}`` + [DONE].
- POST /api/v1/analysis/character-voice/{novel_id} — SSE envelope events
  ``progress`` / one ``result`` per character / ``done``.
- POST /api/v1/consistency/check/stream?novel_id=… — SSE events
  ``{"type": "stage", …}`` then ``{"type": "result", …}`` + [DONE];
  errors are in-band ``{"type": "error", "message": …}`` (the real router
  emits exactly that shape — no ``error``/``is_final`` keys);
  the non-stream POST /consistency/check answers JSON directly.
  Stage vocabulary mirrors consistency_orchestrator.py:
  ``extracting_facts`` → ``checking_consistency`` → ``complete``.
- POST /api/v1/analysis/pov?novel_id=… — JSON POVResult
  (narrare_core.analysis.types); the panel's error branch maps 5xx to
  ``aiActions.errorConnection``.
Severity/category enums are REAL values (FeedbackSeverity/FeedbackCategory).
"""

from __future__ import annotations

import json

from tests.e2e.mocks.catalog import RouteSpec, assert_sse_body_wellformed


def _sse(*events: str) -> str:
    return "".join(f"data: {event}\n\n" for event in events) + "data: [DONE]\n\n"


BETA_READER_HAPPY = json.dumps(
    {
        "novel_id": "e2e-mock-novel",
        "chapter_ids": ["e2e-mock-chapter"],
        "total_word_count": 1024,
        "strengths": [
            {
                "category": "character",
                "title": "Elara's motivation is concrete",
                "description": "The ring trade ties her goal to a visible cost.",
                "text_excerpt": "the way her mother had taught her",
            }
        ],
        "feedback": [
            {
                "category": "pacing",
                "severity": "minor",
                "location": "paragraph 3",
                "title": "Gatekeeper exchange rushes the turn",
                "description": "The refusal flips to acceptance within two lines.",
                "suggestion": "Let Elara's first offer fail before the ring appears.",
                "text_excerpt": None,
            }
        ],
        "questions": [
            {
                "category": "plot",
                "location": "paragraph 5",
                "question": "Who issued the sealed writ Elara forges?",
                "context": "The forgery implies an authority the chapter never names.",
            }
        ],
        "overall": {
            "summary": "A focused opening scene with one clear objective.",
            "reader_engagement": 7,
            "emotional_impact": 6,
            "pacing_score": 6,
            "prose_quality": 7,
            "plot_progression": 6,
            "character_development": 7,
        },
        "analyzed_at": "2026-10-12T00:00:00Z",
        "cache_key": "e2e-mock-cache-key",
    }
)

_COREFERENCE_RESULT = {
    "chapter_id": "00000000-0000-0000-0000-0000000000c1",
    "clarity_score": 92.0,
    "summary": "Pronoun use is unambiguous; one speaker chain stays clear.",
    "resolutions": [
        {
            "pronoun": "she",
            "position": 14,
            "referent": "Elara",
            "confidence": 0.96,
            "is_ambiguous": False,
        }
    ],
    "character_mentions": [{"character_name": "Elara", "mentions": [0, 14], "is_pov": True}],
}

COREFERENCE_HAPPY_SSE = _sse(
    json.dumps({"event": "result", "result": _COREFERENCE_RESULT}),
    json.dumps({"event": "done", "is_final": True}),
)
COREFERENCE_ERROR_SSE = _sse(
    json.dumps({"event": "error", "error": "e2e-mock: coreference agent failed", "is_final": True}),
)

_CHARACTER_VOICE_RESULT = {
    "character_name": "Elara",
    "voice_analysis": {
        "formality": 0.3,
        "vocabulary_level": "moderate",
        "sentence_profile": "varied",
        "emotional_range": "expressive",
        "cultural_regional_markers": "harbour-town idioms",
        "voice_examples": ["Two strikes. The gate, then."],
        "voice_metrics": {
            "avg_sentence_length": 11.2,
            "sentence_length_std": 4.1,
            "type_token_ratio": 0.62,
            "avg_syllables_per_word": 1.4,
            "contraction_rate": 0.21,
            "verbal_tic_frequency": {"Two strikes": 0.08},
            "punctuation_profile": {"ellipsis": 0.02},
        },
    },
    "distinctiveness_notes": "Clipped countdown speech unlike the gatekeeper's formality.",
    "kb_entry_id": "00000000-0000-0000-0000-0000000000b1",
}

CHARACTER_VOICE_HAPPY_SSE = _sse(
    json.dumps({"event": "progress", "progress": "Found 1 speaking character"}),
    json.dumps({"event": "result", "result": _CHARACTER_VOICE_RESULT}),
    json.dumps({"event": "done", "is_final": True}),
)
CHARACTER_VOICE_ERROR_SSE = _sse(
    json.dumps(
        {
            "event": "error",
            "error": "e2e-mock: character-voice agent failed",
            "is_final": True,
        }
    ),
)

# Mirrors ConsistencyResponse.model_dump(mode="json") of the real route:
# the auto-computed severity counts are always on the wire.
_CONSISTENCY_RESULT = {
    "novel_id": "00000000-0000-0000-0000-0000000000a1",
    "chapter_ids": ["00000000-0000-0000-0000-0000000000c1"],
    "check_types": ["timeline", "character"],
    "issues": [],
    "error_count": 0,
    "warning_count": 0,
    "info_count": 0,
    "total_issues": 0,
    "overall_assessment": "Consistent",
    "analyzed_at": "2026-10-12T00:00:00Z",
}

# Stage payloads mirror the real orchestrator sequence
# (consistency_orchestrator.py): extracting_facts start → … →
# checking_consistency complete with facts_extracted/issues_found.
CONSISTENCY_HAPPY_SSE = _sse(
    json.dumps(
        {
            "type": "stage",
            "stage": "extracting_facts",
            "status": "start",
            "progress": 0.0,
            "message": "Extracting facts from chapters, KB, and timeline.",
        }
    ),
    json.dumps(
        {
            "type": "stage",
            "stage": "checking_consistency",
            "status": "complete",
            "progress": 1.0,
            "message": "Consistency checking complete.",
            "facts_extracted": 2,
            "issues_found": 0,
        }
    ),
    json.dumps({"type": "result", **_CONSISTENCY_RESULT}),
)
CONSISTENCY_ERROR_SSE = _sse(
    json.dumps(
        {
            "type": "error",
            "message": "e2e-mock: consistency pipeline failed",
        }
    ),
)

# Mirrors POVResult (narrare_core.analysis.types — field names verified
# in-tree 2026-10-18: POVScene.scene_index/start_position/end_position/
# pov_character/confidence; POVIssue.type/location/text/explanation/
# suggestion/severity; POVIssueType values are snake_case strings).
_POV_RESULT = {
    "scenes": [
        {
            "scene_index": 0,
            "start_position": 0,
            "end_position": 220,
            "pov_character": "Elara",
            "confidence": 0.93,
        }
    ],
    "issues": [
        {
            "type": "head_hop",
            "location": "chapter 1, paragraph 4",
            "text": "The gatekeeper doubted her story.",
            "explanation": "Mid-scene slip into the gatekeeper's interiority.",
            "suggestion": "Keep the gatekeeper externally observed.",
            "severity": "warning",
        }
    ],
    "pov_distribution": {"first_person": 1},
    "switch_count": 0,
    "analysis_type": "single_pov",
}

POV_HAPPY = json.dumps(_POV_RESULT)
POV_ERROR = json.dumps({"detail": "e2e-mock: pov agent failed"})

SPECS: tuple[RouteSpec, ...] = (
    RouteSpec(
        capability="beta_reader",
        variant="happy",
        pattern="**/api/v1/analysis/beta-reader*",
        method="POST",
        body=BETA_READER_HAPPY,
        url_exclude="/deep-dive",
    ),
    RouteSpec(
        capability="coreference_stream",
        variant="happy",
        pattern="**/api/v1/analysis/coreference/*",
        method="POST",
        content_type="text/event-stream",
        body=COREFERENCE_HAPPY_SSE,
    ),
    RouteSpec(
        capability="coreference_stream",
        variant="error",
        pattern="**/api/v1/analysis/coreference/*",
        method="POST",
        content_type="text/event-stream",
        body=COREFERENCE_ERROR_SSE,
    ),
    RouteSpec(
        capability="character_voice_stream",
        variant="happy",
        pattern="**/api/v1/analysis/character-voice/*",
        method="POST",
        content_type="text/event-stream",
        body=CHARACTER_VOICE_HAPPY_SSE,
    ),
    RouteSpec(
        capability="character_voice_stream",
        variant="error",
        pattern="**/api/v1/analysis/character-voice/*",
        method="POST",
        content_type="text/event-stream",
        body=CHARACTER_VOICE_ERROR_SSE,
    ),
    RouteSpec(
        capability="consistency_stream",
        variant="happy",
        pattern="**/api/v1/consistency/check/stream*",
        method="POST",
        content_type="text/event-stream",
        body=CONSISTENCY_HAPPY_SSE,
    ),
    RouteSpec(
        capability="consistency_stream",
        variant="error",
        pattern="**/api/v1/consistency/check/stream*",
        method="POST",
        content_type="text/event-stream",
        body=CONSISTENCY_ERROR_SSE,
    ),
    RouteSpec(
        capability="consistency_check",
        variant="happy",
        pattern="**/api/v1/consistency/check*",
        method="POST",
        body=json.dumps(_CONSISTENCY_RESULT),
        url_exclude="/stream",
    ),
    RouteSpec(
        capability="pov",
        variant="happy",
        pattern="**/api/v1/analysis/pov*",
        method="POST",
        body=POV_HAPPY,
    ),
    RouteSpec(
        capability="pov",
        variant="error",
        pattern="**/api/v1/analysis/pov*",
        method="POST",
        status=500,
        body=POV_ERROR,
    ),
)


def validate() -> None:
    """Spec §10 ratchet against the real app models."""
    from narrare.analysis.schemas import BetaReaderResponse
    from narrare.analysis.schemas_character_voice import CharacterVoiceStreamEvent
    from narrare.analysis.schemas_coreference import CoreferenceStreamEvent
    from narrare.consistency.schemas import ConsistencyResponse
    from narrare.consistency.stage_schemas import ConsistencyStageEvent
    from narrare_core.analysis.types import POVResult

    BetaReaderResponse.model_validate_json(BETA_READER_HAPPY)
    ConsistencyResponse.model_validate_json(json.dumps(_CONSISTENCY_RESULT))
    POVResult.model_validate_json(POV_HAPPY)

    for body in (COREFERENCE_HAPPY_SSE, COREFERENCE_ERROR_SSE):
        for event in assert_sse_body_wellformed(body):
            CoreferenceStreamEvent.model_validate(event)
    for body in (CHARACTER_VOICE_HAPPY_SSE, CHARACTER_VOICE_ERROR_SSE):
        for event in assert_sse_body_wellformed(body):
            CharacterVoiceStreamEvent.model_validate(event)

    for event in assert_sse_body_wellformed(CONSISTENCY_HAPPY_SSE):
        payload = {k: v for k, v in event.items() if k != "type"}
        if event["type"] == "stage":
            ConsistencyStageEvent.model_validate(payload)
        else:
            ConsistencyResponse.model_validate(payload)
