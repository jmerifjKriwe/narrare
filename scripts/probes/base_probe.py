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

from pathlib import Path
from typing import TYPE_CHECKING

from narrare_core.ai_invocation.evidence import FileEvidenceSink
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from collections.abc import Sequence

    from narrare_core.ai_invocation.contracts import ContextEnricher
    from narrare_core.ai_invocation.models import PromptInvocationContext

# Default evidence directory: <repo_root>/.evidence/
EVIDENCE_DIR_DEFAULT = Path(__file__).resolve().parent.parent.parent / ".evidence"


def make_pipeline(
    evidence_dir: Path | None = None,
    enrichers: Sequence[ContextEnricher] = (),
) -> InvocationPipeline:
    """Create an InvocationPipeline with a FileEvidenceSink.

    No validators or budget resolvers — this is a minimal probe that
    only exercises the evidence recording path and optional enrichers.

    Args:
        evidence_dir: Directory for evidence files. Defaults to
            ``<repo_root>/.evidence/``.
        enrichers: Optional sequence of context enrichers to include
            in the pipeline (e.g. PreferenceContextEnricherImpl).

    Returns:
        A configured InvocationPipeline ready for probe calls.
    """
    sink = FileEvidenceSink(
        evidence_dir=evidence_dir or EVIDENCE_DIR_DEFAULT,
    )
    return InvocationPipeline(evidence_sink=sink, enrichers=enrichers)


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
