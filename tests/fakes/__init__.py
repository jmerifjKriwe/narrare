"""
Fake test infrastructure for Narrare.

Every Fake class implements the corresponding Protocol from contracts.py.
Used in unit tests instead of MagicMock — see RULE-TEST-01 in testing-standards.md.

Usage:
    from tests.fakes import FakeLLMGateway, FakeChapterRepository

    fake_repo = FakeChapterRepository()
    fake_repo.seed(make_chapter(id=uuid4(), novel_id=uuid4()))

    fake_gateway = FakeLLMGateway()
    fake_gateway.returns("Generated text")
"""

from tests.fakes.fake_llm_gateway import FakeLLMGateway
from tests.fakes.fake_repositories import (
    FakeAuthRepository,
    FakeChapterRepository,
    FakeNovelRepository,
    FakeVolumeRepository,
)
from tests.fakes.fake_services import (
    FakeNovelService,
)
from tests.fakes.fake_setup import FakeDemoLoader, FakeProviderService

__all__ = [
    "FakeAuthRepository",
    "FakeChapterRepository",
    "FakeDemoLoader",
    "FakeLLMGateway",
    "FakeNovelRepository",
    "FakeNovelService",
    "FakeProviderService",
    "FakeVolumeRepository",
]
