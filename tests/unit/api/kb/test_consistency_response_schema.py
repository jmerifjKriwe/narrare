"""Unit tests for ConsistencyCheckResponse schema (CR-AUFG-03-10).

Verifies the ``suppressed_count`` field serializes correctly and defaults
to ``0`` so cached responses produced before the field existed still parse
(backwards compatibility).
"""

from __future__ import annotations

import json

from narrare.kb.consistency_contracts import ConsistencyCheckResponse


def _base_kwargs() -> dict:
    return {
        "novel_id": "novel-1",
        "entity_count": 5,
        "issues": [],
        "summary": {"entry_internal": 0, "asymmetry": 0, "cross_entity": 0},
        "checked_at": "2026-01-01T00:00:00Z",
    }


class TestSuppressedCountField:
    """Tests for the suppressed_count field on ConsistencyCheckResponse."""

    def test_field_defaults_to_zero_when_omitted(self) -> None:
        """Omitting suppressed_count yields 0 (backwards-compatible default)."""
        response = ConsistencyCheckResponse(**_base_kwargs())
        assert response.suppressed_count == 0

    def test_field_serializes_in_json_output(self) -> None:
        """suppressed_count appears in model_dump_json() as snake_case."""
        response = ConsistencyCheckResponse(**_base_kwargs(), suppressed_count=3)
        data = json.loads(response.model_dump_json())
        assert data["suppressed_count"] == 3

    def test_field_accepts_explicit_zero(self) -> None:
        """Explicit suppressed_count=0 round-trips."""
        response = ConsistencyCheckResponse(**_base_kwargs(), suppressed_count=0)
        assert response.suppressed_count == 0

    def test_cached_json_without_field_still_parses(self) -> None:
        """A cached response JSON (pre-field) parses with suppressed_count=0."""
        cached_json = json.dumps(_base_kwargs())  # no suppressed_count key
        response = ConsistencyCheckResponse.model_validate_json(cached_json)
        assert response.suppressed_count == 0

    def test_cached_json_with_field_parses_correctly(self) -> None:
        """A cached response JSON that includes the field round-trips."""
        payload = _base_kwargs()
        payload["suppressed_count"] = 7
        response = ConsistencyCheckResponse.model_validate_json(json.dumps(payload))
        assert response.suppressed_count == 7
