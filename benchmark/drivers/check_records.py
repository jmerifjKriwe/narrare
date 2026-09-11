"""Typed parsed records for the CHECK-direction capability drivers (Task 10).

One frozen record per driver (plus their nested finding shapes), mirroring
the REAL response schemas they are parsed from (per-record schema sources
cited). These records carry the DETECTION REPORTS the Task-12 scorer
consumes, so the findings/contradiction/verdict fields are complete; the
complete raw payloads live in the run's event sink
(``benchmark.ingest_events``). Lists become tuples; count dicts become
key-sorted tuple pairs (deterministic record equality, ``GraphRecord``
precedent).

Schema sources (``apps/api/narrare/`` unless noted):

- ``ConsistencyIssueFinding`` / ``ConsistencyCheckRecord`` —
  ``ConsistencyIssue`` (``kb/worldbuilding_contracts.py``) /
  ``ConsistencyCheckResponse`` (``kb/consistency_contracts.py``), served
  by ``kb/router_consistency.py``. Only ``checked_at`` (timestamp) stays
  in the raw sink.
- ``CanonConflictFinding`` / ``SnapshotRead`` /
  ``SeriesConsistencyRecord`` — ``CanonConflict``
  (``packages/core/narrare_core/agents/series_consistency_types.py``,
  reused verbatim per RULE-22) / ``SeriesConsistencyCheckResponse``
  (``series/series_consistency_schemas.py``) / ``SeriesDriftSnapshotResponse``
  (``series/series_drift_schemas.py``). The snapshot's embedded section
  documents (full ``consistency``/``voice_drift`` payloads) stay in the
  raw sink; the record keeps ``generated_at``/``stale`` plus which
  sections are persisted — the snapshot is the store-on-run (C2)
  persistence proof, not a second detection source.
- ``TrendPointRef`` / ``JumpPointRef`` / ``DriftVerdict`` —
  ``TrendPoint`` / ``JumpPoint``
  (``packages/core/narrare_core/analysis/voice_drift_scoring_types.py``)
  / ``VoiceDriftResult``
  (``packages/core/narrare_core/agents/character_voice_drift_types.py``),
  embedded in all three drift surfaces below.
- ``AuthorDriftResult`` / ``SeriesVoiceDriftRecord`` —
  ``AuthorVoiceDriftResult`` / ``AuthorVoiceDriftResponse``
  (``analysis/schemas_author_voice_drift.py``; the series router
  ``series/router_voice_drift.py`` reuses the response verbatim,
  RULE-22). Exactly one of ``result`` / ``no_profile_reason`` is set.
- ``TemporalIssue`` / ``TemporalConsistencyRecord`` —
  ``TemporalIssueResponse`` / ``TemporalConsistencyResponse``
  (``planning/timeline_schemas.py``).
- ``FlaggedLine`` / ``VoiceCheckFinding`` / ``VoiceCheckRecord`` —
  ``FlaggedLineResponse`` / ``VoiceCheckResult`` /
  ``VoiceCheckStreamEvent`` stream (``analysis/schemas_voice_check.py``).
- ``VoiceDriftNoProfileRef`` / ``CharacterDriftResult`` /
  ``VoiceDriftRecord`` — ``VoiceDriftNoProfile`` /
  ``VoiceDriftCharacterResult`` / ``VoiceDriftEvent`` stream
  (``analysis/schemas_voice_drift.py``; the per-character results arrive
  as ``character_result`` events, graceful skips as ``no_profile``
  events).
- ``AuthorVoiceDriftRecord`` — the ``AuthorVoiceDriftEvent`` stream
  (``analysis/schemas_author_voice_drift.py``): a single ``result``
  event XOR a single ``no_profile`` event (one narrator per novel).
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# CAP-CHK-01 — novel KB consistency report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConsistencyIssueFinding:
    """One contradiction/inconsistency (``ConsistencyIssue``) — complete."""

    finding_index: int
    category: str
    entity_ids: tuple[str, ...]
    entity_names: tuple[str, ...]
    description: str
    contradiction: str
    suggested_resolution: str | None
    severity: str
    confidence: float


@dataclass(frozen=True)
class ConsistencyCheckRecord:
    """CAP-CHK-01: combined KB consistency report (scorer surface)."""

    novel_id: str
    entity_count: int
    issues: tuple[ConsistencyIssueFinding, ...]
    summary: tuple[tuple[str, int], ...]
    suppressed_count: int


# ---------------------------------------------------------------------------
# CAP-CHK-02 — series canon contradiction check + drift snapshot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CanonConflictFinding:
    """One chapter-prose ↔ canon contradiction (``CanonConflict``) — complete."""

    canon_entry_slug: str
    canon_entry_name: str
    chapter_text_excerpt: str
    canon_statement: str
    explanation: str
    severity: str


@dataclass(frozen=True)
class SnapshotRead:
    """Persistence projection of ``SeriesDriftSnapshotResponse``."""

    generated_at: str | None
    stale: bool
    has_consistency: bool
    has_voice_drift: bool


@dataclass(frozen=True)
class SeriesConsistencyRecord:
    """CAP-CHK-02: canon contradictions + transparency counts + snapshot."""

    series_id: str
    novel_id: str
    conflicts: tuple[CanonConflictFinding, ...]
    summary: str
    canon_entry_count: int
    chapter_count: int
    snapshot: SnapshotRead


# ---------------------------------------------------------------------------
# Shared drift shapes (CAP-CHK-03/06/07) — Core value types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrendPointRef:
    """One per-chapter trend point (``TrendPoint``) — complete."""

    chapter_id: str
    match_subscore: float
    per_metric_deltas: tuple[tuple[str, float], ...]
    band: str


@dataclass(frozen=True)
class JumpPointRef:
    """One adjacent-chapter jump (``JumpPoint``) — complete."""

    from_chapter_id: str
    to_chapter_id: str
    jumped_metrics: tuple[str, ...]
    magnitude: float


@dataclass(frozen=True)
class DriftVerdict:
    """The agent's drift classification (``VoiceDriftResult``) — complete."""

    drift_type: str
    confidence: float
    longitudinal_reasons: tuple[str, ...]
    per_chapter_notes: tuple[tuple[str, str], ...]
    suggested_attention: tuple[str, ...]


