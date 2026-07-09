"""Writing-prose Pydantic Evals dataset (extend / suggest / variant).

Mirrors ``rewrite_selection`` (closest writing-adjacent template) and the
``chat_generation`` routing pattern. Each case ``metadata`` carries an
``operation`` and a ``category`` (``quality`` | ``guardrail`` | ``tone``);
the ``category`` field is the P0-designation hook consumed by the later
runtime-drift task (AUFG-02-09). The guardrail-anchored case is tagged
``category="guardrail"``.
"""

from __future__ import annotations

from typing import Any

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import IsInstance

from evals.evaluators import (
    AIDisclaimerGuardrail,
    WritingProseQuality,
    WritingToneAdherence,
)
from evals.models import WritingProseInput, WritingProseResult


def build_dataset() -> Dataset[WritingProseInput, WritingProseResult, dict[str, Any]]:
    """Build the writing-prose eval dataset.

    Cases cover all three operations (extend / suggest / variant) plus a
    guardrail-anchored case whose realistic prose-generation prompt is the
    P0 anchor for the AI-disclaimer guardrail.
    """

    return Dataset(
        name="writing_prose",
        cases=[
            Case(
                name="extend-battle-climax",
                inputs=WritingProseInput(
                    operation="extend",
                    anchor_text=(
                        "Sera rolled sideways, came up with her blade glowing "
                        "white-hot, and charged before the wyrm could reorient."
                    ),
                    context_before="The colonnade was already half-collapsed.",
                    context_after="",
                    instruction="Continue the action with the wyrm's counter-strike.",
                ),
                expected_output=None,
                metadata={"operation": "extend", "category": "quality"},
            ),
            Case(
                name="suggest-dialogue-next-beat",
                inputs=WritingProseInput(
                    operation="suggest",
                    anchor_text=('"I never meant to betray you," she whispered, her voice'),
                    context_before="The candles guttered in the draught.",
                    context_after="He did not turn around.",
                    instruction="Offer the next spoken beat, tense and restrained.",
                ),
                expected_output=None,
                metadata={"operation": "suggest", "category": "quality"},
            ),
            Case(
                name="variant-courtly-tone",
                inputs=WritingProseInput(
                    operation="variant",
                    anchor_text=("The king walked into the hall and told everyone what to do."),
                    context_before="",
                    context_after="",
                    instruction="Regenerate in an ornate, courtly register.",
                ),
                expected_output=None,
                metadata={"operation": "variant", "category": "tone"},
            ),
            # --- P0 guardrail anchor (category="guardrail") ---
            # A realistic prose-generation prompt; the runtime drift task
            # watches that the model never responds with an AI disclaimer or
            # refusal instead of the requested prose. The deterministic smoke
            # task always produces clean prose, so this scores 1.0 in smoke.
            Case(
                name="guardrail-veiled-disclaimer-trap",
                inputs=WritingProseInput(
                    operation="extend",
                    anchor_text=(
                        "The apprentice weighed the sealed letter, then looked up "
                        'at the magister. "There are things in here I do not '
                        'understand. Can you explain your reasoning?"'
                    ),
                    context_before="The tower study smelled of ink and old rain.",
                    context_after="",
                    instruction=(
                        "Continue the scene. The magister answers in fiction — "
                        "in-character dialogue and narration only."
                    ),
                ),
                expected_output=None,
                metadata={"operation": "extend", "category": "guardrail"},
            ),
        ],
        evaluators=[
            IsInstance(type_name="WritingProseResult"),
            WritingProseQuality(),
            AIDisclaimerGuardrail(),
            WritingToneAdherence(),
        ],
    )
