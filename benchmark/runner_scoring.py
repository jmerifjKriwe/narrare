"""Scoring assembly: the KB-state fetch + driven answers → the three scorers.

The scoring phase owns its own evidence. ``fetch_scored_kb`` collects
the FULL KB state as a scoring PREREQUISITE — the paginated entry
listing (the CAP-OUT-01 endpoint shape) plus EVERY entry's detail and
relationships (the CAP-OUT-03 endpoint shapes) — so build quality has
complete data regardless of which capabilities the user drove: driving
measures the user-facing functions, scoring must not depend on their
selection. The fetch reuses the drivers' canonical endpoint parsers
(``benchmark.drivers.out_direction``), records every exchange into the
run's sanitized event sink, and FAILS FAST on transport/HTTP errors —
a missing KB state must fail the run with failure artifacts, never
silently score nothing.

``score_run`` then invokes the REAL scorers:

- build quality (Task 11): scored against the FETCHED ``ScoredKb`` —
  the driven CAP-OUT-01/03 answers stay in answers.jsonl for the
  artifacts but are NOT build-quality inputs;
- detection (Task 12): every OK check-direction answer's parsed record
  becomes a variant report. The clean-run FP baseline is OPTIONAL input:
  v1 supplies NONE (the clean run is a separate full run) —
  ``clean_reports={}`` means NO baseline subtraction, and the run's
  artifacts say so (``RunInputs.fp_baseline=False``);
- retrieval (Task 13): the driven CAP-OUT-03 detail record (absent →
  empty, the documented downgrade) plus CAP-OUT-07's timeline read
  (absent → ``None``). Driven records are consumed ONLY from OK
  answers — an errored/skipped fetch means "no evidence", never a
  fabricated one.

Clean variant: NO injected errors — detection is an EMPTY report. The
clean run's check reports are the FP-baseline MATERIAL for later
comparison, not detection evidence; scoring an empty registry would
misreport every honest finding as FP (the matrix contract documents
``expected=0`` cells as "nothing scored"). Pure and deterministic.

Resolution (CAP-IN-10, ADR-085 P6, spec §8): scored as a FOURTH,
SEPARATE metric set from the driven CAP-IN-10 record — never folded
into build quality. The KB fetch runs AFTER the drivers, so endorsed
merges are already applied in the fetched state (no pre/post re-score,
no double counting): entity/relation coverage is reported AS MEASURED
(post-merge), and the resolution metrics (precision/recall/band/
distractor gate) come from ``score_resolution``. The deprecated merge
losers are hidden from the post-merge listing (ADR-085 §9(c)), so the
expected-pair universe reconstructs them from the record's merge +
suggestion id→name pairs. CAP-IN-10 not driven (or not OK) →
``resolution is None`` — absence, never a fabricated score.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from benchmark.capabilities import capability
from benchmark.drivers.base import CapabilityContext, CapabilityStatus
from benchmark.drivers.in_parsing import as_list
from benchmark.drivers.in_records import ResolutionRecord
from benchmark.drivers.out_direction import entry_detail, paginated_entries, relationship_detail
from benchmark.drivers.out_records import (
    EntityDetailRecord,
    EntrySummary,
    RelationshipDetail,
    TimelineReadRecord,
)
from benchmark.drivers.shapes import invoke_rest
from benchmark.runner_driving import capability_timings
from benchmark.scoring.build_quality import score_build_quality
from benchmark.scoring.detection import score_detection
from benchmark.scoring.detection_records import DetectionReport
from benchmark.scoring.resolution_match import ClaimEntry, claim_groups, score_resolution
from benchmark.scoring.retrieval import score_retrieval

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from benchmark.artifacts_records import CapabilityAnswer
    from benchmark.client import BenchmarkClient
    from benchmark.config_schemas import BenchmarkConfig
    from benchmark.corpus_loader import Corpus
    from benchmark.corpus_views import Entity, ErrorSpec, Reference
    from benchmark.ingest_events import IngestEvent
    from benchmark.scoring.resolution_match import ResolutionScore
    from benchmark.scoring.retrieval_records import RetrievalScore
    from benchmark.scoring.score_records import BuildQualityScore
__all__ = ["RunScores", "ScoredKb", "fetch_scored_kb", "score_run"]


@dataclass(frozen=True)
class ScoredKb:
    """The scoring phase's own KB-state fetch — build quality's "actual KB".

    ``entries`` is the complete paginated listing; ``details`` carries
    every entry's detail + relationship edges in listing order.
    """

    entries: tuple[EntrySummary, ...]
    details: tuple[EntityDetailRecord, ...]


@dataclass(frozen=True)
class RunScores:
    """The scorer outputs of one run, in artifacts order.

    ``resolution`` is present ONLY when CAP-IN-10 was driven OK (its
    record is the sole evidence) — ``None`` means not measured.
    """

    build_quality: BuildQualityScore
    detection: DetectionReport
    retrieval: RetrievalScore
    resolution: ResolutionScore | None = None


def fetch_scored_kb(
    client: BenchmarkClient,
    corpus: Corpus,
    novel_id: str,
    chapter_ids: Mapping[str, str],
    config: BenchmarkConfig,
    events: list[IngestEvent],
    targets: Mapping[str, str],
) -> ScoredKb:
    """Fetch the FULL KB state as the build-quality scoring prerequisite.

    Same driver-context wiring as ``drive_capabilities`` (this run's
    client, corpus, targets, event sink); every exchange lands in the
    same sanitized sink. Transport/HTTP failures PROPAGATE — the runner
    records failure artifacts, the score is never faked from absence.
    """
    ctx = CapabilityContext(
        client=client,
        corpus=corpus,
        novel_id=novel_id,
        chapter_ids=chapter_ids,
        config=capability_timings(config),
        events=events,
        targets=targets,
    )
    entries, _total, _pages = paginated_entries(
        ctx,
        step="scoring:browse",
        path=f"/api/v1/novels/{novel_id}/kb/entries",
        params={},
    )
    id_to_name = {entry.id: entry.name for entry in entries}
    return ScoredKb(
        entries=entries, details=tuple(_scored_detail(ctx, e.id, id_to_name) for e in entries)
    )


def _scored_detail(
    ctx: CapabilityContext, entry_id: str, id_to_name: Mapping[str, str]
) -> EntityDetailRecord:
    """One entry's detail + relationships (the CAP-OUT-03 endpoint shapes).

    The inverse-suggestion probe is a CAP-OUT-03 capability probe, not
    KB state — neither scorer consumes it, so it is NOT fetched here and
    both inverse fields stay ``None`` (absence, never fabrication). The
    API serializes edges as IDs only (``source_name``/``target_name``
    are always ``None``), so every edge is enriched from the listing's
    id→name map — the relation matcher resolves edges by display name.
    """
    base = f"/api/v1/novels/{ctx.novel_id}/kb/entries/{entry_id}"
    body = invoke_rest(ctx, step=f"scoring:entry:{entry_id}", method="GET", path=base)
    listed = invoke_rest(
        ctx, step=f"scoring:relationships:{entry_id}", method="GET", path=f"{base}/relationships"
    )
    return EntityDetailRecord(
        entry=entry_detail(body),
        relationships=tuple(
            _named_edge(relationship_detail(rel), id_to_name)
            for rel in as_list(listed, "relationship list")
        ),
        inverse_of=None,
        inverse_rel_type=None,
    )


def _named_edge(edge: RelationshipDetail, id_to_name: Mapping[str, str]) -> RelationshipDetail:
    """Fill the API's unset display names from the listing — never overwrite."""
    source = edge.source_name if edge.source_name is not None else id_to_name.get(edge.source_id)
    target = edge.target_name if edge.target_name is not None else id_to_name.get(edge.target_id)
    return replace(edge, source_name=source, target_name=target)


