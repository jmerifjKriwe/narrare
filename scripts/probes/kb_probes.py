#!/usr/bin/env python3
"""Eval probes for all knowledge-base category modes.

Exercises the invocation pipeline with KB intents (consistency,
worldbuilding, improvement, suggestion, interview, extraction,
enhancement) and records runtime evidence for CI verification.

Usage:
    python scripts/probes/kb_probes.py [--evidence-dir PATH]

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

#: (feature_id, mode, intent, dynamic_inputs) for each KB mode.
MODE_INPUTS: list[tuple[str, str, LLMIntent, dict[str, str]]] = [
    (
        "kb",
        "consistency",
        LLMIntent.KB_CONSISTENCY,
        {
            "entity_type": "character",
            "entry_content": "Age: 30, Born: 1800",
        },
    ),
    (
        "kb",
        "worldbuilding/phase1",
        LLMIntent.KB_WORLDBUILD,
        {
            "entity_summaries": "Characters: 3, Locations: 5",
            "template_structures": "character, location",
        },
    ),
    (
        "kb",
        "worldbuilding/phase2",
        LLMIntent.KB_WORLDBUILD,
        {
            "candidate_pairs": "hero:villain",
            "entity_details": "Hero: brave, Villain: cunning",
        },
    ),
    (
        "kb",
        "improve",
        LLMIntent.KB_IMPROVE,
        {
            "entity_type": "location",
            "entry_content": "A dark forest.",
            "template_structure": "name, description, inhabitants",
        },
    ),
    (
        "kb",
        "suggest",
        LLMIntent.KB_SUGGEST,
        {
            "template_structure": "name, description",
            "target_field": "description",
            "existing_answers": '{"name": "Mirkwood"}',
        },
    ),
    (
        "kb",
        "interview",
        LLMIntent.KB_INTERVIEW,
        {
            "template_structure": "name, age, motivation",
            "existing_answers": '{"name": "Gandalf"}',
        },
    ),
    (
        "kb",
        "extract",
        LLMIntent.KB_EXTRACT,
        {
            "existing_entity_names": "Gandalf, Frodo",
            "chapter_text": "Aragorn walked into the tavern.",
        },
    ),
    (
        "kb",
        "enhance",
        LLMIntent.KB_ENHANCE,
        {
            "entity_type": "location",
            "template_structure": "description, history, inhabitants",
            "existing_answers": '{"name": "Rivendell"}',
        },
    ),
    (
        "kb",
        "merge",
        LLMIntent.KB_CONSISTENCY,
        {
            "entity_type": "character",
            "candidate_pairs": (
                '[{"id_A": "h", "id_B": "p", "name_A": "Hero", "name_B": "Protagonist"}]'
            ),
            "world_context": "A fantasy novel about a hero's journey.",
        },
    ),
]


async def main_async(evidence_dir: Path) -> int:
    """Run all KB mode probes.

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
    """CLI entry point for KB eval probes."""
    parser = argparse.ArgumentParser(description="KB mode eval probes")
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
