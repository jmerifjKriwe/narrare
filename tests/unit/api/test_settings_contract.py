"""Contract test: Settings/AI Pydantic schemas match frontend expectations.

The frontend consumes ProviderResponse, UserAiSettingsResponse,
ProjectAiSettingsResponse, TokenLimitOverrides, etc. Field name and type
mismatches cause runtime crashes.
"""

from __future__ import annotations


class TestProviderResponseContract:
    """ProviderResponse is consumed by the frontend's provider management UI."""

    def test_provider_response_has_required_fields(self) -> None:
        from narrare.settings.schemas import ProviderResponse

        field_names = set(ProviderResponse.model_fields.keys())
        expected = {
            "id",
            "provider_name",
            "has_api_key",
            "api_key_last4",
            "base_url",
            "is_active",
            "created_at",
            "updated_at",
        }
        missing = expected - field_names
        assert not missing, f"ProviderResponse is missing fields: {missing}"

    def test_provider_response_has_api_key_last4(self) -> None:
        """Frontend displays masked key — api_key_last4 must exist and be str."""
        from narrare.settings.schemas import ProviderResponse

        field = ProviderResponse.model_fields["api_key_last4"]
        assert field.annotation is str, f"Expected api_key_last4 to be str, got {field.annotation}"

    def test_provider_response_base_url_is_optional(self) -> None:
        from narrare.settings.schemas import ProviderResponse

        field = ProviderResponse.model_fields["base_url"]
        assert field.default is None, "base_url should default to None"


class TestUserAiSettingsResponseContract:
    """UserAiSettingsResponse is consumed by the AI settings page."""

    def test_user_ai_settings_has_required_fields(self) -> None:
        from narrare.settings.schemas import UserAiSettingsResponse

        field_names = set(UserAiSettingsResponse.model_fields.keys())
        expected = {
            "user_id",
            "default_provider_id",
            "default_model",
            "category_overrides",
            "intent_overrides",
            "embedding_provider",
            "embedding_model",
            "active_embedding_tier",
            "updated_at",
        }
        missing = expected - field_names
        assert not missing, f"UserAiSettingsResponse is missing fields: {missing}"

    def test_user_ai_settings_default_model_is_str(self) -> None:
        from narrare.settings.schemas import UserAiSettingsResponse

        ann = UserAiSettingsResponse.model_fields["default_model"].annotation
        assert ann is str, f"Expected default_model to be str, got {ann}"

    def test_user_ai_settings_embedding_provider_defaults_to_auto(self) -> None:
        from narrare.settings.schemas import UserAiSettingsResponse

        field = UserAiSettingsResponse.model_fields["embedding_provider"]
        assert field.default == "auto", (
            f"Expected embedding_provider default 'auto', got {field.default!r}"
        )


class TestProjectAiSettingsResponseContract:
    """ProjectAiSettingsResponse is consumed by the project settings page."""

    def test_project_ai_settings_has_required_fields(self) -> None:
        from narrare.settings.schemas import ProjectAiSettingsResponse

        field_names = set(ProjectAiSettingsResponse.model_fields.keys())
        expected = {
            "novel_id",
            "category_overrides",
            "intent_overrides",
            "updated_at",
        }
        missing = expected - field_names
        assert not missing, f"ProjectAiSettingsResponse is missing fields: {missing}"


class TestUserSettingsResponseContract:
    """UserSettingsResponse is consumed by the user settings page."""

    def test_user_settings_has_required_fields(self) -> None:
        from narrare.settings.schemas import UserSettingsResponse

        field_names = set(UserSettingsResponse.model_fields.keys())
        expected = {
            "user_id",
            "display_name",
            "ui_language",
            "theme",
            "custom_tones",
            "updated_at",
        }
        missing = expected - field_names
        assert not missing, f"UserSettingsResponse is missing fields: {missing}"

    def test_user_settings_custom_tones_is_list(self) -> None:
        from narrare.settings.schemas import UserSettingsResponse

        ann = UserSettingsResponse.model_fields["custom_tones"].annotation
        assert "list" in str(ann).lower() or "list" in str(ann), (
            f"Expected custom_tones to be a list type, got {ann}"
        )


class TestProjectSettingsResponseContract:
    """ProjectSettingsResponse is consumed by the project settings page."""

    def test_project_settings_has_required_fields(self) -> None:
        from narrare.settings.schemas import ProjectSettingsResponse

        field_names = set(ProjectSettingsResponse.model_fields.keys())
        expected = {
            "novel_id",
            "autosave_interval",
            "default_language",
            "ai_provider",
            "ai_model",
            "updated_at",
        }
        missing = expected - field_names
        assert not missing, f"ProjectSettingsResponse is missing fields: {missing}"


class TestTokenLimitOverridesContract:
    """TokenLimitOverrides is consumed by token limit configuration."""

    def test_token_limit_overrides_has_required_fields(self) -> None:
        from narrare.settings.token_limits.contracts import TokenLimitOverrides

        field_names = set(TokenLimitOverrides.__dataclass_fields__.keys())
        expected = {
            "output_limit",
            "token_profile",
            "tier_percentages",
            "ws_timeout",
        }
        missing = expected - field_names
        assert not missing, f"TokenLimitOverrides is missing fields: {missing}"

    def test_token_limit_profile_defaults_to_balanced(self) -> None:
        from narrare.settings.token_limits.contracts import TokenLimitOverrides

        overrides = TokenLimitOverrides()
        assert overrides.token_profile == "balanced", (
            f"Expected default token_profile 'balanced', got {overrides.token_profile!r}"
        )

    def test_output_limit_default_is_4096(self) -> None:
        from narrare.settings.token_limits.contracts import TokenLimitOverrides

        overrides = TokenLimitOverrides()
        assert overrides.output_limit == 4096, (
            f"Expected default output_limit 4096, got {overrides.output_limit}"
        )


class TestCreateProviderRequestContract:
    """CreateProviderRequest — request schema for registering AI providers."""

    def test_create_provider_has_required_fields(self) -> None:
        from narrare.settings.schemas import CreateProviderRequest

        field_names = set(CreateProviderRequest.model_fields.keys())
        for f in ("provider_name", "api_key"):
            assert f in field_names, f"CreateProviderRequest missing field '{f}'"

    def test_create_provider_api_key_min_length(self) -> None:
        from narrare.settings.schemas import CreateProviderRequest

        field = CreateProviderRequest.model_fields["api_key"]
        # Pydantic v2 stores constraints in metadata, not as direct attributes
        assert any(
            hasattr(meta, "min_length") and meta.min_length == 1  # type: ignore[arg-type]
            for meta in field.metadata
        ), "Expected api_key min_length 1"
