"""Unit tests for memory schemas — Pydantic model validation."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from narrare.memory.schemas import (
    AnalyzeRequest,
    FeedbackRequest,
    FeedbackResponse,
    ResetResponse,
)


class TestFeedbackRequest:
    def test_valid_accept_action(self) -> None:
        req = FeedbackRequest(
            action="accept",
            suggestion_id=uuid4(),
            intent="write",
            suggestion_text="Good text",
            project_id=uuid4(),
        )
        assert req.action == "accept"

    def test_valid_reject_action(self) -> None:
        req = FeedbackRequest(
            action="reject",
            suggestion_id=uuid4(),
            intent="write",
            suggestion_text="Bad text",
            project_id=uuid4(),
        )
        assert req.action == "reject"

    def test_valid_modify_action(self) -> None:
        req = FeedbackRequest(
            action="modify",
            suggestion_id=uuid4(),
            intent="edit",
            suggestion_text="Original",
            project_id=uuid4(),
            modification="Changed",
        )
        assert req.modification == "Changed"

    def test_invalid_action_raises(self) -> None:
        with pytest.raises(ValidationError):
            FeedbackRequest(
                action="invalid",
                suggestion_id=uuid4(),
                intent="write",
                suggestion_text="text",
                project_id=uuid4(),
            )

    def test_rating_validation_valid(self) -> None:
        req = FeedbackRequest(
            action="accept",
            suggestion_id=uuid4(),
            intent="write",
            suggestion_text="text",
            project_id=uuid4(),
            rating=4,
        )
        assert req.rating == 4

    def test_rating_validation_too_high_raises(self) -> None:
        with pytest.raises(ValidationError):
            FeedbackRequest(
                action="accept",
                suggestion_id=uuid4(),
                intent="write",
                suggestion_text="text",
                project_id=uuid4(),
                rating=6,
            )

    def test_optional_fields_default_none(self) -> None:
        req = FeedbackRequest(
            action="accept",
            suggestion_id=uuid4(),
            intent="write",
            suggestion_text="text",
            project_id=uuid4(),
        )
        assert req.modification is None
        assert req.rating is None
        assert req.context is None
        assert req.genre is None


class TestFeedbackResponse:
    def test_from_attributes_config(self) -> None:
        uid = uuid4()
        resp = FeedbackResponse(id=uid, action="accept", created_at=datetime(2025, 1, 1))
        assert resp.id == uid


class TestAnalyzeRequest:
    def test_valid_request(self) -> None:
        pid = uuid4()
        req = AnalyzeRequest(project_id=pid)
        assert req.project_id == pid


class TestResetResponse:
    def test_defaults(self) -> None:
        resp = ResetResponse(message="Done", deleted_count=5)
        assert resp.deleted_count == 5
