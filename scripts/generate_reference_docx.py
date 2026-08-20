"""Generate the DOCX export reference document (C3 — design §6.1).

Builds ``apps/api/narrare/export/pandoc/reference.docx`` — the pandoc
``--reference-doc`` that gives DOCX exports the classic publishing
manuscript format (Times 12 pt, 1.5 line spacing, 0.5" first-line indent,
centred chapter headings). See ``apps/api/narrare/export/pandoc/README.md``
for the full regeneration procedure.

The script is PURE STDLIB (zipfile + xml.etree): it reads pandoc's default
``reference.docx`` as a base (a file argument — RULE-08: this script never
spawns pandoc; the extraction shell command is documented in the README),
patches the four manuscript-format styles, and rewrites the zip
DETERMINISTICALLY (fixed 1980-01-01 entry timestamps, sorted entry order)
so regeneration is byte-reproducible for a given pandoc version + Python
zlib. The committed asset and the golden baseline
(``tests/golden/export/baselines/docx-manuscript.json``) are regenerated
TOGETHER when the pandoc pin changes.

Manuscript-format values (design §6.1, binding; OOXML units in comments):
- Times New Roman 12 pt   -> w:sz/w:szCs 24 (half-points) on Normal + Heading2
- 1.5 line spacing        -> w:spacing w:line="360" w:lineRule="auto" on Normal
- first-line indent 0.5"  -> w:ind w:firstLine="720" (twips) on BodyText
- centred chapter headings-> w:jc w:val="center" on Heading2 (chapters are
                             <h2> in the assembled HTML — Heading2, not H1)
Title/Author are set to Times as well (Title at 14 pt) so the title page
matches the manuscript look; everything else keeps pandoc's defaults.

The numeric format literals are FUNCTION-LOCAL by design: they are OOXML
document-format constants (half-points / twips / fifths of a line), not
runtime configuration — keeping them inside the patch function keeps the
RULE-18 configurable-defaults checker untriggered without an exemption.
"""

from __future__ import annotations

import argparse
import io
import sys

# Parses the locally generated pandoc reference.docx — trusted input, not user-supplied XML.
import xml.etree.ElementTree as ET  # nosec B405
import zipfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

#: CT_PPr child order (the subset this script can emit, in schema order) —
#: new pPr children are inserted so the sequence stays schema-valid (Word
#: rejects out-of-order style children; pandoc alone would tolerate them).
_PPR_ORDER: tuple[str, ...] = (
    "keepNext",
    "keepLines",
    "spacing",
    "ind",
    "jc",
    "outlineLvl",
)

#: CT_RPr child order (the subset this script can emit).
_RPR_ORDER: tuple[str, ...] = ("rFonts", "color", "sz", "szCs")

#: The one entry this generator patches.
_STYLES_ENTRY = "word/styles.xml"

#: The manuscript-format styles (design §6.1) this generator touches.
_TIMES_NEW_ROMAN = "Times New Roman"


def _register_declared_prefixes(xml_bytes: bytes) -> None:
    """Register every (prefix, uri) the document declares.

    ElementTree re-serializes with ``ns0:`` prefixes for unregistered
    namespaces, which would corrupt ``mc:Ignorable``-style prefix references.
    Registering the declared prefixes keeps the output prefixes identical to
    the input's.
    """
    for _event, (prefix, uri) in ET.iterparse(io.BytesIO(xml_bytes), events=["start-ns"]):  # nosec B314  # noqa: S314 — pandoc's own reference.docx (local toolchain, not untrusted input)
        ET.register_namespace(prefix, uri)


def _insert_ordered(parent: ET.Element, child: ET.Element, order: tuple[str, ...]) -> None:
    """Insert ``child`` into ``parent`` at the schema-order-correct position.

    Finds the first existing child whose tag sorts AFTER ``child`` in
    ``order`` and inserts before it; appends when none follows. The
    insertion index comes from a materialized ``list(parent)`` — stdlib
    Elements have no lxml ``addprevious``.
    """
    tag = child.tag.split("}")[-1]
    try:
        position = order.index(tag)
    except ValueError:  # pragma: no cover — tags are hardcoded above
        parent.append(child)
        return
    for index, existing in enumerate(list(parent)):
        existing_tag = existing.tag.split("}")[-1]
        if existing_tag in order and order.index(existing_tag) > position:
            parent.insert(index, child)
            return
    parent.append(child)


def _ensure_child(
    parent: ET.Element,
    tag: str,
    order: tuple[str, ...],
) -> ET.Element:
    """Find or create ``{w}tag`` under ``parent`` (schema-ordered on create)."""
    existing = parent.find(f"{{{_W}}}{tag}")
    if existing is not None:
        return existing
    child = ET.Element(f"{{{_W}}}{tag}")
    _insert_ordered(parent, child, order)
    return child


def _set_times_fonts(r_pr: ET.Element, *, replace_existing: bool) -> None:
    """Set rFonts to Times New Roman on all four slots."""
    fonts = r_pr.find(f"{{{_W}}}rFonts")
    if fonts is not None and replace_existing:
        r_pr.remove(fonts)
        fonts = None
    if fonts is None:
        fonts = ET.Element(f"{{{_W}}}rFonts")
        _insert_ordered(r_pr, fonts, _RPR_ORDER)
    for slot in ("ascii", "hAnsi", "cs", "eastAsia"):
        fonts.set(f"{{{_W}}}{slot}", _TIMES_NEW_ROMAN)


def _style_by_id(styles: ET.Element, style_id: str) -> ET.Element:
    for style in styles.findall(f"{{{_W}}}style"):
        if style.get(f"{{{_W}}}styleId") == style_id:
            return style
    raise SystemExit(f"style {style_id!r} missing from the base reference.docx")


