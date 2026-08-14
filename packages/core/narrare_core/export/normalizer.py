"""Narrare Normalizer — TipTap HTML → clean semantic HTML (Pure Core).

The only Narrare-specific stage of the export pipeline (IO-001 / ADR-081,
Slice 1). Strips editor artifacts (AIAnnotation, GhostText) and normalizes
structural marks (SceneBreak, DialogueMark) to clean semantic equivalents that
pandoc and Typst consume.

**Non-LLM / non-prompt** (no ``narrare_core.agents`` / ``narrare_core.prompts``
imports) and **Pure Core** (RULE-05: no ``apps/`` imports, no I/O, no
subprocess). The HTML transformation uses BeautifulSoup with the lxml parser —
a tolerant parser that repairs malformed/unclosed tags (regex on HTML is
prohibited as fragile).

The strip-guarantee is the central invariant and is asserted per custom
TipTap mark in ``tests/unit/core/export/test_normalizer.py``. Selectors are
derived from the TipTap extension source
(``packages/web/components/studio/editor/extensions/``).
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from narrare_core.export._internal import (
    normalize_dialogue,
    normalize_scene_breaks,
    order_chapters,
    strip_ai_annotation,
    strip_ghost_text,
)
from narrare_core.export.contracts import (
    ManuscriptMetadata,
    NormalizedManuscript,
)

#: lxml is a tolerant HTML parser — robust against malformed/unclosed tags.
_PARSER = "lxml"


def _parse(raw_html: str) -> BeautifulSoup:
    """Parse a manuscript HTML fragment with the tolerant lxml parser.

    lxml repairs malformed/unclosed tags and wraps a fragment in
    ``<html><body>…</body></html>``; :func:`_serialize` emits only the body's
    children so the fragment shape is preserved.
    """
    return BeautifulSoup(raw_html, _PARSER)


def _serialize(soup: BeautifulSoup) -> str:
    """Emit the clean inner HTML of the parsed body (no ``<html>``/``<body>``)."""
    body = soup.body
    if body is None:
        return ""
    return body.decode_contents()


class NarrareNormalizer:
    """Concrete :class:`ManuscriptNormalizer` (the Core Protocol).

    Callers depend on the Protocol (``ManuscriptNormalizer``) for type hints
    and inject/construct this implementation. The transformation is
    deterministic and idempotent: normalizing the normalizer's own output is a
    no-op (a fixed point).
    """

    async def normalize(
        self,
        raw_tiptap_html: str,
        metadata: ManuscriptMetadata,
    ) -> NormalizedManuscript:
        if not raw_tiptap_html.strip():
            # Empty/whitespace-only input → empty output (skip the parser).
            return self._result(semantic_html="", metadata=metadata)

        soup = _parse(raw_tiptap_html)
        strip_ai_annotation(soup)  # unwrap AI mark → keep inner text
        strip_ghost_text(soup)  # remove decoration residue (defensive)
        normalize_scene_breaks(soup)  # → canonical <hr class="scene-break">
        normalize_dialogue(soup)  # unwrap dialogue spans → keep quotes
        return self._result(semantic_html=_serialize(soup), metadata=metadata)

    @staticmethod
    def _result(*, semantic_html: str, metadata: ManuscriptMetadata) -> NormalizedManuscript:
        """Assemble the NormalizedManuscript, passing metadata scalars through."""
        return NormalizedManuscript(
            semantic_html=semantic_html,
            title=metadata.title,
            author=metadata.author,
            language=metadata.language,
            chapters=order_chapters(metadata.chapters),
            isbn=metadata.isbn,
            description=metadata.description,
        )
