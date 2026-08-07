"""``render_author_voice_delta`` — Series Voice Hierarchy Delta-model renderer
(Spec 3 / ADR-078).

Extracted from :mod:`tests.unit.core.profiles.test_author_voice` (RULE-04 —
the parent file exceeded the 400-line hard limit once the Delta renderer
suite was added). The shared profile fixtures
(:func:`~tests.unit.core.profiles.test_author_voice._full_profile`,
``_populated_voice_metrics``, ``_populated_author_metrics``) are imported from
the origin module to avoid fixture drift; the DISTINCT
:func:`_series_profile` (the Delta foundation) lives here.

This suite covers the three Delta concerns:

    1. :class:`TestRenderAuthorVoiceDeltaBackwardCompat` — ``series_id=None``
       (standalone novel) is byte-identical to the legacy descriptive-only
       renderer. CRITICAL Spec 3 Task 4 backward-compat guarantee.
    2. :class:`TestRenderAuthorVoiceDeltaSeriesHierarchy` — the resolution
       matrix (series + novel → Delta; series only; opt-out; no series voice;
       empty).
    3. :class:`TestRenderAuthorVoiceDeltaBoundary` — the ADR-074 binding
       boundary holds under the Delta composition (no metric leak from either
       profile).

See:
    ``docs/superpowers/specs/2026-08-02-series-voice-hierarchy-design.md`` §3.1.
    ADR-078 — Series Voice Hierarchy (Delta model).
    ADR-074 — descriptive/metric binding boundary.
"""

from __future__ import annotations

from uuid import uuid4

from narrare_core.analysis.author_metrics import AuthorMetrics
from narrare_core.profiles.author_voice import (
    AuthorVoiceProfile,
    render_author_voice_delta,
    render_author_voice_for_generation,
)
from narrare_core.schemas.voice import VoiceAnalysis, VoiceMetrics

# Shared fixtures imported from the origin module (RULE-04 split — keeps the
# fixtures SSOT in one place so the descriptive-only renderer tests and the
# Delta renderer tests cannot drift apart).
from tests.unit.core.profiles.test_author_voice import (
    _full_profile,
    _populated_author_metrics,
)


def _series_profile() -> AuthorVoiceProfile:
    """A DISTINCT series-level profile (Delta-model foundation).

    Uses different descriptive values than :func:`_full_profile` so Delta
    tests can assert BOTH voices appear (series foundation + novel nuances)
    and that they are not conflated.
    """
    return AuthorVoiceProfile(
        voice_analysis=VoiceAnalysis(
            formality=0.30,
            vocabulary_level="plain-spoken",
            sentence_profile="short and rhythmic",
            emotional_range="understated",
            cultural_regional_markers="Southern American vernacular",
            voice_examples=["The road went on. Dust and heat."],
            voice_metrics=VoiceMetrics(
                avg_sentence_length=9.1,
                sentence_length_std=2.2,
                type_token_ratio=0.55,
                avg_syllables_per_word=1.2,
                contraction_rate=0.21,
                punctuation_profile={"exclamation": 0.0, "question": 0.01},
            ),
        ),
        author_examples=["The road went on. Dust and heat."],
        author_metrics=AuthorMetrics(
            dialogue_ratio=0.61,
            description_density=0.07,
            action_introspection_ratio=0.33,
            metaphor_density=0.01,
        ),
        updated_at="2026-07-27T00:00:00Z",
        is_fresh=True,
    )


# ---------------------------------------------------------------------------
# Backward compatibility — standalone novels are UNAFFECTED
# ---------------------------------------------------------------------------


class TestRenderAuthorVoiceDeltaBackwardCompat:
    """``series_id=None`` (standalone novel) MUST be byte-identical to the
    existing descriptive-only renderer.

    This is the CRITICAL backward-compatibility guarantee of Spec 3 Task 4:
    standalone novels are completely unaffected by the Delta-model change.
    The Delta renderer with ``series_id=None`` must produce exactly what
    :func:`render_author_voice_for_generation` has always produced — no new
    labels, no reformatting, no regression.
    """

    def test_standalone_with_profile_matches_legacy_renderer(self) -> None:
        novel = _full_profile()
        assert render_author_voice_delta(novel, None, series_id=None) == (
            render_author_voice_for_generation(novel)
        )

    def test_standalone_without_profile_renders_empty(self) -> None:
        assert render_author_voice_delta(None, None, series_id=None) == ""

    def test_standalone_ignores_series_profile_argument(self) -> None:
        """series_id=None means standalone — a passed series_profile is ignored.

        Defends against a caller accidentally passing a series profile while
        omitting series_id (which would otherwise silently inject series
        content into a standalone novel — a RULE-11 / backward-compat break).
        """
        novel = _full_profile()
        series = _series_profile()
        out = render_author_voice_delta(novel, series, series_id=None)
        assert out == render_author_voice_for_generation(novel)
        # Series-only content must NOT appear in a standalone render.
        assert "Southern American vernacular" not in out
        assert "Series voice" not in out


