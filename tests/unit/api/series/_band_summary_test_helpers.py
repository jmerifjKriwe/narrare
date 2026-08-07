"""Shared fakes + fixtures for BandSummaryService unit tests (ADR-030).

Extracted from ``test_band_summary_service.py`` so the test module stays under
the RULE-04 300-line limit (mirrors ``_author_voice_test_helpers.py`` /
``_voice_drift_test_helpers.py``). Domain behaviour is faked with real classes,
not ``MagicMock``: the agent is injectable via ``agent_factory`` so tests
supply ``_FakeBandSummaryAgent`` whose ``.run()`` returns a controlled
``BandSummaryOutput``.
"""

from __future__ import annotations

from typing import Any

from narrare.series.band_summary_service import BandSummaryService
from narrare_core.agents.band_summary_types import BandSummaryOutput
from narrare_core.llm import ResolvedModelConfig
from narrare_core.prompts.composer import ComposedPrompt
from tests.fakes.fake_band_summary_repo import FakeBandSummaryRepository
from tests.fakes.fake_chapter_repo import FakeChapterRepository
from tests.fakes.fake_novel_repo import FakeNovelRepository


class FakeBandSummaryComposer:
    """Minimal PromptComposer fake — always returns a fixed composed prompt."""

    def __init__(self) -> None:
        self.build_calls: list[tuple[Any, Any]] = []

    async def build(self, intent: Any, context: Any) -> ComposedPrompt:
        self.build_calls.append((intent, context))
        return ComposedPrompt(system="You are a band summariser.", user="")


class FakeBandSummaryRegistry:
    """Minimal ModelRegistry fake — returns a sentinel model object."""

    def __init__(self) -> None:
        self.get_model_calls: int = 0

    async def get_model(
        self, config: Any, *, api_key: str | None = None, base_url: str | None = None
    ) -> Any:
        self.get_model_calls += 1
        return object()  # the agent factory ignores it in tests


class FakeBandSummaryAgent:
    """Fake BandSummaryAgent — records the run call and returns fixed output.

    Configurable via ``raises``; captures ``last_deps`` / ``last_prompt`` for
    assertions.
    """

    def __init__(
        self,
        output: BandSummaryOutput | None = None,
        raises: BaseException | None = None,
    ) -> None:
        self._output = output or BandSummaryOutput(
            full_summary="The hero prevails and the realm is restored.",
            short_summary="A hero restores a fractured realm.",
        )
        self._raises = raises
        self.last_deps: Any = None
        self.last_prompt: str = ""
        self.run_count: int = 0

    async def run(self, prompt: str, deps: Any, **kwargs: Any) -> BandSummaryOutput:
        self.last_prompt = prompt
        self.last_deps = deps
        self.run_count += 1
        if self._raises is not None:
            raise self._raises
        return self._output


def make_band_summary_config() -> ResolvedModelConfig:
    """A default ``ResolvedModelConfig`` for BandSummaryService tests."""
    return ResolvedModelConfig(
        provider_name="anthropic",
        model_id="claude-sonnet-4-5-20251020",
        temperature=0.3,
        max_tokens=2000,
    )


def make_band_summary_service(
    *,
    novel_repo: FakeNovelRepository | None = None,
    chapter_repo: FakeChapterRepository | None = None,
    repo: FakeBandSummaryRepository | None = None,
    agent: FakeBandSummaryAgent | None = None,
    composer: FakeBandSummaryComposer | None = None,
    registry: FakeBandSummaryRegistry | None = None,
) -> tuple[BandSummaryService, FakeBandSummaryAgent, FakeBandSummaryRepository]:
    """Build a ``BandSummaryService`` wired with fakes + a fake agent factory.

    Returns ``(service, agent, repo)`` so tests can assert interactions.
    """
    novel_repo = novel_repo or FakeNovelRepository()
    chapter_repo = chapter_repo or FakeChapterRepository()
    repo = repo or FakeBandSummaryRepository()
    agent = agent or FakeBandSummaryAgent()
    composer = composer or FakeBandSummaryComposer()
    registry = registry or FakeBandSummaryRegistry()

    service = BandSummaryService(
        repo=repo,  # type: ignore[arg-type]
        novel_repo=novel_repo,  # type: ignore[arg-type]
        chapter_repo=chapter_repo,  # type: ignore[arg-type]
        registry=registry,  # type: ignore[arg-type]
        config=make_band_summary_config(),
        composer=composer,  # type: ignore[arg-type]
        agent_factory=lambda model, system_prompt=None: agent,  # type: ignore[arg-type]
    )
    return service, agent, repo
