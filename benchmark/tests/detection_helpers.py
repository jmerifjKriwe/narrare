"""Fixture builders for the detection scorer tests (Task 12).

Synthetic check records (``benchmark.drivers.check_records`` shapes) and
synthetic errors/reference built on REAL registry id shapes (L01/L03/L06/X07
with their real classes, chapters, and ground-truth refs F132/E022/OF010 from
``benchmark/corpus/variants/*/errors.yaml`` and the committed reference).
Plain helpers — no fixtures, no network. Split from the test module per
RULE-04 (predecessor pattern: ``scoring_helpers.py``).
"""

from __future__ import annotations

from benchmark.corpus_views import (
    Entity,
    ErrorSpec,
    Event,
    Fact,
    PartialDate,
    Reference,
    Relation,
)
from benchmark.drivers.check_records import (
    AuthorDriftResult,
    AuthorVoiceDriftRecord,
    CanonConflictFinding,
    CharacterDriftResult,
    ConsistencyCheckRecord,
    ConsistencyIssueFinding,
    DriftVerdict,
    FlaggedLine,
    SeriesConsistencyRecord,
    SnapshotRead,
    TemporalConsistencyRecord,
    TemporalIssue,
    VoiceCheckFinding,
    VoiceCheckRecord,
    VoiceDriftRecord,
)

NOVEL_ID = "novel-1"


# ---------------------------------------------------------------------------
# Errors (real registry ids/classes/chapters/ground-truth refs)
# ---------------------------------------------------------------------------


def err(error_id: str, error_class: str, chapter: str, ground_truth_ref: str) -> ErrorSpec:
    """Registry-shaped error with stub anchor fields (not consumed here)."""
    return ErrorSpec(
        id=error_id,
        error_class=error_class,
        chapter=chapter,
        anchor="anchor",
        replacement="replacement",
        ground_truth_ref=ground_truth_ref,
        description=f"inject {error_id}",
    )


L01 = err("L01", "attribute_value", "ch-12", "F132")
L03 = err("L03", "date_mismatch", "ch-08", "E022")
L06 = err("L06", "place_mismatch", "ch-12", "OF010")
X07 = err("X07", "retcon", "ch-12", "OF010")

E900 = err("E900", "synthetic", "ch-01", "F900")
"""Six-token topic (name 4 + predicate + value) for threshold-edge tests."""


def synthetic_reference() -> Reference:
    """Entity ``Alpha Beta Gamma Delta`` with fact F900 (predicate ``w``, value ``x``)."""
    return Reference(
        persons=(
            Entity(
                id="p_syn",
                name="Alpha Beta Gamma Delta",
                aliases=(),
                facts=(
                    Fact(
                        id="F900",
                        predicate="w",
                        value="x",
                        valid_from=None,
                        valid_to=None,
                        source_chapters=(1,),
                    ),
                ),
            ),
        ),
        places=(),
        objects=(),
        relations=(),
        events=(),
    )


# ---------------------------------------------------------------------------
# Reference (real id shapes; topics per the scorer's derivation rules)
# ---------------------------------------------------------------------------


def detection_reference() -> Reference:
    """F132 (Anna/age_stated/35), OF010 (Zeichentisch/located_at), E022, R001."""
    anna = Entity(
        id="p_anna_meyer",
        name="Anna Meyer",
        aliases=(),
        facts=(
            Fact(
                id="F132",
                predicate="age_stated",
                value="35",
                valid_from=None,
                valid_to=None,
                source_chapters=(12,),
            ),
        ),
    )
    table = Entity(
        id="o_zeichentisch",
        name="Zeichentisch",
        aliases=(),
        facts=(
            Fact(
                id="OF010",
                predicate="located_at",
                value="pl_tuerkenstrasse",
                valid_from=PartialDate(year=2021, month=8),
                valid_to=None,
                source_chapters=(8,),
            ),
        ),
    )
    move = Event(
        id="E022",
        name="Der Umzug zur Türkenstraße 41",
        date=PartialDate(year=2021, month=8),
        participants=("p_anna_meyer", "p_peter_meyer", "p_juna_meyer"),
        location="pl_tuerkenstrasse",
        source_chapters=(8,),
    )
    sibling = Relation(
        id="R001",
        subject="p_anna_meyer",
        predicate="sibling_of",
        object="p_thomas_meyer",
        valid_from=None,
        valid_to=None,
        source_chapters=(1,),
    )
    return Reference(
        persons=(anna,),
        places=(),
        objects=(table,),
        relations=(sibling,),
        events=(move,),
    )


# ---------------------------------------------------------------------------
# Check-record builders (one record per capability, driver shapes)
# ---------------------------------------------------------------------------


