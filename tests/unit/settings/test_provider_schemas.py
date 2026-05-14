"""Tests for provider Pydantic schemas.

Tests CreateProviderRequest, UpdateProviderRequest, ProviderResponse.
Split from test_schemas.py for RULE-04 compliance.
"""

from __future__ import annotations

import uuid
from datetime import UTC

from pydantic import ValidationError

from narrare.settings.schemas import (
    CreateProviderRequest,
    ProviderResponse,
    UpdateProviderRequest,
)

# ---------------------------------------------------------------------------
# CreateProviderRequest
# ---------------------------------------------------------------------------


class TestCreateProviderRequest:
    def test_valid_request(self) -> None:
        req = CreateProviderRequest(
            provider_name="anthropic",
            api_key="sk-ant-key123",
        )
        assert req.provider_name == "anthropic"
        assert req.api_key == "sk-ant-key123"
        assert req.base_url is None

    def test_valid_request_with_base_url(self) -> None:
        req = CreateProviderRequest(
            provider_name="openai",
            api_key="sk-key",
            base_url="https://my-proxy.example.com/v1",
        )
        assert req.base_url == "https://my-proxy.example.com/v1"

    def test_empty_api_key_raises(self) -> None:
        import pytest

        with pytest.raises(ValidationError):
            CreateProviderRequest(provider_name="anthropic", api_key="")

    def test_empty_provider_name_with_max_length(self) -> None:
        """Provider name at max length (50) is valid."""
        req = CreateProviderRequest(provider_name="x" * 50, api_key="sk-key")
        assert len(req.provider_name) == 50

    def test_provider_name_exceeds_max_length_raises(self) -> None:
        import pytest

        with pytest.raises(ValidationError):
            CreateProviderRequest(provider_name="x" * 51, api_key="sk-key")

    def test_base_url_exceeds_max_length_raises(self) -> None:
        import pytest

        with pytest.raises(ValidationError):
            CreateProviderRequest(
                provider_name="openai",
                api_key="sk-key",
                base_url="https://" + "x" * 500,
            )


# ---------------------------------------------------------------------------
# UpdateProviderRequest
# ---------------------------------------------------------------------------


class TestUpdateProviderRequest:
    def test_all_fields_none_is_valid(self) -> None:
        """All fields optional - empty update is valid."""
        req = UpdateProviderRequest()
        assert req.api_key is None
        assert req.base_url is None
        assert req.is_active is None

    def test_partial_update_api_key(self) -> None:
        req = UpdateProviderRequest(api_key="new-key")
        assert req.api_key == "new-key"
        assert req.base_url is None

    def test_partial_update_is_active(self) -> None:
        req = UpdateProviderRequest(is_active=False)
        assert req.is_active is False

    def test_empty_api_key_raises(self) -> None:
        import pytest

        with pytest.raises(ValidationError):
            UpdateProviderRequest(api_key="")


# ---------------------------------------------------------------------------
# ProviderResponse
# ---------------------------------------------------------------------------


class TestProviderResponse:
    def test_valid_response(self) -> None:
        provider_id = uuid.uuid4()
        from datetime import datetime

        now = datetime.now(UTC)
        resp = ProviderResponse(
            id=provider_id,
            provider_name="anthropic",
            has_api_key=True,
            api_key_last4="----",
            base_url=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        assert resp.id == provider_id
        assert resp.has_api_key is True

    def test_response_no_api_key(self) -> None:
        provider_id = uuid.uuid4()
        from datetime import datetime

        now = datetime.now(UTC)
        resp = ProviderResponse(
            id=provider_id,
            provider_name="ollama",
            has_api_key=False,
            api_key_last4="****",
            base_url="http://localhost:11434",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        assert resp.has_api_key is False
