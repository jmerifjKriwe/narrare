"""Cross-layer identifier contract regression (CR-AUFG-07-24).

This is the platform cross-layer gate for the feedback identifier policy. It
validates that the backend Pydantic ``FeedbackRequest`` schema accepts the
canonical payload shape that each frontend rating surface emits via
``buildFeedbackRequest`` (``packages/web/lib/ai-rating/build-feedback.ts``).

NOT an MSW test — uses real Pydantic validation against the live backend schema
to catch contract drift between the frontend TypeScript types and the Python API
boundary (RULE-17 cross-layer contract).

Identifier policy (CR-AUFG-07-24) enforced here:
  - non-UUID ``source_id`` + ``source_type`` -> ACCEPTED (backend derives uuid5)
  - non-UUID ``suggestion_id`` -> REJECTED (field is ``uuid.UUID | None``)
  - both ``source_id`` and ``suggestion_id`` missing -> REJECTED
  - UUID ``suggestion_id`` alone -> ACCEPTED (back-compat)

Regression guard: before the CR-AUFG-07-24 implementation the schema had no
``source_id`` field, so every non-UUID payload in the parametrized acceptance
table would have failed ``_require_identifier``. This test fails if the
``source_id`` field or the identifier validator is removed or weakened.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from narrare.memory.schemas import FeedbackRequest

# Canonical per-surface payloads matching ``buildFeedbackRequest`` output.
#
# Each ``source_id`` is a realistic NON-UUID value that the corresponding
# frontend adapter actually emits (change id, message id, field key, numeric
# id coerced to string). If any of these is rejected by the backend schema,
# the cross-layer contract is broken (RULE-17).
#
# Mirrors the five adapters in ``packages/web/lib/ai-rating/adapters/``:
#   coauthor.ts   -> change.id         (e.g. "change-7")
#   chat.ts       -> messageId         (e.g. "msg-42")
#   kb-field.ts   -> field.field_key   (e.g. "entry-title")
#   kb-enhance.ts -> enhancement.field_key (e.g. "protagonist.name")
#   kb-improve.ts -> String(suggestion_id) (e.g. "3")
_SURFACE_RATING_PAYLOADS = [
    pytest.param("co_author_change", "change-7", "co_author", id="co_author"),
    pytest.param("chat_message", "msg-42", "chat_assistant", id="chat"),
    pytest.param("kb_field_suggest", "entry-title", "kb_field_suggest", id="kb_field"),
    pytest.param("kb_enhance_field", "protagonist.name", "kb_enhance", id="kb_enhance"),
    pytest.param("kb_improve_suggestion", "3", "kb_improve", id="kb_improve"),
]


class TestFeedbackIdentifierContractAcrossSurfaces:
    """All five rating surfaces produce payloads the backend Pydantic schema accepts."""

    @pytest.mark.parametrize("source_type,source_id,intent", _SURFACE_RATING_PAYLOADS)
    def test_backend_accepts_frontend_surface_payload(
        self,
        source_type: str,
        source_id: str,
        intent: str,
    ) -> None:
        """Each frontend adapter's canonical (source_id, source_type) pair must
        pass backend Pydantic validation without a suggestion_id.

        This is the exact payload shape ``buildFeedbackRequest`` serializes when
        the surface id is non-UUID: ``suggestion_id`` is omitted (undefined
        dropped by JSON.stringify), ``source_id`` carries the raw surface id.
        """
        req = FeedbackRequest(
            action="accept",
            source_id=source_id,
            source_type=source_type,  # type: ignore[arg-type]
            intent=intent,
            suggestion_text="Example suggestion text.",
            rating=5,
            context={},
            project_id=uuid4(),
        )
        assert req.source_id == source_id
        assert req.source_type == source_type
        assert req.suggestion_id is None

    @pytest.mark.parametrize("source_type,source_id,intent", _SURFACE_RATING_PAYLOADS)
    def test_surface_payload_serializes_through_dict_roundtrip(
        self,
        source_type: str,
        source_id: str,
        intent: str,
    ) -> None:
        """Simulate JSON wire transport: dict -> model_dump(exclude_none) -> model.

        ``buildFeedbackRequest`` omits ``suggestion_id`` (undefined) so the wire
        payload has no ``suggestion_id`` key. Pydantic must accept the round-trip.
        """
        original = FeedbackRequest(
            action="reject",
            source_id=source_id,
            source_type=source_type,  # type: ignore[arg-type]
            intent=intent,
            suggestion_text="Another example.",
            rating=2,
            context={"rating_reason": "off-tone"},
            project_id=uuid4(),
        )
        wire = original.model_dump(mode="json", exclude_none=True)
        # suggestion_id is None and excluded; source_id must survive the wire.
        assert "suggestion_id" not in wire
        assert wire["source_id"] == source_id

        rehydrated = FeedbackRequest.model_validate(wire)
        assert rehydrated.source_id == source_id
        assert rehydrated.source_type == source_type
        assert rehydrated.suggestion_id is None


class TestFeedbackIdentifierPolicy:
    """The identifier-policy invariants from CR-AUFG-07-24 (schema-level)."""

    def test_non_uuid_suggestion_id_rejected(self) -> None:
        """Non-UUID suggestion_id must be rejected: the field is uuid.UUID | None."""
        with pytest.raises(ValidationError):
            FeedbackRequest(
                action="accept",
                suggestion_id="not-a-uuid",  # type: ignore[arg-type]  # intentional invalid
                intent="write",
                suggestion_text="text",
                project_id=uuid4(),
            )

    def test_both_identifiers_missing_rejected(self) -> None:
        """Neither suggestion_id nor source_id supplied must be rejected."""
        with pytest.raises(ValidationError):
            FeedbackRequest(
                action="accept",
                intent="write",
                suggestion_text="text",
                project_id=uuid4(),
            )

    def test_source_id_without_source_type_rejected(self) -> None:
        """source_id alone (without source_type) must be rejected."""
        with pytest.raises(ValidationError):
            FeedbackRequest(
                action="accept",
                source_id="change-7",
                intent="write",
                suggestion_text="text",
                project_id=uuid4(),
            )

    def test_uuid_suggestion_id_alone_accepted_backcompat(self) -> None:
        """Existing callers that send only a UUID suggestion_id still work."""
        suggestion_uuid = uuid4()
        req = FeedbackRequest(
            action="accept",
            suggestion_id=suggestion_uuid,
            intent="write",
            suggestion_text="text",
            project_id=uuid4(),
        )
        assert req.suggestion_id == suggestion_uuid
        assert req.source_id is None

    def test_non_uuid_source_id_with_source_type_accepted(self) -> None:
        """The canonical CR-AUFG-07-24 path: non-UUID source_id + source_type."""
        req = FeedbackRequest(
            action="accept",
            source_id="msg-42",
            source_type="chat_message",  # type: ignore[arg-type]
            intent="chat_assistant",
            suggestion_text="text",
            project_id=uuid4(),
        )
        assert req.source_id == "msg-42"
        assert req.suggestion_id is None
