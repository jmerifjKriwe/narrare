"""Shared fakes + fixtures for BandSummaryService unit tests (ADR-030).

Extracted from ``test_band_summary_service.py`` so the test module stays under
the RULE-04 300-line limit (mirrors ``_author_voice_test_helpers.py`` /
``_voice_drift_test_helpers.py``). Domain behaviour is faked with real classes,
not ``MagicMock``: the agent is injectable via ``agent_factory`` so tests
supply ``_FakeBandSummaryAgent`` whose ``.run()`` returns a controlled
``BandSummaryOutput``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

from narrare.series._band_summary_support import BandSummaryModelRuntime
from narrare.series.band_summary_service import BandSummaryService
from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
from narrare_core.agents.band_summary_types import BandSummaryOutput
from narrare_core.llm import ResolvedModelConfig
from narrare_core.prompts.composer import ComposedPrompt
from tests.fakes.fake_band_summary_repo import FakeBandSummaryRepository
from tests.fakes.fake_chapter_repo import FakeChapterRepository
from tests.fakes.fake_novel_repo import FakeNovelRepository

if TYPE_CHECKING:
    from collections.abc import Callable

    from narrare.kb.context_contracts import KBContextProviderProtocol
    from narrare_core.prompts.composer import PromptComposer


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


class FakeBandSummaryAgent:
    """Fake BandSummaryAgent — records the run call and returns fixed output.

    Configurable via ``raises``; captures ``last_deps`` / ``last_prompt`` for
    assertions. Task 6d-2: ``last_model`` (set by the service's agent
    factory) and ``last_run_kwargs`` record the coherent prepare() triple
    at the agent boundary.
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
        self.last_model: Any = None
        self.last_run_kwargs: dict[str, Any] = {}
        self.run_count: int = 0

    async def run(self, prompt: str, deps: Any, **kwargs: Any) -> BandSummaryOutput:
        self.last_prompt = prompt
        self.last_deps = deps
        self.last_run_kwargs = kwargs
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


def make_static_runtime_factory(
    config: ResolvedModelConfig,
    api_key: str | None,
    base_url: str | None,
) -> Callable[[], Any]:
    """A zero-arg async factory returning a fixed ``BandSummaryModelRuntime``.

    Test-side stand-in for the DI factory's deferred composition (ADR-086
    L25): injects the pre-resolved triple without touching either cascade.
    """

    async def _factory() -> BandSummaryModelRuntime:
        return BandSummaryModelRuntime(config=config, api_key=api_key, base_url=base_url)

    return _factory


# ---------------------------------------------------------------------------
# ADR-086 L25 lazy-wiring harness (shared by the lazy-resolution test files)
# ---------------------------------------------------------------------------


def make_user_routing_config() -> ResolvedModelConfig:
    """The config the eager factory's routing cascade would return (0.7 base
    temperature — deliberately different from the 0.3 overlay so overlay
    assertions are meaningful)."""
    return ResolvedModelConfig(
        provider_name="zai",
        model_id="glm-4.7",
        temperature=0.7,
        max_tokens=4096,
    )


