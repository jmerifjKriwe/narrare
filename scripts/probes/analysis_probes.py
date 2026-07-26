#!/usr/bin/env python3
"""Eval probes for all analysis category modes.

Exercises the invocation pipeline with analysis intents (beta reading,
review, voice analysis, summarization, consistency checking) and
records runtime evidence for CI verification.

Usage:
    python scripts/probes/analysis_probes.py [--evidence-dir PATH]

Returns:
    0 if all probes passed, 1 if any failed.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path so `scripts.probes` resolves
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from scripts.probes.base_probe import EVIDENCE_DIR_DEFAULT, make_pipeline, run_probe  # noqa: E402

from narrare_core.ai_invocation.models import PromptInvocationContext  # noqa: E402
from narrare_core.llm.intents import LLMIntent  # noqa: E402

#: (feature_id, mode, intent, dynamic_inputs) for each analysis mode.
MODE_INPUTS: list[tuple[str, str, LLMIntent, dict[str, str]]] = [
    (
        "analysis",
        "beta_reader",
        LLMIntent.BETA_READ,
        {
            "chapter_text": "The hero entered the dark forest.",
            "genre": "Fantasy",
        },
    ),
    (
        "analysis",
        "beta_reader_deepdive",
        LLMIntent.BETA_READ,
        {
            "chapter_text": "She traced the ancient runes on the wall.",
            "genre": "Fantasy",
            "focus_categories": "plot,character",
        },
    ),
    (
        "analysis",
        "review",
        LLMIntent.ANALYSE,
        {
            "chapter_text": "The battle raged across the plains.",
        },
    ),
    (
        "analysis",
        "preferences",
        LLMIntent.VOICE,
        {
            "chapter_text": "He knew the truth would change everything.",
        },
    ),
    (
        "analysis",
        "character_voice",
        LLMIntent.VOICE,
        {
            "chapter_text": "She spoke with a quiet, measured cadence.",
        },
    ),
    # ADR-057 D3 / WRITE-010: voice_check (flag+score checker) shares the
    # VOICE intent and exercises the same invocation pipeline as character_voice.
    (
        "analysis",
        "voice_check",
        LLMIntent.VOICE,
        {
            "chapter_text": "He spoke in a clipped, formal register throughout.",
        },
    ),
    # ADR-073 D3 / ANAL-009: voice_drift (longitudinal trend classifier) shares
    # the VOICE intent and exercises the same invocation pipeline as
    # character_voice and voice_check.
    (
        "analysis",
        "voice_drift",
        LLMIntent.VOICE,
        {
            "chapter_text": "Across chapters his cadence shifted measurably.",
        },
    ),
    (
        "analysis",
        "summarize",
        LLMIntent.SUMMARIZE,
        {
            "chapter_text": "In the beginning, there was only darkness.",
            "chapter_title": "Prologue",
        },
    ),
    (
        "analysis",
        "remap",
        LLMIntent.ANALYSE,
        {
            "chapter_text": "The old map revealed hidden paths.",
            "remap_target": "character_arcs",
        },
    ),
    (
        "analysis",
        "consistency",
        LLMIntent.CONSISTENCY,
        {
            "chapter_texts": "Chapter 1: Arrival\nChapter 2: Discovery",
            "check_types": "character,timeline",
        },
    ),
    (
        "analysis",
        "fact_extraction",
        LLMIntent.FACT_EXTRACT,
        {
            "chapter_text": "Elena walked to the gate at dawn.",
        },
    ),
    (
        "analysis",
        "readability",
        LLMIntent.ANALYSE,
        {
            "chapter_text": (
                "Convoluted nested subordinate clauses made comprehension unnecessarily difficult."
            ),
        },
    ),
    (
        "analysis",
        "pov",
        LLMIntent.ANALYSE,
        {
            "chapter_text": (
                "She walked through the door and saw him standing there. "
                "He looked older, wearier — she couldn't tell what he was thinking."
            ),
        },
    ),
    (
        "analysis",
        "coreference",
        LLMIntent.ANALYSE,
        {
            "chapter_text": (
                "Alice handed Bob the letter. She watched him read it carefully. "
                "His expression darkened as he reached the end."
            ),
        },
    ),
]


async def main_async(evidence_dir: Path) -> int:
    """Run all analysis mode probes.

    Args:
        evidence_dir: Directory for evidence output.

    Returns:
        0 if all probes passed, 1 otherwise.
    """
    pipeline = make_pipeline(evidence_dir)
    results: list[tuple[str, bool]] = []

    for feature_id, mode, intent, inputs in MODE_INPUTS:
        context = PromptInvocationContext(
            feature_id=feature_id,
            intent=intent,
            mode=mode,
            language="en",
            dynamic_inputs=inputs,
        )
        ok = await run_probe(pipeline, context)
        label = f"{feature_id}/{mode}"
        if ok:
            print(f"  ✅ {label}: evidence recorded")
        else:
            print(f"  ❌ {label}: no evidence recorded")
        results.append((label, ok))

    all_ok = all(ok for _, ok in results)
    return 0 if all_ok else 1


def main() -> int:
    """CLI entry point for analysis eval probes."""
    parser = argparse.ArgumentParser(description="Analysis mode eval probes")
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=EVIDENCE_DIR_DEFAULT,
        help="Directory for evidence files (default: .evidence/)",
    )
    args = parser.parse_args()
    return asyncio.run(main_async(args.evidence_dir))


if __name__ == "__main__":
    sys.exit(main())
