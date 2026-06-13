"""Tests for memory/mem0_client.py — create_memory_client factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from narrare_core.memory._null_client import NullMemoryClient
from narrare_core.memory.mem0_client import create_memory_client

# ---------------------------------------------------------------------------
# Test helpers — structured mocks for the mem0 module
# ---------------------------------------------------------------------------
# mem0 may not be installed, so we cannot use spec=mem0.AsyncMemory.
# These helpers document the expected interface and satisfy RULE-TEST-01
# by using explicit spec lists instead of bare MagicMock().
# ---------------------------------------------------------------------------


def _make_mock_client() -> MagicMock:
    """Create a mock mem0 AsyncMemory client instance.

    Uses ``spec=[]`` so attribute access raises ``AttributeError`` for
    unknown attributes — matching real-object behaviour.
    """
    return MagicMock(spec=[])


def _make_mock_mem0_module(
    from_config_return_value: MagicMock | None = None,
    from_config_side_effect: Exception | None = None,
) -> MagicMock:
    """Create a mock mem0 module with the expected AsyncMemory interface.

    Pre-configures ``module.AsyncMemory.from_config`` to return the given
    client or raise the given exception.  Avoids bare ``MagicMock()``
    (RULE-TEST-01) by declaring the known interface via ``spec``.
    """
    mock_async_memory = MagicMock(spec=["from_config"])
    if from_config_side_effect is not None:
        mock_async_memory.from_config.side_effect = from_config_side_effect
    else:
        mock_async_memory.from_config.return_value = from_config_return_value or _make_mock_client()
    mock_module = MagicMock(spec=["AsyncMemory"])
    mock_module.AsyncMemory = mock_async_memory
    return mock_module


class TestCreateMemoryClientImportError:
    """When mem0 is not installed, returns NullMemoryClient."""

    async def test_returns_null_client_on_import_error(self) -> None:
        with patch.dict("sys.modules", {"mem0": None}):
            result = await create_memory_client(
                provider="openai",
                api_key="test-key",
            )
        assert isinstance(result, NullMemoryClient)


class TestCreateMemoryClientCreationFailure:
    """When mem0 raises during client creation, returns NullMemoryClient."""

    async def test_returns_null_client_on_creation_error(self) -> None:
        mock_mem0 = _make_mock_mem0_module(
            from_config_side_effect=RuntimeError("config error"),
        )

        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            result = await create_memory_client(
                provider="openai",
                api_key="test-key",
            )
        assert isinstance(result, NullMemoryClient)


class TestCreateMemoryClientSuccess:
    """When mem0 creates a client successfully, returns it."""

    async def test_returns_client_on_success(self) -> None:
        mock_client = _make_mock_client()
        mock_mem0 = _make_mock_mem0_module(from_config_return_value=mock_client)

        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            result = await create_memory_client(
                provider="openai",
                api_key="test-key",
                memory_model="gpt-4.1-nano",
                db_url="postgresql://localhost/test",
            )
        assert result is mock_client

    async def test_uses_default_model_when_none_provided(self) -> None:
        mock_client = _make_mock_client()
        mock_mem0 = _make_mock_mem0_module(from_config_return_value=mock_client)

        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            await create_memory_client(
                provider="anthropic",
                api_key="test-key",
            )

        call_args = mock_mem0.AsyncMemory.from_config.call_args
        config = call_args.kwargs.get("config_dict") or call_args[0][0]
        assert config["llm"]["model"] == "claude-haiku-4-20250414"

    async def test_uses_custom_model_when_provided(self) -> None:
        mock_client = _make_mock_client()
        mock_mem0 = _make_mock_mem0_module(from_config_return_value=mock_client)

        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            await create_memory_client(
                provider="openai",
                api_key="test-key",
                memory_model="gpt-4o-mini",
            )

        call_args = mock_mem0.AsyncMemory.from_config.call_args
        config = call_args.kwargs.get("config_dict") or call_args[0][0]
        assert config["llm"]["model"] == "gpt-4o-mini"

    async def test_passes_base_url_to_llm_config(self) -> None:
        mock_client = _make_mock_client()
        mock_mem0 = _make_mock_mem0_module(from_config_return_value=mock_client)

        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            await create_memory_client(
                provider="openai",
                api_key="test-key",
                base_url="https://custom.api.com/v1",
            )

        call_args = mock_mem0.AsyncMemory.from_config.call_args
        config = call_args.kwargs.get("config_dict") or call_args[0][0]
        assert config["llm"]["base_url"] == "https://custom.api.com/v1"

    async def test_includes_vector_store_when_db_url_provided(self) -> None:
        mock_client = _make_mock_client()
        mock_mem0 = _make_mock_mem0_module(from_config_return_value=mock_client)

        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            await create_memory_client(
                provider="openai",
                api_key="test-key",
                db_url="postgresql://user:pass@localhost:5432/testdb",
            )

        call_args = mock_mem0.AsyncMemory.from_config.call_args
        config = call_args.kwargs.get("config_dict") or call_args[0][0]
        assert "vector_store" in config
        assert config["vector_store"]["provider"] == "pgvector"

    async def test_no_vector_store_when_db_url_empty(self) -> None:
        mock_client = _make_mock_client()
        mock_mem0 = _make_mock_mem0_module(from_config_return_value=mock_client)

        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            await create_memory_client(
                provider="openai",
                api_key="test-key",
                db_url="",
            )

        call_args = mock_mem0.AsyncMemory.from_config.call_args
        config = call_args.kwargs.get("config_dict") or call_args[0][0]
        assert "vector_store" not in config

    async def test_embedding_api_key_defaults_to_llm_key(self) -> None:
        mock_client = _make_mock_client()
        mock_mem0 = _make_mock_mem0_module(from_config_return_value=mock_client)

        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            await create_memory_client(
                provider="openai",
                api_key="llm-key-123",
            )

        call_args = mock_mem0.AsyncMemory.from_config.call_args
        config = call_args.kwargs.get("config_dict") or call_args[0][0]
        assert config["embedder"]["config"]["api_key"] == "llm-key-123"

    async def test_custom_embedding_params(self) -> None:
        mock_client = _make_mock_client()
        mock_mem0 = _make_mock_mem0_module(from_config_return_value=mock_client)

        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            await create_memory_client(
                provider="openai",
                api_key="llm-key",
                embedding_model="text-embedding-3-large",
                embedding_provider="openai",
                embedding_api_key="embed-key",
                embedding_base_url="https://embed.api.com",
            )

        call_args = mock_mem0.AsyncMemory.from_config.call_args
        config = call_args.kwargs.get("config_dict") or call_args[0][0]
        embedder_config = config["embedder"]
        assert embedder_config["provider"] == "openai"
        assert embedder_config["config"]["model"] == "text-embedding-3-large"
        assert embedder_config["config"]["api_key"] == "embed-key"
        assert embedder_config["config"]["base_url"] == "https://embed.api.com"


class TestCreateMemoryClientCascade:
    """Tests for cascade-based embedding resolution in create_memory_client."""

    async def test_zai_user_gets_local_embeddings(self) -> None:
        """z.ai user (no embedding API) → Tier 3 local sentence-transformers."""
        mock_client = _make_mock_client()
        mock_mem0 = _make_mock_mem0_module(from_config_return_value=mock_client)

        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            result = await create_memory_client(
                provider="zai",
                api_key="zai-key",
                user_providers=["zai"],
                user_api_keys={"zai": "zai-key"},
            )

        assert result is mock_client
        call_args = mock_mem0.AsyncMemory.from_config.call_args
        config = call_args.kwargs.get("config_dict") or call_args[0][0]
        # mem0 uses "huggingface" provider for sentence-transformers
        assert config["embedder"]["provider"] == "huggingface"
        assert config["embedder"]["config"]["model"] == "all-MiniLM-L6-v2"

    async def test_openai_user_gets_openai_embeddings(self) -> None:
        """OpenAI user → Tier 1 OpenAI embeddings."""
        mock_client = _make_mock_client()
        mock_mem0 = _make_mock_mem0_module(from_config_return_value=mock_client)

        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            result = await create_memory_client(
                provider="openai",
                api_key="sk-test",
                user_providers=["openai"],
                user_api_keys={"openai": "sk-test"},
            )

        assert result is mock_client
        call_args = mock_mem0.AsyncMemory.from_config.call_args
        config = call_args.kwargs.get("config_dict") or call_args[0][0]
        assert config["embedder"]["provider"] == "openai"
        assert config["embedder"]["config"]["model"] == "text-embedding-3-small"
        assert config["embedder"]["config"]["api_key"] == "sk-test"

    async def test_openai_embedding_base_url_from_cascade(self) -> None:
        """OpenAI cascade with base_url → base_url flows to embedder config."""
        mock_client = _make_mock_client()
        mock_mem0 = _make_mock_mem0_module(from_config_return_value=mock_client)

        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            result = await create_memory_client(
                provider="openai",
                api_key="sk-test",
                user_providers=["openai"],
                user_api_keys={"openai": "sk-test"},
                user_base_urls={"openai": "https://api.openai.com/v1"},
            )

        assert result is mock_client
        call_args = mock_mem0.AsyncMemory.from_config.call_args
        config = call_args.kwargs.get("config_dict") or call_args[0][0]
        assert config["embedder"]["provider"] == "openai"
        assert config["embedder"]["config"]["base_url"] == "https://api.openai.com/v1"

    async def test_anthropic_user_gets_local_embeddings(self) -> None:
        """Anthropic user (no embedding API) → Tier 3 local."""
        mock_client = _make_mock_client()
        mock_mem0 = _make_mock_mem0_module(from_config_return_value=mock_client)

        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            result = await create_memory_client(
                provider="anthropic",
                api_key="sk-ant-key",
                user_providers=["anthropic"],
                user_api_keys={"anthropic": "sk-ant-key"},
            )

        assert result is mock_client
        call_args = mock_mem0.AsyncMemory.from_config.call_args
        config = call_args.kwargs.get("config_dict") or call_args[0][0]
        assert config["embedder"]["provider"] == "huggingface"

    async def test_disabled_provider_returns_null_client(self) -> None:
        """embedding_provider="disabled" → NullMemoryClient."""
        result = await create_memory_client(
            provider="openai",
            api_key="sk-test",
            embedding_provider="disabled",
        )
        assert isinstance(result, NullMemoryClient)

    async def test_custom_instructions_in_config(self) -> None:
        """Custom instructions are passed to mem0 config."""
        mock_client = _make_mock_client()
        mock_mem0 = _make_mock_mem0_module(from_config_return_value=mock_client)

        custom_prompt = "Extract only dialogue preferences."
        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            await create_memory_client(
                provider="openai",
                api_key="sk-test",
                custom_instructions=custom_prompt,
            )

        call_args = mock_mem0.AsyncMemory.from_config.call_args
        config = call_args.kwargs.get("config_dict") or call_args[0][0]
        assert config["custom_instructions"] == custom_prompt

    async def test_default_custom_instructions_in_config(self) -> None:
        """Default WRITING_PREFERENCE_EXTRACTION_PROMPT used when no custom."""
        mock_client = _make_mock_client()
        mock_mem0 = _make_mock_mem0_module(from_config_return_value=mock_client)

        from narrare_core.memory.mem0_client import WRITING_PREFERENCE_EXTRACTION_PROMPT

        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            await create_memory_client(
                provider="openai",
                api_key="sk-test",
            )

        call_args = mock_mem0.AsyncMemory.from_config.call_args
        config = call_args.kwargs.get("config_dict") or call_args[0][0]
        assert config["custom_instructions"] == WRITING_PREFERENCE_EXTRACTION_PROMPT

    async def test_legacy_embedding_params_override_cascade(self) -> None:
        """Legacy embedding_model/api_key/base_url params override cascade."""
        mock_client = _make_mock_client()
        mock_mem0 = _make_mock_mem0_module(from_config_return_value=mock_client)

        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            await create_memory_client(
                provider="openai",
                api_key="llm-key",
                embedding_model="text-embedding-3-large",
                embedding_api_key="embed-key",
                embedding_base_url="https://embed.api.com",
            )

        call_args = mock_mem0.AsyncMemory.from_config.call_args
        config = call_args.kwargs.get("config_dict") or call_args[0][0]
        assert config["embedder"]["config"]["model"] == "text-embedding-3-large"
        assert config["embedder"]["config"]["api_key"] == "embed-key"
