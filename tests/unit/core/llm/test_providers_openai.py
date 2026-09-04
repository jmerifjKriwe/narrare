"""Tests for llm/_providers/openai.py — OpenAI factory construction.

Exercises the actual ``_make_openai`` factory body to verify:
- Correct pydantic-ai Model type returned
- API key routing (explicit vs env-var fallback)
- Base URL override (proxy / OpenAI-compatible endpoints)
"""

from __future__ import annotations

import pytest
from pydantic_ai.exceptions import UserError
from pydantic_ai.models.openai import OpenAIChatModel

from narrare_core.llm._providers.openai import _make_openai
from narrare_core.llm._schema_transformer import NarrareOpenAICompatJsonSchemaTransformer


class TestMakeOpenAI:
    """``_make_openai`` creates ``OpenAIChatModel`` with credential routing."""

    def test_with_api_key_returns_openai_model(self) -> None:
        model = _make_openai("gpt-4o", api_key="sk-test")
        assert isinstance(model, OpenAIChatModel)
        assert model.model_name == "gpt-4o"

    def test_with_base_url_returns_openai_model(self) -> None:
        model = _make_openai("gpt-4o", base_url="https://proxy.example.com/v1")
        assert isinstance(model, OpenAIChatModel)
        assert model.model_name == "gpt-4o"

    def test_with_both_api_key_and_base_url(self) -> None:
        model = _make_openai("gpt-4o", api_key="sk-test", base_url="https://proxy/v1")
        assert isinstance(model, OpenAIChatModel)
        assert "proxy" in model.base_url

    def test_env_var_fallback_when_no_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without explicit credentials, falls back to OPENAI_API_KEY env var."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-fallback")
        model = _make_openai("gpt-4o")
        assert isinstance(model, OpenAIChatModel)
        assert model.model_name == "gpt-4o"

    def test_no_credentials_with_base_url_defers_to_pydantic_ai(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No key arg, no env var, but base_url set -> construction defers.

        ``OpenAIProvider(api_key=None, base_url=...)`` accepts a null key and
        defers credential resolution, so a model is returned (it would only
        fail if a real call were attempted without a key). This deterministically
        exercises the no-credential + base_url branch.
        """
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        model = _make_openai("gpt-4o", base_url="https://proxy.example.com/v1")
        assert isinstance(model, OpenAIChatModel)
        assert model.model_name == "gpt-4o"

    def test_no_credentials_bare_raises_openai_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No key, no env var, no base_url -> bare construction fails fast.

        ``OpenAIChatModel(model_id)`` with no provider cannot resolve a
        credential and raises a clear OpenAI SDK error at construction. This is
        the desired fail-fast behaviour: an LLM client cannot be built without a
        credential.
        """
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(UserError):
            _make_openai("gpt-4o")


class TestOpenAISchemaInlining:
    """OpenAI models carry the universal inlining transformer.

    OpenAI resolves ``$ref``/``$defs`` natively, so inlining is not a
    correctness fix here — but it is beneficial for consistency (uniform
    schema shape across all OpenAI-compatible providers and one shared
    transformer behaviour to audit). Both model-returning construction paths
    (explicit client, no-key with base URL) must inject it; the bare path
    fails fast and never returns a model.
    """

    def test_with_api_key_profile_carries_inlining_transformer(self) -> None:
        model = _make_openai("gpt-4o", api_key="sk-test")
        assert model.profile.get("json_schema_transformer") is (
            NarrareOpenAICompatJsonSchemaTransformer
        )

    def test_with_base_url_profile_carries_inlining_transformer(self) -> None:
        model = _make_openai("gpt-4o", base_url="https://proxy.example.com/v1")
        assert model.profile.get("json_schema_transformer") is (
            NarrareOpenAICompatJsonSchemaTransformer
        )
