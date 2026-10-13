"""KB + wiki catalog entries (spec §3: validator-strict AI surfaces).

Wire formats mirror the REAL endpoints (verified 2026-10-12):
- POST /api/v1/novels/{id}/kb/extract/{chapter_id} — ExtractionOutput JSON
  (bulk extract lives at /kb/extract/bulk… and is excluded).
- POST /api/v1/novels/{id}/kb/entities/{entry_id}/improve —
  KBImproveAnalysisResponse JSON (…/improve/apply excluded).
- POST /api/v1/novels/{id}/wiki/summaries/{entity_id}/refresh —
  WikiRefreshResponse JSON (path param is UUID-typed: real UUID required;
  a successful regeneration answers status="fresh" like the real service).
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

WIKI_REFRESH_HAPPY = json.dumps(
    {
        "summary_id": "00000000-0000-0000-0000-0000000000d1",
        "status": "fresh",
        "message": "Summary refreshed successfully.",
    }
)

SPECS: tuple[RouteSpec, ...] = (
    RouteSpec(
        capability="kb_extraction",
        variant="happy",
        pattern="**/api/v1/novels/*/kb/extract/*",
        method="POST",
        body=KB_EXTRACTION_HAPPY,
        url_exclude="/extract/bulk",
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
)


def validate() -> None:
    """Spec §10 ratchet against the real app/core models."""
    from narrare.kb.improve_contracts import KBImproveAnalysisResponse
    from narrare.wiki.schemas import WikiRefreshResponse
    from narrare_core.agents.extraction_types import ExtractionOutput

    ExtractionOutput.model_validate_json(KB_EXTRACTION_HAPPY)
    KBImproveAnalysisResponse.model_validate_json(KB_IMPROVE_HAPPY)
    WikiRefreshResponse.model_validate_json(WIKI_REFRESH_HAPPY)
