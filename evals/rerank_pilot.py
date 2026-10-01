"""Pilot measurement: rewrite-selection retrieval with vs. without rerank (ADR-090).

Task 16 (plan F5). Question: does the ADR-090 multi-vector rerank tier improve
the rank of instruction-relevant context blocks on the ADR-032 rewrite-selection
substrate? The flag stays default-off either way; a negative result is recorded
honestly (ADR-090 rollback = disable flag).

Methodology (also emitted into the report):
- Query per case: ``instruction + "\\n" + selection_text`` — the natural
  rewrite-selection retrieval input.
- Pool: gold = the case's own non-empty context blocks (``before``/``after``)
  plus 6 seeded distractor blocks from the other cases (see the substrate
  module: ``evals/rerank_pilot_substrate.py`` — cases, pools, scorers).
- Baseline arm: a deterministic lexical-overlap surrogate (Jaccard over
  lowercased word tokens) stands in for hybrid scoring — the pilot has no
  pgvector vectors or usage metadata. Identical for both arms.
- Rerank arm: exact ADR-090 Decision-3 / production semantics — candidates are
  handed to ``MultiVectorReranker`` in first-stage order with ``base_score`` =
  the surrogate; the MaxSim rerank score becomes the new sort key via
  ``rerank_candidates`` (stable; no numeric blending). Same call path as the
  production search tail (``apps/api/narrare/embeddings/search_rerank.py``).
- Metrics: MRR (mean 1/best-gold-rank), recall@3 (>=1 gold block in top 3),
  overall and per language — language is a recorded dimension (the ADR's
  multilingual Review Trigger needs non-English data; LateOn is en-tagged).

**Dormant wiring**: no production search consumer exists today (admin routes
only; ``ProactiveContextService`` is deliberately argument-free), so the
rerank flag is NOT yet a live lever. This pilot measures the CORE reranker
(``narrare_core.embeddings.rerank``) directly — not the wired apps/api path.

**Textless-candidate merge v1** (Task 15 implementation choice, not pinned by
ADR-090): the reranked subset is placed first (rerank-score order); candidates
whose text cannot be fetched are appended AFTER it in first-stage (hybrid)
order. All pilot candidates have text, so the merge is out of measurement
scope; it is documented in the report as the interpretation under test.

**Modes**: ``real`` (default) loads the pinned LateOn checkpoint (~600 MB,
first-use download) and measures real MaxSim scores. ``dry-run`` (``--dry-run``
or automatic when the checkpoint cannot be loaded) derives rerank scores from
a deterministic content-seeded hash — such numbers do NOT answer the pilot
question; a dry run only validates the pipeline. The mode is recorded in the
report and printed loudly.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from narrare_core.embeddings import (
    DEFAULT_RERANK_MODEL,
    MultiVectorReranker,
    RerankCandidate,
    is_rerank_available,
    rerank_candidates,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from evals.rerank_pilot_report import PilotReport

REPORT_PATH = Path("evals/results/rerank_pilot.json")
RECALL_K = 3
VERDICT_THRESHOLD = 0.05  # |MRR delta| above this flips the verdict to helps/hurts


@dataclass(frozen=True, slots=True)
class PilotLimits:
    """Pilot tunables (RULE-18): config-style named defaults, not inline magic.

    Same pattern as the production ``RerankStageLimits`` (search tail).
    """

    seed: int = 90
    n_distractors: int = 6


PILOT_LIMITS = PilotLimits()


def _ensure_repo_root_importable() -> None:
    """Make ``evals.*`` importable when this file is run as a script.

    The repo root is a virtual uv workspace container (``[tool.uv] package =
    false``), so ``evals`` is not an installed package: running
    ``python evals/rerank_pilot.py`` puts ``evals/`` (not the root) on
    ``sys.path``. The ``evals.*`` imports in this module are therefore lazy
    (function-level) and preceded by this bootstrap; ``narrare_core`` resolves
    from the installed workspace member either way.
    """
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)


# ---------------------------------------------------------------------------
# Scoring arms
# ---------------------------------------------------------------------------


async def try_real_reranker(model_name: str) -> tuple[MultiVectorReranker | None, str]:
    """Probe the real reranker (loads the checkpoint); degrade loudly on failure.

    Returns ``(reranker, "")`` on success, ``(None, reason)`` otherwise — the
    reason is recorded in the report (RULE-11: no silent degradation).
    """
    if not is_rerank_available():
        return None, "sentence-transformers not installed (embeddings extra missing)"
    reranker = MultiVectorReranker(model_name)
    probe = RerankCandidate(
        source_id=uuid.uuid5(uuid.NAMESPACE_URL, "rerank-pilot:probe"),
        source_type="probe",
        text="probe text",
        base_score=0.0,
    )
    try:
        await reranker.rerank("probe query", [probe], top_n=1)
    except Exception as exc:  # degradation boundary — reason recorded, never silent
        return None, f"{type(exc).__name__}: {exc}"
    return reranker, ""


async def rerank_arm(
    query: str,
    candidates: Sequence[RerankCandidate],
    *,
    reranker: MultiVectorReranker | None,
    seed: int,
) -> list[RerankCandidate]:
    """Second-stage order: real MaxSim scores, or seeded hashes in dry-run.

    Both paths converge on the core ``rerank_candidates`` reorder (stable sort
    by rerank score; ``base_score`` kept for tie-break/observability).
    """
    from evals.rerank_pilot_substrate import seeded_scores

    if reranker is not None:
        return await reranker.rerank(query, candidates, top_n=len(candidates))
    scores = seeded_scores(query, [candidate.text for candidate in candidates], seed=seed)
    return await rerank_candidates(candidates, scores)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OrderMetrics:
    """Retrieval metrics for one ordering of one case's pool."""

    gold_ranks: tuple[int, ...]
    best_gold_rank: int
    reciprocal_rank: float
    recall_at_3: float

    @classmethod
    def of(cls, order: Sequence[RerankCandidate], gold_ids: set[uuid.UUID]) -> OrderMetrics:
        """Compute metrics for one ordering (1-based gold positions)."""
        ranks = tuple(
            position
            for position, candidate in enumerate(order, start=1)
            if candidate.source_id in gold_ids
        )
        best = min(ranks) if ranks else 0
        return cls(
            gold_ranks=ranks,
            best_gold_rank=best,
            reciprocal_rank=1.0 / best if best else 0.0,
            recall_at_3=1.0 if ranks and best <= RECALL_K else 0.0,
        )


