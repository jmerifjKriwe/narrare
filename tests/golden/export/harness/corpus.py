"""Corpus registry for the Golden-Pages acceptance test (IO-001 Slice 7).

Each :class:`CorpusFixture` carries a committed HTML file (exactly the
``NormalizedManuscript.semantic_html`` shape — clean, normalised TipTap HTML)
plus the manuscript metadata the REAL renderer consumes
(:class:`TypstPdfRenderer.render()` → title, author, language). The chapter
metadata (:class:`ChapterMeta`) is parsed from the ``<h2>`` headings in the
HTML, so the HTML remains the single source of content.

``build_manuscript()`` / ``build_options()`` construct the exact inputs the
production ``TypstPdfRenderer.render()`` takes — the golden test renders every
fixture through that adapter (not a hand-rolled compile), which is what makes
it an acceptance test of the whole pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from uuid import UUID, uuid5

from narrare.export.options import ExportFormat, ExportOptions
from narrare_core.export.contracts import (
    ChapterMeta,
    Language,
    ManuscriptMetadata,
    NormalizedManuscript,
)

#: Directory holding the committed HTML fixtures (this file's parent/../corpus).
CORPUS_DIR: Path = Path(__file__).resolve().parent.parent / "corpus"

#: Directory holding the committed baseline JSONs.
BASELINE_DIR: Path = Path(__file__).resolve().parent.parent / "baselines"

#: A deterministic namespace UUID for chapter-id generation (so renders are
#: reproducible — the UUID does not affect the PDF, but a stable id keeps test
#: output clean and avoids leaking entropy into the manuscript model).
_NAMESPACE = uuid5(UUID(int=0), "narrare-golden-pages-corpus")

#: Regex extracting ``<h2>`` heading text from the clean semantic HTML. The
#: normalised manuscript never nests tags inside headings, so a non-greedy
#: capture of the text content is sufficient and dependency-free (no
#: BeautifulSoup for controlled, clean input). HTML comments are stripped
#: FIRST — the corpus fixtures carry documentation comments that may contain
#: the literal string ``<h2>`` (e.g. "pandoc converts … so <h2> becomes …"),
#: which would otherwise match across the comment boundary.
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_H2_RE = re.compile(r"<h2[^>]*>\s*(.*?)\s*</h2>", re.IGNORECASE | re.DOTALL)

#: The probe names that apply to every fixture (universal invariants).
_UNIVERSAL_PROBES: frozenset[str] = frozenset(
    {
        "byte_reproducibility",
        "text_layer_tounicode",
        "folio_numbering",
        "running_header",
        "recto_start",
    }
)


@dataclass(frozen=True)
class CorpusFixture:
    """One committed manuscript fixture + the probes that apply to it.

    ``html_file``  — the committed ``.html`` (semantic_html shape).
    ``title``      — book title (title page + verso running head).
    ``author``     — author (title page, scalar string — F-7).
    ``language``   — primary manuscript language (drives Typst ``text(lang:)``).
    ``tounicode_words`` — distinctive substrings that MUST extract verbatim from
                      the PDF text layer (the ToUnicode / SILE-disqualifier
                      probe). Prefer words carrying accented codepoints
                      (ä/ö/ü/ß/é/è) so a ToUnicode regression surfaces.
    ``extra_probes`` — fixture-specific probes beyond the universal set
                      (e.g. ``scene_break_present`` for the scene-break fixture;
                      ``right_edge_max_error`` + ``word_gap_stdev`` for
                      fixtures with justified multi-line body text).
    """

    name: str
    html_file: Path
    title: str
    author: str
    language: Language
    tounicode_words: tuple[str, ...]
    extra_probes: frozenset[str] = frozenset()

    @cached_property
    def probes(self) -> frozenset[str]:
        """All probes that apply to this fixture (universal + extra)."""
        return _UNIVERSAL_PROBES | self.extra_probes

    @cached_property
    def semantic_html(self) -> str:
        """The committed HTML, read once and cached."""
        return self.html_file.read_text(encoding="utf-8")

    @cached_property
    def chapter_titles(self) -> tuple[str, ...]:
        """Chapter headings parsed from the ``<h2>`` elements (in document order).

        Used by the ``recto_start`` and ``running_header`` probes to locate
        chapter-opener pages and to identify the current-chapter running head.
        HTML comments are stripped before matching so documentation comments
        containing the literal ``<h2>`` do not produce phantom headings.
        """
        html = _COMMENT_RE.sub("", self.semantic_html)
        return tuple(m.group(1).strip() for m in _H2_RE.finditer(html))

    @cached_property
    def chapters(self) -> list[ChapterMeta]:
        """Per-chapter metadata, derived from the ``<h2>`` headings.

        Mirrors what the Backend assembles: one :class:`ChapterMeta` per heading,
        in position order, with deterministic UUIDs. The renderer does not
        consume this (the chapter structure comes from the ``semantic_html``),
        but the manuscript model requires it.
        """
        return [
            ChapterMeta(
                chapter_id=uuid5(_NAMESPACE, f"{self.name}:{position}:{title}"),
                title=title,
                position=position,
                volume_id=None,
            )
            for position, title in enumerate(self.chapter_titles)
        ]

    @property
    def baseline_file(self) -> Path:
        """The committed baseline JSON for this fixture."""
        return BASELINE_DIR / f"{self.name}.json"


def _fixture(
    name: str,
    title: str,
    author: str,
    language: Language,
    tounicode_words: tuple[str, ...],
    extra_probes: frozenset[str] = frozenset(),
) -> CorpusFixture:
    """Build a fixture whose HTML lives at ``corpus/{name}.html``."""
    return CorpusFixture(
        name=name,
        html_file=CORPUS_DIR / f"{name}.html",
        title=title,
        author=author,
        language=language,
        tounicode_words=tounicode_words,
        extra_probes=extra_probes,
    )


#: The committed, varied corpus. Each fixture exercises a distinct concern:
#:   de-prose           — normal German prose (justified body + hyphenation).
#:   de-long-compounds  — the bake-off Belastungsprobe (compound stress).
#:   mixed-dialogue     — per-span de/en/fr (smart quotes + hyphenation per lang).
#:   chapter-opener     — 3 short chapters (recto starts + blank versos).
#:   scene-break        — <hr> → asterism ornament.
#:   novella            — 5-chapter booklet (ToC + 4-phase numbering + heads).
#:
#: The ``right_edge_max_error`` + ``word_gap_stdev`` drift probes apply only to
#: fixtures with justified multi-line body text (the short-chapter fixtures
#: have too little body to measure meaningfully).
CORPUS: list[CorpusFixture] = [
    _fixture(
        name="de-prose",
        title="Der lange Sommer",
        author="Golden-Pages Korpus",
        language=Language.DE,
        tounicode_words=("Bibliothek", "Schwalben", "Fingerspitzen"),
        extra_probes=frozenset({"right_edge_max_error", "word_gap_stdev"}),
    ),
    _fixture(
        name="de-long-compounds-belastungsprobe",
        title="Die Belastungsprobe",
        author="Golden-Pages Korpus",
        language=Language.DE,
        # Long compounds with ä — decisive ToUnicode substrings.
        tounicode_words=(
            "Donaudampfschifffahrtskapitänspatent",
            "Streichholzschächtelchen",
            "Belastungsprobe",
        ),
        extra_probes=frozenset({"right_edge_max_error", "word_gap_stdev"}),
    ),
    _fixture(
        name="mixed-dialogue-de-en-fr",
        title="Das Gespräch in drei Sprachen",
        author="Golden-Pages Korpus",
        language=Language.DE,  # primary language; per-span langs are inline in HTML
        # Accented French substrings (é/è) — the load-bearing ToUnicode test
        # for Latin-1 Supplement glyphs across the mixed-language text layer.
        tounicode_words=("voyageuse", "précisément", "Morgen"),
        extra_probes=frozenset({"right_edge_max_error", "word_gap_stdev"}),
    ),
    _fixture(
        name="chapter-opener",
        title="Drei Kapitel",
        author="Golden-Pages Korpus",
        language=Language.DE,
        tounicode_words=("Erstes Kapitel", "Zweites Kapitel", "Drittes Kapitel"),
    ),
    _fixture(
        name="scene-break",
        title="Der Schnitt",
        author="Golden-Pages Korpus",
        language=Language.DE,
        tounicode_words=("Olivenhaine", "Hafen", "Feigen"),
        extra_probes=frozenset({"scene_break_present"}),
    ),
    CorpusFixture(
        name="novella",
        html_file=CORPUS_DIR / "novella" / "novella.html",
        title="Das weiße Haus",
        author="Golden-Pages Korpus",
        language=Language.DE,
        tounicode_words=("Fensterläden", "Lavendel", "Ysop"),
        extra_probes=frozenset({"right_edge_max_error", "word_gap_stdev"}),
    ),
]


def build_manuscript(fixture: CorpusFixture) -> NormalizedManuscript:
    """Build the :class:`NormalizedManuscript` the real renderer consumes.

    The manuscript carries the committed ``semantic_html`` plus the parsed
    chapter metadata — exactly the shape ``ExportService`` would hand the
    renderer in production.
    """
    return NormalizedManuscript(
        semantic_html=fixture.semantic_html,
        title=fixture.title,
        author=fixture.author,
        language=fixture.language,
        chapters=fixture.chapters,
    )


def build_metadata(fixture: CorpusFixture) -> ManuscriptMetadata:
    """Build the :class:`ManuscriptMetadata` (documentation / completeness)."""
    return ManuscriptMetadata(
        title=fixture.title,
        author=fixture.author,
        language=fixture.language,
        chapters=fixture.chapters,
    )


def build_options(fixture: CorpusFixture) -> ExportOptions:
    """Build the :class:`ExportOptions` for a PDF render with defaults.

    Defaults (``include_toc=True``, B-format paper) exercise the full booklet
    pipeline (title page → frontmatter/ToC → body) on every fixture — that is
    what makes the folio-numbering + running-head probes meaningful.
    """
    return ExportOptions(format=ExportFormat.PDF)


#: Lookup by fixture name (used by the parametrized test + baseline loader).
CORPUS_BY_NAME: dict[str, CorpusFixture] = {f.name: f for f in CORPUS}
