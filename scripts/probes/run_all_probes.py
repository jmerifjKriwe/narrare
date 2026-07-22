#!/usr/bin/env python3
"""Run all eval probes and report evidence status.

Executes every probe in the probes package, collects results, and
prints a summary. Used in CI to verify that all adoption registry modes
with ``requires_runtime_evidence: true`` produce evidence.

Usage:
    python scripts/probes/run_all_probes.py [--evidence-dir PATH]

Returns:
    0 if all probes passed, 1 if any failed.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path so `scripts.probes` resolves
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from scripts.probes.ai_assist_probes import main_async as ai_assist_probe  # noqa: E402
from scripts.probes.analysis_probes import main_async as analysis_probe  # noqa: E402
from scripts.probes.base_probe import EVIDENCE_DIR_DEFAULT  # noqa: E402
from scripts.probes.chat_chat_probe import main_async as chat_probe  # noqa: E402
from scripts.probes.generation_names_probe import main_async as names_probe  # noqa: E402
from scripts.probes.kb_probes import main_async as kb_probe  # noqa: E402
from scripts.probes.planning_outline_probe import main_async as outline_probe  # noqa: E402
from scripts.probes.preference_enrichment_probe import main_async as enrichment_probe  # noqa: E402
from scripts.probes.validation_budget_probes import (  # noqa: E402
    main_async as validation_budget_probe,
)
from scripts.probes.writing_probes import main_async as writing_probe  # noqa: E402

ProbeFn = Callable[[Path], Coroutine[Any, Any, int]]

PROBES: list[tuple[str, ProbeFn]] = [
    ("writing/chat", chat_probe),
    ("writing/* (9 modes)", writing_probe),
    ("analysis/* (13 modes)", analysis_probe),
    ("kb/* (9 modes)", kb_probe),
    ("planning/outline", outline_probe),
    ("generation/names", names_probe),
    ("preference_enrichment", enrichment_probe),
    ("validation_budget", validation_budget_probe),
    ("ai_assist/dialogue_coach", ai_assist_probe),
]


async def main_async(evidence_dir: Path) -> int:
    """Run all probes and report results.

    Args:
        evidence_dir: Directory for evidence output.

    Returns:
        0 if all probes passed, 1 otherwise.
    """
    results: list[tuple[str, bool]] = []

    for name, probe_fn in PROBES:
        print(f"Running probe: {name} ...")
        try:
            exit_code = await probe_fn(evidence_dir)
            results.append((name, exit_code == 0))
        except Exception as exc:
            print(f"  ERROR: {exc}")
            results.append((name, False))

    print(f"\n{'=' * 40}")
    print("Probe Results:")
    passed = sum(1 for _, ok in results if ok)
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")
    print(f"\n{passed}/{len(results)} probes passed")

    return 0 if passed == len(results) else 1


def main() -> int:
    """CLI entry point for the probe runner."""
    parser = argparse.ArgumentParser(description="Run all eval probes")
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
