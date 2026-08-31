"""Markdown overview rendering for one benchmark run (plan Task 14).

The plan's "aussagekräftige Übersicht" (meaningful overview) —
deterministic text given the same ``RunInputs`` (no clocks here: the
header echoes the caller's timestamps). Sections:

- run header (id, variant, mode, commit, LLM fingerprint, counts);
- build-quality aggregates + itemized outcome counts;
- the detection matrix (one row per capability x error class, FP counts
  included) plus the Task-12 rider: a PER-CAPABILITY FP-baseline note row
  making the exact-fingerprint subtraction mechanism visible in the
  artifact;
- retrieval aggregates + the per-capability coverage/surface table;
- the skipped/unavailable table with reasons (skipped answers, then the
  registry's unmounted surfaces — honest reporting, never omission).

Floats render with 3 decimals; undefined aggregates (``None``) render as
``n/a`` (undefined, not zero — the scorers' documented conventions).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Protocol

from benchmark.capabilities import UNAVAILABLE_SURFACES

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from benchmark.artifacts_records import RunInputs

__all__ = [
    "render_overview",
]

_FP_MECHANISM: Final[str] = (
    "clean-run subtraction by exact fingerprint: a finding whose normalized "
    "fingerprint also occurs in the clean run's report of this capability "
    "counts neither TP nor FP; only findings new to the variant that match "
    "no injected error count as FP"
)


class _StatusRow(Protocol):
    """Any scorer outcome row carrying a ``status`` literal."""

    @property
    def status(self) -> str: ...


def render_overview(
    inputs: RunInputs, *, run_id: str, git_commit: str, fingerprint: Mapping[str, str]
) -> str:
    """Render the full overview document for one run."""
    lines: list[str] = []
    _header(inputs, lines, run_id=run_id, git_commit=git_commit, fingerprint=fingerprint)
    _build_quality(inputs, lines)
    _detection(inputs, lines)
    _retrieval(inputs, lines)
    _skipped(inputs, lines)
    return "\n".join(lines) + "\n"


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _header(
    inputs: RunInputs,
    lines: list[str],
    *,
    run_id: str,
    git_commit: str,
    fingerprint: Mapping[str, str],
) -> None:
    driven = sum(1 for answer in inputs.answers if answer.status.value == "ok")
    errored = sum(1 for answer in inputs.answers if answer.status.value == "error")
    skipped = sum(1 for answer in inputs.answers if answer.status.value == "skipped")
    lines += [
        f"# KB Benchmark Run {run_id}",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Variant | {inputs.variant} |",
        f"| Mode | {inputs.mode} |",
        f"| Git commit | {git_commit} |",
        f"| LLM | {fingerprint['provider']} / {fingerprint['model']} "
        f"(config {fingerprint['config_hash']}) |",
        f"| Started / finished | {inputs.started_at.isoformat()} / "
        f"{inputs.finished_at.isoformat()} |",
        f"| Corpus version | {inputs.corpus_version} |",
        f"| Capabilities | {driven} driven · {errored} errored · {skipped} skipped |",
        "",
    ]


def _build_quality(inputs: RunInputs, lines: list[str]) -> None:
    score = inputs.build_quality
    found = sum(1 for row in score.entities if row.status == "found")
    missing = len(score.entities) - found
    lines += [
        "## Build quality (KB after ingest)",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Entity coverage | {_fmt(score.entity_coverage)} |",
        f"| Fact coverage | {_fmt(score.fact_coverage)} |",
        f"| Fact precision | {_fmt(score.fact_precision)} |",
        f"| Relation coverage | {_fmt(score.relation_coverage)} |",
        "",
        "| Itemized | Count |",
        "|---|---|",
        f"| Entities found / missing | {found} / {missing} |",
        "| Facts found / found_wrong / missing | "
        f"{_count(score.facts, 'found')} / {_count(score.facts, 'found_wrong')} / "
        f"{_count(score.facts, 'missing')} |",
        f"| Relations found / missing | {_count(score.relations, 'found')} / "
        f"{_count(score.relations, 'missing')} |",
        f"| Spurious entities / facts / relations | {len(score.spurious_entities)} / "
        f"{len(score.spurious_facts)} / {len(score.spurious_relations)} |",
        "",
    ]


def _count(rows: Sequence[_StatusRow], status: str) -> int:
    return sum(1 for row in rows if row.status == status)


def _detection(inputs: RunInputs, lines: list[str]) -> None:
    detection = inputs.detection
    lines += [
        "## Detection (variant run vs error registry)",
        "",
        "| Capability | Class | Expected | TP | FP | FN | Precision | Recall | F1 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in sorted(detection.matrix, key=lambda row: (row.capability, row.error_class)):
        lines.append(
            f"| {row.capability} | {row.error_class} | {row.expected} | {row.tp} | {row.fp} | "
            f"{row.fn} | {_fmt(row.precision)} | {_fmt(row.recall)} | {_fmt(row.f1)} |"
        )
    lines += [
        "",
        "### FP baseline per capability",
        "",
        "| Capability | FP (new-to-variant) | Mechanism |",
        "|---|---|---|",
    ]
    # The matrix is capability x injected error class; FPs are recorded
    # independently of it — a capability with unmatched findings but zero
    # matrix rows still owes its FP-baseline row (never omitted).
    for capability in sorted(
        {row.capability for row in detection.matrix}
        | {row.capability for row in detection.false_positives}
    ):
        fp = sum(1 for row in detection.false_positives if row.capability == capability)
        lines.append(f"| {capability} | {fp} | {_FP_MECHANISM} |")
    lines += ["", "### Detection evidence", "", "| Evidence | Traceable ids |", "|---|---|"]
    lines.append(
        "| True positives | "
        + (
            "; ".join(
                f"{row.error_id} ← {row.capability}[{row.item_index}]"
                for row in detection.true_positives
            )
            or "none"
        )
        + " |"
    )
    lines.append(
        "| False negatives | "
        + ("; ".join(row.error_id for row in detection.false_negatives) or "none")
        + " |"
    )
    lines.append(
        "| False positives | "
        + (
            "; ".join(f"{row.capability}[{row.item_index}]" for row in detection.false_positives)
            or "none"
        )
        + " |"
    )
    lines.append("")


def _retrieval(inputs: RunInputs, lines: list[str]) -> None:
    retrieval = inputs.retrieval
    lines += [
        "## Retrieval (reference-derived queries)",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Answer coverage | {_fmt(retrieval.answer_coverage)} |",
        f"| Answer precision | {_fmt(retrieval.answer_precision)} |",
        f"| Queries | {len(retrieval.queries)} |",
        "",
        "| Capability | Surface | Driven | Reason |",
        "|---|---|---|---|",
    ]
    for row in retrieval.coverage:
        driven = "yes" if row.driven else "no"
        lines.append(f"| {row.capability} | {row.surface} | {driven} | {row.reason} |")
    lines.append("")


def _skipped(inputs: RunInputs, lines: list[str]) -> None:
    lines += ["## Skipped and unavailable surfaces", "", "| Surface | Reason |", "|---|---|"]
    for answer in sorted(inputs.answers, key=lambda answer: answer.cap_id):
        if answer.status.value != "ok" and answer.reason is not None:
            lines.append(f"| {answer.cap_id} | {answer.reason} |")
    for unavailable in UNAVAILABLE_SURFACES:
        lines.append(f"| {unavailable.label} | {unavailable.reason} |")
    lines.append("")
