"""Report itemization: parsed check records → comparable detection items.

One ``DetectionItem`` per locatable report finding, per record shape
(``benchmark.drivers.check_records``; capability ids from the registry):

- ``ConsistencyCheckRecord`` (CAP-CHK-01): one item per consistency
  issue; evidence = entity names + description + contradiction
  (novel-scoped — no item-level chapter identity).
- ``SeriesConsistencyRecord`` (CAP-CHK-02): one item per canon
  conflict; evidence = canon entry name + chapter excerpt + canon
  statement + explanation (novel-scoped).
- ``TemporalConsistencyRecord`` (CAP-CHK-04): one item per issue;
  evidence = rule id + description + suggestion. ``event_ids`` are
  run-scoped surrogates — excluded from evidence so fingerprints stay
  comparable across runs (novel-scoped).
- ``VoiceCheckRecord`` (CAP-CHK-05): one item per flagged line;
  evidence = character name + quote + reason; chapter-pinned via the
  record's ``chapter_id``.
- Drift records (CAP-CHK-03/06/07): one item per drift verdict;
  evidence = drift type + longitudinal reasons + per-chapter note
  texts (novel-scoped; note chapter ids are run-scoped surrogates).
  A graceful ``no_profile`` skip is data with ZERO items.

Consumer-side protocol validation (T10 review riders carried forward):
- Author-voice-drift records (``SeriesVoiceDriftRecord`` /
  ``AuthorVoiceDriftRecord``): ``result`` XOR ``no_profile_reason``
  must hold WITH at-least-one — neither set (or both) is a protocol
  error, raised as ``DetectionProtocolError`` (never silently scored
  as data).
- Duplicate-result shape: the drivers already error on duplicate SSE
  result events; the consumer asserts the collected shape (unique
  character identities per record) and raises on violation.
- Any other record shape is a protocol error (the scorer knows exactly
  the seven check-direction shapes).
"""

from __future__ import annotations

from dataclasses import dataclass

from benchmark.drivers.check_records import (
    AuthorDriftResult,
    AuthorVoiceDriftRecord,
    ConsistencyCheckRecord,
    DriftVerdict,
    SeriesConsistencyRecord,
    SeriesVoiceDriftRecord,
    TemporalConsistencyRecord,
    VoiceCheckRecord,
    VoiceDriftRecord,
)
from benchmark.scoring.normalize import normalize_text


class DetectionProtocolError(RuntimeError):
    """A parsed check record violates its protocol shape; never score it."""


@dataclass(frozen=True)
class DetectionItem:
    """One locatable report finding, comparable across runs.

    ``index`` locates the finding inside the parsed record (traceable
    to the report item); ``evidence`` is the raw matching text;
    ``fingerprint`` is its normalized form (clean-run baseline
    identity); ``chapter_ref`` is the run chapter id the item is pinned
    to, or ``None`` for novel-scoped shapes.
    """

    index: str
    evidence: str
    fingerprint: str
    chapter_ref: str | None


def flatten_record(record: object) -> tuple[DetectionItem, ...]:
    """Itemize one parsed check record; validates its protocol shape."""
    if isinstance(record, ConsistencyCheckRecord):
        return _consistency_items(record)
    if isinstance(record, SeriesConsistencyRecord):
        return _series_items(record)
    if isinstance(record, TemporalConsistencyRecord):
        return _temporal_items(record)
    if isinstance(record, VoiceCheckRecord):
        return _voice_check_items(record)
    if isinstance(record, (SeriesVoiceDriftRecord, AuthorVoiceDriftRecord)):
        return _author_drift_items(record)
    if isinstance(record, VoiceDriftRecord):
        return _character_drift_items(record)
    msg = f"unsupported detection-record shape: {type(record).__name__}"
    raise DetectionProtocolError(msg)


def _item(index: str, parts: tuple[str, ...], chapter_ref: str | None) -> DetectionItem:
    evidence = " ".join(part for part in parts if part)
    return DetectionItem(
        index=index,
        evidence=evidence,
        fingerprint=normalize_text(evidence),
        chapter_ref=chapter_ref,
    )


def _consistency_items(record: ConsistencyCheckRecord) -> tuple[DetectionItem, ...]:
    return tuple(
        _item(
            f"issues[{issue.finding_index}]",
            (*issue.entity_names, issue.description, issue.contradiction),
            None,
        )
        for issue in record.issues
    )


def _series_items(record: SeriesConsistencyRecord) -> tuple[DetectionItem, ...]:
    return tuple(
        _item(
            f"conflicts[{position}]",
            (
                conflict.canon_entry_name,
                conflict.chapter_text_excerpt,
                conflict.canon_statement,
                conflict.explanation,
            ),
            None,
        )
        for position, conflict in enumerate(record.conflicts)
    )


def _temporal_items(record: TemporalConsistencyRecord) -> tuple[DetectionItem, ...]:
    return tuple(
        _item(
            f"issues[{position}]",
            (issue.rule_id, issue.description, issue.suggestion),
            None,
        )
        for position, issue in enumerate(record.issues)
    )


def _voice_check_items(record: VoiceCheckRecord) -> tuple[DetectionItem, ...]:
    _assert_unique(
        [finding.character_name for finding in record.characters],
        f"voice-check chapter {record.chapter_id}",
    )
    items: list[DetectionItem] = []
    for char_position, finding in enumerate(record.characters):
        for line_position, line in enumerate(finding.flagged_lines):
            items.append(
                _item(
                    f"characters[{char_position}].flagged_lines[{line_position}]",
                    (finding.character_name, line.quote, line.reason),
                    record.chapter_id,
                )
            )
    return tuple(items)


def _author_drift_items(
    record: SeriesVoiceDriftRecord | AuthorVoiceDriftRecord,
) -> tuple[DetectionItem, ...]:
    _validate_exclusive(record.result, record.no_profile_reason, type(record).__name__)
    if record.result is None:
        return ()
    return (_verdict_item("result.drift", None, record.result.drift),)


def _character_drift_items(record: VoiceDriftRecord) -> tuple[DetectionItem, ...]:
    _assert_unique([result.character_id for result in record.characters], "voice-drift results")
    return tuple(
        _verdict_item(f"characters[{position}].drift", result.character_name, result.drift)
        for position, result in enumerate(record.characters)
    )


def _verdict_item(index: str, character_name: str | None, verdict: DriftVerdict) -> DetectionItem:
    note_texts = tuple(note for _, note in verdict.per_chapter_notes)
    return _item(
        index,
        (
            *((character_name,) if character_name is not None else ()),
            verdict.drift_type,
            *verdict.longitudinal_reasons,
            *note_texts,
        ),
        None,
    )


def _validate_exclusive(
    result: AuthorDriftResult | None, no_profile_reason: str | None, where: str
) -> None:
    """``result`` XOR ``no_profile_reason`` with at-least-one (T10 rider)."""
    if (result is None) == (no_profile_reason is None):
        msg = (
            f"{where}: result XOR no_profile_reason violated — "
            f"result={result!r}, no_profile_reason={no_profile_reason!r}"
        )
        raise DetectionProtocolError(msg)


def _assert_unique(identities: list[str], where: str) -> None:
    """Duplicate collected results are a protocol violation (T10 rider)."""
    if len(set(identities)) != len(identities):
        msg = f"{where}: duplicate character results in one record"
        raise DetectionProtocolError(msg)
