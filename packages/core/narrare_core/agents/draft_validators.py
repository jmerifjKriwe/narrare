"""DraftAgent output validator — ADR-035.

Deterministic invariants enforced at the agent boundary:
- text must be non-empty
- word_count should approximately match len(text.split()) (toleration ±2)
- scene_breaks positions must be valid (>= 0, <= len(text))

Usage:
    from narrare_core.agents.draft_validators import validate_draft_output

    validator = validate_draft_output
    # Register: agent._agent.output_validator(validate_draft_output)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai import ModelRetry

if TYPE_CHECKING:
    from pydantic_ai import RunContext

    from narrare_core.agents.draft_types import DraftDeps, DraftOutput


async def validate_draft_output(
    ctx: RunContext[DraftDeps],
    output: DraftOutput,
) -> DraftOutput:
    """Validate deterministic invariants for draft output.

    ADR-035: Enforces output quality at the agent boundary.
    No side effects — deterministic validation only.

    Invariants (additional to output function's word-target check):
    - text must be non-empty
    - word_count should approximately match len(text.split()) (±2 tolerance)
    - scene_breaks positions must be valid (>= 0, <= len(text))
    """
    text = output.text

    # text must be non-empty
    if not text.strip():
        raise ModelRetry("Draft text must be non-empty — the model returned whitespace-only output")

    # scene_breaks positions must be valid
    text_len = len(text)
    for idx, pos in enumerate(output.scene_breaks):
        if pos < 0:
            raise ModelRetry(f"scene_breaks[{idx}] is negative ({pos}) — positions must be >= 0")
        if pos > text_len:
            raise ModelRetry(
                f"scene_breaks[{idx}] ({pos}) exceeds text length "
                f"({text_len}) — positions must be <= text length"
            )

    # word_count should approximately match actual count (±2 tolerance)
    actual_word_count = len(text.split())
    if output.word_count > 0 and abs(output.word_count - actual_word_count) > 2:
        # Fix it silently — don't retry for a cosmetic mismatch
        return output.model_copy(update={"word_count": actual_word_count})

    return output