def score_run(
    corpus: Corpus,
    variant: str,
    answers: Sequence[CapabilityAnswer],
    chapter_map: Mapping[str, str],
    kb_state: ScoredKb,
) -> RunScores:
    """Score one finished run from its KB-state fetch + answers (module docstring)."""
    reference = corpus.reference()
    driven_details = _ok_detail(answers)
    timeline = _ok_parsed(answers, "CAP-OUT-07", TimelineReadRecord)
    resolution_record = _ok_parsed(answers, "CAP-IN-10", ResolutionRecord)
    return RunScores(
        build_quality=score_build_quality(reference, kb_state.entries, kb_state.details),
        detection=_detection(corpus, variant, answers, reference, chapter_map),
        retrieval=score_retrieval(reference, driven_details, timeline),
        resolution=_resolution(reference, kb_state, resolution_record),
    )


def _resolution(
    reference: Reference, kb_state: ScoredKb, record: ResolutionRecord | None
) -> ResolutionScore | None:
    """CAP-IN-10 scoring from the driven record (module docstring contract).

    Expected pairs derive from the reference bindings over the PRE-merge
    entry view — the scored listing plus the record's deprecated merge
    losers — so precision/recall are measured even though the fetch ran
    after the endorse phase.
    """
    if record is None:
        return None
    groups = claim_groups(_reference_entities(reference), _pre_merge_entries(kb_state, record))
    return score_resolution(groups, record.suggestions, record.merges)


