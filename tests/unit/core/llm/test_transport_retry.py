"""ADR-060 (Option B) — transport-retry effect-integrity tests.

LLM transport retry (transient HTTP 429/5xx/timeout retry at connection /
first-token establishment) is governed at the **provider layer**
(``core/llm/_providers/``), where the SDK clients are constructed — NOT as a
user/project token-limit setting. These tests prove RULE-18b for transport
retry at the correct runtime boundary:

1. **Governed source** (``_transport_retry.get_transport_max_retries``):
   the single operator-scoped value with a sensible default.
2. **Behavioral effect** (mandatory, fail-if-changed): changing the governed
   ``max_retries`` changes the *observable* number of HTTP attempts the SDK
   makes against a persistent transient error. The SDK's real retry loop runs;
   only the network is faked (``httpx.MockTransport``) — the retry behaviour
   under test is NOT mocked away.
3. **Factory wiring**: each provider factory passes the governed value to its
   SDK client (``client.max_retries`` for OpenAI/Anthropic/Groq;
   ``HttpRetryOptions.attempts`` for Google), so the value reaches the runtime
   boundary for both ``run()`` and ``stream()``.

See: ``docs/architecture/decisions/ADR-060-retry-false-control-resolution.md``.
"""

from __future__ import annotations

from typing import Any, cast

import httpx
import pytest
from openai import AsyncOpenAI, RateLimitError

from narrare_core.llm._transport_retry import (
    TRANSPORT_MAX_RETRIES_DEFAULT,
    TRANSPORT_MAX_RETRIES_ENV_VAR,
    get_transport_max_retries,
)
from narrare_core.settings import get_core_settings

# ---------------------------------------------------------------------------
# 1. Governed source
# ---------------------------------------------------------------------------


class TestTransportRetryGovernedSource:
    """``get_transport_max_retries`` — single operator-scoped value."""

    def test_default_when_env_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(TRANSPORT_MAX_RETRIES_ENV_VAR, raising=False)
        assert get_transport_max_retries() == TRANSPORT_MAX_RETRIES_DEFAULT == 2

    def test_default_is_two(self) -> None:
        """Governed default is 2 (parity with OpenAI/Anthropic/Groq SDK defaults)."""
        assert TRANSPORT_MAX_RETRIES_DEFAULT == 2

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(TRANSPORT_MAX_RETRIES_ENV_VAR, "5")
        assert get_transport_max_retries() == 5

    def test_zero_is_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """0 disables SDK retry (operator may want fail-fast)."""
        monkeypatch.setenv(TRANSPORT_MAX_RETRIES_ENV_VAR, "0")
        assert get_transport_max_retries() == 0

    def test_invalid_int_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(TRANSPORT_MAX_RETRIES_ENV_VAR, "not-an-int")
        assert get_transport_max_retries() == TRANSPORT_MAX_RETRIES_DEFAULT

    def test_negative_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(TRANSPORT_MAX_RETRIES_ENV_VAR, "-3")
        assert get_transport_max_retries() == TRANSPORT_MAX_RETRIES_DEFAULT

    def test_empty_string_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(TRANSPORT_MAX_RETRIES_ENV_VAR, "")
        assert get_transport_max_retries() == TRANSPORT_MAX_RETRIES_DEFAULT


# ---------------------------------------------------------------------------
# 2. Behavioral effect (MANDATORY — fail-if-changed)
# ---------------------------------------------------------------------------


async def _count_429_attempts(max_retries: int) -> int:
    """Drive the real OpenAI SDK retry loop against a persistent 429.

    Returns the number of HTTP attempts the SDK made before giving up. The
    SDK's retry logic is real and unmocked; only the transport (network) is
    faked to always return a transient rate-limit error.
    """
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            status_code=429,
            json={
                "error": {
                    "message": "rate limited",
                    "type": "rate_limit_exceeded",
                }
            },
        )

    transport = httpx.MockTransport(handler)
    # Constructed exactly as the provider factory does:
    # AsyncOpenAI(api_key=..., max_retries=get_transport_max_retries()).
    client = AsyncOpenAI(
        api_key="sk-effect-test",
        max_retries=max_retries,
        http_client=httpx.AsyncClient(transport=transport),
    )
    try:
        with pytest.raises(RateLimitError):
            await client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "hi"}],
            )
    finally:
        await client.close()
    return attempts