def make_resolved_model(
    config: ResolvedModelConfig | None = None,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Any:
    """A ``ResolvedModel`` as the routing cascade would return it."""
    from narrare_core.llm.model_routing import ResolvedModel

    return ResolvedModel(
        config=config or make_user_routing_config(),
        api_key=api_key,
        base_url=base_url,
        source="unit-test",
    )


class FakeTokenLimitsService:
    """Fake TokenLimitsService — records cascade calls, fixed output limit."""

    def __init__(self, output_limit: int = 4096) -> None:
        self.output_limit = output_limit
        self.calls: list[dict[str, str | None]] = []

    async def get_resolved_limits(self, *, user_id: str, project_id: str | None) -> Any:
        self.calls.append({"user_id": user_id, "project_id": project_id})
        return SimpleNamespace(output_limit=self.output_limit, tier_percentages=None)


class BandSummaryLazyWiringHarness:
    """Patches the band-summary factory's wiring surface (ADR-086 L25).

    Exposes cascade-counting fakes: ``resolver.resolve`` (spec'd MagicMock,
    replaceable via ``resolver``) and ``limits_service``. ``async with``
    starts/stops the patches.
    """

    def __init__(self, resolver: Any | None = None) -> None:
        import narrare.series.dependencies_band_summary as deps_module

        self._deps_module = deps_module
        self.resolved = make_resolved_model(api_key="sk-user-key", base_url="https://u.example/v1")
        self.resolver = (
            resolver
            if resolver is not None
            else MagicMock(spec=ModelRoutingResolverImpl, name="ModelRoutingResolver")
        )
        if resolver is None:
            self.resolver.resolve = AsyncMock(return_value=self.resolved)
        self.limits_service = FakeTokenLimitsService(output_limit=2048)
        self.registry = MagicMock(spec=["get_model", "prepare"], name="ModelRegistry")
        self.composer = MagicMock(spec=["build"], name="PromptComposer")
        self.pipeline = MagicMock(spec=["generate"], name="InvocationPipeline")
        self._patches = [
            patch.object(deps_module, "get_model_routing_resolver", return_value=self.resolver),
            patch(
                "narrare.settings.token_limits.service.TokenLimitsService",
                return_value=self.limits_service,
            ),
            patch(
                "narrare._app.config.get_settings",
                return_value=MagicMock(spec=True, name="Settings"),
            ),
            patch.object(deps_module, "get_model_registry", return_value=self.registry),
            patch.object(deps_module, "get_composer", return_value=self.composer),
            patch.object(deps_module, "get_invocation_pipeline", return_value=self.pipeline),
        ]

    async def __aenter__(self) -> BandSummaryLazyWiringHarness:
        for p in self._patches:
            p.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        for p in self._patches:
            p.stop()


def make_band_summary_service(
    *,
    novel_repo: FakeNovelRepository | None = None,
    chapter_repo: FakeChapterRepository | None = None,
    repo: FakeBandSummaryRepository | None = None,
    agent: FakeBandSummaryAgent | None = None,
    composer: FakeBandSummaryComposer | PromptComposer | None = None,
    registry: Any | None = None,
    config: ResolvedModelConfig | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    kb_context_provider: KBContextProviderProtocol | None = None,
    agent_factory: Callable[..., Any] | None = None,
) -> tuple[BandSummaryService, FakeBandSummaryAgent, FakeBandSummaryRepository]:
    """Build a ``BandSummaryService`` wired with fakes + a fake agent factory.

    Task 6d-2: ``config`` / ``api_key`` / ``base_url`` overrides let wiring
    tests inject the recorded prepare() registry + per-user credentials.
    The agent factory records the resolved model on ``agent.last_model``.
    ``composer`` accepts the real ``PromptComposer`` (prompt-render tests
    compose the governed template through the real cascade) and
    ``kb_context_provider`` the ADR-067 provider (Slice 5 kb_* supply).
    ``agent_factory`` overrides the default discarding factory (system-prompt
    capture tests).

    Returns ``(service, agent, repo)`` so tests can assert interactions.
    """
    novel_repo = novel_repo or FakeNovelRepository()
    chapter_repo = chapter_repo or FakeChapterRepository()
    repo = repo or FakeBandSummaryRepository()
    agent = agent or FakeBandSummaryAgent()
    composer = composer or FakeBandSummaryComposer()
    registry = registry or FakeBandSummaryRegistry()

    def _agent_factory(model: Any, system_prompt: Any = None) -> FakeBandSummaryAgent:
        del system_prompt
        agent.last_model = model
        return agent

    service = BandSummaryService(
        repo=repo,  # type: ignore[arg-type]
        novel_repo=novel_repo,  # type: ignore[arg-type]
        chapter_repo=chapter_repo,  # type: ignore[arg-type]
        registry=registry,  # type: ignore[arg-type]
        model_runtime_factory=make_static_runtime_factory(
            config or make_band_summary_config(), api_key, base_url
        ),
        composer=composer,  # type: ignore[arg-type]
        agent_factory=agent_factory or _agent_factory,  # type: ignore[arg-type]
        kb_context_provider=kb_context_provider,
    )
    return service, agent, repo
