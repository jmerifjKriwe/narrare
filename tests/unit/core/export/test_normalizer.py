"""Unit tests for the Narrare Normalizer (IO-001 / ADR-081, Slice 1).

The **strip-guarantee** is the central invariant: editor artifacts NEVER appear
in ``NormalizedManuscript.semantic_html``. One test per custom TipTap mark
asserts the REAL HTML each extension emits — the selectors are derived from the
TipTap extension source in ``packages/web/components/studio/editor/extensions/``
(``AIAnnotation.ts``, ``GhostText.ts``, ``SceneBreak.ts``, ``DialogueMark.ts``).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bs4 import BeautifulSoup

from narrare_core.export.contracts import (
    ChapterMeta,
    Language,
    ManuscriptMetadata,
    NormalizedManuscript,
)
from narrare_core.export.normalizer import NarrareNormalizer

# ---------------------------------------------------------------------------
# Real HTML each TipTap extension emits (the contract — load-bearing).
# ---------------------------------------------------------------------------
#
# AIAnnotation — AIAnnotationMark.renderHTML (AIAnnotation.ts): wraps AI text.
AI_ANNOTATION_HTML = (
    '<p>He walked in. <span data-ai-generated="true" data-request-id="req-1" '
    'data-source="extend" data-original-text="old" data-status="pending" '
    'data-created-at="2026-01-01T00:00:00Z" '
    'class="ai-generated-text ai-generated-pending">'
    "The door creaked open.</span> Then silence.</p>"
)
AI_INNER_TEXT = "The door creaked open."

# GhostText — ProseMirror Decoration.widget classes (GhostText.ts). Decoration-
# based; never serialized by getHTML() — stripped defensively if residue leaks.
GHOST_SUGGESTION = '<span class="ghost-text-suggestion" aria-hidden="true">a ghost</span>'
GHOST_HINT = '<span class="ghost-text-hint" aria-hidden="true">(Tab)</span>'
GHOST_FETCHING = '<span class="ghost-text-fetching" aria-hidden="true">…</span>'
GHOST_ERROR = '<span class="ghost-text-error" aria-hidden="true">err</span>'
GHOST_CLASSES = (
    "ghost-text-suggestion",
    "ghost-text-hint",
    "ghost-text-fetching",
    "ghost-text-error",
)

# SceneBreak — SceneBreak.renderHTML emits the <p> form; parseHTML also takes <hr>.
SCENEBREAK_P = '<p class="scene-break">* * *</p>'
SCENEBREAK_HR = '<hr class="scene-break">'

# DialogueMark — DialogueMark.renderHTML wraps the quoted speech.
DIALOGUE_HTML = '<p><span class="dialogue">"Are you coming?"</span> she asked.</p>'
DIALOGUE_QUOTE = '"Are you coming?"'

# Canonical scene break the normalizer produces.
CANONICAL_SCENE_BREAK = '<hr class="scene-break"/>'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _meta(**overrides: object) -> ManuscriptMetadata:
    fields: dict[str, object] = {
        "title": "The Test Novel",
        "author": "Jane Doe",
        "language": Language.EN,
    }
    fields.update(overrides)
    return ManuscriptMetadata(**fields)  # type: ignore[arg-type]


def _chapters_order(*positions: int) -> list[ChapterMeta]:
    """Chapters deliberately seeded out of position order (for ordering tests)."""
    return [
        ChapterMeta(chapter_id=uuid4(), title=f"Chapter {p}", position=p, volume_id=None)
        for p in positions
    ]


def _count_tags(html: str, selector: str) -> int:
    """Re-parse and count tags matching a CSS selector (structure assertion)."""
    return len(BeautifulSoup(html, "lxml").select(selector))


# ---------------------------------------------------------------------------
# Strip-guarantee: AIAnnotation
# ---------------------------------------------------------------------------


class TestStripAIAnnotation:
    """AIAnnotation wrapper is stripped; inner text becomes plain prose."""

    @pytest.mark.asyncio
    async def test_strips_wrapper_keeps_inner_text(self) -> None:
        result = await NarrareNormalizer().normalize(AI_ANNOTATION_HTML, _meta())

        assert "data-ai-generated" not in result.semantic_html
        assert "ai-generated-text" not in result.semantic_html
        assert "ai-generated-pending" not in result.semantic_html
        assert AI_INNER_TEXT in result.semantic_html

    @pytest.mark.asyncio
    async def test_nested_ai_annotation_unwrapped(self) -> None:
        html = (
            '<p><span data-ai-generated="true" class="ai-generated-text ai-generated-pending">'
            '<span class="dialogue">"Nested."</span></span></p>'
        )
        result = await NarrareNormalizer().normalize(html, _meta())

        assert "data-ai-generated" not in result.semantic_html
        assert '"Nested."' in result.semantic_html
        assert 'class="dialogue"' not in result.semantic_html  # dialogue also unwrapped

    @pytest.mark.asyncio
    async def test_multiple_ai_annotations_all_stripped(self) -> None:
        html = (
            '<p><span data-ai-generated="true">One.</span> '
            '<span data-ai-generated="true">Two.</span></p>'
        )
        result = await NarrareNormalizer().normalize(html, _meta())

        assert result.semantic_html.count("data-ai-generated") == 0
        assert "One." in result.semantic_html
        assert "Two." in result.semantic_html


# ---------------------------------------------------------------------------
# Strip-guarantee: GhostText (defensive)
# ---------------------------------------------------------------------------


class TestStripGhostText:
    """GhostText residue is removed entirely; absent residue is a no-op."""

    @pytest.mark.asyncio
    async def test_strips_all_four_decoration_classes(self) -> None:
        html = f"<p>Start {GHOST_SUGGESTION} {GHOST_HINT} {GHOST_FETCHING} {GHOST_ERROR} end.</p>"
        result = await NarrareNormalizer().normalize(html, _meta())

        for residue_class in GHOST_CLASSES:
            assert residue_class not in result.semantic_html
        # The suggestion text must NOT survive (it was never accepted content).
        assert "a ghost" not in result.semantic_html

    @pytest.mark.asyncio
    async def test_noop_when_no_residue(self) -> None:
        html = "<p>A clean paragraph with no ghost text.</p>"
        result = await NarrareNormalizer().normalize(html, _meta())

        for residue_class in GHOST_CLASSES:
            assert residue_class not in result.semantic_html
        assert "A clean paragraph with no ghost text." in result.semantic_html


# ---------------------------------------------------------------------------
# Normalize: SceneBreak
# ---------------------------------------------------------------------------


class TestNormalizeSceneBreak:
    """Both scene-break forms → the single canonical <hr>."""

    @pytest.mark.asyncio
    async def test_p_form_normalized_to_canonical_hr(self) -> None:
        result = await NarrareNormalizer().normalize(SCENEBREAK_P, _meta())

        assert CANONICAL_SCENE_BREAK in result.semantic_html
        assert '<p class="scene-break">' not in result.semantic_html
        assert "* * *" not in result.semantic_html  # literal text dropped

    @pytest.mark.asyncio
    async def test_hr_form_normalized_to_canonical(self) -> None:
        result = await NarrareNormalizer().normalize(SCENEBREAK_HR, _meta())

        assert _count_tags(result.semantic_html, "hr.scene-break") == 1

    @pytest.mark.asyncio
    async def test_multiple_scene_breaks_each_normalized(self) -> None:
        html = f"<p>Scene one.</p>{SCENEBREAK_P}<p>Scene two.</p>{SCENEBREAK_HR}<p>Scene three.</p>"
        result = await NarrareNormalizer().normalize(html, _meta())

        assert _count_tags(result.semantic_html, "hr.scene-break") == 2
        assert result.semantic_html.count("* * *") == 0


# ---------------------------------------------------------------------------
# Normalize: DialogueMark
# ---------------------------------------------------------------------------


class TestNormalizeDialogueMark:
    """Dialogue spans are unwrapped; the quoted text (with quotes) is kept."""

    @pytest.mark.asyncio
    async def test_unwraps_span_keeps_quotes(self) -> None:
        result = await NarrareNormalizer().normalize(DIALOGUE_HTML, _meta())

        assert 'class="dialogue"' not in result.semantic_html
        assert "<span" not in result.semantic_html  # dialogue span fully unwrapped
        assert DIALOGUE_QUOTE in result.semantic_html
        assert "she asked." in result.semantic_html

    @pytest.mark.asyncio
    async def test_multiple_dialogue_spans_all_unwrapped(self) -> None:
        html = '<p><span class="dialogue">"Yes."</span> <span class="dialogue">"No."</span></p>'
        result = await NarrareNormalizer().normalize(html, _meta())

        assert 'class="dialogue"' not in result.semantic_html
        assert '"Yes."' in result.semantic_html
        assert '"No."' in result.semantic_html


# ---------------------------------------------------------------------------
# Structure: metadata passthrough + chapter ordering
# ---------------------------------------------------------------------------


class TestStructure:
    """Metadata scalars pass through; chapters are returned in position order."""

    @pytest.mark.asyncio
    async def test_metadata_scalars_passthrough(self) -> None:
        meta = ManuscriptMetadata(
            title="Der Wald",
            author="K. Mustermann",
            language=Language.DE,
            isbn="978-0-00-000000-1",
            description="A novel.",
        )
        result = await NarrareNormalizer().normalize("<p>Body.</p>", meta)

        assert result.title == "Der Wald"
        assert result.author == "K. Mustermann"
        assert result.language is Language.DE

    @pytest.mark.asyncio
    async def test_isbn_description_passthrough(self) -> None:
        """Optional EPUB metadata is carried through for dc:identifier/description."""
        meta = _meta(isbn="978-0-00-000000-1", description="A novel.")
        result = await NarrareNormalizer().normalize("<p>Body.</p>", meta)

        assert result.isbn == "978-0-00-000000-1"
        assert result.description == "A novel."

    @pytest.mark.asyncio
    async def test_isbn_description_none_when_absent(self) -> None:
        """Backward compat: metadata without isbn/description yields None (not an error)."""
        result = await NarrareNormalizer().normalize("<p>Body.</p>", _meta())

        assert result.isbn is None
        assert result.description is None

    @pytest.mark.asyncio
    async def test_chapters_sorted_by_position(self) -> None:
        # Seed deliberately out of order (position 2, 0, 1).
        chapters = _chapters_order(2, 0, 1)
        meta = _meta(chapters=chapters)
        result = await NarrareNormalizer().normalize("<p>Body.</p>", meta)

        assert [c.position for c in result.chapters] == [0, 1, 2]
        # Stable sort preserves nothing-to-break here; titles align to positions.
        assert [c.title for c in result.chapters] == ["Chapter 0", "Chapter 1", "Chapter 2"]

    @pytest.mark.asyncio
    async def test_empty_chapters_default(self) -> None:
        result = await NarrareNormalizer().normalize("<p>Body.</p>", _meta())
        assert result.chapters == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Empty, idempotent, malformed, and mixed-content handling."""

    @pytest.mark.asyncio
    async def test_empty_manuscript(self) -> None:
        result = await NarrareNormalizer().normalize("", _meta())
        assert result.semantic_html == ""
        assert isinstance(result, NormalizedManuscript)

    @pytest.mark.asyncio
    async def test_whitespace_only_manuscript(self) -> None:
        result = await NarrareNormalizer().normalize("   \n\t  ", _meta())
        assert result.semantic_html == ""

    @pytest.mark.asyncio
    async def test_comment_only_body_has_no_renderable_content(self) -> None:
        # A non-empty body that parses to no <body> (lxml drops a bare comment)
        # bypasses the whitespace guard; the serializer yields empty HTML.
        result = await NarrareNormalizer().normalize("<!-- a note -->", _meta())
        assert result.semantic_html == ""

    @pytest.mark.asyncio
    async def test_clean_html_is_noop_idempotent(self) -> None:
        clean = "<p>Just a normal paragraph.</p>"
        once = await NarrareNormalizer().normalize(clean, _meta())
        twice = await NarrareNormalizer().normalize(once.semantic_html, _meta())
        # Already-clean HTML passes through without introducing artifacts, and the
        # normalizer's own output is a fixed point.
        assert once.semantic_html == twice.semantic_html
        assert "data-ai-generated" not in once.semantic_html

    @pytest.mark.asyncio
    async def test_malformed_unclosed_tags_repaired(self) -> None:
        # lxml repairs unclosed tags; no crash, no artifact leakage.
        html = '<p>Unclosed paragraph <span data-ai-generated="true">kept</span>'
        result = await NarrareNormalizer().normalize(html, _meta())

        assert "data-ai-generated" not in result.semantic_html
        assert "kept" in result.semantic_html

    @pytest.mark.asyncio
    async def test_per_span_lang_attribute_preserved(self) -> None:
        # A non-mark span carrying a language attribute must survive untouched.
        html = '<p>He said <span lang="fr">bonjour</span> and left.</p>'
        result = await NarrareNormalizer().normalize(html, _meta())

        assert 'lang="fr"' in result.semantic_html
        assert "bonjour" in result.semantic_html


