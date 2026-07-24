"""Optional LLM-judge evaluators for subjective quality checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_evals.evaluators import LLMJudge

if TYPE_CHECKING:
    from typing import Any


_RUBRICS: dict[str, str] = {
    "dialogue_coach": (
        "The high-fidelity run (voice_fidelity=1.0, voice profiles included) "
        "detects more voice_mismatch issues than the low-fidelity run "
        "(voice_fidelity=0.1, voice profiles suppressed). The weight change "
        "has a clear, measurable effect on the LLM's voice-mismatch detection."
    ),
    "kb_extraction": (
        "Output extracts only entities, facts, relationships, or conflicts supported by "
        "the input text, and omits hallucinated knowledge-base content."
    ),
    "preference_analysis": (
        "Output summarizes durable writing preferences from the feedback text and "
        "separates style, content, and avoidance signals clearly."
    ),
    "rewrite_selection": (
        "Output applies the requested rewrite mode, preserves core meaning, and returns "
        "a usable rewritten selection rather than analysis only."
    ),
}


def add_optional_llm_judge(dataset: Any, suite: str, judge_model: str | None) -> None:
    """Add an LLMJudge evaluator when a judge model is explicitly configured."""

    if judge_model is None:
        return
    rubric = _RUBRICS[suite]
    dataset.add_evaluator(
        LLMJudge(
            rubric=rubric,
            include_input=True,
            model=judge_model,
            score={"evaluation_name": "llm_quality"},
            assertion=False,
        )
    )