@dataclass(frozen=True)
class AuthorDriftResult:
    """Narrator drift result (``AuthorVoiceDriftResult``) — complete."""

    novel_id: str
    trend: tuple[TrendPointRef, ...]
    jumps: tuple[JumpPointRef, ...]
    overall_match_score: float | None
    overall_band: str | None
    drift: DriftVerdict


@dataclass(frozen=True)
class SeriesVoiceDriftRecord:
    """CAP-CHK-03: series narrator drift (``AuthorVoiceDriftResponse``).

    Exactly one of ``result`` / ``no_profile_reason`` is set (the schema
    guarantees exclusivity); ``series_id`` is the driven path target.
    """

    series_id: str
    novel_id: str
    result: AuthorDriftResult | None
    no_profile_reason: str | None


# ---------------------------------------------------------------------------
# CAP-CHK-04 — temporal timeline consistency
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TemporalIssue:
    """One temporal issue (``TemporalIssueResponse``) — complete."""

    severity: str
    rule_id: str
    event_ids: tuple[str, ...]
    description: str
    suggestion: str
    source: str


@dataclass(frozen=True)
class TemporalConsistencyRecord:
    """CAP-CHK-04: merged deterministic + LLM timeline issues."""

    issues: tuple[TemporalIssue, ...]
    deterministic_pass: bool
    overall_assessment: str


# ---------------------------------------------------------------------------
# CAP-CHK-05 — chapter voice check (SSE stream B)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FlaggedLine:
    """One flagged dialogue line (``FlaggedLineResponse``)."""

    quote: str
    reason: str


@dataclass(frozen=True)
class VoiceCheckFinding:
    """Per-character verdict (``VoiceCheckResult``) — complete."""

    character_name: str
    match_score: float | None
    band: str | None
    match_judgment: str | None
    qualitative_sub_score: float | None
    metric_delta_subscore: float | None
    flagged_lines: tuple[FlaggedLine, ...]
    has_profile: bool
    n_comparable_metrics: int


@dataclass(frozen=True)
class VoiceCheckRecord:
    """CAP-CHK-05: collected per-character verdicts + progress trail."""

    chapter_id: str
    characters: tuple[VoiceCheckFinding, ...]
    progress_messages: tuple[str, ...]


# ---------------------------------------------------------------------------
# CAP-CHK-06 — longitudinal character voice drift (SSE stream B)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VoiceDriftNoProfileRef:
    """Graceful skip detail (``VoiceDriftNoProfile``) — complete."""

    character_id: str
    character_name: str
    reason: str


@dataclass(frozen=True)
class CharacterDriftResult:
    """Per-character drift result (``VoiceDriftCharacterResult``) — complete."""

    character_id: str
    character_name: str
    trend: tuple[TrendPointRef, ...]
    jumps: tuple[JumpPointRef, ...]
    overall_match_score: float | None
    overall_band: str | None
    drift: DriftVerdict


@dataclass(frozen=True)
class VoiceDriftRecord:
    """CAP-CHK-06: per-character drift results + graceful skips."""

    characters: tuple[CharacterDriftResult, ...]
    no_profiles: tuple[VoiceDriftNoProfileRef, ...]
    progress_messages: tuple[str, ...]


# ---------------------------------------------------------------------------
# CAP-CHK-07 — author-voice narrator drift (SSE stream B)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuthorVoiceDriftRecord:
    """CAP-CHK-07: the singular narrator drift outcome.

    Exactly one of ``result`` / ``no_profile_reason`` is set — the wire
    schema is exclusive (one narrator per novel), and the driver enforces
    that on the stream.
    """

    result: AuthorDriftResult | None
    no_profile_reason: str | None
    progress_messages: tuple[str, ...]
