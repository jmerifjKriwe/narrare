"""Runtime tasks that exercise Narrare's real AI abstractions."""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from evals.models import (
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
