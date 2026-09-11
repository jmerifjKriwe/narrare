"""Unit + integration tests for the pandoc Markdown renderer (Slice 3 / ADR-081).

Two layers:

1. **Pure unit tests** (always run, no binary): availability probe + filename
   slug derivation.
2. **Real-pandoc tests** (``_REQUIRES_PANDOC`` skip guard): the renderer against
   the actual ``pandoc`` binary, including the normalizer→renderer strip-
   guarantee (dirty TipTap HTML in, clean GFM out) and a service-level E2E
   through the real runner (no DB — a fake repo feeds a real source).

The integration-test home is ``tests/unit/api/export/`` (not
``tests/integration/``) deliberately: these tests need the pandoc binary but NO
postgres, and ``tests/integration/conftest.py`` auto-skips every test when the
DB is unavailable — which would hide the renderer coverage on machines without
postgres. The ``skipif`` guard keeps the suite green where the toolchain is
absent instead. ``tests/golden/export/`` is reserved for the Slice-7 PDF
acceptance harness.
"""

from __future__ import annotations

import re
import shutil
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import pytest

from narrare.export import registry, tasks
from narrare.export.contracts import ExportJobStatus
from narrare.export.options import ExportFormat, ExportOptions, MarkdownOptions
from narrare.export.renderers.pandoc_md import PandocMarkdownRenderer, _slugify
from narrare_core.export.contracts import (
    ChapterMeta,
    Language,
    NormalizedManuscript,
)
from narrare_core.export.normalizer import NarrareNormalizer
from tests.unit.api.export.conftest import make_chapter, make_source

NOVEL_ID = UUID("00000000-0000-0000-0000-0000000000a1")
OWNER = UUID("00000000-0000-0000-0000-0000000000ff")  # job owner for registry seeding

_REQUIRES_PANDOC = pytest.mark.skipif(
    shutil.which("pandoc") is None,
    reason="pandoc not installed (install via scripts/install_export_toolchain.sh)",
)

#: A line of three-or-more dashes/asterisks/underscores — the Markdown thematic
#: break pandoc emits for a normalized ``<hr class="scene-break"/>``. Asserted
#: with front matter OFF so the YAML ``---`` delimiter cannot mask the match.
_THEMATIC_BREAK = re.compile(r"(?m)^[-*_]{3,}$")

# Real dirty TipTap HTML — mirrors the per-mark fixtures in
# tests/unit/core/export/test_normalizer.py (the strip-guarantee contract).
_DIRTY_HTML = (
    "<h2>Chapter One</h2>"
    "<p>He walked in. "
    '<span data-ai-generated="true" data-request-id="req-1" '
    'class="ai-generated-text ai-generated-pending">The door creaked open.</span>'
    '<span class="ghost-text-suggestion" aria-hidden="true">a ghost</span>'
    " Then silence.</p>"
    '<p class="scene-break">* * *</p>'
    '<p><span class="dialogue">"Are you coming?"</span> she asked.</p>'
)


def _normalized(
    semantic_html: str,
    *,
    title: str = "Test Novel",
    author: str = "Test Author",
    language: Language = Language.EN,
) -> NormalizedManuscript:
    """Build a NormalizedManuscript with a single placeholder chapter."""
    return NormalizedManuscript(
        semantic_html=semantic_html,
        title=title,
        author=author,
        language=language,
        chapters=[ChapterMeta(chapter_id=uuid4(), title="C1", position=0, volume_id=None)],
    )


def _token_from_url(artifact_url: str) -> str:
    """Extract the raw single-use token from a registry artifact_url."""
    return parse_qs(urlparse(artifact_url).query)["token"][0]


# ── Pure unit tests (always run) ────────────────────────────────────────────