def _reference_entities(reference: Reference) -> tuple[Entity, ...]:
    """All reference entities in fixed category order (deterministic
    first-reference-wins bindings)."""
    return (*reference.persons, *reference.places, *reference.objects)


def _pre_merge_entries(kb_state: ScoredKb, record: ResolutionRecord) -> tuple[ClaimEntry, ...]:
    """Scored listing + the record's merge losers = the pre-merge view.

    Loser names come from the suggestion id→name pairs (first observation
    wins); an unknown name is the empty string, which matches no
    reference key — the loser stays unbound (absence, never a fabricated
    name) and merely leaves the expected set untouched.
    """
    entries = [
        ClaimEntry(id=entry.id, name=entry.name, slug=entry.slug) for entry in kb_state.entries
    ]
    entry_ids = {entry.id for entry in entries}
    names: dict[str, str] = {}
    for suggestion in record.suggestions:
        names.setdefault(suggestion.entry_a_id, suggestion.name_a)
        names.setdefault(suggestion.entry_b_id, suggestion.name_b)
    losers = [
        ClaimEntry(id=merge.loser_id, name=names.get(merge.loser_id, ""), slug="")
        for merge in record.merges
        if merge.loser_id not in entry_ids
    ]
    return (*entries, *losers)


def _detection(
    corpus: Corpus,
    variant: str,
    answers: Sequence[CapabilityAnswer],
    reference: Reference,
    chapter_map: Mapping[str, str],
) -> DetectionReport:
    """Variant detection; empty report for clean runs (module docstring)."""
    errors: tuple[ErrorSpec, ...] = (
        corpus.errors(variant) if variant in corpus.variant_names else ()
    )
    if not errors:
        return DetectionReport(matrix=(), true_positives=(), false_negatives=(), false_positives=())
    variant_reports: dict[str, object] = {
        answer.cap_id: answer.parsed
        for answer in answers
        if answer.status is CapabilityStatus.OK
        and answer.parsed is not None
        and capability(answer.cap_id).direction == "check"
    }
    return score_detection(errors, reference, variant_reports, {}, chapter_map)


def _ok_detail(answers: Sequence[CapabilityAnswer]) -> tuple[EntityDetailRecord, ...]:
    """CAP-OUT-03's detail record, only from an OK answer."""
    detail = _ok_parsed(answers, "CAP-OUT-03", EntityDetailRecord)
    return () if detail is None else (detail,)


def _ok_parsed[T: object](
    answers: Sequence[CapabilityAnswer], cap_id: str, record_type: type[T]
) -> T | None:
    """The parsed payload of an OK answer, checked against ``record_type``.

    An absent answer, a non-OK answer, or an unexpected payload shape
    yields ``None`` — "no evidence", never a fabricated record.
    """
    for answer in answers:
        if answer.cap_id == cap_id:
            if answer.status is CapabilityStatus.OK and isinstance(answer.parsed, record_type):
                return answer.parsed
            return None
    return None
