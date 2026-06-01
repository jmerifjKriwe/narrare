"""CharacterArcAgent — NarrareAgent for planning character development arcs.

Usage:
    model = await registry.get_model(config)
    agent = CharacterArcAgent(model=model)
    deps = CharacterArcDeps(
        character_name="Lyra Silvertongue",
        character_current_state="A timid orphan afraid of her own shadow",
        character_goal_state="A confident leader who inspires others",
        genre="Fantasy",
        language="en",
    )
    result = await agent.run(
        prompt="Design a character arc for Lyra Silvertongue.",
        deps=deps,
    )
    print(result.character_name)
    print(result.phases)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai import RunContext  # noqa: TC002 — needed at runtime by pydantic_ai internals

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.character_arc_types import (
    ArcPhase,
    CharacterArcOutput,
)

if TYPE_CHECKING:
    from narrare_core.writing.context_assembler import WritingContextAssembler


class CharacterArcDeps:
    """Dependencies for CharacterArcAgent.

    Attributes:
        character_name: Name of the character to analyse.
        character_current_state: The character's starting state.
        character_goal_state: The character's desired end state.
        genre: Story genre.
        language: Output language code.
        context_assembler: Optional context provider for additional context.
    """

    def __init__(
        self,
        character_name: str = "",
        character_current_state: str = "",
        character_goal_state: str = "",
        genre: str = "",
        language: str = "en",
        context_assembler: WritingContextAssembler | None = None,
    ) -> None:
        self.character_name = character_name
        self.character_current_state = character_current_state
        self.character_goal_state = character_goal_state
        self.genre = genre
        self.language = language
        self.context_assembler = context_assembler


class CharacterArcAgent(NarrareAgent[CharacterArcDeps, CharacterArcOutput]):
    """Agent for planning character development arcs.

    Takes character starting and goal states, plus story context,
    produces a multi-phase character arc with turning points,
    key relationships, and internal conflict resolution.
    """

    def __init__(self, model: Any, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=CharacterArcDeps,
            output_type=[self._process_output, CharacterArcOutput],
            system_prompt=system_prompt,
        )

    async def _process_output(
        self,
        ctx: RunContext[CharacterArcDeps],
        character_name: str | None = None,
        starting_state: str | None = None,
        ending_state: str | None = None,
        arc_type: str | None = None,
        phases: list[dict[str, str]] | None = None,
        key_relationships: list[str] | None = None,
        internal_conflict: str | None = None,
        resolution: str | None = None,
    ) -> CharacterArcOutput:
        """Output Function — strukturiert die LLM-Response in CharacterArcOutput.

        Bei Streaming (``ctx.partial_output``) wird nur ein Minimalergebnis zurückgegeben.
        """
        if ctx.partial_output:
            return CharacterArcOutput()

        return CharacterArcOutput(
            character_name=character_name or "",
            starting_state=starting_state or "",
            ending_state=ending_state or "",
            arc_type=arc_type or "",
            phases=[ArcPhase(**p) for p in (phases or [])],
            key_relationships=key_relationships or [],
            internal_conflict=internal_conflict or "",
            resolution=resolution or "",
        )

    async def run(
        self,
        prompt: str,
        deps: CharacterArcDeps,
        **kwargs: Any,
    ) -> CharacterArcOutput:
        """Execute the character arc agent and return structured output."""
        result = await self._agent.run(prompt, deps=deps, **kwargs)
        return result.output  # type: ignore[return-value]
