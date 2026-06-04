"""Verify that every Fake class implements the methods of its corresponding Protocol.

Every Fake class with a matching @runtime_checkable Protocol must have:
1. A conformance test (assert_implements_protocol)
2. AN isinstance test (verify structural subtype check)

Add new tests here when new Fake classes are created.
"""

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


def _assert_isinstance(fake_cls: type, protocol_cls: type) -> None:
    """Assert that an instance of fake_cls passes isinstance check for protocol_cls."""
    fake = fake_cls()
    assert isinstance(fake, protocol_cls), (
        f"{fake_cls.__name__} does not satisfy {protocol_cls.__name__} isinstance() check"
    )


class TestFakeConformance:
    """Each test verifies a Fake class has all methods from its Protocol."""

    # ------------------------------------------------------------------
    # Existing Fakes — conformance only (isinstance in separate class)
    # ------------------------------------------------------------------

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
        from narrare.embeddings.contracts import EmbeddingRepositoryProtocol
        from tests.fakes import FakeEmbeddingRepository

        assert_implements_protocol(FakeEmbeddingRepository, EmbeddingRepositoryProtocol)

    # ------------------------------------------------------------------
    # New Fakes added since original conformance suite
    # ------------------------------------------------------------------

    def test_fake_user_settings_repo(self) -> None:
        """FakeUserSettingsRepository implements UserSettingsRepositoryProtocol."""
        from narrare.settings.contracts import UserSettingsRepositoryProtocol
        from tests.fakes import FakeUserSettingsRepository

        assert_implements_protocol(FakeUserSettingsRepository, UserSettingsRepositoryProtocol)

    def test_fake_outline_repo(self) -> None:
        """FakeOutlineRepository implements OutlineRepositoryProtocol."""
        from narrare.planning.contracts import OutlineRepositoryProtocol
        from tests.fakes import FakeOutlineRepository

        assert_implements_protocol(FakeOutlineRepository, OutlineRepositoryProtocol)

    # ------------------------------------------------------------------
    # Memory module Fakes (ADR-030)
    # ------------------------------------------------------------------

    def test_fake_feedback_repo(self) -> None:
        """FakeFeedbackRepository implements FeedbackRepositoryProtocol."""
        from narrare.memory.contracts import FeedbackRepositoryProtocol
        from tests.fakes import FakeFeedbackRepository

        assert_implements_protocol(FakeFeedbackRepository, FeedbackRepositoryProtocol)

    def test_fake_preference_profile_repo(self) -> None:
        """FakePreferenceProfileRepository implements PreferenceProfileRepositoryProtocol."""
        from narrare.memory.contracts import PreferenceProfileRepositoryProtocol
        from tests.fakes import FakePreferenceProfileRepository

        assert_implements_protocol(
            FakePreferenceProfileRepository, PreferenceProfileRepositoryProtocol
        )


class TestFakeIsinstance:
    """Every @runtime_checkable Fake must pass isinstance() for structural subtyping."""

    def test_fake_auth_repo_isinstance(self) -> None:
        from narrare.auth.contracts import AuthRepositoryProtocol
        from tests.fakes import FakeAuthRepository

        _assert_isinstance(FakeAuthRepository, AuthRepositoryProtocol)

    def test_fake_novel_repo_isinstance(self) -> None:
        from narrare.novels.contracts import NovelRepositoryProtocol
        from tests.fakes import FakeNovelRepository

        _assert_isinstance(FakeNovelRepository, NovelRepositoryProtocol)

    def test_fake_chapter_repo_isinstance(self) -> None:
        from narrare.chapters.contracts import ChapterRepositoryProtocol
        from tests.fakes import FakeChapterRepository

        _assert_isinstance(FakeChapterRepository, ChapterRepositoryProtocol)

    def test_fake_volume_repo_isinstance(self) -> None:
        from narrare.volumes.contracts import VolumeRepositoryProtocol
        from tests.fakes import FakeVolumeRepository

        _assert_isinstance(FakeVolumeRepository, VolumeRepositoryProtocol)

    def test_fake_novel_service_isinstance(self) -> None:
        from narrare.novels.contracts import NovelServiceProtocol
        from tests.fakes import FakeNovelService

        _assert_isinstance(FakeNovelService, NovelServiceProtocol)

    def test_fake_llm_gateway_isinstance(self) -> None:
        from narrare_core.llm.contracts import ModelRegistryProtocol
        from tests.fakes import FakeLLMGateway

        _assert_isinstance(FakeLLMGateway, ModelRegistryProtocol)

    def test_fake_provider_service_isinstance(self) -> None:
        from narrare.setup.contracts import ProviderServiceProtocol
        from tests.fakes import FakeProviderService

        _assert_isinstance(FakeProviderService, ProviderServiceProtocol)

    def test_fake_demo_loader_isinstance(self) -> None:
        from narrare.setup.contracts import DemoLoaderProtocol
        from tests.fakes import FakeDemoLoader

        _assert_isinstance(FakeDemoLoader, DemoLoaderProtocol)

    def test_fake_embedding_repo_isinstance(self) -> None:
        from narrare.embeddings.contracts import EmbeddingRepositoryProtocol
        from tests.fakes import FakeEmbeddingRepository

        _assert_isinstance(FakeEmbeddingRepository, EmbeddingRepositoryProtocol)

    def test_fake_user_settings_repo_isinstance(self) -> None:
        from narrare.settings.contracts import UserSettingsRepositoryProtocol
        from tests.fakes import FakeUserSettingsRepository

        _assert_isinstance(FakeUserSettingsRepository, UserSettingsRepositoryProtocol)

    def test_fake_outline_repo_isinstance(self) -> None:
        from narrare.planning.contracts import OutlineRepositoryProtocol
        from tests.fakes import FakeOutlineRepository

        _assert_isinstance(FakeOutlineRepository, OutlineRepositoryProtocol)

    # ------------------------------------------------------------------
    # Memory module Fakes (ADR-030)
    # ------------------------------------------------------------------

    def test_fake_feedback_repo_isinstance(self) -> None:
        """FakeFeedbackRepository passes isinstance check for FeedbackRepositoryProtocol."""
        from narrare.memory.contracts import FeedbackRepositoryProtocol
        from tests.fakes import FakeFeedbackRepository

        _assert_isinstance(FakeFeedbackRepository, FeedbackRepositoryProtocol)

    def test_fake_preference_profile_repo_isinstance(self) -> None:
        """FakePreferenceProfileRepository matches PreferenceProfileRepositoryProtocol."""
        from narrare.memory.contracts import PreferenceProfileRepositoryProtocol
        from tests.fakes import FakePreferenceProfileRepository

        _assert_isinstance(FakePreferenceProfileRepository, PreferenceProfileRepositoryProtocol)
