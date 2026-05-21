"""Tests for memory/embedding_cascade.py — EmbeddingCascadeResolver."""

from __future__ import annotations

from narrare_core.memory.embedding_cascade import (
    EmbeddingCascadeResolver,
    EmbeddingConfig,
)


def _make_resolver() -> EmbeddingCascadeResolver:
    return EmbeddingCascadeResolver()


def _resolve(
    *,
    providers: list[str] | None = None,
    api_keys: dict[str, str] | None = None,
    base_urls: dict[str, str | None] | None = None,
    explicit: str | None = None,
) -> EmbeddingConfig:
    resolver = _make_resolver()
    return resolver.resolve(
        user_providers=providers or [],
        user_api_keys=api_keys or {},
        user_base_urls=base_urls or {},
        explicit_provider=explicit,
    )


class TestCascadeTier1OpenAI:
    """Tier 1: OpenAI user with API key → OpenAI embeddings."""

    def test_openai_user_gets_tier1(self) -> None:
        config = _resolve(
            providers=["openai"],
            api_keys={"openai": "sk-test-key"},
        )
        assert config.provider == "openai"
        assert config.model == "text-embedding-3-small"
        assert config.api_key == "sk-test-key"

    def test_openai_user_with_base_url(self) -> None:
        config = _resolve(
            providers=["openai"],
            api_keys={"openai": "sk-test"},
            base_urls={"openai": "https://custom.api.com"},
        )
        assert config.base_url == "https://custom.api.com"

    def test_openai_user_without_key_falls_to_tier3(self) -> None:
        """OpenAI in providers but no API key → Tier 3 local."""
        config = _resolve(providers=["openai"], api_keys={})
        assert config.provider == "local"
        assert config.model == "all-MiniLM-L6-v2"


class TestCascadeTier3Local:
    """Tier 3: Users without OpenAI → local sentence-transformers."""

    def test_zai_user_gets_local(self) -> None:
        config = _resolve(
            providers=["zai"],
            api_keys={"zai": "zai-key"},
        )
        assert config.provider == "local"
        assert config.model == "all-MiniLM-L6-v2"
        assert config.api_key is None

    def test_anthropic_user_gets_local(self) -> None:
        config = _resolve(
            providers=["anthropic"],
            api_keys={"anthropic": "sk-ant-key"},
        )
        assert config.provider == "local"

    def test_ollama_user_gets_local(self) -> None:
        config = _resolve(
            providers=["ollama"],
            api_keys={"ollama": "ollama-key"},
        )
        assert config.provider == "local"

    def test_no_providers_gets_local(self) -> None:
        config = _resolve()
        assert config.provider == "local"


class TestCascadeMultiProvider:
    """Multi-provider users: OpenAI wins when present."""

    def test_openai_plus_anthropic_gets_tier1(self) -> None:
        config = _resolve(
            providers=["anthropic", "openai"],
            api_keys={"anthropic": "sk-ant", "openai": "sk-oai"},
        )
        assert config.provider == "openai"
        assert config.api_key == "sk-oai"

    def test_zai_plus_anthropic_no_openai_gets_local(self) -> None:
        config = _resolve(
            providers=["zai", "anthropic"],
            api_keys={"zai": "zai-key", "anthropic": "sk-ant"},
        )
        assert config.provider == "local"


class TestCascadeExplicit:
    """Explicit provider overrides."""

    def test_explicit_disabled(self) -> None:
        config = _resolve(explicit="disabled")
        assert config.provider == "disabled"
        assert config.model == ""

    def test_explicit_local(self) -> None:
        config = _resolve(
            providers=["openai"],
            api_keys={"openai": "sk-test"},
            explicit="local",
        )
        assert config.provider == "local"
        assert config.model == "all-MiniLM-L6-v2"

    def test_explicit_openai_with_key(self) -> None:
        config = _resolve(
            providers=["anthropic"],
            api_keys={"openai": "sk-test"},
            explicit="openai",
        )
        assert config.provider == "openai"
        assert config.api_key == "sk-test"

    def test_explicit_openai_without_key_falls_to_disabled(self) -> None:
        """Explicit openai but no key → disabled."""
        config = _resolve(explicit="openai", api_keys={})
        assert config.provider == "disabled"

    def test_explicit_auto_uses_cascade(self) -> None:
        config = _resolve(
            providers=["openai"],
            api_keys={"openai": "sk-test"},
            explicit="auto",
        )
        assert config.provider == "openai"

    def test_explicit_unknown_provider_falls_to_disabled(self) -> None:
        config = _resolve(explicit="nonexistent_provider")
        assert config.provider == "disabled"


class TestEmbeddingConfig:
    """EmbeddingConfig dataclass."""

    def test_frozen(self) -> None:
        config = EmbeddingConfig(provider="local", model="test-model")
        assert config.provider == "local"
        assert config.model == "test-model"

    def test_optional_fields_default_none(self) -> None:
        config = EmbeddingConfig(provider="local", model="test")
        assert config.api_key is None
        assert config.base_url is None

    def test_with_all_fields(self) -> None:
        config = EmbeddingConfig(
            provider="openai",
            model="text-embedding-3-small",
            api_key="sk-test",
            base_url="https://api.custom.com",
        )
        assert config.api_key == "sk-test"
        assert config.base_url == "https://api.custom.com"