def consistency_finding(
    finding_index: int, names: tuple[str, ...], description: str, contradiction: str
) -> ConsistencyIssueFinding:
    """One CAP-CHK-01 issue finding."""
    return ConsistencyIssueFinding(
        finding_index=finding_index,
        category="entry_internal",
        entity_ids=("entry-1",),
        entity_names=names,
        description=description,
        contradiction=contradiction,
        suggested_resolution=None,
        severity="major",
        confidence=0.9,
    )


def consistency_record(*findings: ConsistencyIssueFinding) -> ConsistencyCheckRecord:
    """CAP-CHK-01 record from explicit findings (multi-item reports)."""
    return ConsistencyCheckRecord(
        novel_id=NOVEL_ID,
        entity_count=len(findings),
        issues=findings,
        summary=(),
        suppressed_count=0,
    )


def consistency_issue(
    finding_index: int, names: tuple[str, ...], description: str, contradiction: str
) -> ConsistencyCheckRecord:
    """CAP-CHK-01 record with exactly one issue."""
    return consistency_record(consistency_finding(finding_index, names, description, contradiction))


def canon_conflict_record(
    name: str, excerpt: str, statement: str, explanation: str
) -> SeriesConsistencyRecord:
    """CAP-CHK-02 record with exactly one canon conflict."""
    return SeriesConsistencyRecord(
        series_id="series-1",
        novel_id=NOVEL_ID,
        conflicts=(
            CanonConflictFinding(
                canon_entry_slug="slug",
                canon_entry_name=name,
                chapter_text_excerpt=excerpt,
                canon_statement=statement,
                explanation=explanation,
                severity="error",
            ),
        ),
        summary="Ein Widerspruch.",
        canon_entry_count=1,
        chapter_count=12,
        snapshot=SnapshotRead(
            generated_at=None, stale=False, has_consistency=True, has_voice_drift=False
        ),
    )


def temporal_record(rule_id: str, description: str, suggestion: str) -> TemporalConsistencyRecord:
    """CAP-CHK-04 record with exactly one issue (event ids are run-scoped)."""
    return TemporalConsistencyRecord(
        issues=(
            TemporalIssue(
                severity="error",
                rule_id=rule_id,
                event_ids=("ev-1",),
                description=description,
                suggestion=suggestion,
                source="deterministic",
            ),
        ),
        deterministic_pass=False,
        overall_assessment="Ein Problem.",
    )


def temporal_record_no_issues() -> TemporalConsistencyRecord:
    """CAP-CHK-04 record reporting nothing."""
    return TemporalConsistencyRecord(
        issues=(), deterministic_pass=True, overall_assessment="Keine Probleme."
    )


def voice_check_record(chapter_id: str, *lines: tuple[str, str, str]) -> VoiceCheckRecord:
    """CAP-CHK-05 record; ``lines`` entries are (character_name, quote, reason)."""
    return VoiceCheckRecord(
        chapter_id=chapter_id,
        characters=tuple(
            VoiceCheckFinding(
                character_name=name,
                match_score=40.0,
                band="red",
                match_judgment="off",
                qualitative_sub_score=40.0,
                metric_delta_subscore=None,
                flagged_lines=(FlaggedLine(quote=quote, reason=reason),),
                has_profile=True,
                n_comparable_metrics=3,
            )
            for name, quote, reason in lines
        ),
        progress_messages=(),
    )


def drift_verdict(*reasons: str) -> DriftVerdict:
    return DriftVerdict(
        drift_type="inconsistency",
        confidence=0.8,
        longitudinal_reasons=reasons,
        per_chapter_notes=(),
        suggested_attention=(),
    )


def author_drift_record(
    *, result: AuthorDriftResult | None, no_profile: str | None
) -> AuthorVoiceDriftRecord:
    """CAP-CHK-07 record; XOR of result/no_profile is the caller's choice."""
    return AuthorVoiceDriftRecord(result=result, no_profile_reason=no_profile, progress_messages=())


def author_drift_result(*reasons: str) -> AuthorDriftResult:
    return AuthorDriftResult(
        novel_id=NOVEL_ID,
        trend=(),
        jumps=(),
        overall_match_score=50.0,
        overall_band="moderate",
        drift=drift_verdict(*reasons),
    )


def character_drift_record(*specs: tuple[str, str, tuple[str, ...]]) -> VoiceDriftRecord:
    """CAP-CHK-06 record; ``specs`` entries are (character_id, name, reasons)."""
    return VoiceDriftRecord(
        characters=tuple(
            CharacterDriftResult(
                character_id=character_id,
                character_name=name,
                trend=(),
                jumps=(),
                overall_match_score=None,
                overall_band=None,
                drift=drift_verdict(*reasons),
            )
            for character_id, name, reasons in specs
        ),
        no_profiles=(),
        progress_messages=(),
    )
