"""Verify that every Fake class implements the methods of its corresponding Protocol."""

from __future__ import annotations

import inspect


def _protocol_methods(protocol_cls: type) -> set[str]:
    """Extract all async/sync method names from a Protocol class."""
    return {
        name
        for name, _ in inspect.getmembers(protocol_cls, predicate=inspect.isfunction)
        if not name.startswith("_")
    }


def _class_methods(cls: type) -> set[str]:
    """Extract all public method names from a class."""
    return {
        name
        for name, value in inspect.getmembers(cls)
        if not name.startswith("_") and callable(value)
    }


def assert_implements_protocol(fake_cls: type, protocol_cls: type) -> None:
    """Assert that fake_cls implements all methods defined in protocol_cls."""
    expected = _protocol_methods(protocol_cls)
    actual = _class_methods(fake_cls)
    missing = expected - actual
    assert not missing, (
        f"{fake_cls.__name__} is missing methods from {protocol_cls.__name__}: {missing}"
    )


class TestFakeConformance:
    """Each test verifies a Fake class has all methods from its Protocol."""

    def test_fake_auth_repo(self) -> None:
        from narrare.auth.contracts import AuthRepositoryProtocol
        from tests.fakes import FakeAuthRepository

        assert_implements_protocol(FakeAuthRepository, AuthRepositoryProtocol)

    def test_fake_novel_repo(self) -> None:
        from narrare.novels.contracts import NovelRepositoryProtocol
        from tests.fakes import FakeNovelRepository

        assert_implements_protocol(FakeNovelRepository, NovelRepositoryProtocol)

    def test_fake_chapter_repo(self) -> None:
        from narrare.chapters.contracts import ChapterRepositoryProtocol
        from tests.fakes import FakeChapterRepository

        assert_implements_protocol(FakeChapterRepository, ChapterRepositoryProtocol)

    def test_fake_volume_repo(self) -> None:
        from narrare.volumes.contracts import VolumeRepositoryProtocol
        from tests.fakes import FakeVolumeRepository

        assert_implements_protocol(FakeVolumeRepository, VolumeRepositoryProtocol)

    def test_fake_novel_service(self) -> None:
        from narrare.novels.contracts import NovelServiceProtocol
        from tests.fakes import FakeNovelService

        assert_implements_protocol(FakeNovelService, NovelServiceProtocol)

    def test_fake_llm_gateway(self) -> None:
        """FakeLLMGateway implements ModelRegistryProtocol."""
        from narrare_core.llm.contracts import ModelRegistryProtocol
        from tests.fakes import FakeLLMGateway

        assert_implements_protocol(FakeLLMGateway, ModelRegistryProtocol)

    def test_fake_provider_service(self) -> None:
        from narrare.setup.contracts import ProviderServiceProtocol
        from tests.fakes import FakeProviderService

        assert_implements_protocol(FakeProviderService, ProviderServiceProtocol)

    def test_fake_demo_loader(self) -> None:
        from narrare.setup.contracts import DemoLoaderProtocol
        from tests.fakes import FakeDemoLoader

        assert_implements_protocol(FakeDemoLoader, DemoLoaderProtocol)

    def test_fake_embedding_repo(self) -> None:
        """FakeEmbeddingRepository implements EmbeddingRepositoryProtocol."""
        from narrare.embeddings.contracts import EmbeddingRepositoryProtocol
        from tests.fakes import FakeEmbeddingRepository

        assert_implements_protocol(FakeEmbeddingRepository, EmbeddingRepositoryProtocol)

    def test_fake_embedding_repo_isinstance(self) -> None:
        """FakeEmbeddingRepository passes isinstance() check for runtime_checkable Protocol."""
        from narrare.embeddings.contracts import EmbeddingRepositoryProtocol
        from tests.fakes import FakeEmbeddingRepository

        fake = FakeEmbeddingRepository()
        assert isinstance(fake, EmbeddingRepositoryProtocol), (
            f"{FakeEmbeddingRepository.__name__} does not satisfy "
            f"{EmbeddingRepositoryProtocol.__name__} isinstance check"
        )
