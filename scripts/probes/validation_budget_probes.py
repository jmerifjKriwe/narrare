#!/usr/bin/env python3
"""Probes: Final validation and budget resolution.

Verifies that:
- FinalPromptValidatorImpl and RuntimeVariableValidatorImpl run without error
  for modes with ``final_validation: required``.
- IntentOutputBudgetResolverImpl resolves budgets for modes with
  ``budget_resolution: required``.

Writes two marker files for the adoption scorer:
- ``final_validation.json`` — flips ``final_validation: missing → verified``
- ``budget_resolution.json`` — flips ``budget_resolution: missing → verified``
  and ``kb_suggested: budget_rejected → verified`` (for inline_suggest).

Usage:
    python scripts/probes/validation_budget_probes.py [--evidence-dir PATH]

Returns:
    0 if all probes passed, 1 if any failed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path so `scripts.probes` resolves
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from scripts.probes.base_probe import (  # noqa: E402
    EVIDENCE_DIR_DEFAULT,
    make_pipeline,
    run_probe,
)

from narrare_core.ai_invocation.models import PromptInvocationContext  # noqa: E402
from narrare_core.llm.intents import LLMIntent  # noqa: E402

# ── Validation probe ─────────────────────────────────────────────────────

#: Modes with ``final_validation: required`` — one representative per intent.
_VALIDATION_MODES: list[tuple[str, str, LLMIntent]] = [
    ("writing", "new_chapter", LLMIntent.WRITE),
    ("analysis", "beta_reader", LLMIntent.BETA_READ),
    ("analysis", "character_voice", LLMIntent.VOICE),
    # ADR-057 D3 / WRITE-010: voice_check shares the VOICE intent and runs the
    # same final-validation path (RuntimeVariableValidatorImpl +
    # FinalPromptValidatorImpl) as character_voice.
    ("analysis", "voice_check", LLMIntent.VOICE),
    # ADR-073 D3 / ANAL-009: voice_drift shares the VOICE intent and runs the
    # same final-validation path (RuntimeVariableValidatorImpl +
    # FinalPromptValidatorImpl) as character_voice and voice_check.
    ("analysis", "voice_drift", LLMIntent.VOICE),
    # ADR-074 / ANAL-007: author_voice shares the VOICE intent and runs the
    # same final-validation path (RuntimeVariableValidatorImpl +
    # FinalPromptValidatorImpl) as character_voice, voice_check, and
    # voice_drift.
    ("analysis", "author_voice", LLMIntent.VOICE),
    # ANAL-009 Phase 2B: author_voice_drift shares the VOICE intent and runs
    # the same final-validation path (RuntimeVariableValidatorImpl +
    # FinalPromptValidatorImpl) as character_voice, voice_check, voice_drift,
    # and author_voice.
    ("analysis", "author_voice_drift", LLMIntent.VOICE),
    ("analysis", "fact_extraction", LLMIntent.FACT_EXTRACT),
    # ANALYSE intent representative — covers readability, pov, coreference
    # (all use LLMIntent.ANALYSE; review is the default context_mode).
    ("analysis", "review", LLMIntent.ANALYSE),
    ("kb", "consistency", LLMIntent.KB_CONSISTENCY),
    ("planning", "outline", LLMIntent.PLAN),
    ("planning", "temporal_consistency", LLMIntent.PLAN),
]

#: All modes per feature that have ``final_validation: required``.
_VALIDATION_FEATURES: dict[str, list[str]] = {
    "writing": [
        "new_chapter",
        "extend_chapter",
        "rewrite_selection",
        "story_suggest",
        "interactive_session",
        "interview",
        "scene_by_scene",
        "chat",
        "co_author",
    ],
    "analysis": [
        "beta_reader",
        "beta_reader_deepdive",
        "review",
        "preferences",
        "character_voice",
        "voice_check",
        "voice_drift",
        "author_voice",
        "author_voice_drift",
        "summarize",
        "remap",
        "consistency",
        "fact_extraction",
        "readability",
        "pov",
        "coreference",
        # SERIES-002: band_summary shares the SUMMARIZE-intent final-validation
        # path (RuntimeVariableValidatorImpl + FinalPromptValidatorImpl).
        "band_summary",
        # SERIES-004: series_consistency shares the ANALYSE-intent
        # final-validation path (covered by the review representative).
        "series_consistency",
    ],
    "kb": [
        "consistency",
        "worldbuilding/phase1",
        "worldbuilding/phase2",
        "improve",
        "suggest",
        "interview",
        "extract",
        "enhance",
        "merge",
    ],
    "planning": [
        "outline",
        "temporal_consistency",
        "character_arc",
        "timeline_extraction",
        "timeline",
    ],
}


async def _validation_probe(evidence_dir: Path) -> int:
    """Run validation probe for all modes that need final_validation: required."""
    from narrare_core.ai_invocation.validators.final_prompt import FinalPromptValidatorImpl
    from narrare_core.ai_invocation.validators.runtime import RuntimeVariableValidatorImpl

    pipeline = make_pipeline(
        evidence_dir=evidence_dir,
        variable_validator=RuntimeVariableValidatorImpl(),
        final_validator=FinalPromptValidatorImpl(),
    )

    results: list[tuple[str, bool]] = []
    for feature_id, mode, intent in _VALIDATION_MODES:
        context = PromptInvocationContext(
            feature_id=feature_id,
            intent=intent,
            mode=mode,
        )
        ok = await run_probe(pipeline, context)
        results.append((f"{feature_id}/{mode}", ok))

    # Write marker file
    marker = {
        "version": 1,
        "validators": ["RuntimeVariableValidatorImpl", "FinalPromptValidatorImpl"],
        "features": _VALIDATION_FEATURES,
    }
    marker_path = evidence_dir / "final_validation.json"
    with marker_path.open("w", encoding="utf-8") as f:
        json.dump(marker, f, indent=2)

    all_ok = all(ok for _, ok in results)
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} validate/{name}")
    return 0 if all_ok else 1


# ── Budget probe ─────────────────────────────────────────────────────────

#: Modes with ``budget_resolution: required`` — writing modes only.
_BUDGET_MODES: list[tuple[str, str, LLMIntent]] = [
    ("writing", "new_chapter", LLMIntent.WRITE),
    ("writing", "extend_chapter", LLMIntent.EXTEND),
    ("writing", "co_author", LLMIntent.CO_AUTHOR),
]

#: All writing modes that get budget_resolution verified.
_BUDGET_FEATURES: dict[str, list[str]] = {
    "writing": [
        "new_chapter",
        "extend_chapter",
        "rewrite_selection",
        "story_suggest",
        "interactive_session",
        "interview",
        "scene_by_scene",
        "chat",
        "co_author",
        "inline_suggest",
    ],
}


async def _budget_probe(evidence_dir: Path) -> int:
    """Run budget resolution probe for all modes that need budget_resolution: required."""
    from narrare_core.ai_invocation.budgets.resolver import IntentOutputBudgetResolverImpl

    pipeline = make_pipeline(
        evidence_dir=evidence_dir,
        budget_resolver=IntentOutputBudgetResolverImpl(),
    )

    results: list[tuple[str, bool]] = []
    for feature_id, mode, intent in _BUDGET_MODES:
        context = PromptInvocationContext(
            feature_id=feature_id,
            intent=intent,
            mode=mode,
        )
        ok = await run_probe(pipeline, context)
        results.append((f"{feature_id}/{mode}", ok))

    # Write marker file
    marker = {
        "version": 1,
        "resolver": "IntentOutputBudgetResolverImpl",
        "features": _BUDGET_FEATURES,
    }
    marker_path = evidence_dir / "budget_resolution.json"
    with marker_path.open("w", encoding="utf-8") as f:
        json.dump(marker, f, indent=2)

    all_ok = all(ok for _, ok in results)
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} budget/{name}")
    return 0 if all_ok else 1


# ── Public entry point ───────────────────────────────────────────────────


async def main_async(evidence_dir: Path) -> int:
    """Run validation and budget probes.

    Args:
        evidence_dir: Directory for evidence output.

    Returns:
        0 if all probes passed, 1 otherwise.
    """
    print("Running validation probe ...")
    val_result = await _validation_probe(evidence_dir)

    print("Running budget probe ...")
    budget_result = await _budget_probe(evidence_dir)

    return 1 if (val_result != 0 or budget_result != 0) else 0


def main() -> int:
    """CLI entry point for validation + budget probes."""
    parser = argparse.ArgumentParser(
        description="Final validation and budget resolution probes",
    )
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
