"""Character Voice analysis service — calls CharacterVoiceAgent (ANAL-008).

Orchestrates the ADR-055 hybrid pipeline over a novel's selected chapters:

1. Resolve the novel (access control + metadata/language).
2. Load the selected chapters' text (specific ids or all chapters).
3. ``DialogueParser.parse`` → attributed utterances.
4. ``VoiceMetricsAnalyzer.analyze`` → per-character deterministic metrics.
5. Resolve the governed ``character_voice`` system prompt via
   ``compose_invocation`` Mode 1 (``LLMIntent.VOICE``) — NO inline f-string
   (RULE-02 / RULE-02b).
6. ``CharacterVoiceAgent(model, system_prompt=resolved).run(prompt=dialogue
   + metrics, deps=...)`` → ``CharacterVoiceOutput`` (one LLM call, all
   characters).
7. For each character: ``merge_character_voice(entry, metrics)`` →
   ``VoiceAnalysis``; write it to ``KBEntity.metadata["speech"]
   ["voice_analysis"]`` + bump ``updated_at`` (the 4 human-authored speech
   fields are preserved — ANAL-008 augments, never overwrites).

Prompt resolution is Mode 1 (composer-driven) per ADR-054 D1/D7/D8. The
attributed dialogue + per-character metrics flow as runtime data in the
agent run prompt (user channel, RULE-02a category 3). No inline f-string
feature prompt is assembled in the service (RULE-02 / RULE-02a).
Invocation-composition errors propagate (RULE-11).

RULE-11 graceful degradation: no dialogue → an empty result set (no crash,
no LLM call). Missing character KB entries → the result is still surfaced
to the UI but not persisted.

Pattern: Service → PromptComposer (RULE-02) → Core Agent (RULE-01b).

See:
    :mod:`narrare.analysis.contracts_character_voice` — the Protocol.
    :mod:`narrare.analysis.schemas_character_voice` — SSE event + response models.
    ADR-055 — Character voice storage contract (Decisions 1, 2, 3, 4).
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.analysis.character_voice_agent_runner import run_character_voice_agent
from narrare.analysis.character_voice_kb_writer import (
    load_selected_chapters,
    persist_voice_analysis,
)
from narrare.analysis.character_voice_prompt import resolve_character_voice_prompt
from narrare.analysis.schemas_character_voice import (
    CharacterVoiceResult,
    CharacterVoiceStreamEvent,
)
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.analysis.dialogue_parser import DialogueParser
    from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


class CharacterVoiceService:
    """Service for character-voice profiling analysis (ANAL-008).

    Takes a novel + chapter selection, runs the ADR-055 hybrid pipeline
    (deterministic metrics + LLM qualitative profile), writes the resulting
    :class:`VoiceAnalysis` to each character's KB ``speech.voice_analysis``
    (bumping ``updated_at``), and streams per-character results as SSE
    events.

    The ``character_voice`` prompt is resolved through :class:`PromptComposer`
    in Mode 1 (ADR-054 D1): the governed
    ``_bundled/analysis/{locale}/character_voice/system.md`` template carries
    the task framing and project metadata variables. No inline f-string
    feature prompt is assembled in the service (RULE-02 / RULE-02a).

    Args:
        novel_repo: For novel existence + metadata (genre, language) and
            access control.
        chapter_repo: For fetching chapter content.
        kb_repo: For finding character KB entries by name and persisting
            ``voice_analysis`` (Layer-0 storage contract).
        relationship_repo: Optional relationship repository for
            populating the ``kb_relationships`` prompt variable.
            Character relationships are charakterprägend — they inform
            voice profiling (e.g. a character's alliance or rivalry may
            shape their register and vocabulary). When ``None``, degrades
            gracefully to an empty string (RULE-11).
        model_registry: Shared LLM model registry.
        model_config: Resolved model config (provider + model ID).
        composer: PromptComposer for resolving the governed character-voice
            system prompt via the cascade (RULE-02b / ADR-054 D1). Required
            for ``analyze``.
        invocation_pipeline: Optional pipeline for invocation evidence
            (Mode 1 prepare/finalize). Retained for DI-contract stability.
    """

    def __init__(
        self,
        novel_repo: NovelRepository,
        chapter_repo: ChapterRepository,
        kb_repo: KBRepository,
        model_registry: ModelRegistry,
        model_config: ResolvedModelConfig | None = None,
        composer: PromptComposer | None = None,
        relationship_repo: RelationshipRepository | None = None,
        *,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._kb_repo = kb_repo
        self._registry = model_registry
        self._config = model_config
        self._composer = composer
        self._relationship_repo = relationship_repo
        self._invocation_pipeline = invocation_pipeline

    async def analyze(
        self,
        novel_id: UUID,
        chapter_ids: list[UUID] | None,
        user_id: UUID,
    ) -> AsyncIterator[CharacterVoiceStreamEvent]:
        """Analyse character voices across selected chapters, streaming SSE events.

        Runs the ADR-055 hybrid pipeline, writes ``VoiceAnalysis`` to each
        character's KB ``speech.voice_analysis`` (bumping ``updated_at``),
        and yields a ``"progress"`` event, one ``"result"`` event per
        profiled character, then a terminal ``"done"`` event.

        Args:
            novel_id: The novel whose chapters are analysed.
            chapter_ids: Specific chapters to analyse, or ``None`` / empty
                for every chapter in the novel.
            user_id: Authenticated user identifier (access control).

        Yields:
            :class:`CharacterVoiceStreamEvent` instances. The final event
            has ``is_final=True``.

        Raises:
            NotFoundError: If the novel or any selected chapter does not
                exist or is not accessible, or no model config is configured.
            ConfigurationError: If no ``PromptComposer`` is configured.
        """
        # 1. Resolve novel (access control + metadata).
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        if self._config is None:
            raise NotFoundError("Model config", identifier="no_model_config")

        if self._composer is None:
            raise ConfigurationError(
                "PromptComposer is not configured for character-voice analysis.",
                code="NO_COMPOSER",
            )

        language = novel.writing_language or "en"

        # 2. Load selected chapters' text (specific ids or all chapters).
        chapters = await load_selected_chapters(self._chapter_repo, novel_id, chapter_ids)
        chapter_text = "\n\n".join(c.content or "" for c in chapters)

        # 3-4. Parse dialogue + compute deterministic per-character metrics.
        parser = self._make_dialogue_parser()
        analyzer = self._make_voice_metrics_analyzer(language)
        utterances = parser.parse(chapter_text)
        metrics = analyzer.analyze(utterances)
        character_names = sorted(metrics.keys())

        # RULE-11 graceful degradation: no attributed dialogue → empty result
        # set, no LLM call (saves cost; the agent has nothing to profile).
        if not character_names:
            logger.info(
                "character_voice_no_dialogue",
                feature_id="analysis_character_voice",
                novel_id=str(novel_id),
                chapter_count=len(chapters),
            )
            yield CharacterVoiceStreamEvent(
                event="progress",
                progress="No attributed dialogue found in the selected chapters.",
            )
            yield CharacterVoiceStreamEvent(event="done", is_final=True)
            return

        yield CharacterVoiceStreamEvent(
            event="progress",
            progress=f"Profiling {len(character_names)} character(s).",
        )

        # 5. Resolve the governed character_voice system prompt via
        #    PromptComposer (RULE-02 / ADR-054 D1). The template
        #    ``_bundled/analysis/{locale}/character_voice/system.md`` carries
        #    the task framing, project metadata, and KB-context variables.
        #    Character relationships are charakterprägend for voice
        #    profiling; fetched from the relationship repo and passed as
        #    runtime data to the prompt builder (degrades to "" when no
        #    repo is wired, RULE-11).
        from narrare.writing._relationship_helpers import (
            fetch_formatted_relationships,
        )

        rel_context = await fetch_formatted_relationships(self._relationship_repo, novel_id)

        composed_prompt = await resolve_character_voice_prompt(
            self._composer,
            self._invocation_pipeline,
            novel=novel,
            language=language,
            novel_id=novel_id,
            user_id=user_id,
            kb_relationships=rel_context.text,
        )

        # 6. Run the agent — one LLM call profiling all characters. The
        #    attributed dialogue + per-character metrics flow as runtime
        #    content in the run prompt (user channel, RULE-02a category 3).
        output = await run_character_voice_agent(
            utterances=utterances,
            metrics=metrics,
            character_names=character_names,
            novel_title=novel.title,
            novel_genre=novel.genre or "",
            novel_id=novel_id,
            language=language,
            model_registry=self._registry,
            model_config=self._config,  # type: ignore[arg-type]
            composed_prompt=composed_prompt,
        )

        # 7. Merge + write per character; yield one result event each.
        from narrare_core.analysis.voice_merge import merge_character_voice

        for entry in output.characters:
            voice_analysis = merge_character_voice(entry, metrics.get(entry.character_name))
            kb_entry_id = await persist_voice_analysis(
                self._kb_repo,
                novel_id=novel_id,
                character_name=entry.character_name,
                voice_analysis=voice_analysis,
            )
            yield CharacterVoiceStreamEvent(
                event="result",
                result=CharacterVoiceResult(
                    character_name=entry.character_name,
                    voice_analysis=voice_analysis,
                    distinctiveness_notes=entry.distinctiveness_notes,
                    kb_entry_id=str(kb_entry_id) if kb_entry_id is not None else None,
                ),
            )

        logger.info(
            "character_voice_analysis_complete",
            feature_id="analysis_character_voice",
            novel_id=str(novel_id),
            character_count=len(output.characters),
        )

        yield CharacterVoiceStreamEvent(event="done", is_final=True)

    # ------------------------------------------------------------------
    # Analyzer construction (overridable for tests)
    # ------------------------------------------------------------------

    def _make_dialogue_parser(self) -> DialogueParser:
        from narrare_core.analysis.dialogue_parser import DialogueParser

        return DialogueParser()

    def _make_voice_metrics_analyzer(self, language: str) -> VoiceMetricsAnalyzer:
        from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer

        return VoiceMetricsAnalyzer(language=language)  # type: ignore[arg-type]
