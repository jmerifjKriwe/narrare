"""Tests for llm/_providers/zai.py — Z.AI factory construction.

Exercises both ``_make_zai`` (General API) and ``make_zai_coding``
(Coding API) factory bodies to verify:
- Correct pydantic-ai Model type returned
- Default endpoints (General vs Coding API)
- API key routing (explicit vs ZAI_API_KEY env var)
- Custom base URL override
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from pydantic_ai.exceptions import UserError
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.zai import ZaiProvider

from narrare_core.llm._providers.zai import _make_zai, make_zai_coding
from narrare_core.llm._schema_transformer import NarrareOpenAICompatJsonSchemaTransformer

if TYPE_CHECKING:
    from pydantic_ai.settings import ModelSettings


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

    def test_no_credentials_raises_user_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No key arg and no env var -> General-endpoint construction fails fast.

        ``ZaiProvider`` validates credential availability eagerly and raises a
        pydantic-ai ``UserError``. Correct fail-fast behaviour: an LLM client
        cannot be built without a credential.
        """
        monkeypatch.delenv("ZAI_API_KEY", raising=False)
        with pytest.raises(UserError):
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

    def test_no_credentials_raises_user_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No key arg and no env var -> Coding-endpoint construction fails fast."""
        monkeypatch.delenv("ZAI_API_KEY", raising=False)
        with pytest.raises(UserError):
            make_zai_coding("glm-4-flash")


class TestZaiNativeProvider:
    """Z.AI models route through pydantic-ai's native ``ZaiProvider``.

    Routing through the native provider imports upstream-maintained capability
    facts (``reasoning_content`` thinking field, thinking-part send-back,
    JSON-object output support) instead of re-deriving them. The Narrare
    capability fragment (:data:`_ZAI_MODEL_PROFILE`) stays on top because
    upstream sets neither ``openai_chat_supports_max_completion_tokens=False``
    nor unconditional ``supports_thinking`` for Narrare's registered model IDs.
    """

    def test_make_zai_provider_is_native_zai_provider(self) -> None:
        model = _make_zai("glm-4-flash", api_key="zai-key")
        assert isinstance(model.provider, ZaiProvider)

    def test_make_zai_coding_provider_is_native_zai_provider(self) -> None:
        model = make_zai_coding("glm-4-flash", api_key="zai-key")
        assert isinstance(model.provider, ZaiProvider)

    def test_upstream_thinking_field_facts_retained(self) -> None:
        model = _make_zai("glm-4-flash", api_key="zai-key")
        assert model.profile.get("openai_chat_thinking_field") == "reasoning_content"
        assert model.profile.get("openai_chat_send_back_thinking_parts") == "field"
        assert model.profile.get("supports_json_object_output") is True


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


class TestZaiSchemaInlining:
    """Z.AI does not resolve JSON Schema ``$ref``/``$defs`` — schemas must be inlined.

    OpenAI proper resolves references natively, so pydantic-ai's OpenAI-family
    transformer keeps ``$defs`` in place. OpenAI-*compatible* endpoints like Z.AI
    do not: a ``results.items.$ref`` output schema reaches the model unresolved
    and produces degenerate structures (observed: empty ``items`` in KB
    extraction). Both factories must inject
    ``NarrareOpenAICompatJsonSchemaTransformer`` via the shared profile hook while
    retaining the Z.AI capability keys.
    """

    def test_make_zai_profile_carries_inlining_transformer(self) -> None:
        model = _make_zai("glm-5.3-flash", api_key="zai-key")
        assert model.profile.get("json_schema_transformer") is (
            NarrareOpenAICompatJsonSchemaTransformer
        )

    def test_make_zai_coding_profile_carries_inlining_transformer(self) -> None:
        model = make_zai_coding("glm-5.3-flash", api_key="zai-key")
        assert model.profile.get("json_schema_transformer") is (
            NarrareOpenAICompatJsonSchemaTransformer
        )

    def test_profile_retains_zai_capability_keys(self) -> None:
        """The profile-callable composition must not drop the Z.AI fragment."""
        model = _make_zai("glm-5.3-flash", api_key="zai-key")
        assert model.profile.get("openai_chat_supports_max_completion_tokens") is False
        assert model.profile.get("supports_thinking") is True

    def test_prepare_request_inlines_output_object_refs(self) -> None:
        """End-to-end: ``prepare_request`` inlines ``$ref``/``$defs`` output schemas.

        This is the framework's actual consumption point —
        ``Model.customize_request_parameters`` applies the profile transformer to
        ``output_tools`` (the KB extraction ``results.items.$ref`` failure path).
        ``OpenAIChatModel`` runs structured output in tool mode, which is how the
        agent hands the output schema to the model.
        """
        from pydantic_ai.models import ModelRequestParameters
        from pydantic_ai.tools import ToolDefinition

        schema = {
            "title": "ExtractionOutput",
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/ExtractionItem"},
                }
            },
            "required": ["results"],
            "$defs": {
                "ExtractionItem": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                }
            },
        }
        model = _make_zai("glm-5.3-flash", api_key="zai-key")
        params = ModelRequestParameters(
            output_mode="tool",
            output_tools=[
                ToolDefinition(name="final_result", parameters_json_schema=schema, kind="output")
            ],
        )

        _, prepared = model.prepare_request(None, params)

        assert len(prepared.output_tools) == 1
        out_schema = prepared.output_tools[0].parameters_json_schema
        assert "$defs" not in out_schema
        items = out_schema["properties"]["results"]["items"]
        assert items["properties"] == {"name": {"type": "string"}}
        assert items["required"] == ["name"]


class TestZaiThinkingProfile:
    """Z.AI models declare thinking support so the unified ``thinking`` setting resolves.

    pydantic-ai's ``Model.prepare_request`` drops ``ModelSettings['thinking']``
    unless the model profile declares ``supports_thinking``. The name-derived
    OpenAI profile knows no ``glm-*`` reasoning family (unknown names fall back
    to ``_NO_REASONING``), so without this flag a runtime thinking default would
    be silently ignored. GLM models do support thinking — glm-5.3-flash thinks
    extensively by default, which is exactly what the default caps.
    """

    def test_make_zai_profile_declares_supports_thinking(self) -> None:
        model = _make_zai("glm-5.3-flash", api_key="zai-key")
        assert model.profile.get("supports_thinking") is True

    def test_make_zai_coding_profile_declares_supports_thinking(self) -> None:
        model = make_zai_coding("glm-5.3-flash", api_key="zai-key")
        assert model.profile.get("supports_thinking") is True

    def test_runtime_thinking_setting_resolves_for_zai_model(self) -> None:
        """End-to-end: ``settings['thinking']`` survives ``prepare_request``.

        Dead-code guard: the intent-aware thinking policy injects
        ``thinking`` levels (e.g. ``"low"`` for KB/extraction intents); this
        proves the zai model actually resolves such a setting into request
        parameters (``params.thinking``) instead of silently dropping it,
        and strips it from the outgoing settings.
        """
        from pydantic_ai.models import ModelRequestParameters

        model = _make_zai("glm-5.3-flash", api_key="zai-key")
        settings, params = model.prepare_request(
            cast("ModelSettings", {"thinking": "low"}), ModelRequestParameters()
        )
        assert params.thinking == "low"
        # pydantic-ai strips the resolved ``thinking`` key from the outgoing
        # settings (a single-key dict strips to ``None`` — nothing else to send).
        assert settings is None or "thinking" not in settings
