"""Deterministic CI-safe smoke task for the ``writing_prose`` suite.

Extracted from ``evals/tasks/smoke.py`` per RULE-04 (mirror
``consistency_smoke.py`` / ``kb_operations_smoke.py``). Produces a clean
``WritingProseResult`` derived deterministically from the inputs — the
operation is echoed, the prose is assembled from the anchor + instruction,
and NO AI-disclaimer phrasing is ever emitted, so all evaluators score
``1.0`` in smoke mode. No provider calls are made.
"""

from __future__ import annotations

from evals.models import WritingProseInput, WritingProseResult


async def writing_prose_task(inputs: object) -> object:
    """Run the CI-safe writing-prose smoke task."""

    return await writing_prose(WritingProseInput.model_validate(inputs))


async def writing_prose(inputs: WritingProseInput) -> WritingProseResult:
    """Produce deterministic writing-prose output without LLM calls.

    The deterministic prose tags the operation, continues from the anchor
    text, and folds in the author's instruction. It is deliberately free
    of any AI-disclaimer / refusal phrasing so the P0 guardrail anchor
    (``AIDisclaimerGuardrail``) and the soft tone check both score ``1.0``.
    """

    anchor = inputs.anchor_text.strip()
    instruction = inputs.instruction.strip()
    lead = f"[{inputs.operation}] {anchor}".strip()
    prose = f"{lead} — {instruction}." if instruction else f"{lead}."
    return WritingProseResult(
        operation=inputs.operation,
        text=prose,
        word_count=len(prose.split()),
        notes="Smoke writing-prose output is deterministic — no model called.",
    )