@dataclass(frozen=True, slots=True)
class CaseResult:
    """Per-case outcome: baseline vs. rerank."""

    name: str
    language: str
    pool_size: int
    n_gold: int
    baseline: OrderMetrics
    rerank: OrderMetrics


@dataclass(frozen=True, slots=True)
class ArmSummary:
    """Aggregate metrics over a set of cases (overall or one language)."""

    n_cases: int
    mrr_baseline: float
    mrr_rerank: float
    recall3_baseline: float
    recall3_rerank: float
    mrr_delta: float
    recall3_delta: float
    verdict: str | None  # overall only; per-language rows carry None


def classify_verdict(mrr_delta: float) -> str:
    """Map the MRR delta to the pilot verdict (thresholds named, not inline)."""
    if mrr_delta > VERDICT_THRESHOLD:
        return "helps"
    if mrr_delta < -VERDICT_THRESHOLD:
        return "hurts"
    return "neutral"


def summarize(results: Sequence[CaseResult], *, with_verdict: bool) -> ArmSummary:
    """Aggregate MRR / recall@3 over the given case results."""
    if not results:
        return ArmSummary(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "neutral" if with_verdict else None)

    def mean(values: Sequence[float]) -> float:
        return sum(values) / len(values)

    mrr_baseline = mean([result.baseline.reciprocal_rank for result in results])
    mrr_rerank = mean([result.rerank.reciprocal_rank for result in results])
    recall3_baseline = mean([result.baseline.recall_at_3 for result in results])
    recall3_rerank = mean([result.rerank.recall_at_3 for result in results])
    mrr_delta = mrr_rerank - mrr_baseline
    return ArmSummary(
        n_cases=len(results),
        mrr_baseline=mrr_baseline,
        mrr_rerank=mrr_rerank,
        recall3_baseline=recall3_baseline,
        recall3_rerank=recall3_rerank,
        mrr_delta=mrr_delta,
        recall3_delta=recall3_rerank - recall3_baseline,
        verdict=classify_verdict(mrr_delta) if with_verdict else None,
    )


# ---------------------------------------------------------------------------
# Pipeline: run
# ---------------------------------------------------------------------------


