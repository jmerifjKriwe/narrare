"""JSON artifact documents: results, answers, events, manifest (Task 14).

One choke point per serialization concern:

- ``json_safe`` — the recursive JSON-safe projection (dataclasses via
  ``dataclasses.asdict``, tuples → lists, dict keys → str). Anything else
  (sets, objects, ...) raises ``ValueError`` — a non-serializable payload
  is a writer bug, never silently stringified. Called on EVERY document
  before ``dumps_sorted`` so a failure happens BEFORE any file is written
  (atomicity: no partial artifact trees).
- ``results_document`` — the per-capability x per-class detection matrix,
  the KB build-quality aggregates with fully itemized reference/error-id
  lists, and the retrieval outcomes + coverage rows. Deterministic by
  construction: scorer records carry no timestamps, keys are sorted by
  ``dumps_sorted``.
- ``answers_lines`` / ``event_lines`` — JSONL rows sorted by capability
  id / in sink order; the sink bodies are written verbatim (they are
  already sanitized at ``record`` time).
- ``manifest_document`` / ``config_fingerprint`` — the fingerprint is the
  SHA-256 of the config's ``redacted_dict`` canonical JSON: provider +
  model + that hash. Raw secret values NEVER enter any document.
- ``next_run_id`` — ``YYYY-MM-DD-<variant>-<mode>-<n>`` where ``n`` is
  max existing suffix + 1 over the runs-root listing (pure function of
  the listing; deterministic).

All documents serialize with ``sort_keys=True``; ``results.json`` and
``manifest.json`` pretty-printed, the JSONL files compact one-per-line.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Final, cast

from benchmark.drivers.base import CapabilityStatus

if TYPE_CHECKING:
    from collections.abc import Sequence

    from benchmark.artifacts_records import CapabilityAnswer, RunInputs
    from benchmark.config_schemas import BenchmarkConfig
    from benchmark.ingest_events import IngestEvent
    from benchmark.scoring.detection_records import DetectionReport
    from benchmark.scoring.resolution_match import ResolutionScore
    from benchmark.scoring.retrieval_records import RetrievalScore
    from benchmark.scoring.score_records import BuildQualityScore

__all__ = [
    "answers_lines",
    "config_fingerprint",
    "dumps_sorted",
    "event_lines",
    "json_safe",
    "manifest_document",
    "next_run_id",
    "results_document",
]

_COMPACT_SEPARATORS: Final[tuple[str, str]] = (",", ":")


# ---------------------------------------------------------------------------
# JSON-safe projection + canonical dumps
# ---------------------------------------------------------------------------


def json_safe(value: object) -> object:
    """Project ``value`` to JSON-safe data; unknown shapes raise (loud)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        mapping = cast("dict[object, object]", value)
        return {str(key): json_safe(item) for key, item in mapping.items()}
    if isinstance(value, (list, tuple)):
        items = cast("list[object]", value)
        return [json_safe(item) for item in items]
    if is_dataclass(value) and not isinstance(value, type):
        return json_safe(asdict(value))
    msg = f"not JSON-serializable: {type(value).__name__}"
    raise ValueError(msg)


def dumps_sorted(document: object, *, pretty: bool) -> str:
    """Canonical deterministic serialization (sorted keys, UTF-8 text)."""
    return json.dumps(
        json_safe(document),
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=None if pretty else _COMPACT_SEPARATORS,
        sort_keys=True,
    )


# ---------------------------------------------------------------------------
# results.json
# ---------------------------------------------------------------------------


