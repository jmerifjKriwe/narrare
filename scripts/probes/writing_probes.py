#!/usr/bin/env python3
"""Eval probes for all writing category modes.

Exercises the invocation pipeline with various writing intents and
records runtime evidence for CI verification.

Usage:
    python scripts/probes/writing_probes.py [--evidence-dir PATH]

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

#: (feature_id, mode, intent, dynamic_inputs) for each writing mode.
MODE_INPUTS: list[tuple[str, str, LLMIntent, dict[str, str]]] = [
    (
        "writing",
        "new_chapter",
        LLMIntent.WRITE,
        {
            "chapter_title": "The Beginning",
            "outline": "Story outline",
        },
    ),
    (
        "writing",
        "extend_chapter",
        LLMIntent.EXTEND,
        {
            "existing_content": "The hero stood at the edge of the forest.",
            "extend_length": "500",
        },
    ),
    (
        "writing",
        "rewrite_selection",
        LLMIntent.REWRITE,
        {
            "selection_text": "He walked slowly through the dark corridor.",
            "rewrite_mode": "more_dynamic",
        },
    ),
    (
        "writing",
        "story_suggest",
        LLMIntent.SUGGEST,
        {
            "story_context": "Fantasy novel about dragons",
            "suggestion_type": "plot_twist",
        },
    ),
    (
        "writing",
        "interactive_session",
        LLMIntent.CHAT,
        {
            "conversation_history": "",
            "user_message": "Help me develop this scene",
        },
    ),
    (
        "writing",
        "interview",
        LLMIntent.WRITE,
        {
            "character_name": "Aragorn",
            "interview_topic": "motivation",
        },
    ),
    (
        "writing",
        "scene_by_scene",
        LLMIntent.WRITE,
        {
            "scene_index": "3",
            "previous_scenes": "Scene 1: Intro, Scene 2: Conflict",
        },
    ),
    (
        "writing",
        "inline_suggest",
        LLMIntent.SUGGEST,
        {
            "text_before": "The dark forest ",
            "text_after": " was silent.",
        },
    ),
    (
        "writing",
        "co_author",
        LLMIntent.CO_AUTHOR,
        {
            "selection_text": "The dialogue felt flat and unrealistic.",
            "focus": "dialogue",
        },
    ),
]


async def main_async(evidence_dir: Path) -> int:
    """Run all writing mode probes.

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
    """CLI entry point for writing eval probes."""
    parser = argparse.ArgumentParser(description="Writing mode eval probes")
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
