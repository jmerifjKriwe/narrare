"""Author-voice Delta-model assembly through WritingContextAssembler
(Spec 3 / ADR-078).

Extracted from :mod:`tests.unit.core.writing.test_author_voice_assembly`
(RULE-04 — the parent file exceeded the 400-line hard limit once the Delta
assembly suite was added). Shared helpers (:func:`_full_profile`,
:func:`_populated_author_metrics`, :class:`_FakeAuthorVoiceConsumer`) are
imported from the origin module to avoid fixture drift; the DISTINCT Delta
helpers (:func:`_series_profile`, :class:`_FakeDeltaAuthorVoiceConsumer`)
live here.

This suite covers the assembler → ``AuthorVoiceConsumer.resolve_for_generation``
→ Core Delta renderer integration (Spec 3 Task 4 — the critical cross-feature
wiring):

    - series + novel → Delta format (``"Series voice:\\n…\\n\\nNovel
      nuances:\\n…"``) in ``author_voice``.
    - series only (novel has no profile) → series voice as foundation.
    - opt-out (``use_series_voice=False``) → novel only (series skipped).
    - standalone (``series_id=None``) → novel only, byte-identical to legacy.
    - empty (no profiles) → ``""`` (RULE-11 graceful).
    - ``series_id`` is threaded through to the consumer.
    - no metric leak from either profile under the Delta composition.

See:
    ``docs/superpowers/specs/2026-08-02-series-voice-hierarchy-design.md`` §3.1.
    ADR-078 — Series Voice Hierarchy (Delta model).
    ADR-074 — descriptive/metric binding boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from narrare_core.profiles.author_voice import (
    AuthorVoiceProfile,
    render_author_voice_delta,
    render_author_voice_for_generation,
)
from narrare_core.schemas.voice import VoiceAnalysis
from narrare_core.writing.context_assembler import WritingContextAssembler

# Shared helpers imported from the origin module (RULE-04 split — keeps the
# fixtures SSOT in one place so the legacy assembly tests and the Delta
# assembly tests cannot drift apart).
from tests.unit.core.writing.test_author_voice_assembly import (
    _FakeAuthorVoiceConsumer,
    _full_profile,
    _populated_author_metrics,
)

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.profiles.author_voice_consumer import AuthorVoiceConsumer


def _series_profile() -> AuthorVoiceProfile:
    """A DISTINCT series-level profile (Delta-model foundation).

    Different descriptive values from :func:`_full_profile` so Delta tests can
    assert the series foundation and the novel nuances are BOTH rendered and
    not conflated (Spec 3 / ADR-078).
    """
    return AuthorVoiceProfile(
        voice_analysis=VoiceAnalysis(
            formality=0.30,
            vocabulary_level="plain-spoken",
            sentence_profile="short and rhythmic",
            emotional_range="understated",
            cultural_regional_markers="Southern American vernacular",
            voice_examples=["The road went on. Dust and heat."],
        ),
        author_examples=["The road went on. Dust and heat."],
        author_metrics=_populated_author_metrics(),
        updated_at="2026-07-27T00:00:00Z",
        is_fresh=True,
    )


class _FakeDeltaAuthorVoiceConsumer(_FakeAuthorVoiceConsumer):
    """Delta-aware fake: resolves ``{{author_voice}}`` via the Core Delta renderer.

    Holds an optional series profile + the per-novel ``use_series_voice`` flag
    and delegates to :func:`render_author_voice_delta` — mirroring how the real
    Backend consumer will compose the Delta output (load novel + series +
    flag → pure Core renderer).
    """

    def __init__(
        self,
        novel_profile: AuthorVoiceProfile | None,
        series_profile: AuthorVoiceProfile | None = None,
        *,
        use_series_voice: bool = True,
    ) -> None:
        super().__init__(novel_profile)
        self._series_profile = series_profile
        self._use_series_voice = use_series_voice

    async def resolve_for_generation(
        self,
        project_id: UUID,
        series_id: UUID | None = None,
    ) -> str:
        self._project_id = project_id
        return render_author_voice_delta(
            self._profile,
            self._series_profile,
            use_series_voice=self._use_series_voice,
            series_id=series_id,
        )


@pytest.fixture()
def assembler() -> WritingContextAssembler:
    """Default assembler with 6000-token budget (mirrors the origin module)."""
    return WritingContextAssembler(total_budget=6000)


# ---------------------------------------------------------------------------
# Tests: Series Voice Hierarchy — Delta model (Spec 3 / ADR-078)
# ---------------------------------------------------------------------------


class TestAuthorVoiceDeltaAssembly:
    """``WritingContextAssembler.assemble()`` produces the Delta ``author_voice``
    for series novels (Spec 3 Task 4 — the critical integration).

    These tests exercise the assembler → ``AuthorVoiceConsumer.resolve_for_generation``
    → Core Delta renderer path. They mirror the spec §3.1 resolution matrix:

        series_id + both voices   → "Series voice:\\n…\\n\\nNovel nuances:\\n…"
        series_id + series only   → "Series voice:\\n…"
        opt-out (use_series=False)→ novel only (series skipped)
        standalone (series_id=None)→ novel only — UNCHANGED from legacy
        empty                     → "" (graceful)

    Backward-compat guarantee: a consumer that resolves novel-only (the legacy
    :class:`_FakeAuthorVoiceConsumer`) + ``series_id=None`` produces byte-identical
    output to the pre-Spec-3 behaviour.
    """

    @pytest.mark.asyncio
    async def test_delta_both_voices_rendered_for_series_novel(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Series novel with both profiles → Delta format in author_voice."""
        consumer: AuthorVoiceConsumer = _FakeDeltaAuthorVoiceConsumer(
            novel_profile=_full_profile(),
            series_profile=_series_profile(),
        )
        ctx = await assembler.assemble(
            project_id=uuid4(),
            series_id=uuid4(),
            chapter_content="Content.",
            author_voice_consumer=consumer,
        )
        assert ctx.author_voice.startswith("Series voice:\n")
        assert "\n\nNovel nuances:\n" in ctx.author_voice
        # Series foundation content.
        assert "Southern American vernacular" in ctx.author_voice
        # Novel nuances content (additive).
        assert "British, literate register" in ctx.author_voice

    @pytest.mark.asyncio
    async def test_delta_series_only_when_novel_has_no_profile(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Series novel without its own profile → series voice as foundation."""
        consumer: AuthorVoiceConsumer = _FakeDeltaAuthorVoiceConsumer(
            novel_profile=None,
            series_profile=_series_profile(),
        )
        ctx = await assembler.assemble(
            project_id=uuid4(),
            series_id=uuid4(),
            chapter_content="Content.",
            author_voice_consumer=consumer,
        )
        assert ctx.author_voice.startswith("Series voice:\n")
        assert "Novel nuances" not in ctx.author_voice
        assert "Southern American vernacular" in ctx.author_voice

    @pytest.mark.asyncio
    async def test_delta_opt_out_renders_novel_only(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """use_series_voice=False → series voice skipped, novel voice only."""
        novel = _full_profile()
        consumer: AuthorVoiceConsumer = _FakeDeltaAuthorVoiceConsumer(
            novel_profile=novel,
            series_profile=_series_profile(),
            use_series_voice=False,
        )
        ctx = await assembler.assemble(
            project_id=uuid4(),
            series_id=uuid4(),
            chapter_content="Content.",
            author_voice_consumer=consumer,
        )
        # Identical to the standalone render of the novel profile — no framing.
        assert ctx.author_voice == render_author_voice_for_generation(novel)
        assert "Series voice" not in ctx.author_voice
        assert "Southern American vernacular" not in ctx.author_voice

    @pytest.mark.asyncio
    async def test_delta_standalone_novel_unaffected_by_series_id_param(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """series_id=None → Delta renderer returns novel-only (unchanged).

        CRITICAL backward-compat regression: a standalone novel's author_voice
        is byte-identical whether or not the Delta path is wired. This holds
        even when the consumer is Delta-aware.
        """
        novel = _full_profile()
        # Delta-aware consumer, but standalone novel (series_id omitted).
        consumer: AuthorVoiceConsumer = _FakeDeltaAuthorVoiceConsumer(
            novel_profile=novel,
            series_profile=_series_profile(),
        )
        ctx = await assembler.assemble(
            project_id=uuid4(),
            chapter_content="Content.",
            author_voice_consumer=consumer,
        )
        assert ctx.author_voice == render_author_voice_for_generation(novel)
        assert "Series voice" not in ctx.author_voice

    @pytest.mark.asyncio
    async def test_delta_empty_when_no_profiles(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Series novel with neither profile → author_voice = "" (graceful)."""
        consumer: AuthorVoiceConsumer = _FakeDeltaAuthorVoiceConsumer(
            novel_profile=None,
            series_profile=None,
        )
        ctx = await assembler.assemble(
            project_id=uuid4(),
            series_id=uuid4(),
            chapter_content="Content.",
            author_voice_consumer=consumer,
        )
        assert ctx.author_voice == ""

    @pytest.mark.asyncio
    async def test_delta_author_voice_threads_series_id_to_consumer(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """The assembler MUST forward ``series_id`` to the consumer.

        Guards against a wiring regression where ``series_id`` is accepted by
        ``assemble()`` but silently dropped before reaching the consumer (which
        would collapse every series novel back to standalone behaviour).
        """
        captured: dict[str, object] = {}

        class _CapturingConsumer(_FakeDeltaAuthorVoiceConsumer):
            async def resolve_for_generation(
                self,
                project_id: UUID,
                series_id: UUID | None = None,
            ) -> str:
                captured["project_id"] = project_id
                captured["series_id"] = series_id
                return await super().resolve_for_generation(project_id, series_id)

        consumer: AuthorVoiceConsumer = _CapturingConsumer(
            novel_profile=_full_profile(),
            series_profile=_series_profile(),
        )
        the_series_id = uuid4()
        the_project_id = uuid4()
        await assembler.assemble(
            project_id=the_project_id,
            series_id=the_series_id,
            chapter_content="Content.",
            author_voice_consumer=consumer,
        )
        assert captured.get("series_id") == the_series_id
        assert captured.get("project_id") == the_project_id

    @pytest.mark.asyncio
    async def test_delta_output_has_no_metric_leak(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """The Delta composition must not leak metrics from either profile."""
        consumer: AuthorVoiceConsumer = _FakeDeltaAuthorVoiceConsumer(
            novel_profile=_full_profile(),
            series_profile=_series_profile(),
        )
        ctx = await assembler.assemble(
            project_id=uuid4(),
            series_id=uuid4(),
            chapter_content="Content.",
            author_voice_consumer=consumer,
        )
        for forbidden in ("14.3", "0.42", "0.55", "0.03", "avg_sentence_length", "dialogue_ratio"):
            assert forbidden not in ctx.author_voice, (
                f"Metric '{forbidden}' leaked into Delta {{author_voice}}: {ctx.author_voice!r}"
            )