async def run_pilot(
    *,
    output: Path,
    dry_run: bool,
    model_name: str = DEFAULT_RERANK_MODEL,
    seed: int = PILOT_LIMITS.seed,
    n_distractors: int = PILOT_LIMITS.n_distractors,
) -> PilotReport:
    """Run the measurement, write the report atomically, return the typed result."""
    _ensure_repo_root_importable()
    from evals.rerank_pilot_report import PilotReport, write_report
    from evals.rerank_pilot_substrate import (
        build_pool,
        lexical_surrogate,
        load_cases,
        to_candidate,
    )

    cases = load_cases()
    reranker: MultiVectorReranker | None = None
    mode = "dry-run"
    dry_run_reason = ""
    if not dry_run:
        reranker, dry_run_reason = await try_real_reranker(model_name)
        mode = "real" if reranker is not None else "dry-run"

    results: list[CaseResult] = []
    for case in cases:
        pool = build_pool(case, cases, seed=seed, n_distractors=n_distractors)
        gold_ids = {to_candidate(block, 0.0).source_id for block in pool if block.is_gold}
        query = f"{case.inputs.instruction}\n{case.inputs.selection_text}"

        # Baseline arm: first stage = stable sort by the lexical surrogate.
        scored = sorted(
            ((block, lexical_surrogate(query, block.text)) for block in pool),
            key=lambda pair: pair[1],
            reverse=True,
        )
        first_stage = [to_candidate(block, score) for block, score in scored]
        baseline_order = await rerank_candidates(first_stage, [c.base_score for c in first_stage])
        # Rerank arm: same candidates, same order in; rerank score is the new key.
        rerank_order = await rerank_arm(query, first_stage, reranker=reranker, seed=seed)

        results.append(
            CaseResult(
                name=case.name,
                language=case.language,
                pool_size=len(pool),
                n_gold=len(gold_ids),
                baseline=OrderMetrics.of(baseline_order, gold_ids),
                rerank=OrderMetrics.of(rerank_order, gold_ids),
            )
        )

    languages = sorted({result.language for result in results})
    report = PilotReport(
        mode=mode,
        dry_run_reason=dry_run_reason,
        rerank_model=model_name if mode == "real" else f"fake:seeded-sha256(seed={seed})",
        seed=seed,
        n_distractors=n_distractors,
        recall_k=RECALL_K,
        summary=summarize(results, with_verdict=True),
        by_language={
            language: summarize(
                [result for result in results if result.language == language], with_verdict=False
            )
            for language in languages
        },
        cases=results,
    )
    write_report(report, output)
    return report


def print_summary(report: PilotReport) -> None:
    """Console summary; dry-run mode prints an unmissable warning banner."""
    if report.mode == "dry-run":
        from evals.rerank_pilot_report import DRY_RUN_BANNER

        print("=" * 72)
        print(DRY_RUN_BANNER)
        print(f"reason: {report.dry_run_reason}")
        print("=" * 72)
    print(f"rerank pilot — mode={report.mode} model={report.rerank_model}")
    for result in report.cases:
        print(
            f"  {result.name:<20} lang={result.language} "
            f"baseline_best_gold_rank={result.baseline.best_gold_rank:>2} "
            f"rerank_best_gold_rank={result.rerank.best_gold_rank:>2} "
            f"rr_delta="
            f"{result.rerank.reciprocal_rank - result.baseline.reciprocal_rank:+.2f}"
        )
    summary = report.summary
    print(
        f"MRR baseline={summary.mrr_baseline:.3f} rerank={summary.mrr_rerank:.3f} "
        f"delta={summary.mrr_delta:+.3f} | recall@{report.recall_k} "
        f"baseline={summary.recall3_baseline:.3f} rerank={summary.recall3_rerank:.3f} "
        f"delta={summary.recall3_delta:+.3f}"
    )
    print(f"verdict: {summary.verdict}")
    for language, row in report.by_language.items():
        print(
            f"  lang={language}: MRR {row.mrr_baseline:.3f}->{row.mrr_rerank:.3f} "
            f"(delta {row.mrr_delta:+.3f}), recall@{report.recall_k} "
            f"{row.recall3_baseline:.2f}->{row.recall3_rerank:.2f}"
        )


async def main() -> int:
    """CLI entry: parse flags, run, summarize."""
    parser = argparse.ArgumentParser(description="ADR-090 rerank pilot measurement")
    parser.add_argument("--dry-run", action="store_true", help="force the fake seeded encoder")
    parser.add_argument("--output", type=Path, default=REPORT_PATH, help="report path")
    parser.add_argument("--model", default=DEFAULT_RERANK_MODEL, help="rerank checkpoint")
    args = parser.parse_args()

    report = await run_pilot(output=args.output, dry_run=args.dry_run, model_name=args.model)
    print_summary(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
