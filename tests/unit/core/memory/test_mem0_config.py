"""Tests for _build_mem0_config and create_memory_client_sync."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from narrare_core.memory._null_client import NullMemoryClient
from narrare_core.memory.mem0_client import (
    _build_mem0_config,
    create_memory_client_sync,
)

# ---------------------------------------------------------------------------
# Test helpers — structured mocks for the mem0 module
# ---------------------------------------------------------------------------
# Same pattern as test_create_memory_client.py — mem0 may not be installed,
# so we use spec-based mocks (RULE-TEST-01).


def _make_mock_client() -> MagicMock:
    """Create a mock mem0 AsyncMemory client instance."""
    return MagicMock(spec=[])


def _make_mock_mem0_module(
    from_config_return_value: MagicMock | None = None,
    from_config_side_effect: Exception | None = None,
) -> MagicMock:
    """Create a mock mem0 module with the expected AsyncMemory interface."""
    mock_async_memory = MagicMock(spec=["from_config"])
    if from_config_side_effect is not None:
        mock_async_memory.from_config.side_effect = from_config_side_effect
    else:
        mock_async_memory.from_config.return_value = from_config_return_value or _make_mock_client()
    mock_module = MagicMock(spec=["AsyncMemory"])
    mock_module.AsyncMemory = mock_async_memory
    return mock_module


class TestBuildMem0Config:
    """Tests for the synchronous config builder."""

    def test_basic_openai_config(self) -> None:
        config = _build_mem0_config(
            provider="openai",
            api_key="sk-test",
            memory_model="gpt-4.1-nano",
            embedding_model="text-embedding-3-small",
        )
        assert config is not None
        assert config["llm"]["model"] == "gpt-4.1-nano"
        assert config["llm"]["api_key"] == "sk-test"
        assert config["embedder"]["provider"] == "openai"
        assert config["embedder"]["config"]["model"] == "text-embedding-3-small"

    def test_embedding_disabled_returns_none(self) -> None:
        config = _build_mem0_config(
            provider="openai",
            api_key="sk-test",
            embedding_provider="disabled",
        )
        assert config is None

    def test_base_url_forwarded(self) -> None:
        config = _build_mem0_config(
            provider="openai",
            api_key="sk-test",
            base_url="https://custom.openai.com",
        )
        assert config is not None
        assert config["llm"]["base_url"] == "https://custom.openai.com"

    def test_custom_instructions(self) -> None:
        config = _build_mem0_config(
            provider="openai",
            api_key="sk-test",
            custom_instructions="Extract mood preferences.",
        )
        assert config is not None
        assert config["custom_instructions"] == "Extract mood preferences."

    def test_default_extraction_prompt_used(self) -> None:
        from narrare_core.memory.mem0_client import WRITING_PREFERENCE_EXTRACTION_PROMPT

        config = _build_mem0_config(
            provider="openai",
            api_key="sk-test",
        )
        assert config is not None
        assert config["custom_instructions"] == WRITING_PREFERENCE_EXTRACTION_PROMPT

    def test_language_extraction_prompt(self) -> None:
        from narrare_core.memory.mem0_client import get_extraction_prompt

        config = _build_mem0_config(
            provider="openai",
            api_key="sk-test",
            language="de",
        )
        assert config is not None
        assert config["custom_instructions"] == get_extraction_prompt("de")

    def test_custom_instructions_override_language(self) -> None:
        config = _build_mem0_config(
            provider="openai",
            api_key="sk-test",
            custom_instructions="Custom prompt",
            language="de",
        )
        assert config is not None
        assert config["custom_instructions"] == "Custom prompt"

    def test_default_model_per_provider(self) -> None:
        config = _build_mem0_config(
            provider="anthropic",
            api_key="sk-ant-test",
        )
        assert config is not None
        assert config["llm"]["model"] == "claude-haiku-4-20250414"

    def test_unknown_provider_uses_fallback_model(self) -> None:
        config = _build_mem0_config(
            provider="unknown-provider",
            api_key="test-key",
        )
        assert config is not None
        assert config["llm"]["model"] == "gpt-4.1-nano"

    def test_vector_store_included_when_db_url_provided(self) -> None:
        config = _build_mem0_config(
            provider="openai",
            api_key="sk-test",
            db_url="postgresql://localhost/testdb",
        )
        assert config is not None
        assert "vector_store" in config
        assert config["vector_store"]["provider"] == "pgvector"

    def test_vector_store_absent_when_no_db_url(self) -> None:
        config = _build_mem0_config(
            provider="openai",
            api_key="sk-test",
            db_url="",
        )
        assert config is not None
        assert "vector_store" not in config

    def test_legacy_embedding_params_override_cascade(self) -> None:
        config = _build_mem0_config(
            provider="openai",
            api_key="llm-key",
            embedding_model="text-embedding-3-large",
            embedding_api_key="embed-key",
            embedding_base_url="https://embed.api.com",
        )
        assert config is not None
        embedder = config["embedder"]
        assert embedder["provider"] == "openai"
        assert embedder["config"]["model"] == "text-embedding-3-large"
        assert embedder["config"]["api_key"] == "embed-key"
        assert embedder["config"]["base_url"] == "https://embed.api.com"

    def test_zai_user_gets_local_embeddings(self) -> None:
        config = _build_mem0_config(
            provider="zai",
            api_key="zai-key",
            user_providers=["zai"],
            user_api_keys={"zai": "zai-key"},
        )
        assert config is not None
        assert config["embedder"]["provider"] == "huggingface"
        assert config["embedder"]["config"]["model"] == "all-MiniLM-L6-v2"


class TestCreateMemoryClientSync:
    """Tests for the synchronous client factory."""

    @pytest.fixture(autouse=True)
    def _clear_e2e_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ensure NARRARE_E2E_TEST is unset — these tests exercise the real
        config-building path. See tests/unit/core/llm/test_providers_registry.py
        for the rationale (justfile exports NARRARE_E2E_TEST=1 from .env)."""
        monkeypatch.delenv("NARRARE_E2E_TEST", raising=False)

    def test_returns_null_on_disabled_embeddings(self) -> None:
        client = create_memory_client_sync(
            provider="openai",
            api_key="sk-test",
            embedding_provider="disabled",
        )
        assert isinstance(client, NullMemoryClient)

    def test_returns_null_on_import_error(self) -> None:
        with patch.dict("sys.modules", {"mem0": None}):
            client = create_memory_client_sync(
                provider="openai",
                api_key="sk-test",
            )
        assert isinstance(client, NullMemoryClient)

    def test_returns_null_on_creation_failure(self) -> None:
        mock_mem0 = _make_mock_mem0_module(
            from_config_side_effect=RuntimeError("config error"),
        )
        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            client = create_memory_client_sync(
                provider="openai",
                api_key="sk-test",
            )
        assert isinstance(client, NullMemoryClient)

    def test_returns_client_on_success(self) -> None:
        mock_client = _make_mock_client()
        mock_mem0 = _make_mock_mem0_module(from_config_return_value=mock_client)
        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            result = create_memory_client_sync(
                provider="openai",
                api_key="sk-test",
                memory_model="gpt-4.1-nano",
            )
        assert result is mock_client

    def test_config_passed_to_from_config(self) -> None:
        mock_client = _make_mock_client()
        mock_mem0 = _make_mock_mem0_module(from_config_return_value=mock_client)
        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            create_memory_client_sync(
                provider="openai",
                api_key="sk-test",
                memory_model="gpt-4o-mini",
                db_url="postgresql://localhost/test",
            )
        call_args = mock_mem0.AsyncMemory.from_config.call_args
        config = call_args.kwargs.get("config_dict") or call_args[0][0]
        assert config["llm"]["model"] == "gpt-4o-mini"
        assert config["vector_store"]["provider"] == "pgvector"


