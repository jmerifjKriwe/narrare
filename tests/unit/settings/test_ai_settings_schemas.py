"""Tests for AI settings Pydantic schemas - overrides, token limits, user settings.

Split from test_schemas.py for RULE-04 compliance.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from narrare.settings.schemas import (
    UpdateProjectAiSettingsRequest,
    UpdateUserAiSettingsRequest,
    UpdateUserSettingsRequest,
)
from narrare.settings.token_profiles import (
    TOKEN_LIMIT_PROFILES,
    VALID_TOKEN_LIMIT_PROFILES,
)

# ---------------------------------------------------------------------------
# UpdateUserAiSettingsRequest
# ---------------------------------------------------------------------------


class TestUpdateUserAiSettingsRequest:
    def test_empty_request_is_valid(self) -> None:
        req = UpdateUserAiSettingsRequest()
        assert req.default_provider_id is None
        assert req.default_model is None

    def test_set_default_model(self) -> None:
        pid = uuid.uuid4()
        req = UpdateUserAiSettingsRequest(
            default_provider_id=pid,
            default_model="gpt-4o",
        )
        assert req.default_provider_id == pid

    def test_set_category_overrides(self) -> None:
        pid = uuid.uuid4()
        req = UpdateUserAiSettingsRequest(
            category_overrides={
                "writing": {"provider_id": str(pid), "model_id": "gpt-4o"},
            },
        )
        assert req.category_overrides is not None
        assert "writing" in req.category_overrides

    def test_default_model_exceeds_max_length_raises(self) -> None:
        with pytest.raises(ValidationError):
            UpdateUserAiSettingsRequest(default_model="x" * 201)


# ---------------------------------------------------------------------------
# UpdateProjectAiSettingsRequest
# ---------------------------------------------------------------------------


class TestUpdateProjectAiSettingsRequest:
    def test_empty_request_is_valid(self) -> None:
        req = UpdateProjectAiSettingsRequest()
        assert req.category_overrides is None
        assert req.intent_overrides is None

    def test_set_all_overrides(self) -> None:
        req = UpdateProjectAiSettingsRequest(
            category_overrides={"writing": {"model_id": "gpt-4o"}},
            intent_overrides={"write": {"model_id": "claude-sonnet-4-5-20251020"}},
        )
        assert req.category_overrides is not None
        assert "writing" in req.category_overrides
        assert req.intent_overrides is not None
        assert "write" in req.intent_overrides


# ---------------------------------------------------------------------------
# Token Limit Profiles
# ---------------------------------------------------------------------------


class TestTokenLimitProfiles:
    """CR-08 P1: the profile vocabulary is derived from Core.

    ``conservative`` is a retired alias and must be absent; preset
    ``max_tokens`` must match Core's ``PROFILE_OUTPUT_LIMITS``.
    """

    def test_all_expected_profiles_exist(self) -> None:
        from narrare_core.llm.token_profiles import public_token_profile_values

        expected = set(public_token_profile_values())
        assert expected == VALID_TOKEN_LIMIT_PROFILES

    def test_conservative_alias_absent(self) -> None:
        assert "conservative" not in VALID_TOKEN_LIMIT_PROFILES
        with pytest.raises(KeyError):
            TOKEN_LIMIT_PROFILES["conservative"]  # pyright: ignore[reportGeneralTypeIssues]

    def test_preset_profiles_match_core_limits(self) -> None:
        from narrare_core.llm.token_profiles import PROFILE_OUTPUT_LIMITS

        for profile, preset in PROFILE_OUTPUT_LIMITS.items():
            assert TOKEN_LIMIT_PROFILES[profile]["default"].max_tokens == preset

    def test_quick_profile_has_defaults(self) -> None:
        profile = TOKEN_LIMIT_PROFILES["quick"]
        assert "default" in profile
        assert profile["default"].max_tokens == 500

    def test_balanced_profile_has_defaults(self) -> None:
        profile = TOKEN_LIMIT_PROFILES["balanced"]
        assert "default" in profile
        assert profile["default"].max_tokens == 2000

    def test_long_texts_profile_has_defaults(self) -> None:
        profile = TOKEN_LIMIT_PROFILES["long_texts"]
        assert "default" in profile
        # Raised 8000 → 16000 with the core preset (structured extraction on
        # thinking models hit the old ceiling before generating output), then
        # 16000 → 32000 (benchmark: ch-11 KB extraction on the densest reveal
        # chapter exhausted the 16000 ceiling).
        assert profile["default"].max_tokens == 32000

    def test_comprehensive_profile_has_defaults(self) -> None:
        profile = TOKEN_LIMIT_PROFILES["comprehensive"]
        assert "default" in profile
        assert profile["default"].max_tokens == 32000

    def test_custom_profile_starts_empty(self) -> None:
        profile = TOKEN_LIMIT_PROFILES["custom"]
        assert len(profile) == 0


# ---------------------------------------------------------------------------
# UpdateUserSettingsRequest
# ---------------------------------------------------------------------------


class TestUpdateUserSettingsRequest:
    def test_valid_theme_values(self) -> None:
        for theme in ["light", "dark", "system"]:
            req = UpdateUserSettingsRequest(theme=theme)
            assert req.theme == theme

    def test_invalid_theme_raises(self) -> None:
        with pytest.raises(ValidationError):
            UpdateUserSettingsRequest(theme="blue")

    def test_empty_strings_are_valid(self) -> None:
        """display_name can be empty string."""
        req = UpdateUserSettingsRequest(display_name="")
        assert req.display_name == ""

    def test_max_length_display_name(self) -> None:
        req = UpdateUserSettingsRequest(display_name="x" * 100)
        assert req.display_name is not None
        assert len(req.display_name) == 100

    def test_display_name_exceeds_max_raises(self) -> None:
        with pytest.raises(ValidationError):
            UpdateUserSettingsRequest(display_name="x" * 101)

    def test_ui_language_min_length(self) -> None:
        with pytest.raises(ValidationError):
            UpdateUserSettingsRequest(ui_language="x")

    def test_ui_language_max_length(self) -> None:
        with pytest.raises(ValidationError):
            UpdateUserSettingsRequest(ui_language="x" * 11)
