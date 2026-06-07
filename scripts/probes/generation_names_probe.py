#!/usr/bin/env python3
"""Eval probe for the generation/names mode.

Exercises the invocation pipeline with a ``NAME_GENERATE`` intent and
records runtime evidence for CI verification.

Usage:
    python scripts/probes/generation_names_probe.py [--evidence-dir PATH]

Returns:
    0 if evidence was recorded, 1 otherwise.
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


async def main_async(evidence_dir: Path) -> int:
    """Run the generation/names probe.

    Args:
        evidence_dir: Directory for evidence output.

    Returns:
        0 if evidence recorded, 1 otherwise.
    """
    pipeline = make_pipeline(evidence_dir)
    context = PromptInvocationContext(
        feature_id="generation",
        intent=LLMIntent.NAME_GENERATE,
        mode="names",
        language="en",
        dynamic_inputs={
            "name_type": "character",
            "count": "5",
            "writing_language": "en",
        },
    )

    success = await run_probe(pipeline, context)

    if success:
        print("✅ generation/names: evidence recorded")
        return 0
    else:
        print("❌ generation/names: no evidence recorded")
        return 1


def main() -> int:
    """CLI entry point for the generation/names probe."""
    parser = argparse.ArgumentParser(description="Generation/names eval probe")
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
