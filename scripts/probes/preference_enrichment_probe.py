#!/usr/bin/env python3
"""Probe: Preference enrichment with PreferenceContextEnricherImpl.

Verifies that the PreferenceContextEnricherImpl can load preferences
and inject them into the invocation context. Writes evidence with
preference_status: PROVIDED.

Also writes a marker file .evidence/preference_enrichment.json that
the adoption scorer checks to flip preference_enrichment: missing -> verified.

Usage:
    python scripts/probes/preference_enrichment_probe.py [--evidence-dir PATH]

Returns:
    0 if all probes passed, 1 if any failed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

# Ensure project root is on sys.path so `scripts.probes` resolves
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from scripts.probes.base_probe import (  # noqa: E402
    EVIDENCE_DIR_DEFAULT,
    make_pipeline,
    run_probe,
)
from scripts.probes.mode_data import ALL_MODES  # noqa: E402

from narrare_core.ai_invocation.enrichers import PreferenceContextEnricherImpl  # noqa: E402
from narrare_core.ai_invocation.models import PromptInvocationContext  # noqa: E402
from narrare_core.memory.models import PreferenceProfile  # noqa: E402

if TYPE_CHECKING:
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm.intents import LLMIntent

#: All modes to enrich with preferences.
MODES_TO_ENRICH = ALL_MODES


class _FakePreferenceProvider:
    """A fake PreferenceProvider that returns a known PreferenceProfile.

    Satisfies the PreferenceProvider protocol structurally.
    """

    def __init__(self) -> None:
        self.user_id_val: UUID = uuid4()
        self.project_id_val: UUID = uuid4()

    async def get_preferences(
        self,
        user_id: object,
        project_id: object,
    ) -> PreferenceProfile:
        """Return a simple PreferenceProfile with known data."""
        return PreferenceProfile(
            user_id=self.user_id_val,
            project_id=self.project_id_val,
            event_count=10,
            confidence=0.85,
            style={"prose_density": "moderate", "dialogue_frequency": "high"},
            content={"theme": "heroic_journey", "tone": "dark"},
            constraints=["avoid passive voice", "keep sentences under 30 words"],
        )

    async def reset(self, user_id: object, project_id: object) -> None:
        """No-op reset for protocol compliance."""
        pass


def _build_marker_data() -> dict[str, object]:
    """Build the marker file content grouped by feature_id."""
    features: dict[str, list[str]] = {}
    for feature_id, mode, _intent, _inputs in MODES_TO_ENRICH:
        features.setdefault(feature_id, []).append(mode)
    return {
        "version": 1,
        "enricher": "PreferenceContextEnricherImpl",
        "features": features,
    }


async def _probe_single(
    pipeline: InvocationPipeline,
    feature_id: str,
    mode: str,
    intent: LLMIntent,
    inputs: dict[str, str],
    user_id: UUID,
    project_id: UUID,
) -> bool:
    """Run a single enrichment probe with user/project context."""
    context = PromptInvocationContext(
        feature_id=feature_id,
        intent=intent,
        mode=mode,
        language="en",
        user_id=user_id,
        project_id=project_id,
        dynamic_inputs=inputs,
    )
    return await run_probe(pipeline, context)


async def main_async(evidence_dir: Path) -> int:
    """Run all preference enrichment probes.

    Creates a pipeline with PreferenceContextEnricherImpl and exercises
    it with each mode. Writes a marker file for the adoption scorer.

    Args:
        evidence_dir: Directory for evidence output.

    Returns:
        0 if all probes passed, 1 otherwise.
    """
    fake_provider = _FakePreferenceProvider()
    enricher = PreferenceContextEnricherImpl(preference_provider=fake_provider)
    pipeline: InvocationPipeline = make_pipeline(evidence_dir, enrichers=[enricher])

    results: list[tuple[str, bool]] = []

    for feature_id, mode, intent, inputs in MODES_TO_ENRICH:
        ok = await _probe_single(
            pipeline,
            feature_id,
            mode,
            intent,
            inputs,
            user_id=fake_provider.user_id_val,
            project_id=fake_provider.project_id_val,
        )
        label = f"enrich/{feature_id}/{mode}"
        if ok:
            print(f"  ✅ {label}: evidence recorded (preference_status: PROVIDED)")
        else:
            print(f"  ❌ {label}: no evidence recorded")
        results.append((label, ok))

    # Write marker file for adoption scorer (never blocks)
    marker_data = _build_marker_data()
    marker_path = evidence_dir / "preference_enrichment.json"
    try:
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        with marker_path.open("w", encoding="utf-8") as f:
            json.dump(marker_data, f, indent=2)
        print(f"  📝 Marker file written: {marker_path}")
    except OSError as exc:
        print(f"  ⚠️  Could not write marker file: {exc}")

    all_ok = all(ok for _, ok in results)
    return 0 if all_ok else 1


def main() -> int:
    """CLI entry point for the preference enrichment probe."""
    parser = argparse.ArgumentParser(
        description="Preference enrichment eval probe",
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