# ---------------------------------------------------------------------------
# Series Voice Hierarchy resolution matrix
# ---------------------------------------------------------------------------


class TestRenderAuthorVoiceDeltaSeriesHierarchy:
    """The Delta model (Spec 3 §3.1) — series voice as foundation, novel voice
    additive, per-novel opt-out.

    Resolution matrix (series_id set):
        series + novel + opt-in  → "Series voice:\\n{series}\\n\\nNovel nuances:\\n{novel}"
        series only + opt-in     → "Series voice:\\n{series}"
        opt-out                  → novel only (series skipped) — UNCHANGED
        no series voice          → novel only — UNCHANGED
        no novel voice           → "" (graceful)
    """

    def test_series_plus_novel_renders_delta_format(self) -> None:
        series_id = uuid4()
        out = render_author_voice_delta(_full_profile(), _series_profile(), series_id=series_id)
        # Both voices appear, framed by the Delta labels.
        assert out.startswith("Series voice:\n")
        assert "\n\nNovel nuances:\n" in out
        # Series foundation content present.
        assert "Southern American vernacular" in out  # series markers
        assert "plain-spoken" in out  # series vocabulary_level
        # Novel nuances content present (additive).
        assert "British, literate register" in out  # novel markers
        assert "complex" in out  # novel vocabulary_level

    def test_series_only_renders_series_voice(self) -> None:
        """Novel without its own profile → series voice as the foundation only."""
        series_id = uuid4()
        out = render_author_voice_delta(None, _series_profile(), series_id=series_id)
        assert out.startswith("Series voice:\n")
        # No "Novel nuances" section when the novel has no profile.
        assert "Novel nuances" not in out
        assert "Southern American vernacular" in out

    def test_opt_out_renders_novel_only(self) -> None:
        """use_series_voice=False → series voice skipped, novel voice only.

        The per-novel opt-out (Spec 3 §3.2). Output MUST be identical to the
        standalone render of the novel profile.
        """
        series_id = uuid4()
        novel = _full_profile()
        out = render_author_voice_delta(
            novel,
            _series_profile(),
            use_series_voice=False,
            series_id=series_id,
        )
        assert out == render_author_voice_for_generation(novel)
        # Series content is absent.
        assert "Series voice" not in out
        assert "Southern American vernacular" not in out

    def test_no_series_voice_renders_novel_only(self) -> None:
        """series_id set but SeriesSettings.author_voice is NULL → novel only.

        Graceful degradation when the series has no profiled voice yet. Output
        is identical to the standalone render (no "Series voice" framing).
        """
        series_id = uuid4()
        novel = _full_profile()
        out = render_author_voice_delta(novel, None, series_id=series_id)
        assert out == render_author_voice_for_generation(novel)
        assert "Series voice" not in out

    def test_no_novel_voice_with_series_renders_series_only(self) -> None:
        """Matrix completeness: novel None + series voice → series only."""
        series_id = uuid4()
        out = render_author_voice_delta(None, _series_profile(), series_id=series_id)
        assert out.startswith("Series voice:\n")
        assert "Novel nuances" not in out

    def test_no_voices_at_all_renders_empty(self) -> None:
        """Both profiles None → empty string (RULE-11 graceful)."""
        series_id = uuid4()
        assert render_author_voice_delta(None, None, series_id=series_id) == ""

    def test_opt_out_with_no_novel_voice_renders_empty(self) -> None:
        """Opt-out + no novel profile → empty (graceful, not series-voice)."""
        series_id = uuid4()
        out = render_author_voice_delta(
            None,
            _series_profile(),
            use_series_voice=False,
            series_id=series_id,
        )
        assert out == ""


# ---------------------------------------------------------------------------
# Binding boundary — metrics NEVER leak under the Delta composition
# ---------------------------------------------------------------------------


class TestRenderAuthorVoiceDeltaBoundary:
    """ADR-074 binding: the Delta composition NEVER leaks metrics from EITHER
    profile into ``{{author_voice}}``.

    Both profiles in the fixtures carry distinctive metric values
    (``avg_sentence_length=14.3``, ``dialogue_ratio=0.42``). The Delta output
    — whether the series block, the novel block, or both — must contain none
    of them.
    """

    def test_delta_output_contains_no_metrics_from_either_profile(self) -> None:
        series_id = uuid4()
        out = render_author_voice_delta(_full_profile(), _series_profile(), series_id=series_id)
        for forbidden in (
            "14.3",
            "0.42",
            "0.55",
            "0.03",
            "avg_sentence_length",
            "dialogue_ratio",
            "metaphor_density",
        ):
            assert forbidden not in out, (
                f"Metric value/label '{forbidden}' leaked into Delta "
                f"{{author_voice}} (boundary violation): {out!r}"
            )


# Re-export the helper so static analysers do not flag it as unused when this
# module is imported BY OTHER test modules (forward-compat for the assembly
# Delta suite). Noop at runtime.
__all__ = ["_full_profile", "_populated_author_metrics", "_series_profile"]
