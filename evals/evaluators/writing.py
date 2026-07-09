"""Deterministic evaluators for the writing-prose eval suite.

All three evaluators are deterministic and provider-free. The smoke task
produces compliant output so every evaluator scores ``1.0``; the
``AIDisclaimerGuardrail`` is the P0 guardrail anchor for the runtime drift
follow-up (AUFG-02-09) — it fails loudly (``0.0``) the moment a generated
prose leaks any AI-disclaimer / refusal phrasing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from evals.models import WritingProseResult

# Substring phrases (case-insensitive) that indicate the model broke
# character and emitted an AI-assistant disclaimer or refusal. Kept as a
# module constant so the guardrail phrase list is reviewable in one place.
# Mirrors the narrare "no AI disclaimers in generated prose" invariant.
_AI_DISCLAIMER_PHRASES: tuple[str, ...] = (
    "as an ai",
    "as a language model",
    "i cannot",
    "i can't",
    "i'm sorry",
    "i am sorry",
    "i'm unable",
    "i don't have personal",
    "language model",
)

# Phrases that signal a flat refusal (no prose delivered). Used by the
# soft tone evaluator; kept narrower than the disclaimer set so a
# legitimate in-fiction "sorry" (e.g. dialogue) is not penalised.
_REFUSAL_PHRASES: tuple[str, ...] = (
    "i cannot",
    "i can't",
    "i'm unable",
    "i am unable",
    "i won't",
    "i will not",
)

# Minimum plausible prose length for the quality floor.
_QUALITY_WORD_FLOOR: int = 3


@dataclass
class WritingProseQuality(Evaluator[Any, WritingProseResult, dict[str, Any]]):
    """Weighted prose-quality score (deterministic, smoke yields 1.0).

    Weighting:
      * 0.4 — non-empty ``text``.
      * 0.3 — ``word_count`` meets the small quality floor.
      * 0.3 — ``operation`` is echoed back on the result.
    """

    def evaluate(self, ctx: EvaluatorContext[Any, WritingProseResult, dict[str, Any]]) -> float:
        text_score = 1.0 if ctx.output.text and ctx.output.text.strip() else 0.0
        length_score = 1.0 if ctx.output.word_count >= _QUALITY_WORD_FLOOR else 0.0
        operation_score = 1.0 if ctx.output.operation else 0.0
        return (text_score * 0.4) + (length_score * 0.3) + (operation_score * 0.3)


@dataclass
class AIDisclaimerGuardrail(Evaluator[Any, WritingProseResult, dict[str, Any]]):
    """P0 guardrail: score 1.0 unless generated prose leaks AI disclaimers.

    Any case-insensitive hit of an ``_AI_DISCLAIMER_PHRASES`` substring in
    ``text`` collapses the score to ``0.0``. Generated fiction must never
    break the fourth wall with assistant disclaimers or refusals.
    """

    def evaluate(self, ctx: EvaluatorContext[Any, WritingProseResult, dict[str, Any]]) -> float:
        lowered = ctx.output.text.casefold()
        if any(phrase in lowered for phrase in _AI_DISCLAIMER_PHRASES):
            return 0.0
        return 1.0


@dataclass
class WritingToneAdherence(Evaluator[Any, WritingProseResult, dict[str, Any]]):
    """Soft/secondary tone check: non-empty prose that is not a refusal.

    Returns ``1.0`` for compliant smoke output (non-empty text with no
    refusal markers). Narrower than the disclaimer guardrail so legitimate
    in-fiction wording is not penalised.
    """

    def evaluate(self, ctx: EvaluatorContext[Any, WritingProseResult, dict[str, Any]]) -> float:
        if not ctx.output.text or not ctx.output.text.strip():
            return 0.0
        lowered = ctx.output.text.casefold()
        if any(phrase in lowered for phrase in _REFUSAL_PHRASES):
            return 0.0
        return 1.0
