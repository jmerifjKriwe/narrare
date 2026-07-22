"""Shared logic for invocation pipeline probes.

Provides a reusable ``make_pipeline()`` factory and ``run_probe()``
function that individual probes call. All probes follow the same pattern:

    1. Create InvocationPipeline with FileEvidenceSink
    2. Build a PromptInvocationContext for the feature/mode
    3. Call pipeline.prepare() -> PreparedInvocation
    4. Call pipeline.finalize() -> FinalizedInvocation
    5. Assert result.evidence_recorded

See:
    ADR-038, ADR-041, INFRA-013.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from narrare_core.ai_invocation.evidence import FileEvidenceSink
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from collections.abc import Sequence

    from narrare_core.ai_invocation.contracts import (
        ContextEnricher,
        FinalPromptValidator,
        IntentOutputBudgetResolver,
        RuntimeVariableValidator,
    )
    from narrare_core.ai_invocation.models import PromptInvocationContext

# Default evidence directory: <repo_root>/.evidence/
EVIDENCE_DIR_DEFAULT = Path(__file__).resolve().parent.parent.parent / ".evidence"


def make_pipeline(
    evidence_dir: Path | None = None,
    enrichers: Sequence[ContextEnricher] = (),
    *,
    variable_validator: RuntimeVariableValidator | None = None,
    budget_resolver: IntentOutputBudgetResolver | None = None,
    final_validator: FinalPromptValidator | None = None,
) -> InvocationPipeline:
    """Create an InvocationPipeline with a FileEvidenceSink.

    Optionally includes validators and budget resolver for exercising
    specific pipeline components.

    Args:
        evidence_dir: Directory for evidence files. Defaults to
            ``<repo_root>/.evidence/``.
        enrichers: Optional sequence of context enrichers to include
            in the pipeline (e.g. AdaptiveContextEnricher).
        variable_validator: Optional pre-composition variable validator.
        budget_resolver: Optional output budget resolver.
        final_validator: Optional post-composition prompt validator.

    Returns:
        A configured InvocationPipeline ready for probe calls.
    """
    sink = FileEvidenceSink(
        evidence_dir=evidence_dir or EVIDENCE_DIR_DEFAULT,
    )
    return InvocationPipeline(
        evidence_sink=sink,
        enrichers=enrichers,
        variable_validator=variable_validator,
        budget_resolver=budget_resolver,
        final_validator=final_validator,
    )


async def run_probe(
    pipeline: InvocationPipeline,
    context: PromptInvocationContext,
) -> bool:
    """Run a single probe invocation.

    Executes the two-phase pipeline (prepare → finalize) with a
    minimal composed prompt.

    Args:
        pipeline: The InvocationPipeline to exercise.
        context: The invocation context for this feature/mode.

    Returns:
        True if evidence was successfully recorded, False otherwise.
    """
    prepared = await pipeline.prepare(context)
    prompt = ComposedPrompt(
        system="probe system prompt",
        user="probe user message",
    )
    result = await pipeline.finalize(prompt, context, prepared=prepared)
    return result.evidence_recorded


def merge_feature_marker(
    evidence_dir: Path,
    filename: str,
    feature_id: str,
    mode: str,
) -> Path:
    """Merge ``feature_id → [mode]`` into a shared marker file.

    Idempotent and additive: reads the existing file (if present), ensures
    ``features[feature_id]`` contains ``mode``, preserves all other entries,
    and writes back. Safe to run after other probes that overwrite the same
    file — the merge re-adds the entry.

    Used by probes that need to declare runtime coverage for a mode in the
    shared marker files the adoption scorer reads (evidence_sink.json,
    final_validation.json, preference_enrichment.json, budget_resolution.json).

    Args:
        evidence_dir: Directory containing the marker file.
        filename: Marker file name (e.g. ``evidence_sink.json``).
        feature_id: Feature id to add (e.g. ``ai_assist``).
        mode: Mode name to add (e.g. ``dialogue_coach``).

    Returns:
        The path to the written marker file.
    """
    marker_path = evidence_dir / filename
    data: dict[str, Any] = {}
    if marker_path.exists():
        try:
            with marker_path.open("r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                data = cast("dict[str, Any]", loaded)
        except json.JSONDecodeError, OSError:
            data = {}

    raw_features = data.get("features")
    features: dict[str, list[str]] = (
        {str(k): [str(m) for m in v] for k, v in cast("dict[str, Any]", raw_features).items()}
        if isinstance(raw_features, dict)
        else {}
    )
    modes = features.get(feature_id, [])
    if mode not in modes:
        modes = [*modes, mode]
    features[feature_id] = modes

    data["version"] = data.get("version", 1)
    data["features"] = features

    marker_path.parent.mkdir(parents=True, exist_ok=True)
    with marker_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    return marker_path
