"""Unit tests for settings schemas — embedding fields."""

from __future__ import annotations

from uuid import uuid4


class TestUserAiSettingsResponse:
    def test_embedding_fields_default(self) -> None:
        from narrare.settings.schemas import UserAiSettingsResponse

        resp = UserAiSettingsResponse(
            user_id=uuid4(),
            default_provider_id=None,
            default_model="",
            category_overrides={},
            intent_overrides={},
            token_limit_profile="balanced",
            token_limit_overrides={},
            updated_at="2026-01-01T00:00:00Z",  # type: ignore[arg-type]
        )
        assert resp.embedding_provider == "auto"
        assert resp.embedding_model is None
        assert resp.active_embedding_tier is None

    def test_embedding_fields_explicit(self) -> None:
        from narrare.settings.schemas import UserAiSettingsResponse

        resp = UserAiSettingsResponse(
            user_id=uuid4(),
            default_provider_id=None,
            default_model="",
            category_overrides={},
            intent_overrides={},
            token_limit_profile="balanced",
            token_limit_overrides={},
            embedding_provider="openai",
            embedding_model="text-embedding-3-small",
            active_embedding_tier="openai",
            updated_at="2026-01-01T00:00:00Z",  # type: ignore[arg-type]
        )
        assert resp.embedding_provider == "openai"
        assert resp.embedding_model == "text-embedding-3-small"
        assert resp.active_embedding_tier == "openai"


class TestUpdateUserAiSettingsRequest:
    def test_embedding_fields_optional(self) -> None:
        from narrare.settings.schemas import UpdateUserAiSettingsRequest

        req = UpdateUserAiSettingsRequest()
        assert req.embedding_provider is None
        assert req.embedding_model is None

    def test_embedding_fields_explicit(self) -> None:
        from narrare.settings.schemas import UpdateUserAiSettingsRequest

        req = UpdateUserAiSettingsRequest(
            embedding_provider="local",
            embedding_model="all-MiniLM-L6-v2",
        )
        assert req.embedding_provider == "local"
        assert req.embedding_model == "all-MiniLM-L6-v2"
