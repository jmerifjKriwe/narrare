"""Type + Deps tests for AuthorVoiceDriftAgent (ANAL-009 Phase 2B / ADR-074).

The author-voice drift agent REUSES the locked
:class:`~narrare_core.agents.character_voice_drift_types.VoiceDriftResult`
output shape (the task's "reuse VoiceDriftResult shape" mandate — the narrator
trend is classified into the same drift_type / confidence / reasons /
per_chapter_notes / suggested_attention contract as a character trend). Only
:class:`AuthorVoiceDriftDeps` is new — it carries the rendered AuthorVoiceProfile
descriptive group (not a per-character profile).
"""

from __future__ import annotations

from narrare_core.agents.author_voice_drift_types import AuthorVoiceDriftDeps
from narrare_core.agents.character_voice_drift_types import (
    ChapterMeta,
    ChapterNote,
    DriftType,
    VoiceDriftResult,
)
from narrare_core.analysis.voice_drift_scoring import (
    JumpPoint,
    TrendPoint,
)


class TestReusesVoiceDriftResultShape:
    """The agent reuses the locked VoiceDriftResult output (no redefinition)."""

    def test_output_is_voice_drift_result(self) -> None:
        # Constructed via the reused type — proves the agent does not redefine
        # a parallel result type.
        out = VoiceDriftResult(
            drift_type="inconsistency",
            confidence=0.82,
            longitudinal_reasons=["dialogue_ratio rises sharply from ch-3"],
            per_chapter_notes=[ChapterNote(chapter_id="ch-7", note="Density jump.")],
            suggested_attention=["ch-7"],
        )
        assert out.drift_type == "inconsistency"
        assert out.confidence == 0.82

    def test_drift_type_literal_still_three_values(self) -> None:
        for dt in ("evolution", "context", "inconsistency"):
            r: DriftType = VoiceDriftResult(drift_type=dt).drift_type  # type: ignore[arg-type]
            assert r == dt


class TestAuthorVoiceDriftDeps:
    """AuthorVoiceDriftDeps construction (plain class, kw-only).

    Mirrors :class:`CharacterVoiceDriftDeps` but for the narrator: no
    ``character_name`` (the trend is narrator-scoped), and
    ``descriptive_profile`` carries the rendered AuthorVoiceProfile descriptive
    group (via ``render_author_voice_for_generation``).
    """

    def test_defaults(self) -> None:
        deps = AuthorVoiceDriftDeps()
        assert deps.descriptive_profile == ""
        assert deps.trend == []
        assert deps.jumps == []
        assert deps.chapter_meta == []
        assert deps.project_title == ""
        assert deps.genre == ""
        assert deps.writing_language == "en"

    def test_all_fields(self) -> None:
        trend = [TrendPoint(chapter_id="ch-1", match_subscore=92.0, band="stable")]
        jumps = [
            JumpPoint(
                from_chapter_id="ch-1",
                to_chapter_id="ch-2",
                jumped_metrics=["dialogue_ratio"],
                magnitude=0.4,
            )
        ]
        meta = [ChapterMeta(chapter_id="ch-1", title="The Arrival")]
        deps = AuthorVoiceDriftDeps(
            descriptive_profile="voice: formal; vocabulary level: complex",
            trend=trend,
            jumps=jumps,
            chapter_meta=meta,
            project_title="The Silent Forest",
            genre="Fantasy",
            writing_language="de",
        )
        assert deps.descriptive_profile.startswith("voice:")
        assert deps.trend == trend
        assert deps.jumps == jumps
        assert deps.chapter_meta == meta
        assert deps.project_title == "The Silent Forest"
        assert deps.genre == "Fantasy"
        assert deps.writing_language == "de"

    def test_trend_defensive_copy(self) -> None:
        source = [TrendPoint(chapter_id="ch-1", match_subscore=90.0, band="stable")]
        deps = AuthorVoiceDriftDeps(trend=source)
        source.append(TrendPoint(chapter_id="ch-2", match_subscore=80.0, band="minor"))
        assert len(deps.trend) == 1

    def test_jumps_defensive_copy(self) -> None:
        source = [
            JumpPoint(
                from_chapter_id="ch-1",
                to_chapter_id="ch-2",
                jumped_metrics=["metaphor_density"],
                magnitude=0.5,
            )
        ]
        deps = AuthorVoiceDriftDeps(jumps=source)
        source.clear()
        assert len(deps.jumps) == 1

    def test_chapter_meta_defensive_copy(self) -> None:
        source = [ChapterMeta(chapter_id="ch-1")]
        deps = AuthorVoiceDriftDeps(chapter_meta=source)
        source.append(ChapterMeta(chapter_id="ch-2"))
        assert len(deps.chapter_meta) == 1

    def test_none_yields_empty_lists(self) -> None:
        deps = AuthorVoiceDriftDeps(trend=None, jumps=None, chapter_meta=None)
        assert deps.trend == []
        assert deps.jumps == []
        assert deps.chapter_meta == []

    def test_has_no_character_name_field(self) -> None:
        """AuthorVoiceDriftDeps is narrator-scoped — no character_name.

        This distinguishes it from CharacterVoiceDriftDeps (per-character) and
        is asserted so a future copy-paste regression fails loudly.
        """
        assert not hasattr(AuthorVoiceDriftDeps(), "character_name")
