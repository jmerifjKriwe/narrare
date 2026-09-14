"""Shared fakes + fixtures for SeriesConsistencyService unit tests (ADR-030).

Mirrors ``_band_summary_test_helpers.py`` (the same-module precedent — same
agent_factory injection pattern). Domain behaviour is faked with real classes,
not ``MagicMock``:

- The series/novel/chapter repositories use the shared ``tests.fakes.*``
  in-memory fakes.
- The Canon KB surface uses :class:`FakeScopeKBRepo` (has
  ``find_canon_for_series``, returns real :class:`SeriesKBEntry` objects).
- The LLM seam (``SeriesConsistencyAgent``) is injectable via ``agent_factory``
  so tests supply :class:`FakeSeriesConsistencyAgent` whose ``.run()`` returns a
  controlled ``SeriesConsistencyOutput``.
- ``compose_invocation`` runs for real with ``invocation_pipeline=None`` and the
  FakeComposer (mirrors how ``_band_summary_test_helpers`` exercises the prompt
  path without patching).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from narrare._app.dependencies_services import StaticModelResolution
from narrare.series.series_consistency_service import SeriesConsistencyService
from narrare_core.agents.series_consistency_types import (
    CanonConflict,
    SeriesConsistencyOutput,
)
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.prompts.composer import ComposedPrompt
from tests.fakes.fake_chapter_repo import FakeChapterRepository
from tests.fakes.fake_kb_scope_repo import FakeScopeKBRepo
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.fakes.fake_series_repo import FakeSeriesRepository

if TYPE_CHECKING:
    from collections.abc import Sequence


class FakeSeriesConsistencyComposer:
    """Minimal PromptComposer fake — always returns a fixed composed prompt."""

    def __init__(self) -> None:
        self.build_calls: list[tuple[Any, Any]] = []

    async def build(self, intent: Any, context: Any) -> ComposedPrompt:
        self.build_calls.append((intent, context))
        return ComposedPrompt(system="You are a series-consistency checker.", user="")


class FakeSeriesConsistencyRegistry:
    """Minimal ModelRegistry fake — returns a sentinel model object."""

    def __init__(self) -> None:
        self.get_model_calls: int = 0

    async def get_model(
        self,
        config: Any,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> Any:
        # api_key/base_url: per-user routing credentials — accepted for
        # protocol fidelity with ModelRegistry.get_model; the fake ignores
        # them.
        self.get_model_calls += 1
        return object()  # the agent factory ignores it in tests

    async def prepare(
        self,
        config: Any,
        *,
        intent: Any = None,
        usage_limits: Any = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> Any:
        """Task-6d bridge: resolution flows through prepare → get_model.

        The service (Task 6d-2) resolves via the single assembly point;
        the bridge forwards the intent/credential pass-throughs so the
        existing get_model-based tests keep their semantics.
        """
        _ = intent
        return SimpleNamespace(
            model=await self.get_model(config, api_key=api_key, base_url=base_url),
            model_settings=None,
            usage_limits=usage_limits,
        )


class FakeSeriesConsistencyAgent:
    """Fake SeriesConsistencyAgent — records the run call and returns fixed output.

    Configurable via ``output`` / ``raises``; captures ``last_deps`` /
    ``last_prompt`` for assertions. Task 6d-2: ``last_model`` (set by the
    service's agent factory) and ``last_run_kwargs`` record the coherent
    prepare() triple at the agent boundary.
    """

    def __init__(
        self,
        output: SeriesConsistencyOutput | None = None,
        raises: BaseException | None = None,
    ) -> None:
        self._output = output or _make_clean_output()
        self._raises = raises
        self.last_deps: Any = None
        self.last_prompt: str = ""
        self.last_model: Any = None
        self.last_run_kwargs: dict[str, Any] = {}
        self.run_count: int = 0

    async def run(self, prompt: str, deps: Any, **kwargs: Any) -> SeriesConsistencyOutput:
        self.last_prompt = prompt
        self.last_deps = deps
        self.last_run_kwargs = kwargs
        self.run_count += 1
        if self._raises is not None:
            raise self._raises
        return self._output


def _make_clean_output() -> SeriesConsistencyOutput:
    """Default agent output: no contradictions found (empty conflicts list)."""
    return SeriesConsistencyOutput(
        conflicts=[],
        summary="No contradictions between the chapter text and the series Canon.",
    )


def make_conflict(
    *,
    slug: str = "character-elara-eye-color",
    name: str = "Elara — Eye Color",
    severity: str = "error",
) -> CanonConflict:
    """Build a single CanonConflict fixture for result-assertion tests."""
    return CanonConflict(
        canon_entry_slug=slug,
        canon_entry_name=name,
        chapter_text_excerpt="Elara's green eyes scanned the horizon.",
        canon_statement="Elara has blue eyes.",
        explanation="The chapter describes green eyes; Canon records blue.",
        severity=severity,  # type: ignore[arg-type]
    )


def make_config() -> ResolvedModelConfig:
    """A default ``ResolvedModelConfig`` for SeriesConsistencyService tests."""
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


def make_service(
    *,
    series_repo: FakeSeriesRepository | None = None,
    novel_repo: FakeNovelRepository | None = None,
    chapter_repo: FakeChapterRepository | None = None,
    kb_repo: FakeScopeKBRepo | None = None,
    agent: FakeSeriesConsistencyAgent | None = None,
    composer: FakeSeriesConsistencyComposer | None = None,
    registry: Any | None = None,
    config: ResolvedModelConfig | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> tuple[
    SeriesConsistencyService,
    FakeSeriesConsistencyAgent,
    FakeScopeKBRepo,
    FakeSeriesRepository,
    FakeNovelRepository,
    FakeChapterRepository,
]:
    """Build a SeriesConsistencyService wired with fakes + a fake agent factory.

    ADR-086 L26: ``config`` / ``api_key`` / ``base_url`` overrides feed a
    ``StaticModelResolution`` (the fixed-resolution test adapter) — the
    service resolves the triple from it on first use, exactly as it would
    from the production ``LazyModelResolution``. The agent factory records
    the resolved model on ``agent.last_model``.

    Returns ``(service, agent, kb_repo, series_repo, novel_repo, chapter_repo)``
    so tests can seed data and assert interactions.
    """
    series_repo = series_repo or FakeSeriesRepository()
    novel_repo = novel_repo or FakeNovelRepository()
    chapter_repo = chapter_repo or FakeChapterRepository()
    kb_repo = kb_repo or FakeScopeKBRepo()
    agent = agent or FakeSeriesConsistencyAgent()
    composer = composer or FakeSeriesConsistencyComposer()
    registry = registry or FakeSeriesConsistencyRegistry()

    def _agent_factory(model: Any, system_prompt: Any = None) -> FakeSeriesConsistencyAgent:
        del system_prompt
        agent.last_model = model
        return agent

    service = SeriesConsistencyService(
        series_repo=series_repo,  # type: ignore[arg-type]
        novel_repo=novel_repo,  # type: ignore[arg-type]
        chapter_repo=chapter_repo,  # type: ignore[arg-type]
        kb_repo=kb_repo,  # type: ignore[arg-type]
        registry=registry,  # type: ignore[arg-type]
        model_resolution=StaticModelResolution(
            ResolvedModel(
                config=config or make_config(),
                api_key=api_key,
                base_url=base_url,
                source="unit-test",
            )
        ),
        composer=composer,  # type: ignore[arg-type]
        agent_factory=_agent_factory,  # type: ignore[arg-type]
    )
    return service, agent, kb_repo, series_repo, novel_repo, chapter_repo


def seed_owned_series_with_canon(
    *,
    series_repo: FakeSeriesRepository,
    novel_repo: FakeNovelRepository,
    chapter_repo: FakeChapterRepository,
    kb_repo: FakeScopeKBRepo,
    user_id: Any,
    canon_slugs: Sequence[str] = ("character-elara-eye-color",),
    chapter_prose: Sequence[str] = ("Elara's green eyes scanned the horizon.",),
) -> tuple[Any, Any]:
    """Seed an owned series + one member novel with Canon entries + prose chapters.

    Returns ``(series_id, novel_id)``. The series owns ``user_id``; the novel's
    ``series_id`` is set so membership verification passes.
    """
    import uuid

    series_id = uuid.uuid4()
    novel_id = uuid.uuid4()
    from narrare_core.series.schemas import Series

    series_repo.seed(
        Series(id=series_id, user_id=user_id, title="The Expanse", writing_language="en")
    )
    novel_repo.seed(_make_member_novel(id=novel_id, user_id=user_id, series_id=series_id))
    for slug in canon_slugs:
        kb_repo.seed_entry(
            slug=slug,
            entity_type="character",
            name=slug.replace("-", " ").title(),
            series_id=series_id,
        )
    for position, prose in enumerate(chapter_prose, start=1):
        chapter_repo.seed(_make_chapter(novel_id=novel_id, position=position, content=prose))
    return series_id, novel_id


def _make_member_novel(**overrides: Any) -> Any:
    """Build a novel fixture that belongs to a series."""
    from tests.factories import make_novel

    return make_novel(**overrides)


def _make_chapter(**overrides: Any) -> Any:
    """Build a chapter fixture with prose."""
    from tests.factories import make_chapter

    return make_chapter(**overrides)