class TestTransportRetryBehavioralEffect:
    """Changing the governed ``max_retries`` changes observable retry behaviour.

    This is the RULE-18b effect regression: the resolved value provably
    changes what happens at the runtime boundary (HTTP attempts against a
    transient error). The provider SDK's retry loop is exercised for real.
    """

    @pytest.mark.parametrize(
        ("governed", "expected_attempts"),
        [
            # OpenAI SDK semantics: max_retries=N -> N+1 total HTTP attempts
            # (1 initial + N retries) against a persistent transient error.
            (0, 1),
            (1, 2),
            (2, 3),
            (4, 5),
        ],
    )
    async def test_max_retries_drives_http_attempt_count(
        self,
        monkeypatch: pytest.MonkeyPatch,
        governed: int,
        expected_attempts: int,
    ) -> None:
        monkeypatch.setenv(TRANSPORT_MAX_RETRIES_ENV_VAR, str(governed))
        # The factory reads this exact value when building the SDK client:
        resolved = get_transport_max_retries()
        assert resolved == governed  # sanity: governed source resolves the env
        attempts = await _count_429_attempts(resolved)
        assert attempts == expected_attempts

    async def test_changing_governed_value_changes_attempts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The fail-if-changed guarantee: two governed values differ in effect."""
        monkeypatch.setenv(TRANSPORT_MAX_RETRIES_ENV_VAR, "1")
        low = await _count_429_attempts(get_transport_max_retries())
        monkeypatch.setenv(TRANSPORT_MAX_RETRIES_ENV_VAR, "4")
        # CoreSettings is cached (@lru_cache); clear so the new env is re-read.
        get_core_settings.cache_clear()
        high = await _count_429_attempts(get_transport_max_retries())
        assert low == 2
        assert high == 5
        assert low != high


# ---------------------------------------------------------------------------
# 3. Factory wiring — governed value reaches each provider's SDK client
# ---------------------------------------------------------------------------


def _google_retry_attempts(model: object) -> int | None:
    """Read Google's ``HttpRetryOptions.attempts`` back from a constructed model.

    Google retries via ``HttpOptions(retry_options=HttpRetryOptions(attempts=N))``
    rather than an SDK ``max_retries`` knob. Returns ``None`` when retry is
    unconfigured (the SDK default).

    The model is duck-typed via :func:`cast` — this is test-only introspection
    of provider-internal state, the only way to read back the retry config.
    """
    # pydantic-ai GoogleModel.client is google.genai.Client; its _api_client
    # holds the normalized _http_options (retry_options.attempts readback
    # verified against google-genai 2.10.0).
    m = cast("Any", model)
    http_options = getattr(m.client._api_client, "_http_options", None)
    retry_options = getattr(http_options, "retry_options", None)
    return getattr(retry_options, "attempts", None)


# Each entry: (factory, model_id, api_key, readback). The readback extracts the
# governed value from the *constructed* provider model, proving the factory
# passed it through to the SDK client.
_PROVIDER_SPECS = [
    pytest.param(
        "narrare_core.llm._providers.openai._make_openai",
        "gpt-4o",
        "sk-test",
        lambda m: m.client.max_retries,
        id="openai",
    ),
    pytest.param(
        "narrare_core.llm._providers.anthropic._make_anthropic",
        "claude-sonnet-4-5-20251020",
        "sk-ant-test",
        lambda m: m.client.max_retries,
        id="anthropic",
    ),
    pytest.param(
        "narrare_core.llm._providers.others._make_groq",
        "mixtral-8x7b-32768",
        "gsk-test",
        lambda m: m.client.max_retries,
        id="groq",
    ),
    pytest.param(
        "narrare_core.llm._providers.others._make_google",
        "gemini-2.0-flash",
        "google-test",
        _google_retry_attempts,
        id="google",
    ),
    pytest.param(
        "narrare_core.llm._providers.ollama._make_ollama",
        "llama3",
        None,
        lambda m: m.client.max_retries,
        id="ollama",
    ),
    pytest.param(
        "narrare_core.llm._providers.others._make_openrouter",
        "meta/llama",
        "or-test",
        lambda m: m.client.max_retries,
        id="openrouter",
    ),
    pytest.param(
        "narrare_core.llm._providers.zai._make_zai",
        "glm-4-flash",
        "zai-test",
        lambda m: m.client.max_retries,
        id="zai",
    ),
]


class TestFactoryWiresTransportRetry:
    """Each provider factory wires the governed value into its SDK client."""

    @pytest.mark.parametrize("factory_path,model_id,api_key,readback", _PROVIDER_SPECS)
    def test_factory_applies_governed_default(
        self,
        monkeypatch: pytest.MonkeyPatch,
        factory_path: str,
        model_id: str,
        api_key: str | None,
        readback,
    ) -> None:
        import importlib

        monkeypatch.delenv(TRANSPORT_MAX_RETRIES_ENV_VAR, raising=False)
        module_path, func_name = factory_path.rsplit(".", 1)
        factory = getattr(importlib.import_module(module_path), func_name)
        model = factory(model_id, api_key=api_key)
        assert readback(model) == TRANSPORT_MAX_RETRIES_DEFAULT

    @pytest.mark.parametrize("factory_path,model_id,api_key,readback", _PROVIDER_SPECS)
    def test_factory_applies_operator_override(
        self,
        monkeypatch: pytest.MonkeyPatch,
        factory_path: str,
        model_id: str,
        api_key: str | None,
        readback,
    ) -> None:
        """A distinct governed value is observable on the constructed client."""
        import importlib

        monkeypatch.setenv(TRANSPORT_MAX_RETRIES_ENV_VAR, "5")
        module_path, func_name = factory_path.rsplit(".", 1)
        factory = getattr(importlib.import_module(module_path), func_name)
        model = factory(model_id, api_key=api_key)
        assert readback(model) == 5

    def test_openai_env_credential_path_gets_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The local-first production path (operator env, no per-user key) is retried.

        api_key is None but OPENAI_API_KEY is set — the factory must resolve the
        env credential and still apply the governed transport retry.
        """
        from pydantic_ai.models.openai import OpenAIChatModel

        from narrare_core.llm._providers.openai import _make_openai

        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-prod")
        monkeypatch.setenv(TRANSPORT_MAX_RETRIES_ENV_VAR, "4")
        model = _make_openai("gpt-4o")  # no api_key arg
        assert isinstance(model, OpenAIChatModel)  # narrows Model -> OpenAIChatModel
        assert model.client.max_retries == 4
