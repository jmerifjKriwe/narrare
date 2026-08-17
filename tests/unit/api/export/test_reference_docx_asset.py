"""Asset tests for the committed DOCX reference document (C3 — design §6.1).

Pure stdlib (zipfile + ElementTree) — NO pandoc needed, so these run in
``test-unit`` everywhere. They pin the manuscript-format style properties
INSIDE the committed ``apps/api/narrare/export/pandoc/reference.docx`` so a
corrupted or accidentally replaced asset fails loudly at unit-test time —
before any golden-drift investigation. The full pipeline (pandoc rendering
with ``--reference-doc``) is covered by
``tests/golden/export/test_docx_golden.py``.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.mutation_inert

#: The committed asset, resolved repo-relatively from this test file:
#: tests/unit/api/export/ → apps/api/narrare/export/pandoc/reference.docx.
_REFERENCE_DOCX = (
    Path(__file__).resolve().parents[4]
    / "apps"
    / "api"
    / "narrare"
    / "export"
    / "pandoc"
    / "reference.docx"
)

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _styles_root() -> ET.Element:
    with zipfile.ZipFile(_REFERENCE_DOCX) as z:
        return ET.fromstring(z.read("word/styles.xml"))


def _style(styles: ET.Element, style_id: str) -> ET.Element:
    for style in styles.findall(f"{_W}style"):
        if style.get(f"{_W}styleId") == style_id:
            return style
    raise AssertionError(f"style {style_id!r} missing from reference.docx")


class TestWellFormedDocx:
    def test_zip_carries_the_docx_skeleton(self) -> None:
        with zipfile.ZipFile(_REFERENCE_DOCX) as z:
            names = set(z.namelist())
        assert "[Content_Types].xml" in names
        assert "word/document.xml" in names
        assert "word/styles.xml" in names


class TestManuscriptFormatStyles:
    """The four binding manuscript-format properties (design §6.1)."""

    def test_normal_is_times_12pt_with_1_5_line_spacing(self) -> None:
        normal = _style(_styles_root(), "Normal")
        r_pr = normal.find(f"{_W}rPr")
        assert r_pr is not None, "Normal lacks rPr"
        fonts = r_pr.find(f"{_W}rFonts")
        assert fonts is not None
        assert fonts.get(f"{_W}ascii") == "Times New Roman"
        assert fonts.get(f"{_W}hAnsi") == "Times New Roman"
        sz = r_pr.find(f"{_W}sz")
        assert sz is not None, "Normal lacks sz"
        assert sz.get(f"{_W}val") == "24"  # 12 pt = 24 half-points
        p_pr = normal.find(f"{_W}pPr")
        assert p_pr is not None, "Normal lacks pPr"
        spacing = p_pr.find(f"{_W}spacing")
        assert spacing is not None
        assert spacing.get(f"{_W}line") == "360"  # 1.5 line spacing
        assert spacing.get(f"{_W}lineRule") == "auto"

    def test_body_text_has_first_line_indent_and_no_extra_spacing(self) -> None:
        body = _style(_styles_root(), "BodyText")
        p_pr = body.find(f"{_W}pPr")
        assert p_pr is not None, "BodyText lacks pPr"
        ind = p_pr.find(f"{_W}ind")
        assert ind is not None
        assert ind.get(f"{_W}firstLine") == "720"  # 0.5 inch = 720 twips
        spacing = p_pr.find(f"{_W}spacing")
        assert spacing is not None
        assert spacing.get(f"{_W}before") == "0"
        assert spacing.get(f"{_W}after") == "0"

    def test_chapter_headings_are_centered_times_12pt(self) -> None:
        """Chapters are <h2> in the assembled HTML → the Heading2 style."""
        heading = _style(_styles_root(), "Heading2")
        p_pr = heading.find(f"{_W}pPr")
        assert p_pr is not None, "Heading2 lacks pPr"
        jc = p_pr.find(f"{_W}jc")
        assert jc is not None
        assert jc.get(f"{_W}val") == "center"
        r_pr = heading.find(f"{_W}rPr")
        assert r_pr is not None, "Heading2 lacks rPr"
        fonts = r_pr.find(f"{_W}rFonts")
        assert fonts is not None
        assert fonts.get(f"{_W}ascii") == "Times New Roman"
        sz = r_pr.find(f"{_W}sz")
        assert sz is not None, "Heading2 lacks sz"
        assert sz.get(f"{_W}val") == "24"
        color = r_pr.find(f"{_W}color")
        assert color is None, "Heading2 keeps pandoc's blue theme color — remove it"

    def test_title_is_times(self) -> None:
        title = _style(_styles_root(), "Title")
        r_pr = title.find(f"{_W}rPr")
        assert r_pr is not None, "Title lacks rPr"
        fonts = r_pr.find(f"{_W}rFonts")
        assert fonts is not None
        assert fonts.get(f"{_W}ascii") == "Times New Roman"
        sz = r_pr.find(f"{_W}sz")
        assert sz is not None, "Title lacks sz"
        assert sz.get(f"{_W}val") == "28"  # 14 pt title page