def results_document(
    build_quality: BuildQualityScore,
    detection: DetectionReport,
    retrieval: RetrievalScore,
    resolution: ResolutionScore | None = None,
) -> dict[str, object]:
    """Per-capability x per-class scores + itemized traceable evidence.

    ``resolution`` (CAP-IN-10, spec §8) is sectioned only when the
    capability was driven — an absent section means "not measured",
    never zero.
    """
    document: dict[str, object] = {
        "build_quality": {
            "entity_coverage": build_quality.entity_coverage,
            "fact_coverage": build_quality.fact_coverage,
            "fact_precision": build_quality.fact_precision,
            "relation_coverage": build_quality.relation_coverage,
            "entities": [asdict(row) for row in build_quality.entities],
            "facts": [asdict(row) for row in build_quality.facts],
            "relations": [asdict(row) for row in build_quality.relations],
            "spurious_entities": [asdict(row) for row in build_quality.spurious_entities],
            "spurious_facts": [asdict(row) for row in build_quality.spurious_facts],
            "spurious_relations": [asdict(row) for row in build_quality.spurious_relations],
        },
        "detection": {
            "matrix": [asdict(row) for row in detection.matrix],
            "true_positives": [asdict(row) for row in detection.true_positives],
            "false_negatives": [asdict(row) for row in detection.false_negatives],
            "false_positives": [asdict(row) for row in detection.false_positives],
        },
        "retrieval": {
            "answer_coverage": retrieval.answer_coverage,
            "answer_precision": retrieval.answer_precision,
            "outcomes": [asdict(row) for row in retrieval.outcomes],
            "coverage": [asdict(row) for row in retrieval.coverage],
        },
    }
    if resolution is not None:
        document["resolution"] = {
            "precision": resolution.precision,
            "recall": resolution.recall,
            "auto_band_ok": resolution.auto_band_ok,
            "distractor_gate": resolution.distractor_never_suggested,
            "expected_pair_count": resolution.expected_pair_count,
            "suggested_count": resolution.suggested_count,
        }
    return document


# ---------------------------------------------------------------------------
# answers.jsonl + events.jsonl (sink)
# ---------------------------------------------------------------------------


def answers_lines(answers: Sequence[CapabilityAnswer]) -> list[str]:
    """One compact JSON line per capability, sorted by id (deterministic)."""
    return [
        dumps_sorted(
            {
                "cap_id": answer.cap_id,
                "status": answer.status.value,
                "elapsed_seconds": answer.elapsed_seconds,
                "reason": answer.reason,
                "parsed": answer.parsed,
            },
            pretty=False,
        )
        for answer in sorted(answers, key=lambda answer: answer.cap_id)
    ]


def event_lines(events: Sequence[IngestEvent]) -> list[str]:
    """The sanitized raw events, verbatim, in sink order (one JSON line)."""
    return [dumps_sorted(asdict(event), pretty=False) for event in events]


# ---------------------------------------------------------------------------
# manifest.json + run identity + config fingerprint
# ---------------------------------------------------------------------------


def next_run_id(existing: Sequence[str], day: str, variant: str, mode: str) -> str:
    """``<day>-<variant>-<mode>-<max existing suffix + 1>`` (pure)."""
    prefix = f"{day}-{variant}-{mode}-"
    numbers = [
        int(name[len(prefix) :])
        for name in existing
        if name.startswith(prefix)
        and name[len(prefix) :].isascii()
        and name[len(prefix) :].isdigit()
    ]
    return f"{prefix}{max(numbers, default=0) + 1}"


def config_fingerprint(config: BenchmarkConfig) -> dict[str, str]:
    """provider/model + SHA-256 over the REDACTED config's canonical JSON."""
    canonical = json.dumps(
        config.redacted_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "provider": config.llm.provider,
        "model": config.llm.model,
        "config_hash": f"sha256:{digest}",
    }


def manifest_document(inputs: RunInputs, run_id: str, git_commit: str) -> dict[str, object]:
    """The run manifest: identity, fingerprint, stack facts, counters."""
    return {
        "run_id": run_id,
        "started_at": inputs.started_at.isoformat(),
        "finished_at": inputs.finished_at.isoformat(),
        "git_commit": git_commit,
        "corpus_version": inputs.corpus_version,
        "variant": inputs.variant,
        "mode": inputs.mode,
        "config_fingerprint": config_fingerprint(inputs.config),
        "stack": {
            "compose_sha256": inputs.stack.compose_sha256,
            "image_digests": dict(inputs.stack.image_digests),
            "api_version": inputs.stack.api_version,
        },
        "capabilities": {
            "driven": sum(1 for answer in inputs.answers if answer.status is CapabilityStatus.OK),
            "errored": sum(
                1 for answer in inputs.answers if answer.status is CapabilityStatus.ERROR
            ),
            "skipped": sum(
                1 for answer in inputs.answers if answer.status is CapabilityStatus.SKIPPED
            ),
        },
    }
