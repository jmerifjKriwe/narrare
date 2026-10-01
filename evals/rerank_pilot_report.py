"""Report layer for the ADR-090 rerank pilot (Task 16) — payload + atomic write.

Split from ``evals/rerank_pilot.py`` for RULE-04 (file-size limit). This
module owns the typed report shape, the binding statements the report must
carry (dormant wiring — carry note 2; textless-candidate merge v1 — carry
note 3), and the atomic JSON write (temp + ``os.replace``).
"""

from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from evals.rerank_pilot import ArmSummary, CaseResult

DORMANT_WIRING = (
    "Dormant wiring: no production search consumer exists today (admin routes only; "
    "ProactiveContextService is deliberately argument-free), so the rerank flag is "
    "not yet a live lever. This pilot measures the CORE reranker directly per the "
    "Task 16 brief — not the wired apps/api search path."
)
DRY_RUN_BANNER = (
    "DRY RUN — rerank scores are deterministic content-seeded hashes, NOT model "
    "scores. These numbers do not answer the pilot question; they only validate "
    "the measurement pipeline."
)
_TEXTLESS_MERGE_V1 = (
    "Textless-candidate merge v1 (Task 15 implementation choice, not pinned by "
    "ADR-090): the reranked subset is placed first (rerank-score order); candidates "
    "whose text cannot be fetched are appended after it in first-stage (hybrid) "
    "order (search_rerank.py::_apply_rerank_stage). All pilot candidates have text, "
    "so the merge is out of measurement scope; documented as the interpretation "
    "under test."
)


@dataclass(frozen=True, slots=True)
class PilotReport:
    """Typed pilot outcome — serialized atomically and printed."""

    mode: str  # "real" | "dry-run"
    dry_run_reason: str
    rerank_model: str
    seed: int
    n_distractors: int
    recall_k: int
    summary: ArmSummary
    by_language: dict[str, ArmSummary]
    cases: list[CaseResult]

    def to_payload(self) -> dict[str, object]:
        """Stable JSON payload (methodology + binding statements included)."""
        return {
            "version": 1,
            "suite": "rerank_pilot",
            "created_at": datetime.now(tz=UTC).isoformat(),
            "mode": self.mode,
            "dry_run_reason": self.dry_run_reason,
            "rerank_model": self.rerank_model,
            "seed": self.seed,
            "n_distractors": self.n_distractors,
            "recall_k": self.recall_k,
            "verdict": self.summary.verdict,
            "wiring_status": DORMANT_WIRING,
            "summary": dataclasses.asdict(self.summary),
            "by_language": {
                language: dataclasses.asdict(row) for language, row in self.by_language.items()
            },
            "cases": [dataclasses.asdict(result) for result in self.cases],
            "methodology": {
                "query": "instruction + '\\n' + selection_text",
                "baseline": (
                    "lexical-overlap surrogate (Jaccard, lowercased word tokens) — "
                    "deterministic, identical for both arms"
                ),
                "rerank_arm": (
                    "ADR-090 Decision 3: first-stage order in, base_score = surrogate, "
                    "MaxSim score is the new sort key via rerank_candidates (stable; "
                    "no numeric blending)"
                ),
                "pool": (
                    "gold = the case's own non-empty context blocks ('before'/'after'); "
                    "distractors = seeded selection from the other cases' context blocks"
                ),
                "metrics": (
                    "MRR = mean(1/best-gold-rank); recall@3 = share of cases with "
                    ">=1 gold block in top 3"
                ),
                "languages": (
                    "recorded per case: en from evals/datasets/rewrite_selection.py; "
                    "de/fr pilot-local so the ADR-032 suite baseline stays untouched"
                ),
                "textless_merge_v1": _TEXTLESS_MERGE_V1,
            },
        }


def write_report(report: PilotReport, path: Path) -> None:
    """Atomic, stable JSON write (``write_report_json``-style: temp + replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(report.to_payload(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)
