"""Runtime tasks that exercise Narrare's real AI abstractions."""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

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

RuntimeTask = Callable[[object], Awaitable[object]]


@dataclass(frozen=True, slots=True)
class RuntimeTaskFactory:
    """Build tasks backed by ModelRegistry and Narrare agents."""

    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None

    @classmethod
    def from_env(cls) -> RuntimeTaskFactory:
        """Create runtime config from environment variables."""

        provider = os.environ.get("NARRARE_EVAL_PROVIDER", "openai")
        model = os.environ.get("NARRARE_EVAL_MODEL", "gpt-5-mini")
        return cls(
            provider=provider,
            model=model,
            api_key=os.environ.get("NARRARE_EVAL_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("NARRARE_EVAL_BASE_URL"),
        )

    def build(self, suite: str) -> RuntimeTask:
        """Return the runtime task for *suite*."""

        tasks: dict[str, RuntimeTask] = {
            "analysis_feedback": self.analysis_feedback_task,
            "chat_generation": self.chat_generation_task,
            "consistency_staged": self.consistency_staged_task,
            "kb_extraction": self.kb_extraction_task,
            "preference_analysis": self.preference_analysis_task,
            "rewrite_selection": self.rewrite_selection_task,
        }
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
        from evals.tasks.consistency_runtime import consistency_staged_task

        return await consistency_staged_task(
            inputs,
            config=self._config(),
            api_key=self.api_key,
            base_url=self.base_url,
        )

    async def kb_extraction(self, inputs: KBExtractionInput) -> KBExtractionResult:
        """Run KB extraction through ExtractionAgent."""

        from narrare_core.agents import ExtractionAgent, ExtractionDeps

        model = await self._model()
        agent = ExtractionAgent(model=model)
        output = await agent.run(
            prompt=inputs.chapter_text,
            deps=ExtractionDeps(
                language="en",
                genre=inputs.genre,
                existing_entity_names=inputs.existing_entity_names,
                chapter_title=inputs.chapter_title,
            ),
        )
        return KBExtractionResult(
            results=[KBExtractionItem.model_validate(item.model_dump()) for item in output.results],
            analysis_notes=output.analysis_notes,
        )

    async def preference_analysis(
        self, inputs: PreferenceAnalysisInput
    ) -> PreferenceAnalysisResult:
        """Run preference analysis through PreferenceAnalysisAgent."""

        from narrare_core.agents import PreferenceAnalysisAgent, PreferenceAnalysisDeps

        model = await self._model()
        agent = PreferenceAnalysisAgent(model=model)
        output = await agent.run(
            prompt=inputs.feedback_text,
            deps=PreferenceAnalysisDeps(
                language="en",
                genre=inputs.genre,
                event_count=inputs.event_count,
                feedback_text=inputs.feedback_text,
            ),
        )
        return PreferenceAnalysisResult.model_validate(output.model_dump())

    async def rewrite_selection(self, inputs: RewriteSelectionInput) -> RewriteSelectionResult:
        """Run rewrite selection through ModelRegistry structured output."""

        from narrare_core.llm import LLMIntent, ModelRegistry

        output = await ModelRegistry().run(
            intent=LLMIntent.REWRITE,
            prompt=inputs.model_dump_json(),
            system_prompt="Return selected_mode, rewritten_text, and rationale for the input.",
            output_type=RewriteSelectionResult,
            config=self._config(),
            api_key=self.api_key,
            base_url=self.base_url,
        )
        return output

    # ------------------------------------------------------------------
    # chat_generation
    # ------------------------------------------------------------------

    async def chat_generation_task(self, inputs: object) -> object:
        return await self.chat_generation(ChatGenerationInput.model_validate(inputs))

    async def chat_generation(self, inputs: ChatGenerationInput) -> ChatGenerationResult:
        """Route to ChatAgent, DraftAgent, or InlineSuggestAgent based on agent_type."""

        model = await self._model()

        if inputs.agent_type == "chat":
            from narrare_core.chat.chat_agent import ChatAgent
            from narrare_core.chat.chat_deps import ChatDeps
            from narrare_core.prompts import PromptComposer, PromptContext
            from narrare_core.prompts.registry import PromptRegistry

            agent = ChatAgent(model=model)
            registry = PromptRegistry()
            composer = PromptComposer(registry=registry)
            ctx = PromptContext(language=inputs.language, genre=inputs.genre)
            deps = ChatDeps(
                prompt_composer=composer,
                context=ctx,
                user_prompt=inputs.prompt_text,
            )
            output = await agent.run(prompt="", deps=deps)
            return ChatGenerationResult(text=output, word_count=len(output.split()))

        elif inputs.agent_type == "draft":
            from narrare_core.agents import DraftAgent, DraftDeps

            agent = DraftAgent(model=model)
            deps = DraftDeps(context_assembler=None)
            output = await agent.run(prompt=inputs.prompt_text, deps=deps)
            return ChatGenerationResult(
                text=output.text,
                draft_output=DraftOutputField(
                    text=output.text,
                    title=output.title,
                    scene_breaks=output.scene_breaks,
                    word_count=output.word_count,
                    metadata=output.metadata,
                ),
                word_count=output.word_count,
            )

        elif inputs.agent_type == "inline_suggest":
            from narrare_core.agents import InlineSuggestAgent, InlineSuggestDeps

            agent = InlineSuggestAgent(model=model)
            deps = InlineSuggestDeps(text_before=inputs.prompt_text)
            output = await agent.run(prompt="Continue this text.", deps=deps)
            return ChatGenerationResult(text=output, word_count=len(output.split()))

        else:
            msg = f"Unknown chat agent_type: {inputs.agent_type}"
            raise ValueError(msg)

    # ------------------------------------------------------------------
    # analysis_feedback
    # ------------------------------------------------------------------

    async def analysis_feedback_task(self, inputs: object) -> object:
        return await self.analysis_feedback(AnalysisFeedbackInput.model_validate(inputs))

    async def analysis_feedback(self, inputs: AnalysisFeedbackInput) -> AnalysisFeedbackResult:
        """Route to BetaReaderAgent, ReviewAgent, or ConsistencyAgent based on agent_type."""

        model = await self._model()

        if inputs.agent_type == "beta_reader":
            from narrare_core.agents import BetaReaderAgent, BetaReaderDeps

            agent = BetaReaderAgent(model=model)
            deps = BetaReaderDeps(
                language=inputs.language,
                chapter_text=inputs.text_content,
                genre=inputs.genre,
            )
            output = await agent.run(prompt="Analyze this chapter.", deps=deps)
            return AnalysisFeedbackResult(
                passed=True,
                issues_found=len(output.feedback),
                quality_score=output.overall.reader_engagement,
                summary=output.overall.summary,
            )

        elif inputs.agent_type == "review":
            from narrare_core.agents import ReviewAgent, ReviewDeps

            agent = ReviewAgent(model=model)
            deps = ReviewDeps(word_target=None, writing_context=None)
            output = await agent.run(
                prompt=f"Review this draft:\n\n{inputs.text_content}",
                deps=deps,
            )
            return AnalysisFeedbackResult(
                passed=output.approved,
                issues_found=len(output.issues),
                quality_score=output.quality_score,
                summary=output.feedback,
            )

        elif inputs.agent_type == "consistency":
            from narrare_core.agents import ConsistencyAgent, ConsistencyDeps

            agent = ConsistencyAgent(model=model)
            deps = ConsistencyDeps(
                language=inputs.language,
                chapter_texts={"ch1": inputs.text_content},
            )
            output = await agent.run(prompt="Check for contradictions.", deps=deps)
            return AnalysisFeedbackResult(
                passed=len(output.issues) == 0,
                issues_found=len(output.issues),
                quality_score=max(1, min(10, 10 - len(output.issues))),
                summary=output.overall_assessment,
            )

        else:
            msg = f"Unknown analysis agent_type: {inputs.agent_type}"
            raise ValueError(msg)

    async def _model(self) -> Any:
        from narrare_core.llm import ModelRegistry

        return await ModelRegistry().get_model(
            self._config(),
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def _config(self) -> Any:
        from narrare_core.llm import ResolvedModelConfig

        return ResolvedModelConfig(
            provider_name=self.provider,
            model_id=self.model,
            temperature=0.0,
            max_tokens=1200,
            streams=False,
            token_limit_profile="quick",  # nosec B106 — profile name, not a password
        )