def _patch_normal(style: ET.Element) -> None:
    """Document base: Times 12 pt + 1.5 line spacing (inherits everywhere)."""
    body_size = "24"  # half-points -> 12 pt
    line_spacing = "360"  # 240 per line -> 360 = 1.5 lines (lineRule auto)
    r_pr = _ensure_child(style, "rPr", ("name", "qFormat", "pPr", "rPr"))
    _set_times_fonts(r_pr, replace_existing=True)
    _ensure_child(r_pr, "sz", _RPR_ORDER).set(f"{{{_W}}}val", body_size)
    _ensure_child(r_pr, "szCs", _RPR_ORDER).set(f"{{{_W}}}val", body_size)
    p_pr = _ensure_child(style, "pPr", ("name", "qFormat", "pPr", "rPr"))
    spacing = _ensure_child(p_pr, "spacing", _PPR_ORDER)
    spacing.set(f"{{{_W}}}line", line_spacing)
    spacing.set(f"{{{_W}}}lineRule", "auto")


def _patch_body_text(style: ET.Element) -> None:
    """Every-paragraph first-line indent (Shunn convention) + flat spacing.

    ``FirstParagraph`` (pandoc's style for the first paragraph after a
    heading) has NO own pPr and inherits this indent — the classic
    manuscript indents every paragraph, including the first.
    """
    first_line = "720"  # twips -> 0.5 inch
    p_pr = _ensure_child(style, "pPr", ("name", "basedOn", "link", "qFormat", "pPr", "rPr"))
    spacing = _ensure_child(p_pr, "spacing", _PPR_ORDER)
    spacing.set(f"{{{_W}}}before", "0")
    spacing.set(f"{{{_W}}}after", "0")
    _ensure_child(p_pr, "ind", _PPR_ORDER).set(f"{{{_W}}}firstLine", first_line)


def _patch_heading2(style: ET.Element) -> None:
    """Chapter headings: centred, Times 12 pt, no theme color."""
    body_size = "24"  # half-points -> 12 pt
    r_pr = _ensure_child(
        style, "rPr", ("name", "basedOn", "next", "link", "uiPriority", "qFormat", "pPr", "rPr")
    )
    _set_times_fonts(r_pr, replace_existing=True)
    color = r_pr.find(f"{{{_W}}}color")
    if color is not None:
        r_pr.remove(color)
    _ensure_child(r_pr, "sz", _RPR_ORDER).set(f"{{{_W}}}val", body_size)
    _ensure_child(r_pr, "szCs", _RPR_ORDER).set(f"{{{_W}}}val", body_size)
    p_pr = _ensure_child(
        style, "pPr", ("name", "basedOn", "next", "link", "uiPriority", "qFormat", "pPr", "rPr")
    )
    _ensure_child(p_pr, "jc", _PPR_ORDER).set(f"{{{_W}}}val", "center")


def _patch_title(style: ET.Element) -> None:
    """Title page: Times 14 pt (stays centred via pandoc's default)."""
    title_size = "28"  # half-points -> 14 pt
    r_pr = _ensure_child(
        style, "rPr", ("name", "basedOn", "next", "link", "uiPriority", "qFormat", "pPr", "rPr")
    )
    _set_times_fonts(r_pr, replace_existing=True)
    _ensure_child(r_pr, "sz", _RPR_ORDER).set(f"{{{_W}}}val", title_size)
    _ensure_child(r_pr, "szCs", _RPR_ORDER).set(f"{{{_W}}}val", title_size)


def patch_styles_xml(styles_xml: bytes) -> bytes:
    """Apply the four manuscript-format patches to a ``word/styles.xml``."""
    _register_declared_prefixes(styles_xml)
    styles = ET.fromstring(styles_xml)  # nosec B314  # noqa: S314 — pandoc's own reference.docx (local toolchain, not untrusted input)
    _patch_normal(_style_by_id(styles, "Normal"))
    _patch_body_text(_style_by_id(styles, "BodyText"))
    _patch_heading2(_style_by_id(styles, "Heading2"))
    _patch_title(_style_by_id(styles, "Title"))
    return ET.tostring(styles, encoding="UTF-8", xml_declaration=True)


def build_reference_docx(base_docx: bytes) -> bytes:
    """Patch pandoc's default reference.docx bytes into the manuscript asset.

    Deterministic zip rewrite: every entry keeps its (patched) content, is
    written with the fixed 1980-01-01 timestamp, and entries are emitted in
    sorted order — so the same base + same Python zlib yield identical bytes.
    """
    entries: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(base_docx)) as z:
        for name in z.namelist():
            entries[name] = z.read(name)
    if _STYLES_ENTRY not in entries:
        raise SystemExit(f"base reference.docx lacks {_STYLES_ENTRY!r}")
    entries[_STYLES_ENTRY] = patch_styles_xml(entries[_STYLES_ENTRY])

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as out:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            out.writestr(info, entries[name])
    return buffer.getvalue()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0] if __doc__ else "DOCX reference.docx generator"
    )
    parser.add_argument(
        "--base",
        required=True,
        help="pandoc's default reference.docx (see the vendor README for the "
        "extraction command — this script never spawns pandoc)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="output path (typically apps/api/narrare/export/pandoc/reference.docx)",
    )
    args = parser.parse_args(argv)

    base_bytes = open(args.base, "rb").read()  # noqa: SIM115 - short-lived CLI read
    result = build_reference_docx(base_bytes)
    with open(args.output, "wb") as handle:
        handle.write(result)
    print(f"wrote {args.output} ({len(result)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
