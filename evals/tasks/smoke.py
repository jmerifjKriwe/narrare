"""Deterministic CI-safe smoke tasks for Pydantic Evals."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from evals.models import (
    AnalysisFeedbackInput,
    AnalysisFeedbackResult,
    ChatGenerationInput,
    ChatGenerationResult,
    DraftOutputField,
    KBExtractionInput,
    KBExtractionItem,
    KBExtractionResult,
    PreferenceAnalysisInput,
    PreferenceAnalysisResult,
    RewriteSelectionInput,
    RewriteSelectionResult,
)

SmokeTask = Callable[[object], Awaitable[object]]


class SmokeTaskFactory:
    """Build deterministic task functions that require no provider secrets."""

    def _task_map(self) -> dict[str, SmokeTask]:
        """Single-source mapping of suite name → smoke task.

        Every registered dataset has a smoke task (smoke is the
        CI-blocking mode). ``available_suites()`` and ``build()`` both
        derive from this map.
        """

        return {
            "analysis_feedback": self.analysis_feedback_task,
            "analysis_metrics": self.analysis_metrics_task,
            "chat_generation": self.chat_generation_task,
            "consistency_staged": self.consistency_staged_task,
            "kb_extraction": self.kb_extraction_task,
            "kb_operations": self.kb_operations_task,
            "names": self.names_task,
            "planning_structure": self.planning_structure_task,
            "preference_analysis": self.preference_analysis_task,
            "rewrite_selection": self.rewrite_selection_task,
            "writing_prose": self.writing_prose_task,
        }

    def available_suites(self) -> list[str]:
        """Return suite names with a smoke task, in stable sorted order."""

        return sorted(self._task_map())

    def build(self, suite: str) -> SmokeTask:
        """Return a smoke task for *suite*.

        Raises ``ValueError`` if *suite* is not in ``available_suites()``.
        """

        tasks = self._task_map()
        try:
            return tasks[suite]
        except KeyError as exc:
            raise ValueError(f"Unknown eval suite: {suite}") from exc

    async def kb_extraction_task(self, inputs: object) -> object:
        return await self.kb_extraction(KBExtractionInput.model_validate(inputs))

    async def rewrite_selection_task(self, inputs: object) -> object:
        return await self.rewrite_selection(RewriteSelectionInput.model_validate(inputs))

    async def preference_analysis_task(self, inputs: object) -> object:
        return await self.preference_analysis(PreferenceAnalysisInput.model_validate(inputs))

    async def consistency_staged_task(self, inputs: object) -> object:
        from evals.tasks.consistency_smoke import consistency_staged_task

        return await consistency_staged_task(inputs)

    async def kb_extraction(self, inputs: KBExtractionInput) -> KBExtractionResult:
        """Extract title-cased entity-like phrases deterministically."""

        names = _known_names(inputs.chapter_text, inputs.existing_entity_names)
        return KBExtractionResult(
            results=[
                KBExtractionItem(
                    item_type="update_entity"
                    if name in inputs.existing_entity_names
                    else "new_entity",
                    name=name,
                    entity_type="entity",
                    confidence=0.9,
                    source_text=name,
                )
                for name in names
            ],
            analysis_notes="Smoke extraction uses deterministic title-case phrase detection.",
        )

    async def rewrite_selection(self, inputs: RewriteSelectionInput) -> RewriteSelectionResult:
        """Return a deterministic rewrite result preserving the requested mode."""

        return RewriteSelectionResult(
            selected_mode=inputs.rewrite_mode,
            rewritten_text=f"[{inputs.rewrite_mode}] {inputs.selection_text}",
            rationale="Smoke rewrite validates mode routing without external model calls.",
        )

    async def preference_analysis(
        self, inputs: PreferenceAnalysisInput
    ) -> PreferenceAnalysisResult:
        """Derive preference buckets from feedback keywords deterministically."""

        text = inputs.feedback_text.casefold()
        return PreferenceAnalysisResult(
            style_patterns=_patterns(text, ["concise", "brisk", "sensory", "subtext"]),
            content_patterns=_patterns(text, ["dialogue", "conflict", "clues"]),
            avoidance_patterns=_patterns(
                text,
                ["exposition", "description", "cliffhangers", "sarcastic"],
            ),
            confidence=0.85 if inputs.event_count else 0.0,
            summary="Smoke analysis maps explicit feedback keywords into preference buckets.",
        )

    # ------------------------------------------------------------------
    # chat_generation
    # ------------------------------------------------------------------

    async def chat_generation_task(self, inputs: object) -> object:
        return await self.chat_generation(ChatGenerationInput.model_validate(inputs))

    async def chat_generation(self, inputs: ChatGenerationInput) -> ChatGenerationResult:
        """Produce deterministic chat/draft/suggest output without LLM calls."""

        word_count = len(inputs.prompt_text.split())
        if inputs.agent_type == "draft":
            return ChatGenerationResult(
                text=inputs.prompt_text,
                draft_output=DraftOutputField(
                    text=inputs.prompt_text,
                    title=f"Draft: {inputs.prompt_text[:30]}",
                    scene_breaks=[15, 30],
                    word_count=word_count,
                ),
                word_count=word_count,
            )
        return ChatGenerationResult(
            text=inputs.prompt_text,
            word_count=word_count,
        )

    # ------------------------------------------------------------------
    # analysis_feedback
    # ------------------------------------------------------------------

    async def analysis_feedback_task(self, inputs: object) -> object:
        return await self.analysis_feedback(AnalysisFeedbackInput.model_validate(inputs))

    async def analysis_feedback(self, inputs: AnalysisFeedbackInput) -> AnalysisFeedbackResult:
        """Produce deterministic analysis output without LLM calls."""

        word_count = len(inputs.text_content.split())
        return AnalysisFeedbackResult(
            passed=True,
            issues_found=max(0, word_count // 200),
            quality_score=7,
            summary=(
                f"Smoke analysis of {inputs.agent_type} agent. "
                f"Analyzed {word_count} words of {inputs.genre} text. "
                f"Deterministic — no model called."
            ),
        )

    # ------------------------------------------------------------------
    # analysis_metrics
    # ------------------------------------------------------------------

    async def analysis_metrics_task(self, inputs: object) -> object:
        from evals.tasks.analysis_metrics_smoke import analysis_metrics_task

        return await analysis_metrics_task(inputs)

    # ------------------------------------------------------------------
    # planning_structure
    # ------------------------------------------------------------------

    async def planning_structure_task(self, inputs: object) -> object:
        from evals.tasks.planning_structure_smoke import planning_structure_task

        return await planning_structure_task(inputs)

    # ------------------------------------------------------------------
    # kb_operations
    # ------------------------------------------------------------------

    async def kb_operations_task(self, inputs: object) -> object:
        from evals.tasks.kb_operations_smoke import kb_operations_task

        return await kb_operations_task(inputs)

    # ------------------------------------------------------------------
    # names
    # ------------------------------------------------------------------

    async def names_task(self, inputs: object) -> object:
        from evals.tasks.names_smoke import names_task

        return await names_task(inputs)

    # ------------------------------------------------------------------
    # writing_prose
    # ------------------------------------------------------------------

    async def writing_prose_task(self, inputs: object) -> object:
        from evals.tasks.writing_prose_smoke import writing_prose_task

        return await writing_prose_task(inputs)


def _known_names(text: str, existing_names: list[str]) -> list[str]:
    candidates = list(existing_names)
    words = text.replace(".", " ").replace(",", " ").split()
    for index, word in enumerate(words):
        if not word[:1].isupper():
            continue
        phrase = word.strip('.;:!?“”"')
        if index + 1 < len(words) and words[index + 1][:1].isupper():
            phrase = f"{phrase} {words[index + 1].strip('.;:!?“”"')}"
        if phrase not in candidates and len(phrase) > 2:
            candidates.append(phrase)
    return candidates


def _patterns(text: str, keywords: list[str]) -> list[str]:
    return [f"prefers {keyword}" for keyword in keywords if keyword in text]
