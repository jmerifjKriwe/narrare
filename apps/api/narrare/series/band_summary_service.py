"""BandSummaryService — generate / lazy / override (Spec 2, Task 3).

Business logic only (RULE-06): no SQL, no HTTP. Delegates persistence to
``BandSummaryRepository`` and the LLM call to ``BandSummaryAgent`` (agents are
the primary LLM surface — RULE-01b). Prompts come from ``PromptComposer``
(RULE-02/02b: no inline prompt strings); chapter summaries flow as runtime
content in the agent run prompt (RULE-02a category 3 — user channel).

Chapter summaries are sourced from ``Chapter.summary`` (``chapters/models.py``)
via ``list_by_novel``; only non-empty summaries are aggregated. Novel metadata
(title, genre, writing_language) comes from ``NovelRepository.get``.

Testability (ADR-030 — Fake-based): the agent is injectable via
``agent_factory`` (default → real ``BandSummaryAgent``) so unit tests supply a
fake agent whose ``.run()`` returns a controlled ``BandSummaryOutput``, instead
of ``unittest.mock.patch``-ing the class. This mirrors how
``FakeLLMGateway`` makes ``ChapterSummaryService`` testable, but at the agent
boundary because that is the LLM surface here.

Model acquisition (ADR-086 L25): the service receives a deferred
``model_runtime_factory`` (composed by the DI factory from the SUMMARIZE
routing cascade + token-limits cascade) and resolves it ONCE at first use
(:meth:`ensure_resolved`, the top of ``generate``) — never at construction.
``get`` / ``update_override`` consume no resolution at all.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from narrare.series._band_summary_support import run_band_summary_invocation
from narrare.series.band_summary_prompt import compose_band_summary_system_prompt
from narrare_core.agents.band_summary_agent import BandSummaryAgent
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.shared.errors import NotFoundError, ValidationError, WritingError

if TYPE_CHECKING:
    import uuid
    from collections.abc import Awaitable, Callable

    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.kb.context_contracts import KBContextProviderProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.series._band_summary_support import BandSummaryModelRuntime
    from narrare.series.band_summary_contracts import BandSummaryRepositoryProtocol
    from narrare.series.band_summary_models import BandSummary
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


def _default_agent_factory(model: Any, system_prompt: str | None = None) -> BandSummaryAgent:
    """Production agent factory (overridable in tests for Fake injection)."""
    return BandSummaryAgent(model=model, system_prompt=system_prompt)


class BandSummaryService:
    """Generates + manages novel-level band summaries for series history.

    Three operations back the Band Summary API (Task 4) and the auto-trigger
    (Task 5):

    - ``generate`` — fetch chapter summaries → run ``BandSummaryAgent`` → upsert.
    - ``get_or_generate`` — lazy: return existing (if override/full set) else
      generate on demand. Used by ``SeriesHistoryTier`` (Task 6).
    - ``update_override`` — set or clear the user override (precedence over
      generated text at assembly time).

    All dependencies are injected (RULE-07). Ownership/authorisation is
    enforced at the router boundary (Task 4) — this service is keyed by
    ``novel_id`` and is also usable from non-request contexts (in-process
    auto-trigger, Task 5).
    """

    def __init__(
        self,
        *,
        repo: BandSummaryRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol,
        chapter_repo: ChapterRepositoryProtocol,
        registry: ModelRegistry,
        model_runtime_factory: Callable[[], Awaitable[BandSummaryModelRuntime]],
        composer: PromptComposer,
        agent_factory: Callable[..., BandSummaryAgent] | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
        kb_context_provider: KBContextProviderProtocol | None = None,
        run_limit_resolver: DefaultRunLimitResolver | None = None,
    ) -> None:
        """Initialise the service with all dependencies.

        Args:
            repo: Band-summary persistence (upsert / override).
            novel_repo: Novel metadata (title, genre, writing_language).
            chapter_repo: Chapter summaries (``list_by_novel`` → ``.summary``).
            registry: Model registry for resolving the LLM model instance.
            model_runtime_factory: Zero-arg async callable returning the frozen
                :class:`BandSummaryModelRuntime` (composed by the DI factory
                from BOTH cascades at first use — ADR-086 M-budget).
            composer: PromptComposer for the governed band_summary system prompt.
            agent_factory: Callable ``(model, system_prompt) -> BandSummaryAgent``.
                Defaults to the real constructor; tests inject a Fake.
            invocation_pipeline: Optional InvocationPipeline for evidence.
            kb_context_provider: Optional canonical KB-context provider
                (ADR-067) for the kb_characters / kb_locations / kb_factions /
                kb_relationships prompt variables. ``None`` degrades to an
                empty bundle (RULE-11).
            run_limit_resolver: Optional ADR-045 run-limit resolver; defaults to
                ``DefaultRunLimitResolver`` (Task 3 wiring).
        """
        self._repo = repo
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._registry = registry
        self._model_runtime_factory = model_runtime_factory
        self._model_runtime: BandSummaryModelRuntime | None = None
        self._composer = composer
        self._agent_factory = agent_factory or _default_agent_factory
        self._invocation_pipeline = invocation_pipeline
        self._kb_context_provider = kb_context_provider
        self._run_limit_resolver = run_limit_resolver or DefaultRunLimitResolver()

    async def ensure_resolved(self) -> BandSummaryModelRuntime:
        """Resolve BOTH cascades once and cache the runtime; idempotent.

        First call runs the deferred factory composition (SUMMARIZE routing
        + token limits, ADR-086 M-budget); repeat calls return the cached
        runtime. Errors propagate loudly and are never cached (RULE-11):
        ``ConfigurationError`` (``NO_AI_PROVIDER``) surfaces as a 400 —
        the eager factory's wiring-time error, now at first use.
        """
        if self._model_runtime is None:
            self._model_runtime = await self._model_runtime_factory()
        return self._model_runtime

    async def get(self, novel_id: uuid.UUID) -> BandSummary:
        """Return the existing band summary (no generation).

        Used by the GET endpoint (Task 4) to fetch a previously generated
        summary without triggering an LLM call. Distinct from
        ``get_or_generate`` (lazy) and ``generate`` (forced).

        Raises:
            NotFoundError: If no band summary row exists for ``novel_id``.
        """
        existing = await self._repo.get(novel_id)
        if existing is None:
            raise NotFoundError("BandSummary", identifier=str(novel_id))
        return existing

    async def generate(self, novel_id: uuid.UUID) -> BandSummary:
        """Auto-generate: fetch chapter summaries → agent → upsert.

        Args:
            novel_id: The novel (band) to summarise.

        Returns:
            The upserted ``BandSummary`` row.

        Raises:
            NotFoundError: The novel does not exist.
            ValidationError: The novel has no chapter summaries to aggregate.
            ConfigurationError: No AI provider is configured for the owner
                (RULE-11 — propagates loudly, un-wrapped).
            WritingError: The LLM call or persistence failed.
        """
        # 0. Resolve BOTH cascades once at first use (ADR-086 L25). This
        #    deliberately runs BEFORE the try-wrapper below and before the
        #    novel/summaries guards, preserving the eager world's ordering
        #    (the factory resolved pre-entry) AND keeping ConfigurationError
        #    OUT of the broad ``except Exception`` → WritingError wrapper —
        #    an unconfigured provider stays a loud 400, never a 500.
        runtime = await self.ensure_resolved()

        # 1. Load novel metadata (title, genre, writing_language).
        novel = await self._novel_repo.get(novel_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        # 2. Aggregate non-empty chapter summaries, ordered by position
        #    (ChapterRepository.list_by_novel already orders by position).
        chapters = await self._chapter_repo.list_by_novel(novel_id)
        chapter_summaries = [c.summary for c in chapters if c.summary.strip()]
        if not chapter_summaries:
            # RULE-11: fail fast + explicit. The agent validator requires
            # non-empty output, so aggregating nothing would hallucinate;
            # callers (auto-trigger, lazy tier) catch this to degrade.
            logger.info("band_summary_skipped_no_summaries", novel_id=str(novel_id))
            raise ValidationError(
                "Cannot generate band summary: the novel has no chapter summaries to aggregate"
            )

        # 3. Compose the governed band_summary system prompt (RULE-02/02b).
        #    Mode 1 (composer-driven) with pipeline fallback to direct build.
        language = novel.writing_language or "en"
        system_prompt = await self._compose_system_prompt(
            novel_title=novel.title,
            genre=novel.genre,
            language=language,
            novel_id=novel_id,
        )

        try:
            # 4-5. Resolve model + run the agent (RULE-01b agents-first) —
            #      invocation assembly delegated to the support module
            #      (RULE-04 split; same behavior, only relocated).
            result = await run_band_summary_invocation(
                run_limit_resolver=self._run_limit_resolver,
                runtime=runtime,
                registry=self._registry,
                agent_factory=self._agent_factory,
                system_prompt=system_prompt,
                novel_title=novel.title,
                genre=novel.genre,
                chapter_summaries=chapter_summaries,
            )

            # 6. Upsert generated summaries (override preserved by the repo).
            band_summary = await self._repo.upsert(
                novel_id,
                full_summary=result.full_summary,
                short_summary=result.short_summary,
            )
            logger.info(
                "band_summary_generated",
                novel_id=str(novel_id),
                chapter_count=len(chapter_summaries),
            )
            return band_summary

        except NotFoundError:
            raise
        except ValidationError:
            raise
        except Exception as exc:
            logger.error(
                "band_summary_generation_failed",
                novel_id=str(novel_id),
                error=str(exc),
                exc_info=True,
            )
            raise WritingError("Band summary generation failed") from exc

    async def get_or_generate(self, novel_id: uuid.UUID) -> BandSummary:
        """Lazy: return existing summary if useful, else generate on demand.

        A row counts as "useful" when it has an override OR a full_summary —
        an empty placeholder row (e.g. created by a lone clear_override) is
        treated as missing and regenerated.
        """
        existing = await self._repo.get(novel_id)
        if existing is not None and (existing.override or existing.full_summary):
            return existing
        return await self.generate(novel_id)

    async def update_override(self, novel_id: uuid.UUID, override: str | None) -> BandSummary:
        """Set or clear the user override.

        An empty/whitespace override is treated as "clear" so no empty
        override is ever persisted.
        """
        if override and override.strip():
            return await self._repo.set_override(novel_id, override)
        return await self._repo.clear_override(novel_id)

    async def _compose_system_prompt(
        self,
        *,
        novel_title: str,
        genre: str,
        language: str,
        novel_id: uuid.UUID,
    ) -> str:
        """Resolve the governed ``band_summary`` system prompt (RULE-02b).

        Delegated to :mod:`narrare.series.band_summary_prompt` (RULE-04
        split — prompt composition is a separate responsibility from the
        generate/persist flow). The optional KB-context provider is
        forwarded so the prompt module can supply the kb_* variables
        (inert pre-activation — see there).
        """
        return await compose_band_summary_system_prompt(
            composer=self._composer,
            invocation_pipeline=self._invocation_pipeline,
            novel_title=novel_title,
            genre=genre,
            language=language,
            novel_id=novel_id,
            kb_context_provider=self._kb_context_provider,
        )
