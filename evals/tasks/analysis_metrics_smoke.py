"""Deterministic smoke task for the analysis_metrics eval suite.

Mirrors the ``consistency_smoke.py`` precedent: a standalone module with the
CI-safe task function and its producer helpers, imported lazily by
``SmokeTaskFactory.analysis_metrics_task`` so that ``evals/tasks/smoke.py``
stays within RULE-04 file-size limits.

Three analysis-panel agents are covered (Readability, POV, ChapterSummary).
Each producer derives a schema-valid result section from the input text — no
LLM is called. The output mirrors the real agent's output shape so the
metadata-aware evaluators assert genuine schema/range properties.
"""

from __future__ import annotations

import re
from typing import Any

from evals.models import (
    AnalysisMetricsInput,
    AnalysisMetricsResult,
    POVMetricsIssue,
    POVMetricsScene,
    POVSection,
    ReadabilitySection,
    SummarySection,
)

# Sentence is considered "long" above this word threshold (ReadabilityAgent
# flags too_long sentences; the threshold keeps the producer deterministic).
_READABILITY_LONG_THRESHOLD = 20


async def analysis_metrics_task(inputs: object) -> object:
    """Run the CI-safe analysis_metrics smoke task."""

    return await analysis_metrics(AnalysisMetricsInput.model_validate(inputs))


async def analysis_metrics(inputs: AnalysisMetricsInput) -> AnalysisMetricsResult:
    """Produce deterministic, schema-valid analysis output without LLM calls.

    Routes to a per-agent deterministic producer based on ``agent_type``.
    Each producer yields a result whose section matches the real agent's
    output shape and satisfies the metadata-aware validators (so smoke
    asserts REAL schema/range behaviour, not stubs).
    """

    if inputs.agent_type == "readability":
        return AnalysisMetricsResult(readability=_readability_smoke(inputs.text_content))
    if inputs.agent_type == "pov":
        return AnalysisMetricsResult(pov=_pov_smoke(inputs.text_content))
    # agent_type == "summary"
    return AnalysisMetricsResult(summary=_summary_smoke(inputs.text_content))


def _split_sentences(text: str) -> list[str]:
    """Split *text* into trimmed, non-empty sentences (best-effort)."""

    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _readability_smoke(text: str) -> ReadabilitySection:
    """Deterministically flag long sentences with issues + 2 suggestions each."""

    sentences = _split_sentences(text)
    problematic: list[dict[str, Any]] = []
    for sentence in sentences:
        if len(sentence.split()) <= _READABILITY_LONG_THRESHOLD:
            continue
        problematic.append(
            {
                "content": sentence,
                "issues": [
                    {
                        "type": "too_long",
                        "description": (
                            "Sentence exceeds readability length guidance (deterministic smoke)."
                        ),
                    }
                ],
                "suggestions": [
                    {
                        "alternative": f"{sentence.split('.')[0]}.",
                        "improvement": "Breaks the long sentence at the first clause.",
                    },
                    {
                        "alternative": sentence[: max(0, len(sentence) // 2)].strip() + "…",
                        "improvement": "Truncates to the first half for brevity.",
                    },
                ],
            }
        )

    return ReadabilitySection(
        overall_assessment=(
            f"Smoke readability: flagged {len(problematic)} sentence(s) for length. "
            "Deterministic — no model called."
        ),
        problematic_sentences=problematic,
    )


def _candidate_pov_characters(text: str) -> list[str]:
    """Return distinct capitalized words that look like character names."""

    seen: list[str] = []
    for word in text.replace(".", " ").replace(",", " ").split():
        candidate = word.strip("“”\"';:!?")
        if not candidate[:1].isupper() or len(candidate) < 3:
            continue
        if candidate in seen:
            continue
        # Skip common sentence-initial articles / pronouns.
        if candidate.lower() in {"the", "she", "he", "they", "it", "we", "you", "i", "a", "an"}:
            continue
        seen.append(candidate)
    return seen


def _pov_smoke(text: str) -> POVSection:
    """Deterministically derive scenes, POV classification, and a violation.

    Classifies as ``first_person`` when the text opens with first-person
    pronouns, ``mixed`` when multiple distinct POV candidates appear across
    paragraph breaks, otherwise ``third_limited``.
    """

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    characters = _candidate_pov_characters(text)
    opens_first_person = text.lstrip().startswith(("I ", "I'", "I\u2019"))

    if opens_first_person:
        analysis_type = "first_person"
    elif len(paragraphs) > 1 and len(characters) > 1:
        analysis_type = "mixed"
    else:
        analysis_type = "third_limited"

    pov_character = characters[0] if characters else "Narrator"

    scenes: list[POVMetricsScene] = []
    scene_characters = characters or [pov_character]
    for index, paragraph in enumerate(paragraphs or [text]):
        scene_char = (
            scene_characters[index] if index < len(scene_characters) else scene_characters[0]
        )
        scenes.append(
            POVMetricsScene(
                scene_index=index,
                pov_character=scene_char,
                confidence=0.9 - (0.05 * index),
                text_sample=paragraph[:100],
            )
        )

    if analysis_type == "mixed":
        distribution: dict[str, float] = {}
        share = 1.0 / max(1, len(scene_characters[:3]))
        for char in scene_characters[:3]:
            distribution[char] = round(share, 2)
        # Renormalize so the sum never exceeds 1.0.
        total = sum(distribution.values())
        if total > 0:
            distribution = {k: v / total for k, v in distribution.items()}
    else:
        distribution = {pov_character: 1.0}

    issues: list[POVMetricsIssue] = []
    if analysis_type == "mixed":
        issues.append(
            POVMetricsIssue(
                type="head_hop",
                location="paragraph boundary",
                text=scenes[0].text_sample if scenes else "",
                explanation="Multiple POV characters across adjacent scenes (deterministic smoke).",
                suggestion="Limit each scene to a single POV character.",
                severity="warning",
            )
        )

    return POVSection(
        scenes=scenes,
        issues=issues,
        pov_distribution=distribution,
        switch_count=max(0, len(scenes) - 1),
        analysis_type=analysis_type,
        overall_assessment=(
            f"Smoke POV detection: classified as {analysis_type} "
            f"across {len(scenes)} scene(s). Deterministic — no model called."
        ),
    )


def _summary_smoke(text: str) -> SummarySection:
    """Deterministically derive a bounded summary and key points.

    The summary is the first one to two sentences; key points are the leading
    clause of each sentence (bounded to 1-5 points). ``word_count`` always
    matches ``len(summary.split())`` to satisfy the length-consistency check.
    """

    sentences = _split_sentences(text)
    if not sentences:
        summary_text = "Smoke summary produced no content."
    else:
        take = sentences[:2]
        summary_text = " ".join(take)

    key_points: list[str] = []
    for sentence in sentences[:5]:
        head = sentence.split(",")[0].split(":")[0].strip()
        if head:
            key_points.append(head[:120])
    if not key_points:
        key_points = ["Key event (deterministic smoke fallback)."]

    return SummarySection(
        summary=summary_text,
        key_points=key_points,
        word_count=len(summary_text.split()),
        metadata={"smoke": True},
    )