class TestFormatAndAvailability:
    def test_format_is_markdown(self) -> None:
        assert PandocMarkdownRenderer().format is ExportFormat.MARKDOWN

    def test_is_available_true_when_pandoc_on_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(shutil, "which", lambda _cmd: "/usr/bin/pandoc")
        assert PandocMarkdownRenderer().is_available() is True

    def test_is_available_false_when_pandoc_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(shutil, "which", lambda _cmd: None)
        # Fresh instance — _available cache must start unset.
        renderer = PandocMarkdownRenderer()
        assert renderer.is_available() is False

    def test_availability_is_cached(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = 0

        def which(_cmd: str) -> str | None:
            nonlocal calls
            calls += 1
            return "/usr/bin/pandoc"

        monkeypatch.setattr(shutil, "which", which)
        renderer = PandocMarkdownRenderer()
        renderer.is_available()
        renderer.is_available()
        assert calls == 1  # probed once, then cached on the instance


class TestSlugify:
    @pytest.mark.parametrize(
        ("title", "expected"),
        [
            ("My Novel", "my-novel"),
            ("My Novel!", "my-novel"),
            ("A <b> & B", "a-b-b"),
            ("", "manuscript"),
            ("!!!", "manuscript"),
            ("Café Münster", "café-münster"),  # Unicode letters preserved
            ("  spaced  out  ", "spaced-out"),
        ],
    )
    def test_slugify_sanitizes_title(self, title: str, expected: str) -> None:
        assert _slugify(title) == expected


# ── Real-pandoc tests (skipif guarded) ──────────────────────────────────────


class TestRenderMarkdown:
    """``render()`` produces a real GFM artifact via pandoc."""

    @_REQUIRES_PANDOC
    @pytest.mark.asyncio
    async def test_produces_h1_chapters_by_default(self) -> None:
        manuscript = _normalized("<h2>Chapter One</h2>\n<p>Body text.</p>")

        artifact = await PandocMarkdownRenderer().render(
            manuscript, ExportOptions(format=ExportFormat.MARKDOWN)
        )

        try:
            md = artifact.path.read_text(encoding="utf-8")
            assert re.search(r"(?m)^# Chapter One$", md)
            assert "Body text." in md
            assert artifact.media_type == "text/markdown"
            assert artifact.suggested_filename == "test-novel.md"
            assert artifact.format is ExportFormat.MARKDOWN
        finally:
            artifact.path.unlink(missing_ok=True)

    @_REQUIRES_PANDOC
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("level", "heading"),
        [(1, "# Chapter One"), (2, "## Chapter One"), (3, "### Chapter One")],
    )
    async def test_heading_shift_respects_chapter_heading_level(
        self, level: int, heading: str
    ) -> None:
        manuscript = _normalized("<h2>Chapter One</h2>\n<p>Body.</p>")
        options = ExportOptions(
            format=ExportFormat.MARKDOWN,
            markdown_options=MarkdownOptions(
                chapter_heading_level=level, include_front_matter=False
            ),
        )

        artifact = await PandocMarkdownRenderer().render(manuscript, options)

        try:
            md = artifact.path.read_text(encoding="utf-8")
            assert re.search(rf"(?m)^{re.escape(heading)}$", md)
        finally:
            artifact.path.unlink(missing_ok=True)

    @_REQUIRES_PANDOC
    @pytest.mark.asyncio
    async def test_front_matter_prepended(self) -> None:
        manuscript = _normalized(
            "<h2>Chapter One</h2>\n<p>Body.</p>",
            title='Title: A "Quoted" Thing',
            author="Jane Doe",
            language=Language.DE,
        )
        options = ExportOptions(
            format=ExportFormat.MARKDOWN,
            markdown_options=MarkdownOptions(include_front_matter=True),
        )

        artifact = await PandocMarkdownRenderer().render(manuscript, options)

        try:
            md = artifact.path.read_text(encoding="utf-8")
            # YAML front-matter block at the very top.
            assert md.startswith("---\n")
            assert 'title: "Title: A \\"Quoted\\" Thing"' in md
            assert 'author: "Jane Doe"' in md
            assert "lang: de" in md
            # Body still present below the block.
            assert re.search(r"(?m)^# Chapter One$", md)
            assert "Body." in md
        finally:
            artifact.path.unlink(missing_ok=True)

    @_REQUIRES_PANDOC
    @pytest.mark.asyncio
    async def test_front_matter_omitted_when_disabled(self) -> None:
        manuscript = _normalized("<h2>Chapter One</h2>\n<p>Body.</p>")
        options = ExportOptions(
            format=ExportFormat.MARKDOWN,
            markdown_options=MarkdownOptions(include_front_matter=False),
        )

        artifact = await PandocMarkdownRenderer().render(manuscript, options)

        try:
            md = artifact.path.read_text(encoding="utf-8")
            assert not md.startswith("---\n")
            assert re.search(r"(?m)^# Chapter One$", md)
        finally:
            artifact.path.unlink(missing_ok=True)


