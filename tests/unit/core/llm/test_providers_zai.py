"""Tests for llm/_providers/zai.py — Z.AI factory construction.

Exercises both ``_make_zai`` (General API) and ``make_zai_coding``
(Coding API) factory bodies to verify:
- Correct pydantic-ai Model type returned
- Default endpoints (General vs Coding API)
- API key routing (explicit vs ZAI_API_KEY env var)
- Custom base URL override
"""

from __future__ import annotations

import pytest
from openai import OpenAIError
from pydantic_ai.models.openai import OpenAIChatModel

from narrare_core.llm._providers.zai import _make_zai, make_zai_coding


class TestMakeZai:
    """``_make_zai`` creates ``OpenAIChatModel`` via Z.AI General API."""

    def test_with_api_key_returns_model(self) -> None:
        model = _make_zai("glm-4-flash", api_key="zai-key")
        assert isinstance(model, OpenAIChatModel)
        assert model.model_name == "glm-4-flash"

    def test_default_general_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ZAI_API_KEY", "dummy-key")
        model = _make_zai("glm-4-flash")
        assert model.base_url == "https://api.z.ai/api/paas/v4/"

    def test_custom_base_url(self) -> None:
        model = _make_zai("glm-4-flash", api_key="k", base_url="https://custom.z.ai/v4")
        assert model.base_url == "https://custom.z.ai/v4/"

    def test_env_var_key_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ZAI_API_KEY", "env-zai-key")
        model = _make_zai("glm-z1-32b")
        assert isinstance(model, OpenAIChatModel)
        assert model.model_name == "glm-z1-32b"

    def test_no_credentials_raises_openai_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No key arg and no env var -> General-endpoint construction fails fast.

        Z.AI passes the (empty) resolved key to ``OpenAIProvider``, which raises
        an ``OpenAIError`` at construction. Correct fail-fast behaviour: an LLM
        client cannot be built without a credential.
        """
        monkeypatch.delenv("ZAI_API_KEY", raising=False)
        with pytest.raises(OpenAIError):
            _make_zai("glm-4-flash")


class TestMakeZaiCoding:
    """``make_zai_coding`` creates ``OpenAIChatModel`` via Z.AI Coding API."""

    def test_with_api_key_returns_model(self) -> None:
        model = make_zai_coding("glm-4-flash", api_key="zai-key")
        assert isinstance(model, OpenAIChatModel)
        assert model.model_name == "glm-4-flash"

    def test_uses_coding_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ZAI_API_KEY", "dummy-key")
        model = make_zai_coding("glm-4-flash")
        assert model.base_url == "https://api.z.ai/api/coding/paas/v4/"

    def test_custom_base_url(self) -> None:
        model = make_zai_coding("glm-4-flash", api_key="k", base_url="https://custom-coding/v4")
        assert model.base_url == "https://custom-coding/v4/"

    def test_env_var_key_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ZAI_API_KEY", "env-key")
        model = make_zai_coding("glm-z1-32b")
        assert isinstance(model, OpenAIChatModel)
        assert model.model_name == "glm-z1-32b"

    def test_no_credentials_raises_openai_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No key arg and no env var -> Coding-endpoint construction fails fast."""
        monkeypatch.delenv("ZAI_API_KEY", raising=False)
        with pytest.raises(OpenAIError):
            make_zai_coding("glm-4-flash")


class TestZaiMaxTokensCompatibility:
    """Z.AI endpoints read ``max_tokens`` — not OpenAI's ``max_completion_tokens``.

    ``OpenAIChatModel`` maps the ``max_tokens`` model setting to
    ``max_completion_tokens`` by default (``openai_chat_supports_max_completion_tokens``).
    Z.AI silently ignores ``max_completion_tokens``, so both factories must inject a
    profile that opts out — otherwise runtime output caps (ADR-045 ``max_tokens``)
    never reach the endpoint and generation runs unbounded.
    """

    def test_make_zai_profile_sends_max_tokens_not_max_completion_tokens(self) -> None:
        model = _make_zai("glm-5.3-flash", api_key="zai-key")
        assert model.profile.get("openai_chat_supports_max_completion_tokens") is False

    def test_make_zai_coding_profile_sends_max_tokens_not_max_completion_tokens(self) -> None:
        model = make_zai_coding("glm-5.3-flash", api_key="zai-key")
        assert model.profile.get("openai_chat_supports_max_completion_tokens") is False
