"""Tests for memory/mem0_client.py — create_memory_client factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from narrare_core.memory.mem0_client import NullMemoryClient, create_memory_client


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
        mock_mem0 = (
            MagicMock()
        )  # narrare: allow reason="Mocking mem0 module for sys.modules injection"
        mock_mem0.AsyncMemory.from_config.side_effect = RuntimeError("config error")

        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            result = await create_memory_client(
                provider="openai",
                api_key="test-key",
            )
        assert isinstance(result, NullMemoryClient)


class TestCreateMemoryClientSuccess:
    """When mem0 creates a client successfully, returns it."""

    async def test_returns_client_on_success(self) -> None:
        mock_client = MagicMock()  # narrare: allow reason="Mocking mem0 AsyncMemory client"
        mock_mem0 = (
            MagicMock()
        )  # narrare: allow reason="Mocking mem0 module for sys.modules injection"
        mock_mem0.AsyncMemory.from_config.return_value = mock_client

        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            result = await create_memory_client(
                provider="openai",
                api_key="test-key",
                memory_model="gpt-4.1-nano",
                db_url="postgresql://localhost/test",
            )
        assert result is mock_client

    async def test_uses_default_model_when_none_provided(self) -> None:
        mock_client = MagicMock()  # narrare: allow reason="Mocking mem0 AsyncMemory client"
        mock_mem0 = (
            MagicMock()
        )  # narrare: allow reason="Mocking mem0 module for sys.modules injection"
        mock_mem0.AsyncMemory.from_config.return_value = mock_client

        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            await create_memory_client(
                provider="anthropic",
                api_key="test-key",
            )

        call_args = mock_mem0.AsyncMemory.from_config.call_args
        config = call_args.kwargs.get("config_dict") or call_args[0][0]
        assert config["llm"]["model"] == "claude-haiku-4-20250414"

    async def test_uses_custom_model_when_provided(self) -> None:
        mock_client = MagicMock()  # narrare: allow reason="Mocking mem0 AsyncMemory client"
        mock_mem0 = (
            MagicMock()
        )  # narrare: allow reason="Mocking mem0 module for sys.modules injection"
        mock_mem0.AsyncMemory.from_config.return_value = mock_client

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
        mock_client = MagicMock()  # narrare: allow reason="Mocking mem0 AsyncMemory client"
        mock_mem0 = (
            MagicMock()
        )  # narrare: allow reason="Mocking mem0 module for sys.modules injection"
        mock_mem0.AsyncMemory.from_config.return_value = mock_client

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
        mock_client = MagicMock()  # narrare: allow reason="Mocking mem0 AsyncMemory client"
        mock_mem0 = (
            MagicMock()
        )  # narrare: allow reason="Mocking mem0 module for sys.modules injection"
        mock_mem0.AsyncMemory.from_config.return_value = mock_client

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
        mock_client = MagicMock()  # narrare: allow reason="Mocking mem0 AsyncMemory client"
        mock_mem0 = (
            MagicMock()
        )  # narrare: allow reason="Mocking mem0 module for sys.modules injection"
        mock_mem0.AsyncMemory.from_config.return_value = mock_client

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
        mock_client = MagicMock()  # narrare: allow reason="Mocking mem0 AsyncMemory client"
        mock_mem0 = (
            MagicMock()
        )  # narrare: allow reason="Mocking mem0 module for sys.modules injection"
        mock_mem0.AsyncMemory.from_config.return_value = mock_client

        with patch.dict("sys.modules", {"mem0": mock_mem0}):
            await create_memory_client(
                provider="openai",
                api_key="llm-key-123",
            )

        call_args = mock_mem0.AsyncMemory.from_config.call_args
        config = call_args.kwargs.get("config_dict") or call_args[0][0]
        assert config["embedder"]["config"]["api_key"] == "llm-key-123"

    async def test_custom_embedding_params(self) -> None:
        mock_client = MagicMock()  # narrare: allow reason="Mocking mem0 AsyncMemory client"
        mock_mem0 = (
            MagicMock()
        )  # narrare: allow reason="Mocking mem0 module for sys.modules injection"
        mock_mem0.AsyncMemory.from_config.return_value = mock_client

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