# ---------------------------------------------------------------------------
# Regression: a representative dirty chapter (all four marks present)
# ---------------------------------------------------------------------------


class TestRegressionDirtyChapter:
    """A chapter carrying every custom mark normalizes to clean semantic HTML."""

    @pytest.mark.asyncio
    async def test_dirty_chapter_normalized(self) -> None:
        dirty = (
            "<h1>Chapter One</h1>"
            f"<p>He entered. {AI_ANNOTATION_HTML.removeprefix('<p>').removesuffix('</p>')}</p>"
            f"{SCENEBREAK_P}"
            f"<p>{DIALOGUE_HTML.removeprefix('<p>').removesuffix('</p>')}</p>"
            f"<p>Tail {GHOST_SUGGESTION} end.</p>"
        )
        result = await NarrareNormalizer().normalize(dirty, _meta())
        out = result.semantic_html

        # Strip-guarantee (negative matches — the load-bearing assertions).
        assert "data-ai-generated" not in out
        assert "ai-generated-text" not in out
        for residue_class in GHOST_CLASSES:
            assert residue_class not in out
        assert '<p class="scene-break">' not in out
        assert 'class="dialogue"' not in out

        # Content preserved.
        assert "Chapter One" in out
        assert AI_INNER_TEXT in out
        assert DIALOGUE_QUOTE in out
        assert "Tail" in out and "end." in out

        # Scene break normalized to the canonical <hr>.
        assert _count_tags(out, "hr.scene-break") == 1
        assert "* * *" not in out


# ---------------------------------------------------------------------------
# Idempotence (fixed-point) property
# ---------------------------------------------------------------------------


class TestIdempotence:
    """Normalizing the normalizer's output is a no-op (stable representation)."""

    @pytest.mark.asyncio
    async def test_double_normalize_is_fixed_point(self) -> None:
        dirty = (
            f"<p>{AI_ANNOTATION_HTML.removeprefix('<p>').removesuffix('</p>')}</p>"
            f"{SCENEBREAK_P}"
            f"<p>{DIALOGUE_HTML.removeprefix('<p>').removesuffix('</p>')}</p>"
        )
        once = await NarrareNormalizer().normalize(dirty, _meta())
        twice = await NarrareNormalizer().normalize(once.semantic_html, _meta())
        assert once.semantic_html == twice.semantic_html
