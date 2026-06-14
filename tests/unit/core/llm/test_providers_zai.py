"""Tests for llm/_providers/zai.py — Z.AI factory construction.

Exercises both ``_make_zai`` (General API) and ``make_zai_coding``
(Coding API) factory bodies to verify:
- Correct pydantic-ai Model type returned
- Default endpoints (General vs Coding API)
- API key routing (explicit vs ZAI_API_KEY env var)
- Custom base URL override
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai.models.openai import OpenAIChatModel

from narrare_core.llm._providers.zai import _make_zai, make_zai_coding

if TYPE_CHECKING:
    import pytest


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