class TestNormalizerToRendererStrip:
    """The headline guarantee: editor artifacts stripped before Markdown out."""

    @_REQUIRES_PANDOC
    @pytest.mark.asyncio
    async def test_strip_guarantee_in_markdown_output(self) -> None:
        # Normalize the dirty HTML, then render — assert the clean Markdown.
        # Reuse the normalizer's metadata fixture helper for the metadata shape.
        from tests.unit.core.export.test_normalizer import _meta

        normalized = await NarrareNormalizer().normalize(_DIRTY_HTML, _meta())
        options = ExportOptions(
            format=ExportFormat.MARKDOWN,
            markdown_options=MarkdownOptions(include_front_matter=False),
        )

        artifact = await PandocMarkdownRenderer().render(normalized, options)

        try:
            md = artifact.path.read_text(encoding="utf-8")
            # Chapter title promoted to H1 (shift -1).
            assert re.search(r"(?m)^# Chapter One$", md)
            # AIAnnotation unwrapped: inner text KEPT, marker/attrs GONE.
            assert "The door creaked open." in md
            assert "data-ai-generated" not in md
            assert "ai-generated" not in md
            # GhostText decomposed: the decoration text is GONE.
            assert "a ghost" not in md
            assert "ghost-text" not in md
            # DialogueMark unwrapped: the quote KEPT, the wrapper GONE.
            assert '"Are you coming?"' in md
            assert "dialogue" not in md
            # SceneBreak normalized to a Markdown thematic break.
            assert _THEMATIC_BREAK.search(md) is not None
        finally:
            artifact.path.unlink(missing_ok=True)


# ── Service-level E2E through the real runner (no DB) ───────────────────────


class _FakeRepo:
    """Stand-in for ExportRepository: returns a canned source (no DB)."""

    def __init__(self, _session: object, *, source: object | None) -> None:
        self._source = source

    async def get_manuscript_source(
        self, _novel_id: object, _volume_id: object | None = None
    ) -> object:
        return self._source


def _install_session_and_repo(monkeypatch: pytest.MonkeyPatch, *, source: object | None) -> None:
    """Inject a no-op session factory + FakeRepo returning ``source``."""

    class _Factory:
        def __call__(self) -> _Factory:
            return self

        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *exc: object) -> bool:
            return False

    monkeypatch.setattr("narrare._app.database.get_session_factory", lambda: _Factory())
    monkeypatch.setattr(
        tasks, "ExportRepository", lambda session: _FakeRepo(session, source=source)
    )


class TestRunnerEndToEndRealRenderer:
    """Full pipeline (assemble → normalize → render → register → consume) with
    the REAL normalizer + REAL renderer, driven through the in-process runner
    with a fake repo (no DB). Demonstrates the Slice-3 DoD end-to-end."""

    @_REQUIRES_PANDOC
    @pytest.mark.asyncio
    async def test_pipeline_produces_consumable_markdown_artifact(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Real normalizer + real renderer in the runner's dependency slots.
        monkeypatch.setattr(tasks, "_normalizer", NarrareNormalizer())
        monkeypatch.setattr(
            tasks,
            "_renderers",
            {ExportFormat.MARKDOWN: PandocMarkdownRenderer()},
        )
        # One chapter carrying dirty TipTap HTML (exercises the whole strip chain).
        source = make_source(
            novel_id=NOVEL_ID,
            chapters=[make_chapter(title="Chapter One", content=_DIRTY_HTML)],
        )
        _install_session_and_repo(monkeypatch, source=source)

        job = registry.create(NOVEL_ID, OWNER, ExportFormat.MARKDOWN)
        await tasks.run_export_inprocess(
            job.job_id, NOVEL_ID, ExportOptions(format=ExportFormat.MARKDOWN)
        )

        completed = registry.get(job.job_id, OWNER)
        assert completed.status is ExportJobStatus.COMPLETED
        assert completed.artifact_url is not None

        token = _token_from_url(completed.artifact_url)
        artifact = registry.consume_artifact(job.job_id, token, OWNER)
        try:
            md = artifact.path.read_text(encoding="utf-8")
            assert artifact.media_type == "text/markdown"
            assert artifact.suggested_filename.endswith(".md")
            # The strip-guarantee survives the full pipeline.
            assert re.search(r"(?m)^# Chapter One$", md)
            assert "The door creaked open." in md
            assert "a ghost" not in md
            assert "data-ai-generated" not in md
        finally:
            artifact.path.unlink(missing_ok=True)
