"""KBAssistAgent — Assisted KB entity creation agent.

Supports 4 interaction modes:
- question: Ask the user a focused question about one template field
- suggestion: Suggest a value for a specific field based on world context
- draft: Generate a partial entity entry with multiple fields
- complete: Finalize the entity entry

Composes with KBAgent via Toolset for world context queries.

Usage:
    model = await registry.get_model(config)
    agent = KBAssistAgent(model=model, kb_agent=kb_agent)
    deps = KBAssistDeps(
        language="en",
        entity_type="character",
        template_structure={...},
        existing_answers={"name": "Anna", "age": 28},
        world_context="...",
    )
    result = await agent.run(prompt="Help me create a character", deps=deps)
    # result.mode, result.question, result.draft_entry, etc.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai import RunContext  # noqa: TC002 — needed at runtime by pydantic_ai internals
from pydantic_ai.capabilities import ToolSearch, Toolset

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.kb_assist_types import KBAssistOutput

if TYPE_CHECKING:
    from narrare_core.agents.kb_agent import KBAgent


class KBAssistDeps:
    """Dependencies for KBAssistAgent.

    Attributes:
        language: Output language code (default "en").
        genre: Project genre for context.
        entity_type: Target entity type (character, location, etc.).
        template_structure: JSON schema of the entity type template fields.
        existing_answers: Previously collected field values.
        world_context: Assembled world context from KB or ProactiveContext.
    """

    def __init__(
        self,
        language: str = "en",
        genre: str = "",
        entity_type: str = "",
        template_structure: dict[str, Any] | None = None,
        existing_answers: dict[str, Any] | None = None,
        world_context: str | None = None,
    ) -> None:
        self.language = language
        self.genre = genre
        self.entity_type = entity_type
        self.template_structure = template_structure
        self.existing_answers = existing_answers
        self.world_context = world_context


class KBAssistAgent(NarrareAgent[KBAssistDeps, KBAssistOutput]):
    """Agent for assisted KB entity creation with multiple interaction modes.

    Composes with KBAgent for world context queries via Toolset capability.
    When no KBAgent is provided, operates in template-only mode.
    """

    def __init__(
        self,
        model: Any,
        kb_agent: KBAgent | None = None,
        system_prompt: str | None = None,
    ) -> None:
        # Build capabilities: ToolSearch + KBAgent tools when available
        capabilities: list[Any] = []
        if kb_agent is not None:
            capabilities.append(ToolSearch(strategy="keywords"))
            capabilities.append(Toolset(kb_agent.get_toolset()))

        super().__init__(
            model=model,
            deps_type=KBAssistDeps,
            output_type=[self._process_output, KBAssistOutput],
            capabilities=capabilities,
            system_prompt=system_prompt,
        )

    async def _process_output(
        self,
        ctx: RunContext[KBAssistDeps],
        mode: str,
        question: str | None = None,
        field_key: str | None = None,
        suggestion: str | None = None,
        reasoning: str | None = None,
        context_used: list[str] | None = None,
        draft_entry: dict[str, Any] | None = None,
        final_entry: dict[str, Any] | None = None,
        progress: float | None = None,
    ) -> KBAssistOutput:
        """Output Function — structures the LLM response into KBAssistOutput.

        During streaming (ctx.partial_output), returns minimal result.
        """
        if ctx.partial_output:
            return KBAssistOutput(mode=mode)  # type: ignore[arg-type]

        return KBAssistOutput(
            mode=mode,  # type: ignore[arg-type]
            question=question,
            field_key=field_key,
            suggestion=suggestion,
            reasoning=reasoning,
            context_used=context_used,
            draft_entry=draft_entry,
            final_entry=final_entry,
            progress=progress,
        )

    async def run(
        self,
        prompt: str,
        deps: KBAssistDeps,
        **kwargs: Any,
    ) -> KBAssistOutput:
        """Execute the assist agent and return structured output."""
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return result.output  # type: ignore[return-value]
