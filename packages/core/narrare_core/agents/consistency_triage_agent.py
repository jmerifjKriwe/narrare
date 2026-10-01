"""ConsistencyTriageAgent — rubric-based re-scoring of ConsistencyAgent issues.

Decision-pattern pilot (Weg A): IntEnum rubric + evidence booleans +
confidence bands on a CHEAP model (LLMIntent.CONSISTENCY_TRIAGE).
Detection stays with ConsistencyAgent/ADR-044; this agent only re-scores.

The rubric questions reach the model through the schema descriptions on the
Task 10 output types (DecisionModel pattern); ``NarrareMeta`` /
``NarrareUniversalRules`` capabilities inject the guaranteed instruction
layer as with every NarrareAgent. No bundled cascade prompt (NON_ROUTEABLE).
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import ModelRetry, RunContext

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.consistency_triage_types import (
    ConsistencyTriageDeps,
    ConsistencyTriageOutput,
)


def build_triage_prompt(deps: ConsistencyTriageDeps) -> str:
    """Serialize the issues under review into the user channel (runtime input).

    RULE-02a §3: deps-driven content is built in ``core/agents/``; services
    call this function instead of writing their own prompt text.
    """
    lines = [f"Triage the {len(deps.issues)} consistency issues below.", ""]
    for i, issue in enumerate(deps.issues):
        lines.append(f"[{i}] ({issue.check_type.value}, current severity: {issue.severity.value})")
        lines.append(f"Description: {issue.description}")
        lines.append("Conflicting facts:")
        lines.extend(f"  - {fact}" for fact in issue.conflicting_facts)
        lines.append("")
    return "\n".join(lines)


class ConsistencyTriageAgent(NarrareAgent[ConsistencyTriageDeps, ConsistencyTriageOutput]):
    """Re-scores severity/confidence of detected issues via described rubrics."""

    def __init__(self, model: Any, *, system_prompt: str | None = None) -> None:
        super().__init__(
            model=model,
            deps_type=ConsistencyTriageDeps,
            output_type=ConsistencyTriageOutput,
            system_prompt=system_prompt,
        )
        self._agent.output_validator(self._validate_output)

    async def _validate_output(
        self,
        ctx: RunContext[ConsistencyTriageDeps],
        output: ConsistencyTriageOutput,
    ) -> ConsistencyTriageOutput:
        """ADR-035 invariants: exactly one in-range assessment per issue.

        The exact index sequence is asserted (not a sorted comparison):
        ``apply_triage`` applies assessments positionally, so out-of-order
        or duplicate indices would silently mis-apply the rubric.
        """
        expected = list(range(len(ctx.deps.issues)))
        indices = [a.issue_index for a in output.assessments]
        if indices != expected:
            raise ModelRetry(
                f"Expected exactly one assessment per issue, in order "
                f"(indices 0..{len(expected) - 1}); got {indices}"
            )
        return output

    async def run(
        self, prompt: str, deps: ConsistencyTriageDeps, **kwargs: Any
    ) -> ConsistencyTriageOutput:
        """Execute the triage agent and return the structured assessments."""
        return await super().run(prompt, deps, **kwargs)
