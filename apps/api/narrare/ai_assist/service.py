"""DialogueCoachService — Backend orchestrator (ASSIST-004 / ADR-069 D17).

Implements ``DialogueCoachServiceProtocol`` (Task 12). Two methods share
one prompt-composition + agent-invocation path (ADR-065):
- ``run()`` — non-streaming. Materialises the agent output into a single
  ``DialogueCoachResponse``.
- ``stream()`` — streaming. Yields ``DialogueCoachStreamEvent`` instances
  (progress / result / done / error).

Pipeline (both methods):
1. Resolve the chapter (access control + content + language/title/genre).
2. Attribute speakers deterministically (DialogueParser — ADR-055 D3).
3. Load AdaptiveContext (Phase 1 Protocol) for the project + user.
4. Compose the governed system prompt via Mode 1 (Task 8 template).
5. Run the DialogueCoachAgent (Task 11) — one LLM call.
6. Map the output to API schemas.
7. Record the adaptive snapshot (Phase 3 Task 4 capability) — best-effort.

RULE-11 graceful degradation: empty selection (after parsing) → a
"nothing to analyse" result, no LLM call. Missing adaptive signals →
the analysis proceeds with empty adaptive variables (the dashboard shows
"no signals active").

See:
    ADR-069 Decision 7 (DialogueParser reuse),
    ADR-069 Decision 17 (run + stream two-method contract),
    ADR-054 (Mode 1 PromptComposer),
    ADR-055/057 (voice_metrics boundary — never consumed),
    CONSTRAINTS.md RULE-03 / RULE-06 / RULE-11 / RULE-13.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.ai_assist._agent_runner import run_dialogue_coach_agent
from narrare.ai_assist._prompt import resolve_dialogue_coach_prompt
from narrare.ai_assist._results import map_output_to_response
from narrare.ai_assist._speaker_attribution import attribute_speakers
from narrare.ai_assist.schemas import (
    DialogueCoachRequest,
    DialogueCoachResponse,
    DialogueCoachStreamEvent,
)
from narrare_core.llm.run_limits import DefaultRunLimitResolver

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.adaptive.adaptive_context_provider import AdaptiveContextProviderImpl
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


class DialogueCoachService:
    """Backend service for the Dialogue Coach (ASSIST-004).

    Args:
        chapter_repo: ChapterRepository for unscoped chapter loading.
        novel_repo: NovelRepository for novel-ownership access control
            and project metadata (title, genre, writing_language). Follows
            the voice_check_service precedent (Plan-Bug #23: the previous
            ``chapter_repo.get_by_id(chapter_id, user_id)`` call mismatched
            the production signature ``get_by_id(chapter_id, novel_id)`` —
            it would have queried ``Chapter.novel_id = user_id`` → always
            None → 404 on every request).
        model_registry: Shared LLM model registry.
        model_config: Resolved model config (analysis-tier). ``None`` only
            in the unit-test harness (fake registry ignores it); production
            always supplies a real config via the DI factory (Plan-Bug #21).
        composer: PromptComposer for Mode 1 resolution.
        invocation_pipeline: Optional pipeline for evidence.
        adaptive_provider: AdaptiveContextProviderImpl — loads adaptive
            context + records snapshots (Phase 3 Task 4 capability).
        api_key: Resolved per-user credential for the model registry call
            (model-routing cascade). ``None`` only in the unit-test
            harness; production wiring always supplies it via the DI
            factory.
        base_url: Resolved base-URL override for OpenAI-compatible
            providers. ``None`` uses the provider default endpoint.
    """

    def __init__(
        self,
        *,
        chapter_repo: ChapterRepository,
        novel_repo: NovelRepository,
        model_registry: ModelRegistry,
        model_config: ResolvedModelConfig | None,
        composer: PromptComposer,
        invocation_pipeline: InvocationPipeline | None,
        adaptive_provider: AdaptiveContextProviderImpl,
        api_key: str | None = None,
        base_url: str | None = None,
        run_limit_resolver: DefaultRunLimitResolver | None = None,
    ) -> None:
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo
        self._registry = model_registry
        self._config = model_config
        self._composer = composer
        self._pipeline = invocation_pipeline
        self._adaptive_provider = adaptive_provider
        self._api_key = api_key
        self._base_url = base_url
        self._run_limit_resolver = run_limit_resolver or DefaultRunLimitResolver()

    # ------------------------------------------------------------------
    # Shared pipeline — both run() and stream() call this.
    # ------------------------------------------------------------------

    async def _invoke(
        self,
        *,
        chapter_id: UUID,
        user_id: UUID,
        request: DialogueCoachRequest,
    ) -> DialogueCoachResponse:
        """Run the full pipeline and return the response."""
        from narrare_core.shared.errors import NotFoundError

        # Plan-Bug #23 fix (voice_check_service precedent): load the chapter
        # unscoped via ``get()``, then enforce access control via novel
        # ownership. The previous ``get_by_id(chapter_id, user_id)`` call
        # mismatched the production signature ``get_by_id(chapter_id, novel_id)``
        # — it queried ``Chapter.novel_id = user_id`` → always None → 404.
        chapter = await self._chapter_repo.get(chapter_id)
        if chapter is None:
            raise NotFoundError("Chapter", identifier=str(chapter_id))

        novel = await self._novel_repo.get_by_id(chapter.novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(chapter.novel_id))

        # Project metadata lives on Novel, not Chapter (formal review Minor #2):
        # Chapter has title + content but no genre / writing_language.
        project_id: UUID = novel.id
        language = novel.writing_language or "en"
        project_title = novel.title or ""
        genre = novel.genre or ""

        selection_text = request.selection_text
        characters = attribute_speakers(selection_text)

        # RULE-11: empty selection after parsing → nothing to analyse.
        if not selection_text.strip():
            return DialogueCoachResponse(
                chapter_id=str(chapter_id),
                mode=request.mode,
                issues=[],
                adaptive_summary="Empty selection — nothing to analyse.",
            )

        # Load AdaptiveContext + extract template variables.
        adaptive_ctx = await self._adaptive_provider.get_context(
            user_id=user_id, project_id=project_id
        )
        adaptive_extra = {
            "user_preferences": adaptive_ctx.preference_text,
            "style_constraints": adaptive_ctx.style_constraints_text,
            "avoidance_patterns": adaptive_ctx.avoidance_patterns_text,
            "character_voice_profiles": adaptive_ctx.voice_profiles_text,
        }

        composed_prompt, invocation_id = await resolve_dialogue_coach_prompt(
            self._composer,
            self._pipeline,
            project_id=project_id,
            user_id=user_id,
            language=language,
            project_title=project_title,
            genre=genre,
            selection_text=selection_text,
            mode=request.mode,
            characters=characters,
            adaptive_extra=adaptive_extra,
        )

        output = await run_dialogue_coach_agent(
            selection_text=selection_text,
            mode=request.mode,
            characters=characters,
            project_title=project_title,
            genre=genre,
            language=language,
            voice_profiles_text=adaptive_ctx.voice_profiles_text,
            chapter_id=chapter_id,
            model_registry=self._registry,
            model_config=self._config,
            api_key=self._api_key,
            base_url=self._base_url,
            run_limit_resolver=self._run_limit_resolver,
            composed_prompt=composed_prompt,
        )

        response = map_output_to_response(chapter_id=chapter_id, mode=request.mode, output=output)

        # Best-effort adaptive snapshot — never blocks the response.
        # invocation_id: prefer the real pipeline-minted id (from
        # compose_invocation's prepared.context) so the evidence row
        # correlates with the prompt fingerprint (ADR-069 Decision 11).
        # Fall back to chapter_id only on the no-pipeline backward-compat
        # path (unit-test setup) where prepare() is skipped and the id
        # is None.
        snapshot_invocation_id = invocation_id or chapter_id
        try:
            await self._adaptive_provider.record_snapshot(
                invocation_id=snapshot_invocation_id,
                adaptive_context=adaptive_ctx,
                evidence_repo=None,  # Phase 3 Task 4 method handles None gracefully.
            )
        except Exception:
            logger.warning(
                "dialogue_coach_snapshot_failed",
                chapter_id=str(chapter_id),
                invocation_id=str(snapshot_invocation_id),
                exc_info=True,
            )

        return response

    # ------------------------------------------------------------------
    # Public Protocol methods (ADR-065 two-method contract).
    # ------------------------------------------------------------------

    async def run(
        self,
        chapter_id: UUID,
        user_id: UUID,
        request: DialogueCoachRequest,
    ) -> DialogueCoachResponse:
        """Non-streaming coach invocation — returns the full result.

        For MCP / A2A / CLI clients.
        """
        return await self._invoke(chapter_id=chapter_id, user_id=user_id, request=request)

    async def stream(
        self,
        chapter_id: UUID,
        user_id: UUID,
        request: DialogueCoachRequest,
    ) -> AsyncIterator[DialogueCoachStreamEvent]:
        """Streaming coach invocation — yields SSE events.

        For the WebUI SSE router (Task 14).
        """
        yield DialogueCoachStreamEvent(event="progress", progress="Analysing dialogue…")
        try:
            response = await self._invoke(chapter_id=chapter_id, user_id=user_id, request=request)
            yield DialogueCoachStreamEvent(event="result", result=response)
            yield DialogueCoachStreamEvent(event="done", is_final=True)
        except Exception as exc:
            logger.error(
                "dialogue_coach_stream_failed",
                chapter_id=str(chapter_id),
                error=str(exc),
                exc_info=True,
            )
            yield DialogueCoachStreamEvent(
                event="error",
                error="Dialogue Coach analysis failed.",
                is_final=True,
            )
