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

from pydantic_ai import (
    ModelRetry,
    RunContext,
)

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.character_arc_types import (
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
            output_type=CharacterArcOutput,
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[CharacterArcDeps],
        output: CharacterArcOutput,
    ) -> CharacterArcOutput:
        """Validate deterministic invariants for character arc output.

        ADR-035: Enforces output quality at the agent boundary.
        No side effects — deterministic validation only.

        Invariants:
        - character_name must be non-empty
        - phases should have 3-5 entries when present
        - Each phase should have non-empty phase_name and description
        - starting_state and ending_state should be non-empty
        """
        # character_name must be non-empty
        if not output.character_name.strip():
            raise ModelRetry(
                "character_name must be non-empty — every character arc needs a character"
            )

        # starting_state must be non-empty
        if not output.starting_state.strip():
            raise ModelRetry(
                "starting_state must be non-empty — the arc needs a defined starting state"
            )

        # ending_state must be non-empty
        if not output.ending_state.strip():
            raise ModelRetry(
                "ending_state must be non-empty — the arc needs a defined ending state"
            )

        # phases should have 3-5 entries when present
        if output.phases and (len(output.phases) < 3 or len(output.phases) > 5):
            raise ModelRetry(f"phases should have 3-5 entries, got {len(output.phases)}")

        # Each phase should have non-empty phase_name and description
        for idx, phase in enumerate(output.phases):
            if not phase.phase_name.strip():
                raise ModelRetry(f"Phase {idx} has an empty phase_name — every phase needs a name")
            if not phase.description.strip():
                raise ModelRetry(
                    f"Phase {idx} ('{phase.phase_name}') has an empty description — "
                    "every phase needs a description"
                )

        return output

    async def run(
        self,
        prompt: str,
        deps: CharacterArcDeps,
        **kwargs: Any,
    ) -> CharacterArcOutput:
        """Execute the character arc agent and return structured output."""
        return await super().run(prompt, deps, **kwargs)