class TestCreateMemoryClientSyncE2ETestMode:
    """When NARRARE_E2E_TEST is set, create_memory_client_sync returns
    NullMemoryClient — no OpenAI embedding calls.

    Root cause this guards: in E2E mode, mem0 is configured with a real
    OpenAI embedder (Tier 1 cascade + dummy key). mem0.search() embeds the
    query via its OWN OpenAI embedder (it does NOT go through
    narrare_core.llm.embedding_providers), causing 401s logged as
    ``preference_query_failed``. mem0's config validator/EmbedderFactory
    reject a "mock" provider, so NullMemoryClient (the existing Tier 4
    graceful-degradation mechanism) is the clean E2E stub.
    """

    @pytest.fixture(autouse=True)
    def _set_e2e_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NARRARE_E2E_TEST", "1")

    def test_returns_null_memory_client_in_e2e(self) -> None:
        client = create_memory_client_sync(
            provider="openai",
            api_key="sk-test-dummy",
        )
        assert isinstance(client, NullMemoryClient)

    def test_e2e_does_not_build_openai_embedder_config(self) -> None:
        """In E2E, _build_mem0_config must not even be called (no OpenAI
        embedder config assembled)."""
        with patch("narrare_core.memory.mem0_client._build_mem0_config") as mock_build:
            client = create_memory_client_sync(
                provider="openai",
                api_key="sk-test-dummy",
            )
        mock_build.assert_not_called()
        assert isinstance(client, NullMemoryClient)

    def test_e2e_does_not_import_or_call_mem0(self) -> None:
        """E2E must short-circuit before touching the mem0 package."""
        with patch.dict("sys.modules", {"mem0": None}):
            client = create_memory_client_sync(
                provider="openai",
                api_key="sk-test-dummy",
            )
        assert isinstance(client, NullMemoryClient)


class TestCreateMemoryClientE2ETestMode:
    """Async factory E2E override (mirrors the sync factory)."""

    @pytest.fixture(autouse=True)
    def _set_e2e_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NARRARE_E2E_TEST", "1")

    async def test_returns_null_memory_client_in_e2e(self) -> None:
        from narrare_core.memory.mem0_client import create_memory_client

        client = await create_memory_client(
            provider="openai",
            api_key="sk-test-dummy",
        )
        assert isinstance(client, NullMemoryClient)
