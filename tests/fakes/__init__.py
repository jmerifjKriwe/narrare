"""
Fake test infrastructure for Narrare.

Every Fake class implements the corresponding Protocol from contracts.py.
Used in unit tests instead of MagicMock — see RULE-TEST-01 in testing-standards.md.

Usage:
    from tests.fakes import FakeModelRegistry, FakeLLMGateway

    fake_registry = FakeModelRegistry()
    fake_registry.returns("Generated text")

    # Or use backward-compatible FakeLLMGateway:
    fake_gateway = FakeLLMGateway()
    fake_gateway.returns("Generated text")
"""

from tests.fakes.fake_auth_repository import FakeAuthRepository
from tests.fakes.fake_chapter_repo import FakeChapterRepository
from tests.fakes.fake_llm_gateway import FakeLLMGateway, FakeModelRegistry
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.fakes.fake_outline_repo import FakeOutlineRepository
from tests.fakes.fake_services import (
    FakeNovelService,
)
from tests.fakes.fake_setup import FakeDemoLoader, FakeProviderService
from tests.fakes.fake_user_settings_repo import FakeUserSettingsRepository
from tests.fakes.fake_volume_repo import FakeVolumeRepository

__all__ = [
    "FakeAuthRepository",
    "FakeChapterRepository",
    "FakeDemoLoader",
    "FakeLLMGateway",
    "FakeModelRegistry",
    "FakeNovelRepository",
    "FakeNovelService",
    "FakeOutlineRepository",
    "FakeProviderService",
    "FakeUserSettingsRepository",
    "FakeVolumeRepository",
]
