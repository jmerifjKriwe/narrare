# C3 — DOCX Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship IO-001's fourth export format — DOCX in the classic publishing manuscript format (Times 12 pt, 1.5 line spacing, 0.5″ first-line indent, centred chapter headings) via pandoc `--reference-doc`, verified by a golden test on the unzipped `word/document.xml` (program item C3 of the Post-Export Follow-ups program, design §6).

**Architecture:** One new RULE-08 renderer adapter — `PandocDocxRenderer` (`apps/api/narrare/export/renderers/pandoc_docx.py`) at the exact seam of its three siblings (Typst PDF / pandoc EPUB / pandoc MD): same `ManuscriptRenderer` structural contract, same `run_pandoc` spawn helper, same cached `shutil.which` availability probe, same graceful binary-absence degradation. The manuscript format lives in ONE committed `reference.docx` in a new pandoc vendor area (`apps/api/narrare/export/pandoc/`, mirroring the `typst/` vendor area) — a binary asset produced by a deterministic, pure-stdlib generator script (`scripts/generate_reference_docx.py`) that patches pandoc's default reference styles and re-zips with fixed timestamps. **No `DocxOptions` model, no Alembic migration, no service/router change** — `ExportFormat` gains a `DOCX` member, two registration dicts gain one entry each, and the frontend gains one format card + 2 i18n keys × 3 locales. Empirically verified against the pinned pandoc 3.10.1 (all probes run 2026-08-17 in this repo): with a fixed `--reference-doc`, the output's `word/document.xml` entry is **byte-deterministic across runs** — the only nondeterministic zip entry is `docProps/core.xml` (created/modified timestamps), which the golden test does not compare. The golden test therefore extracts `word/document.xml` and compares its sha256 against a committed baseline with **no normalization beyond extraction** (the design's rsid/date concern is empirically moot: pandoc emits no rsids, and dates live only in `docProps/core.xml`).

**Tech Stack:** Python 3.14 (stdlib `zipfile` + `xml.etree` only — no new dependency), pandoc 3.10.1 (pinned by `scripts/install_export_toolchain.sh`), pytest (`golden_pages` marker), TypeScript/React (lucide-react `FileType` icon), next-intl (en/de/fr).

**Binding spec:** `docs/superpowers/specs/2026-08-14-post-export-followups-design.md` §6 (C3 — binding decisions: **manuscript format via `--reference-doc`**, not pandoc's plain default, not a configurable template system (§11 YAGNI); **one maintained `reference.docx`** (Times 12 pt, 1.5 line spacing, first-line indent, centred chapter headings — "the classic publishing manuscript format = the use case that justifies DOCX at all") **stored in the export vendor area**; **new `PandocDocxRenderer`** (RULE-08 renderer adapter, same seam as PDF/EPUB/MD); **format option in the existing export UI + i18n (en/de/fr)**; **verification = golden test on the unzipped `document.xml`**, analogous to the Golden-Pages procedure; **IO-001 feature spec gains the DOCX format — no new ADR**, ADR-081's engine decision applies unchanged). §12 C3 gates: **golden `document.xml` test; i18n keys en/de/fr; RULE-08 checker green**. This plan implements exactly that — nothing more, nothing less.

## Global Constraints

- **Slice semantics (RULE-20):** Tasks 1–7 are sequentially executable sub-slices of ONE coherent slice. The format becomes user-selectable when Task 6 lands; the golden gate is Task 4. Tasks 1–3 land typed-but-inert plumbing (mirroring the C5/C1 seam-first ordering); each sub-task is independently testable and commits cleanly.
- **Package sizing:** ≤3 production files and ≤250 new LOC per delegated sub-task (test files, baselines, corpus fixtures, and docs do NOT count toward the file cap; i18n message files COUNT as production files — Task 5 is exactly the 3 locale files).
- **File-size limits** (`pyproject.toml [tool.narrare.architecture.file_size_limits]`; the pre-commit `architecture-constraints` hook BLOCKS the commit on violation). Verified at plan time: `export/options.py` **106/400**, `export/dependencies.py` **48/400**, `export/tasks.py` **283/400** (all filename-categorized → `default`; the checker's categories are `router*/150`, `*service.py|service.py/300`, `repository.py/250`, `contracts.py/200`, `models.py/200`, `*_schemas.py|schemas.py/200`, `agent.py/200`, `gateway.py/300`, `composer.py/250`, everything else `default/400`). New files: `renderers/pandoc_docx.py` ~180/400, `scripts/generate_reference_docx.py` ~200/400. All comfortably under.
- **RULE-08 (binding gate, §12):** the `pandoc` binary is spawned ONLY via `run_pandoc` in `pandoc_base.py`. The new `pandoc_docx.py` calls that helper — it contains NO subprocess call, so the checker passes by construction; it is nonetheless ADDED to `export_binary_allowed_modules` in `pyproject.toml` for convention consistency with its four listed siblings (Task 2). `scripts/generate_reference_docx.py` **never spawns pandoc** — the pandoc-default base document is a `--base` file argument; the documented extraction shell command lives in the vendor README (docs, outside checker scope). Tests that spawn pandoc (`tests/golden/export/test_docx_golden.py`) are exempt by location (the checker's documented `tests/` exemption — the EPUBCheck rationale).
- **RULE-03 (contract-first):** NO new contract file is needed and `export/contracts.py` stays **byte-identical** — `PandocDocxRenderer` structurally satisfies the EXISTING `ManuscriptRenderer` Protocol (the sibling convention: no explicit inheritance). `ExportFormat` gains one enum member in `options.py` (an options-model extension, not a contract change).
- **No `DocxOptions` model (design-interpretation ruling 1):** v1 has ZERO DOCX-specific request options. `--reference-doc` is unconditional (a template toggle would reintroduce the silent-fallback failure mode the D7 no-silent-fallback principle exists to prevent; the configurable-template system is §11-YAGNI). `isbn`/`description` stay EPUB-only (the `EpubOptions` docstring's D7-precedent rule: "PDF/MD renderers ignore both fields" — DOCX joins them). `ExportOptions`, `ExportRequest`, the TS `ExportOptions` interface, and `useExportSettings.defaultExportOptions` are therefore all **unchanged**.
- **Golden normalization ruling (design-interpretation ruling 2 — evidence-based):** the design prescribes the golden test "on the unzipped `document.xml`" and anticipates needing normalization ("docx XML may embed rsid/date metadata"). Empirically verified against pandoc 3.10.1 on this machine (2026-08-17): rendering the same input twice with the same `reference.docx` produces **byte-identical `word/document.xml`** (and byte-identical `styles.xml`, `numbering.xml`, …); the ONLY entry that differs is `docProps/core.xml` (`dcterms:created`/`dcterms:modified` wall-clock stamps). Pandoc emits **no `w:rsid` attributes and no dates in `document.xml`**. Ruling: normalization = **extract the `word/document.xml` zip entry and compare its sha256 — strip nothing**. Zip-container timestamps live in the zip directory, not in the entry bytes, and never affect the comparison.
- **Styles verification ruling (design-interpretation ruling 3):** `document.xml` carries content + style *references* (`w:pStyle w:val="BodyText"`); the manuscript format itself lives in `word/styles.xml`. A `document.xml`-only golden would leave C3's headline property (Times/12 pt/1.5/indent/centred headings) UNVERIFIED. Ruling: the golden file keeps the design-mandated `document.xml` baseline AND adds structural assertions on the OUTPUT `word/styles.xml` (the four binding style properties) + content assertions on `document.xml`. The committed asset is additionally pinned by a no-pandoc unit test (Task 1) and a generator-reproducibility check (Task 4).
- **No `--toc` ruling (design-interpretation ruling 4):** EPUB passes `--toc` because e-books navigate; a submission manuscript conventionally carries NO table of contents. DOCX omits the flag. Recorded here so no implementer "harmonizes" it later.
- **Heading-level ruling (design-interpretation ruling 5):** chapters are `<h2>` in the assembled manuscript HTML (the `tasks.assemble_raw_html` seam decision; the book title is metadata → pandoc `Title`/`Author` styles, never a body `<h1>`). The manuscript format therefore patches the **`Heading2`** style (centred, Times, 12 pt) — NOT `Heading1`. No `--shift-heading-level-by` (Word heading semantics come from the style, not the level number).
- **First-line-indent scope ruling (design-interpretation ruling 6):** the indent lives on `BodyText` and is INHERITED by `FirstParagraph` (pandoc's style for the first paragraph after a heading — it has no own `pPr`). The classic manuscript convention (Shunn) indents EVERY paragraph including the first after a heading — inheritance gives exactly that, with zero extra patching. No exemption fight.
- **`reference.docx` bundling ruling (committed binary + reproducible generator):** the asset is COMMITTED as a binary (the `.otf` font precedent — binaries ship in-tree, no gitattributes needed) at `apps/api/narrare/export/pandoc/reference.docx`, resolved by the renderer PACKAGE-RELATIVELY (`Path(__file__)…parent.parent / "pandoc" / "reference.docx"`, the `_FONTS_DIR` pattern — never cwd). The generator (`scripts/generate_reference_docx.py`) is pure stdlib, produces byte-reproducible output for a given pandoc version (fixed 1980-01-01 zip timestamps + sorted entries), and is the documented regeneration path when the pandoc pin changes. A missing asset raises `ExportRenderError` (RULE-11 — never a silent fallback to pandoc's default styles).
- **RULE-18 (configurable defaults):** the OOXML format literals (half-point sizes 24/28, twips 720, line-spacing 360, the fixed zip epoch) are FUNCTION-LOCAL in the generator and as call arguments/comparisons in tests — the checker flags only module-/class-level numeric constants > 5, so NO `ignored_modules` entry is needed. The renderer itself contains no numeric literals > 5.
- **Zero-regression guarantee:** `contracts.py`, `schemas.py`, `service.py`, `router.py`, `repository.py`, `registry.py`, `errors.py`, and the three existing renderers stay **byte-identical**. The only production changes to existing files are: `options.py` (+2 enum lines), `dependencies.py` (+3), `tasks.py` (+3), `pyproject.toml` (+1 list entry), `types/export.ts` (1 line), `ExportFormatSelector.tsx` (+7), 3 i18n files (+2 keys each).
- **Regression-first TDD:** every new test is written and run (expected FAIL) before the implementation step that satisfies it.
- **Commits:** implementer edits + runs gates, then reports; **Platform specialist commits with the verbatim message in each task's commit step**. No `--no-verify`/`-n`, no push. On hook failure: STOP and report. The pre-commit **openapi-regenerate** hook will auto-stage `docs/reference/openapi.json` when Task 2 adds the `DOCX` enum member (the format appears in the `/export/formats` response schema) — let it ride along in the commit; NEVER hand-edit `openapi.json`.
- **Language / locating:** English everywhere (code, comments, tests, commit messages; i18n message FILES excepted — en/de/fr values). Locate edit targets by semantic name/text (the code blocks below quote the current text) — never by line number. Where a task says "rg sweep", run the given `rg` command and mechanically update every match.
- **Test commands:** backend focused runs via `just test-file <path>`; per-task backend gate `just test-unit` (`just test-lowmem` on <12 GB RAM machines). Golden tests: `just test-file tests/golden/export/test_docx_golden.py` (needs pandoc — `bash scripts/install_export_toolchain.sh` if absent); baseline regeneration via the `--golden-update` command in Task 4. Frontend: `cd packages/web && pnpm test <path-filter>` (scoped), `pnpm type-check`, `pnpm lint:check`; frontend gate `just test-frontend`. Architecture checker: `just check-architecture`. Slice-final gates (Task 7): `just check-architecture`, `just typecheck`, `just lint-check`, `just test-unit`, `just test-integration`, frontend `pnpm type-check` + `pnpm lint:check`, `just test-frontend`.

---

### Task 1: Pandoc vendor area — `reference.docx` + deterministic generator

**Files:**
- Create: `scripts/generate_reference_docx.py`
- Create: `apps/api/narrare/export/pandoc/reference.docx` (generated binary asset)
- Create: `apps/api/narrare/export/pandoc/README.md` (docs — does not count toward the file cap)
- Test: `tests/unit/api/export/test_reference_docx_asset.py` (new)

**Interfaces:**
- Consumes: pandoc's default `reference.docx` (extracted by a shell command the implementer runs once — see Step 3; the script itself never spawns pandoc, RULE-08).
- Produces (verbatim for Tasks 2 + 4): the committed binary `apps/api/narrare/export/pandoc/reference.docx`, whose `word/styles.xml` defines — `Normal`: `rFonts` Times New Roman (all four slots) + `sz`/`szCs` 24 + `spacing` `line="360" lineRule="auto"`; `BodyText`: `spacing` `before="0" after="0"` + `ind` `firstLine="720"`; `Heading2`: `jc` `val="center"` + Times `rFonts` + `sz`/`szCs` 24 (theme fonts + color removed); `Title`: Times `rFonts` + `sz`/`szCs` 28. Also `scripts.generate_reference_docx.build_reference_docx(base_docx: bytes) -> bytes` (imported by Task 4's reproducibility test).

- [ ] **Step 1: Write the failing asset tests**

Create `tests/unit/api/export/test_reference_docx_asset.py`:

```python
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
        assert r_pr.find(f"{_W}sz").get(f"{_W}val") == "24"  # 12 pt = 24 half-points
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
        assert r_pr.find(f"{_W}sz").get(f"{_W}val") == "24"
        color = r_pr.find(f"{_W}color")
        assert color is None, "Heading2 keeps pandoc's blue theme color — remove it"

    def test_title_is_times(self) -> None:
        title = _style(_styles_root(), "Title")
        r_pr = title.find(f"{_W}rPr")
        assert r_pr is not None, "Title lacks rPr"
        fonts = r_pr.find(f"{_W}rFonts")
        assert fonts is not None
        assert fonts.get(f"{_W}ascii") == "Times New Roman"
        assert r_pr.find(f"{_W}sz").get(f"{_W}val") == "28"  # 14 pt title page
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test-file tests/unit/api/export/test_reference_docx_asset.py`
Expected: FAIL — `FileNotFoundError` (or zipfile `BadZipFile`) for `apps/api/narrare/export/pandoc/reference.docx`: the asset does not exist yet. This failing run satisfies the regression-first rule.

- [ ] **Step 3: Create the generator script**

Create `scripts/generate_reference_docx.py`:

```python
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
import zipfile
import xml.etree.ElementTree as ET
from collections.abc import Sequence

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

#: CT_PPr child order (the subset this script can emit, in schema order) —
#: new pPr children are inserted so the sequence stays schema-valid (Word
#: rejects out-of-order style children; pandoc alone would tolerate them).
_PPR_ORDER: tuple[str, ...] = (
    "keepNext", "keepLines", "spacing", "ind", "jc", "outlineLvl",
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
    for _event, (prefix, uri) in ET.iterparse(io.BytesIO(xml_bytes), events=["start-ns"]):
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
    r_pr = _ensure_child(style, "rPr", ("name", "basedOn", "next", "link", "uiPriority", "qFormat", "pPr", "rPr"))
    _set_times_fonts(r_pr, replace_existing=True)
    color = r_pr.find(f"{{{_W}}}color")
    if color is not None:
        r_pr.remove(color)
    _ensure_child(r_pr, "sz", _RPR_ORDER).set(f"{{{_W}}}val", body_size)
    _ensure_child(r_pr, "szCs", _RPR_ORDER).set(f"{{{_W}}}val", body_size)
    p_pr = _ensure_child(style, "pPr", ("name", "basedOn", "next", "link", "uiPriority", "qFormat", "pPr", "rPr"))
    _ensure_child(p_pr, "jc", _PPR_ORDER).set(f"{{{_W}}}val", "center")


def _patch_title(style: ET.Element) -> None:
    """Title page: Times 14 pt (stays centred via pandoc's default)."""
    title_size = "28"  # half-points -> 14 pt
    r_pr = _ensure_child(style, "rPr", ("name", "basedOn", "next", "link", "uiPriority", "qFormat", "pPr", "rPr"))
    _set_times_fonts(r_pr, replace_existing=True)
    _ensure_child(r_pr, "sz", _RPR_ORDER).set(f"{{{_W}}}val", title_size)
    _ensure_child(r_pr, "szCs", _RPR_ORDER).set(f"{{{_W}}}val", title_size)


def patch_styles_xml(styles_xml: bytes) -> bytes:
    """Apply the four manuscript-format patches to a ``word/styles.xml``."""
    _register_declared_prefixes(styles_xml)
    styles = ET.fromstring(styles_xml)
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
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
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
```

- [ ] **Step 4: Generate the committed asset**

The implementer runs (pandoc is on `$PATH` — `bash scripts/install_export_toolchain.sh` if not):

```bash
mkdir -p apps/api/narrare/export/pandoc
pandoc --print-default-data-file reference.docx > /tmp/reference-base.docx
python scripts/generate_reference_docx.py \
  --base /tmp/reference-base.docx \
  --output apps/api/narrare/export/pandoc/reference.docx
```

Then verify reproducibility (run the two commands again into a second output and compare):

```bash
python scripts/generate_reference_docx.py --base /tmp/reference-base.docx --output /tmp/reference-check.docx
cmp apps/api/narrare/export/pandoc/reference.docx /tmp/reference-check.docx && echo REPRODUCIBLE
```

Expected: `REPRODUCIBLE` (byte-identical — the deterministic-zip property Task 4 pins).

- [ ] **Step 5: Run the asset tests to verify they pass**

Run: `just test-file tests/unit/api/export/test_reference_docx_asset.py`
Expected: PASS — 5 tests.

- [ ] **Step 6: Run the architecture checker**

Run: `just check-architecture`
Expected: PASS (new script file under the 400-line default limit; function-local numeric literals do not trigger RULE-18; no subprocess call in the script → RULE-08 untouched).

- [ ] **Step 7: Create the vendor README**

Create `apps/api/narrare/export/pandoc/README.md`:

```markdown
# pandoc vendor area — DOCX manuscript format (C3)

Holds the committed `reference.docx` that `PandocDocxRenderer`
(`apps/api/narrare/export/renderers/pandoc_docx.py`) passes to pandoc via
`--reference-doc` — unconditionally, with no template toggle (design
§6.1 + §11; the D7 no-silent-fallback principle applied to document
styles). The pandoc/typst vendor split mirrors `export/typst/` (engine
assets live under an engine-named directory).

## The manuscript format (design §6.1, binding)

| Property | Style | OOXML |
|---|---|---|
| Times New Roman 12 pt | `Normal` (+ `Heading2`) | `w:sz 24` half-points |
| 1.5 line spacing | `Normal` | `w:spacing w:line="360" w:lineRule="auto"` |
| 0.5″ first-line indent, every paragraph | `BodyText` (inherited by `FirstParagraph`) | `w:ind w:firstLine="720"` twips |
| Centred chapter headings | `Heading2` (chapters are `<h2>` in the assembled HTML) | `w:jc w:val="center"` |
| Title page in Times 14 pt | `Title` | `w:sz 28` |

## Provenance + regeneration

The asset is a deterministic patch of **pandoc's own default
`reference.docx`** (pandoc 3.10.1 — the pinned version from
`scripts/install_export_toolchain.sh`), produced by
`scripts/generate_reference_docx.py` (pure stdlib; fixed zip timestamps +
sorted entries → byte-reproducible for a given pandoc version).

Regenerate when the pandoc pin changes (or a format property is
deliberately changed):

```sh
pandoc --print-default-data-file reference.docx > /tmp/reference-base.docx
python scripts/generate_reference_docx.py \
  --base /tmp/reference-base.docx \
  --output apps/api/narrare/export/pandoc/reference.docx
```

Then regenerate the golden baseline (the two drift together):

```sh
uv run pytest tests/golden/export/test_docx_golden.py -v -m golden_pages \
  --golden-update -p no:xdist
```

Review both diffs, then commit. The generator never spawns pandoc
(RULE-08); the extraction command above is a shell command, not code.
The committed asset is pinned by
`tests/unit/api/export/test_reference_docx_asset.py` (style properties, no
pandoc needed) and by the reproducibility check in
`tests/golden/export/test_docx_golden.py` (asset == generator(pandoc
default) for the installed pandoc).
```

- [ ] **Step 8: Commit (via Platform, verbatim)**

```bash
git add scripts/generate_reference_docx.py \
        apps/api/narrare/export/pandoc/reference.docx \
        apps/api/narrare/export/pandoc/README.md \
        tests/unit/api/export/test_reference_docx_asset.py
```

Commit message:

```
feat(export): add pandoc vendor area — manuscript-format reference.docx

C3 (design §6.1): the committed --reference-doc asset that gives DOCX
exports the classic publishing manuscript format — Times 12 pt, 1.5 line
spacing, 0.5" first-line indent (every paragraph, inherited by
FirstParagraph), centred chapter headings (Heading2 — chapters are <h2> in
the assembled HTML), Times 14 pt title page.

- scripts/generate_reference_docx.py: pure-stdlib deterministic generator
  (patch pandoc's default reference.docx styles; fixed 1980-01-01 zip
  timestamps + sorted entries → byte-reproducible). RULE-08 clean: the
  script never spawns pandoc — the base document is a --base file argument
  (the extraction shell command is documented in the vendor README).
  Numeric format literals are function-local OOXML constants (RULE-18).
- apps/api/narrare/export/pandoc/: new pandoc vendor area (mirrors
  export/typst/) holding reference.docx + the provenance/regeneration
  README.
- Asset tests pin the four binding style properties INSIDE the committed
  binary (zipfile + ElementTree, no pandoc — test-unit tier).

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §6 (C3)
```

---

### Task 2: `ExportFormat.DOCX` + `PandocDocxRenderer`

**Files:**
- Modify: `apps/api/narrare/export/options.py` (106/400 lines — headroom verified)
- Create: `apps/api/narrare/export/renderers/pandoc_docx.py`
- Modify: `pyproject.toml` (`export_binary_allowed_modules` list)
- Test: `tests/unit/api/export/test_pandoc_docx.py` (new)

**Interfaces:**
- Consumes: `run_pandoc` / `DEFAULT_TIMEOUT_SECONDS` (`narrare.export.renderers.pandoc_base`); `Artifact` / `ExportFormat` / `ExportOptions` (`narrare.export.contracts`); `ExportRenderError` (`narrare.export.errors`); `NormalizedManuscript` (`narrare_core.export.contracts`); the committed `reference.docx` (Task 1).
- Produces (verbatim for Tasks 3–4): `ExportFormat.DOCX == "docx"` (the StrEnum's fourth member); `PandocDocxRenderer` with `format` → `ExportFormat.DOCX`, `is_available() -> bool`, and `async render(manuscript: NormalizedManuscript, options: ExportOptions) -> Artifact` (`media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"`, `suggested_filename="<slug>.docx"`); module constant `_REFERENCE_DOC_PATH: Path` (redirectable in tests — the `_FONTS_DIR` pattern).

- [ ] **Step 1: Write the failing unit tests**

Create `tests/unit/api/export/test_pandoc_docx.py`:

```python
"""Unit + real-pandoc tests for the pandoc DOCX renderer (C3 — design §6).

Two layers (mirrors test_pandoc_md.py):

1. **Pure unit tests** (always run, no binary): availability probe, slug
   derivation, missing-reference fast-fail (no silent fallback to pandoc's
   default styles).
2. **Real-pandoc tests** (``_REQUIRES_PANDOC`` skip guard): render → a
   well-formed docx zip whose document.xml carries the chapters as
   Heading2 paragraphs + the title, and whose styles.xml carries the
   manuscript format from the reference doc.

The full golden verification (byte-determinism + committed baseline) lives
in ``tests/golden/export/test_docx_golden.py`` (Task 4).
"""

from __future__ import annotations

import shutil
import zipfile
from uuid import UUID

import pytest

from narrare.export.errors import ExportRenderError
from narrare.export.options import ExportFormat, ExportOptions
from narrare.export.renderers.pandoc_docx import PandocDocxRenderer, _slugify
from narrare_core.export.contracts import ChapterMeta, Language, NormalizedManuscript

_REQUIRES_PANDOC = pytest.mark.skipif(
    shutil.which("pandoc") is None,
    reason="pandoc not installed (install via scripts/install_export_toolchain.sh)",
)

#: Deterministic chapter ids (the golden file shares this practice — uuid4
#: entropy must never leak into anything a test asserts on).
_CHAPTER_ONE_ID = UUID("00000000-0000-0000-0000-0000000000d1")
_CHAPTER_TWO_ID = UUID("00000000-0000-0000-0000-0000000000d2")


def _normalized(
    semantic_html: str = (
        "<h2>Chapter One</h2>\n<p>Body text here.</p>\n"
        "<h2>Chapter Two</h2>\n<p>More prose follows.</p>"
    ),
    *,
    title: str = "Test Novel",
    author: str = "Test Author",
    language: Language = Language.EN,
) -> NormalizedManuscript:
    return NormalizedManuscript(
        semantic_html=semantic_html,
        title=title,
        author=author,
        language=language,
        chapters=[
            ChapterMeta(chapter_id=_CHAPTER_ONE_ID, title="C1", position=0, volume_id=None),
            ChapterMeta(chapter_id=_CHAPTER_TWO_ID, title="C2", position=1, volume_id=None),
        ],
    )


# ── Pure unit tests (always run) ────────────────────────────────────────────


class TestFormatAndAvailability:
    def test_format_is_docx(self) -> None:
        assert PandocDocxRenderer().format is ExportFormat.DOCX

    def test_export_format_enum_has_docx_member(self) -> None:
        assert ExportFormat("docx") is ExportFormat.DOCX
        assert ExportFormat.DOCX.value == "docx"

    def test_is_available_true_when_pandoc_on_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(shutil, "which", lambda _cmd: "/usr/bin/pandoc")
        assert PandocDocxRenderer().is_available() is True

    def test_is_available_false_when_pandoc_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(shutil, "which", lambda _cmd: None)
        # Fresh instance — _available cache must start unset.
        assert PandocDocxRenderer().is_available() is False

    def test_availability_is_cached(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = 0

        def which(_cmd: str) -> str | None:
            nonlocal calls
            calls += 1
            return "/usr/bin/pandoc"

        monkeypatch.setattr(shutil, "which", which)
        renderer = PandocDocxRenderer()
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
        ],
    )
    def test_slug(self, title: str, expected: str) -> None:
        assert _slugify(title) == expected


class TestMissingReferenceFastFail:
    def test_missing_reference_raises_export_render_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        from narrare.export.renderers import pandoc_docx

        monkeypatch.setattr(pandoc_docx, "_REFERENCE_DOC_PATH", tmp_path / "missing.docx")
        with pytest.raises(ExportRenderError, match="reference document missing"):
            import asyncio

            asyncio.run(
                PandocDocxRenderer().render(
                    _normalized(), ExportOptions(format=ExportFormat.DOCX)
                )
            )


# ── Real-pandoc tests ───────────────────────────────────────────────────────


@_REQUIRES_PANDOC
class TestRealPandocRender:
    @pytest.mark.asyncio
    async def test_render_produces_docx_with_chapters_and_title(self) -> None:
        artifact = await PandocDocxRenderer().render(
            _normalized(), ExportOptions(format=ExportFormat.DOCX)
        )
        try:
            assert artifact.format is ExportFormat.DOCX
            assert artifact.media_type == (
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            )
            assert artifact.suggested_filename == "test-novel.docx"

            with zipfile.ZipFile(artifact.path) as z:
                document_xml = z.read("word/document.xml").decode("utf-8")
                styles_xml = z.read("word/styles.xml").decode("utf-8")

            # Content: title (metadata → Title style) + chapters (h2 → Heading2).
            assert '<w:pStyle w:val="Title" />' in document_xml
            assert "Test Novel" in document_xml
            assert document_xml.count('<w:pStyle w:val="Heading2" />') == 2
            assert "Chapter One" in document_xml
            assert "Chapter Two" in document_xml
            # Manuscript format reached the OUTPUT styles (reference.docx wired).
            assert "Times New Roman" in styles_xml
        finally:
            artifact.path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_metadata_author_lang_reach_core_properties(self) -> None:
        manuscript = _normalized(title="Das Leuchtfeuer", author="Ada Quill")
        artifact = await PandocDocxRenderer().render(
            manuscript, ExportOptions(format=ExportFormat.DOCX)
        )
        try:
            with zipfile.ZipFile(artifact.path) as z:
                core_xml = z.read("docProps/core.xml").decode("utf-8")
            assert "<dc:title>Das Leuchtfeuer</dc:title>" in core_xml
            assert "<dc:creator>Ada Quill</dc:creator>" in core_xml
        finally:
            artifact.path.unlink(missing_ok=True)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test-file tests/unit/api/export/test_pandoc_docx.py`
Expected: FAIL — `ImportError: cannot import name 'PandocDocxRenderer'` (module does not exist; `ExportFormat.DOCX` likewise).

- [ ] **Step 3: Add the enum member**

In `apps/api/narrare/export/options.py`, replace:

```python
class ExportFormat(StrEnum):
    """Output format produced by a renderer."""

    PDF = "pdf"
    EPUB = "epub"
    MARKDOWN = "md"
```

with:

```python
class ExportFormat(StrEnum):
    """Output format produced by a renderer."""

    PDF = "pdf"
    EPUB = "epub"
    MARKDOWN = "md"
    DOCX = "docx"
```

- [ ] **Step 4: Create the renderer**

Create `apps/api/narrare/export/renderers/pandoc_docx.py`:

```python
"""pandoc DOCX renderer adapter — co-owner (with ``pandoc_md.py`` /
``pandoc_epub.py``) of the ``pandoc`` binary invocation (RULE-08).

Implements :class:`narrare.export.contracts.ManuscriptRenderer` for
:class:`~narrare.export.options.ExportFormat.DOCX` (C3 — Post-Export
Follow-ups design §6). Spawns pandoc via the shared helper in
:mod:`narrare.export.renderers.pandoc_base` — never calls
``asyncio.create_subprocess_exec`` directly (RULE-08 confinement).

Manuscript format via ``--reference-doc`` (design §6.1, binding)
-----------------------------------------------------------------
The committed ``apps/api/narrare/export/pandoc/reference.docx`` carries the
classic publishing manuscript format — Times 12 pt, 1.5 line spacing, 0.5"
first-line indent, centred chapter headings — and is passed UNCONDITIONALLY.
There is no template toggle: a configurable DOCX template system is
explicitly YAGNI (design §11), mirroring D7's unconditional font policy —
DOCX output never silently falls back to pandoc's default styles. A missing
reference file raises :class:`ExportRenderError` (RULE-11 — the same
no-silent-fallback guard as the EPUB renderer's bundled fonts).

No ``DocxOptions`` model exists BY DESIGN: v1 has zero DOCX-specific
request options. ``isbn`` / ``description`` stay EPUB-only (see
:class:`~narrare.export.options.EpubOptions` — the PDF/MD renderers ignore
them too; D7 precedent). No ``--toc``: a submission manuscript carries no
table of contents (the EPUB renderer's ``--toc`` exists because e-books
navigate).

Empirically verified against pandoc 3.10.1: with a fixed reference.docx the
``word/document.xml`` entry of the output is byte-deterministic across
runs (only ``docProps/core.xml`` — created/modified timestamps — varies) —
the property the C3 golden test pins.

Non-LLM (no ``narrare_core.agents`` / ``narrare_core.prompts`` imports) —
export is a deterministic render pipeline.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from narrare.export.contracts import (
    Artifact,
    ExportFormat,
    ExportOptions,
)
from narrare.export.errors import ExportRenderError
from narrare.export.renderers.pandoc_base import (
    DEFAULT_TIMEOUT_SECONDS,
    run_pandoc,
)

if TYPE_CHECKING:
    from narrare_core.export.contracts import NormalizedManuscript

logger = structlog.get_logger(__name__)

#: The committed manuscript-format reference document (design §6.1),
#: resolved PACKAGE-RELATIVELY (``Path(__file__)``), never via cwd — the
#: background runner may execute with any working directory. ``renderers/``
#: → ``../pandoc/reference.docx`` (the pandoc vendor area — the same
#: package-relative reach the EPUB renderer uses for ``../typst/fonts/``).
#: Read at call time so tests can redirect it (the ``_FONTS_DIR`` pattern).
_REFERENCE_DOC_PATH: Path = Path(__file__).resolve().parent.parent / "pandoc" / "reference.docx"

#: OOXML media type for WordprocessingML documents (the Artifact surface).
_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

#: Fallback filename stem when a manuscript title has no slug-able characters.
_EMPTY_TITLE_SLUG = "manuscript"


def _slugify(title: str) -> str:
    """Reduce a manuscript title to a safe filename stem.

    Mirrors :func:`narrare.export.renderers.pandoc_md._slugify` /
    :func:`narrare.export.renderers.pandoc_epub._slugify` so all three
    pandoc adapters derive identical stems for the same title.
    """
    stem = re.sub(r"[^\w]+", "-", title, flags=re.UNICODE).strip("-").lower()
    return stem or _EMPTY_TITLE_SLUG


def _resolve_reference_doc() -> Path:
    """Resolve the committed reference.docx (manuscript format, §6.1).

    Raises :class:`ExportRenderError` when the file is missing — there is
    never a silent fallback to pandoc's default styles (RULE-11 / the D7
    no-silent-fallback principle applied to document styles).
    """
    if not _REFERENCE_DOC_PATH.is_file():
        raise ExportRenderError(
            f"DOCX reference document missing (manuscript format, no silent "
            f"fallback): {_REFERENCE_DOC_PATH}. Restore the file or reinstall "
            f"the package."
        )
    return _REFERENCE_DOC_PATH


class PandocDocxRenderer:
    """RULE-08 renderer adapter for pandoc DOCX output (manuscript format).

    Structurally satisfies :class:`~narrare.export.contracts.ManuscriptRenderer`
    (no explicit inheritance — matches the repo's adapter convention).
    """

    def __init__(self) -> None:
        # Cached availability probe (RULE-11); refreshable by re-instantiating.
        self._available: bool | None = None

    @property
    def format(self) -> ExportFormat:
        """The format this renderer produces."""
        return ExportFormat.DOCX

    def is_available(self) -> bool:
        """True iff the ``pandoc`` binary is on ``$PATH`` (RULE-11).

        Cached on the instance after the first call; a missing binary degrades
        gracefully (the service reports the format unavailable).
        """
        if self._available is None:
            self._available = shutil.which("pandoc") is not None
        return self._available

    async def render(
        self,
        manuscript: NormalizedManuscript,
        options: ExportOptions,
    ) -> Artifact:
        """Render ``manuscript`` to a DOCX artifact in manuscript format.

        Pandoc writes the docx (a zip) to a temp ``--output`` file rather
        than stdout; the body is piped on stdin. The output is unlinked only
        on render failure (the registry owns cleanup on success).
        """
        reference_doc = _resolve_reference_doc()

        fd, raw_path = tempfile.mkstemp(suffix="-export.docx", prefix="narrare-")
        os.close(fd)  # pandoc overwrites it via --output
        output_path = Path(raw_path)
        try:
            argv: list[str] = [
                "--from=html",
                "--to=docx",
                f"--reference-doc={reference_doc}",
                f"--metadata=title:{manuscript.title}",
                f"--metadata=author:{manuscript.author}",
                f"--metadata=lang:{manuscript.language.value}",
                f"--output={output_path}",
            ]
            await run_pandoc(
                argv,
                manuscript.semantic_html.encode("utf-8"),
                format_label=self.format.value,
                timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
            )
            logger.info(
                "export_docx_rendered",
                bytes=output_path.stat().st_size,
                reference_doc=reference_doc.name,
            )
        except Exception:
            # RULE-11: never leave a partial/corrupt docx on disk; the typed
            # error (from run_pandoc or _resolve_reference_doc) propagates.
            output_path.unlink(missing_ok=True)
            raise

        return Artifact(
            format=self.format,
            path=output_path,
            media_type=_MEDIA_TYPE,
            suggested_filename=f"{_slugify(manuscript.title)}.docx",
        )
```

- [ ] **Step 5: Register the adapter module in the RULE-08 allowed list**

In `pyproject.toml`, locate:

```toml
export_binary_allowed_modules = [
  "apps/api/narrare/export/renderers/typst.py",
  "apps/api/narrare/export/renderers/pandoc_base.py",
  "apps/api/narrare/export/renderers/pandoc_md.py",
  "apps/api/narrare/export/renderers/pandoc_epub.py",
]
```

and append one entry (keeping the list complete over all renderer adapters — convention consistency with the four listed siblings; the checker passes either way because `pandoc_docx.py` contains no spawn call):

```toml
  "apps/api/narrare/export/renderers/pandoc_docx.py",
```

- [ ] **Step 6: Run the renderer tests to verify they pass**

Run: `just test-file tests/unit/api/export/test_pandoc_docx.py`
Expected: PASS — 13 tests (5 availability + 1 missing-reference + 5 slug params + 2 real-pandoc; the real-pandoc tests SKIP only where pandoc is absent).

- [ ] **Step 7: Run the sibling suites + architecture checker for regressions**

Run: `just test-file tests/unit/api/export/` then `just check-architecture`
Expected: PASS — the enum addition is purely additive; RULE-08 checker green.

- [ ] **Step 8: Commit (via Platform, verbatim)**

```bash
git add apps/api/narrare/export/options.py \
        apps/api/narrare/export/renderers/pandoc_docx.py \
        pyproject.toml \
        tests/unit/api/export/test_pandoc_docx.py
```

Commit message (NOTE: the pre-commit openapi-regenerate hook will auto-stage `docs/reference/openapi.json` — the `DOCX` enum member appears in the `/export/formats` schema — let it ride along; do NOT hand-edit that file):

```
feat(export): add PandocDocxRenderer — DOCX manuscript format via --reference-doc

C3 (design §6): IO-001's fourth format. Same RULE-08 seam as PDF/EPUB/MD —
structural ManuscriptRenderer, run_pandoc spawn helper, cached
shutil.which availability probe, graceful binary-absence degradation.

- ExportFormat gains DOCX = "docx" (options.py — the only change to an
  existing export module besides registration).
- The committed reference.docx (Task 1) is passed UNCONDITIONALLY via
  --reference-doc — Times 12 pt, 1.5 line spacing, 0.5" first-line indent,
  centred Heading2 chapters. No template toggle (§11 YAGNI; D7
  no-silent-fallback applied to document styles): a missing asset raises
  ExportRenderError.
- No DocxOptions model BY DESIGN: zero v1 DOCX options; isbn/description
  stay EPUB-only (EpubOptions D7-precedent rule). No --toc (submission
  manuscripts carry none).
- pyproject: pandoc_docx.py added to export_binary_allowed_modules
  (convention consistency — the module spawns nothing itself).
- Tests: availability probe + caching, slug parity, missing-reference
  fast-fail, real-pandoc render (Heading2 chapters, Title metadata,
  manuscript styles in the OUTPUT styles.xml, artifact fields).

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §6 (C3), ADR-081
```

---

### Task 3: Registration — DI factory + background runner

**Files:**
- Modify: `apps/api/narrare/export/dependencies.py` (48/400 lines — headroom verified)
- Modify: `apps/api/narrare/export/tasks.py` (283/400 lines — headroom verified)
- Test: `tests/unit/api/export/test_docx_registration.py` (new)

**Interfaces:**
- Consumes: `PandocDocxRenderer` + `ExportFormat.DOCX` (Task 2); `ExportServiceImpl` (existing); `RecordingEnqueuer` (`tests/unit/api/export/conftest.py`).
- Produces: `get_export_renderers()` returns a FOUR-entry dict including `ExportFormat.DOCX`; `tasks._resolve_runner_deps()` resolves a four-renderer dict — the DOCX format becomes dispatchable end-to-end (`list_formats` advertises it; `export(format=docx)` runs it).

- [ ] **Step 1: Write the failing registration tests**

Create `tests/unit/api/export/test_docx_registration.py`:

```python
"""Registration tests for the DOCX format (C3).

Pins that the renderer is wired into BOTH registration sites — the DI
factory (request path: ``list_formats`` / fast-fail availability) and the
background runner's lazy renderer map (the path real exports walk) — and
that the graceful binary-absence degradation covers DOCX like its siblings.
"""

from __future__ import annotations

import asyncio
import shutil

import pytest

from narrare.export import tasks
from narrare.export.dependencies import get_export_renderers
from narrare.export.options import ExportFormat
from narrare.export.renderers.pandoc_docx import PandocDocxRenderer
from narrare.export.service import ExportServiceImpl
from tests.unit.api.export.conftest import RecordingEnqueuer


class TestDiFactoryRegistration:
    def test_get_export_renderers_includes_docx(self) -> None:
        renderers = get_export_renderers()

        assert set(renderers) == {
            ExportFormat.PDF,
            ExportFormat.EPUB,
            ExportFormat.MARKDOWN,
            ExportFormat.DOCX,
        }
        assert isinstance(renderers[ExportFormat.DOCX], PandocDocxRenderer)
        assert renderers[ExportFormat.DOCX].format is ExportFormat.DOCX


class TestRunnerRegistration:
    def test_resolve_runner_deps_includes_docx(self) -> None:
        saved = tasks._renderers
        tasks._renderers = None  # force lazy rebuild with the new adapter
        try:
            _normalizer, renderers = tasks._resolve_runner_deps()
            assert ExportFormat.DOCX in renderers
            assert isinstance(renderers[ExportFormat.DOCX], PandocDocxRenderer)
        finally:
            tasks._renderers = saved


class TestServiceAvailabilitySurface:
    """RULE-11 graceful degradation: DOCX availability tracks pandoc."""

    def _service(self) -> ExportServiceImpl:
        return ExportServiceImpl(
            renderers=get_export_renderers(),
            enqueue=RecordingEnqueuer(),
        )

    def test_docx_reported_unavailable_when_pandoc_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(shutil, "which", lambda _cmd: None)
        formats = dict(asyncio.run(self._service().list_formats()))
        assert formats[ExportFormat.DOCX] is False

    def test_docx_reported_available_when_pandoc_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(shutil, "which", lambda _cmd: "/usr/bin/pandoc")
        formats = dict(asyncio.run(self._service().list_formats()))
        assert formats[ExportFormat.DOCX] is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test-file tests/unit/api/export/test_docx_registration.py`
Expected: FAIL — `test_get_export_renderers_includes_docx`: the dict has only 3 keys (`set(renderers)` mismatch); `test_resolve_runner_deps_includes_docx`: `ExportFormat.DOCX not in renderers`.

- [ ] **Step 3: Register in the DI factory**

In `apps/api/narrare/export/dependencies.py`:

3a. Replace the import block:

```python
from narrare.export.contracts import ExportFormat, ManuscriptRenderer
from narrare.export.renderers.pandoc_epub import PandocEpubRenderer
from narrare.export.renderers.pandoc_md import PandocMarkdownRenderer
from narrare.export.renderers.typst import TypstPdfRenderer
```

with:

```python
from narrare.export.contracts import ExportFormat, ManuscriptRenderer
from narrare.export.renderers.pandoc_docx import PandocDocxRenderer
from narrare.export.renderers.pandoc_epub import PandocEpubRenderer
from narrare.export.renderers.pandoc_md import PandocMarkdownRenderer
from narrare.export.renderers.typst import TypstPdfRenderer
```

3b. Replace:

```python
def get_export_renderers() -> dict[ExportFormat, ManuscriptRenderer]:
    """Instantiate the three renderer adapters (PDF / EPUB / Markdown)."""
    return {
        ExportFormat.PDF: TypstPdfRenderer(),
        ExportFormat.MARKDOWN: PandocMarkdownRenderer(),
        ExportFormat.EPUB: PandocEpubRenderer(),
    }
```

with:

```python
def get_export_renderers() -> dict[ExportFormat, ManuscriptRenderer]:
    """Instantiate the four renderer adapters (PDF / EPUB / Markdown / DOCX)."""
    return {
        ExportFormat.PDF: TypstPdfRenderer(),
        ExportFormat.MARKDOWN: PandocMarkdownRenderer(),
        ExportFormat.EPUB: PandocEpubRenderer(),
        ExportFormat.DOCX: PandocDocxRenderer(),
    }
```

3c. In the module docstring, replace `instantiates the three renderer adapters` with `instantiates the four renderer adapters`.

- [ ] **Step 4: Register in the background runner**

In `apps/api/narrare/export/tasks.py`:

4a. Inside `_resolve_runner_deps`, replace:

```python
    if _renderers is None:
        from narrare.export.renderers.pandoc_epub import PandocEpubRenderer
        from narrare.export.renderers.pandoc_md import PandocMarkdownRenderer
        from narrare.export.renderers.typst import TypstPdfRenderer

        _renderers = {
            ExportFormat.PDF: TypstPdfRenderer(),
            ExportFormat.MARKDOWN: PandocMarkdownRenderer(),
            ExportFormat.EPUB: PandocEpubRenderer(),
        }
```

with:

```python
    if _renderers is None:
        from narrare.export.renderers.pandoc_docx import PandocDocxRenderer
        from narrare.export.renderers.pandoc_epub import PandocEpubRenderer
        from narrare.export.renderers.pandoc_md import PandocMarkdownRenderer
        from narrare.export.renderers.typst import TypstPdfRenderer

        _renderers = {
            ExportFormat.PDF: TypstPdfRenderer(),
            ExportFormat.MARKDOWN: PandocMarkdownRenderer(),
            ExportFormat.EPUB: PandocEpubRenderer(),
            ExportFormat.DOCX: PandocDocxRenderer(),
        }
```

4b. In `_resolve_runner_deps`'s docstring, replace `the three renderer adapters` with `the four renderer adapters`.

- [ ] **Step 5: Run the registration tests to verify they pass**

Run: `just test-file tests/unit/api/export/test_docx_registration.py`
Expected: PASS — 4 tests.

- [ ] **Step 6: Run the full export suite + architecture checker**

Run: `just test-file tests/unit/api/export/` then `just check-architecture`
Expected: PASS — no sibling regression (service tests iterate whatever the injected renderer dict contains).

- [ ] **Step 7: Commit (via Platform, verbatim)**

```bash
git add apps/api/narrare/export/dependencies.py \
        apps/api/narrare/export/tasks.py \
        tests/unit/api/export/test_docx_registration.py
```

Commit message:

```
feat(export): register DOCX renderer (DI factory + background runner)

C3: PandocDocxRenderer joins both registration sites —
dependencies.get_export_renderers (request path: list_formats advertises
DOCX with its live availability; export() fast-fails when pandoc is
missing) and tasks._resolve_runner_deps (the lazy map real export jobs
walk). Registration tests pin the four-entry dicts on both paths + the
RULE-11 graceful binary-absence degradation for DOCX.

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §6 (C3)
```

---

### Task 4: Golden `document.xml` test

**Files:**
- Create: `tests/golden/export/test_docx_golden.py`
- Create: `tests/golden/export/baselines/docx-manuscript.json` (generated in Step 3 — test asset, not counted)

**Interfaces:**
- Consumes: `PandocDocxRenderer` + `ExportFormat.DOCX` (Tasks 2–3); `scripts.generate_reference_docx.build_reference_docx` (Task 1); the `--golden-update` pytest option registered in `tests/golden/export/conftest.py` (existing — Slice 7); the committed `reference.docx` (Task 1).
- Produces: the design-§12 golden gate — `tests/golden/export/baselines/docx-manuscript.json` (`{"schema_version": 1, "document_xml_sha256": "<hex>"}`) asserted by `test_document_xml_matches_committed_baseline`; the regeneration path `uv run pytest tests/golden/export/test_docx_golden.py -v -m golden_pages --golden-update -p no:xdist`.

- [ ] **Step 1: Write the golden test**

Create `tests/golden/export/test_docx_golden.py`:

```python
"""Golden acceptance test for the pandoc DOCX renderer (C3 — design §6.2).

Design §6.2 (binding): verification is a golden test on the UNZIPPED
``word/document.xml`` — a docx is a zip whose container timestamps make
byte-diffing the FILE impossible.

Normalization ruling (evidence-based, locked in the plan)
---------------------------------------------------------
Empirically verified against pandoc 3.10.1 (the pinned version): rendering
the same input twice with the same ``--reference-doc`` yields BYTE-IDENTICAL
``word/document.xml`` (and styles.xml, numbering.xml, …). The ONLY entry
that varies is ``docProps/core.xml`` (``dcterms:created``/``modified``
wall-clock stamps). Pandoc emits no ``w:rsid`` attributes and no dates in
``document.xml`` itself. Normalization is therefore EXTRACT-ONLY: read the
``word/document.xml`` zip entry and compare its sha256 — strip nothing.
Zip-entry metadata (timestamps) lives in the zip directory, never in the
entry bytes.

Tiers (mirrors test_golden_pages.py / test_epubcheck.py):
1. Determinism probe — two consecutive renders produce identical
   document.xml bytes (the premise the golden rests on).
2. THE golden — sha256(document.xml) == the committed baseline. Intentional
   drift (pandoc pin bump, reference.docx regeneration) is blessed via
   ``--golden-update`` (the conftest option) — review + commit the diff.
3. Manuscript-format styles — the OUTPUT word/styles.xml carries the four
   binding properties (document.xml only REFERENCES styles; without this
   class the headline feature would be unverified).
4. Content — title/chapters/bookmarks/prose reach document.xml.
5. Reference-asset reproducibility — the committed reference.docx equals
   generator(pandoc's default) for the INSTALLED pandoc (RULE-08: tests/
   spawns are exempt — the checker's documented test-harness carve-out).

Pandoc-version coupling (honest note): tiers 2 + 5 are pinned to the
installed pandoc. CI installs 3.10.1 (install_export_toolchain.sh); a
local dev machine with a different pandoc may fail these — the documented
response is the regeneration procedure in
apps/api/narrare/export/pandoc/README.md, NOT a skip.

Non-LLM (deterministic render pipeline; no agent, no prompt).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from uuid import UUID

import pytest

from narrare.export.options import ExportFormat, ExportOptions
from narrare.export.renderers.pandoc_docx import PandocDocxRenderer
from narrare_core.export.contracts import ChapterMeta, Language, NormalizedManuscript
from scripts.generate_reference_docx import build_reference_docx

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

#: The committed baseline for the document.xml golden (this dir/../baselines).
_BASELINE_FILE = Path(__file__).resolve().parent / "baselines" / "docx-manuscript.json"
_BASELINE_SCHEMA_VERSION = 1

#: The committed reference asset (tests/golden/export → repo root → vendor).
_COMMITTED_REFERENCE = (
    Path(__file__).resolve().parents[3]
    / "apps"
    / "api"
    / "narrare"
    / "export"
    / "pandoc"
    / "reference.docx"
)

pytestmark = [
    pytest.mark.golden_pages,
    pytest.mark.skipif(
        shutil.which("pandoc") is None,
        reason="pandoc not installed (install via scripts/install_export_toolchain.sh)",
    ),
]

#: Deterministic chapter ids (uuid4 entropy must never enter asserted output).
_CHAPTER_IDS = (
    UUID("00000000-0000-0000-0000-0000000000e1"),
    UUID("00000000-0000-0000-0000-0000000000e2"),
)

#: The committed corpus content (inline — the test_epubcheck.py pattern for
#: non-PDF golden tests; the PDF CORPUS registry stays untouched). Covers:
#: two chapters (Heading2), multi-paragraph bodies (FirstParagraph AND
#: BodyText styles), one canonical scene break (<hr class="scene-break"/>),
#: one German prose paragraph (UTF-8 round-trip into document.xml).
_SEMANTIC_HTML = (
    "<h2>Chapter One</h2>\n"
    "<p>The lighthouse keeper counted the steps again — forty-two, "
    "always forty-two.</p>\n"
    "<p>Elsewhere in the tower, dust settled over the ledgers no one "
    "read.</p>\n"
    '<hr class="scene-break"/>\n'
    "<p>Morning arrived with gulls.</p>\n"
    "<h2>Chapter Two</h2>\n"
    "<p>Die Wirtin stellte zwei Tassen auf den Tisch und schwieg.</p>\n"
    "<p>Neither of them mentioned the lighthouse.</p>\n"
)


def _manuscript() -> NormalizedManuscript:
    return NormalizedManuscript(
        semantic_html=_SEMANTIC_HTML,
        title="The Lighthouse Years",
        author="Ada Quill",
        language=Language.EN,
        chapters=[
            ChapterMeta(chapter_id=_CHAPTER_IDS[0], title="Chapter One", position=0, volume_id=None),
            ChapterMeta(chapter_id=_CHAPTER_IDS[1], title="Chapter Two", position=1, volume_id=None),
        ],
    )


async def _render_entries() -> dict[str, bytes]:
    """Render through the REAL adapter; return the docx zip entries."""
    artifact = await PandocDocxRenderer().render(
        _manuscript(), ExportOptions(format=ExportFormat.DOCX)
    )
    try:
        with zipfile.ZipFile(artifact.path) as z:
            return {name: z.read(name) for name in z.namelist()}
    finally:
        artifact.path.unlink(missing_ok=True)


def _write_baseline(sha_hex: str) -> None:
    """--golden-update path: write the baseline (pretty, sorted — the
    tests/golden/export/harness/baselines.py save convention)."""
    payload = {
        "schema_version": _BASELINE_SCHEMA_VERSION,
        "document_xml_sha256": sha_hex,
    }
    _BASELINE_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _style(styles_root: ET.Element, style_id: str) -> ET.Element:
    for style in styles_root.findall(f"{_W}style"):
        if style.get(f"{_W}styleId") == style_id:
            return style
    raise AssertionError(f"style {style_id!r} missing from output styles.xml")


@pytest.fixture(scope="module")
def golden_update(request: pytest.FixtureRequest) -> bool:
    """True when ``--golden-update`` was passed (baseline regeneration mode)."""
    return bool(request.config.getoption("--golden-update"))


class TestDocumentXmlDeterminism:
    @pytest.mark.asyncio
    async def test_two_consecutive_renders_are_byte_identical(self) -> None:
        first, second = await _render_entries(), await _render_entries()
        assert first["word/document.xml"] == second["word/document.xml"]


class TestGoldenDocumentXml:
    """THE design-§12 gate: sha256 of the extracted document.xml."""

    @pytest.mark.asyncio
    async def test_document_xml_matches_committed_baseline(
        self, golden_update: bool
    ) -> None:
        entries = await _render_entries()
        sha = hashlib.sha256(entries["word/document.xml"]).hexdigest()
        if golden_update:
            _write_baseline(sha)
            return
        assert _BASELINE_FILE.is_file(), (
            "baseline missing — regenerate via: uv run pytest "
            "tests/golden/export/test_docx_golden.py -v -m golden_pages "
            "--golden-update -p no:xdist"
        )
        baseline = json.loads(_BASELINE_FILE.read_text(encoding="utf-8"))
        assert baseline["schema_version"] == _BASELINE_SCHEMA_VERSION
        assert sha == baseline["document_xml_sha256"], (
            f"document.xml drift: sha256 {sha[:16]}… != baseline "
            f"{str(baseline['document_xml_sha256'])[:16]}… — intentional drift "
            f"(pandoc pin bump, reference.docx regeneration) is blessed via "
            f"--golden-update; review + commit the diff."
        )


class TestManuscriptFormatStyles:
    """The four binding §6.1 properties in the OUTPUT word/styles.xml."""

    @pytest.mark.asyncio
    async def test_manuscript_format_reaches_output_styles(self) -> None:
        entries = await _render_entries()
        styles = ET.fromstring(entries["word/styles.xml"])

        # Times 12 pt + 1.5 line spacing on the document base.
        normal = _style(styles, "Normal")
        normal_fonts = normal.find(f"{_W}rPr/{_W}rFonts")
        assert normal_fonts is not None
        assert normal_fonts.get(f"{_W}ascii") == "Times New Roman"
        assert normal.find(f"{_W}rPr/{_W}sz").get(f"{_W}val") == "24"
        normal_spacing = normal.find(f"{_W}pPr/{_W}spacing")
        assert normal_spacing.get(f"{_W}line") == "360"
        assert normal_spacing.get(f"{_W}lineRule") == "auto"

        # 0.5" first-line indent on body paragraphs.
        body_ind = _style(styles, "BodyText").find(f"{_W}pPr/{_W}ind")
        assert body_ind is not None
        assert body_ind.get(f"{_W}firstLine") == "720"

        # Centred, Times, 12 pt chapter headings.
        heading = _style(styles, "Heading2")
        jc = heading.find(f"{_W}pPr/{_W}jc")
        assert jc is not None
        assert jc.get(f"{_W}val") == "center"
        heading_fonts = heading.find(f"{_W}rPr/{_W}rFonts")
        assert heading_fonts is not None
        assert heading_fonts.get(f"{_W}ascii") == "Times New Roman"
        assert heading.find(f"{_W}rPr/{_W}sz").get(f"{_W}val") == "24"


class TestContentReachesDocumentXml:
    @pytest.mark.asyncio
    async def test_title_chapters_bookmarks_prose(self) -> None:
        entries = await _render_entries()
        document = ET.fromstring(entries["word/document.xml"])
        texts = [t.text or "" for t in document.iter(f"{_W}t")]
        joined = "\n".join(texts)

        assert "The Lighthouse Years" in joined  # title (metadata → Title style)
        heading_styles = [
            p.find(f"{_W}pPr/{_W}pStyle").get(f"{_W}val")
            for p in document.iter(f"{_W}p")
            if p.find(f"{_W}pPr/{_W}pStyle") is not None
        ]
        assert heading_styles.count("Heading2") == 2
        assert "Chapter One" in joined
        assert "Chapter Two" in joined
        bookmarks = {b.get(f"{_W}name") for b in document.iter(f"{_W}bookmarkStart")}
        assert "chapter-one" in bookmarks
        assert "chapter-two" in bookmarks
        # Prose survives verbatim (incl. the German UTF-8 paragraph).
        assert "forty-two, always forty-two" in joined
        assert "Die Wirtin stellte zwei Tassen auf den Tisch und schwieg." in joined
        # Both paragraph styles are used (first-after-heading vs body).
        assert heading_styles.count("FirstParagraph") >= 2
        assert heading_styles.count("BodyText") >= 2


class TestReferenceAssetReproducible:
    def test_committed_reference_equals_generator_output(self) -> None:
        """Committed asset == build_reference_docx(pandoc default).

        Pins the vendor-README regeneration contract: the asset in-tree is
        exactly what the documented procedure produces for the installed
        pandoc. A mismatch after a pandoc bump is the signal to regenerate
        the asset + golden baseline together.
        """
        base = subprocess.run(
            ["pandoc", "--print-default-data-file", "reference.docx"],
            check=True,
            capture_output=True,
        ).stdout
        assert build_reference_docx(base) == _COMMITTED_REFERENCE.read_bytes()
```

- [ ] **Step 2: Run the golden test to verify it fails (baseline missing)**

Run: `just test-file tests/golden/export/test_docx_golden.py`
Expected: the determinism / styles / content / reproducibility classes PASS (the renderer + asset landed in Tasks 1–3); `test_document_xml_matches_committed_baseline` FAILS on the explicit `baseline missing` assertion (`docx-manuscript.json` does not exist yet). This failing run satisfies the regression-first rule.

- [ ] **Step 3: Generate the committed baseline**

Run:

```bash
uv run pytest tests/golden/export/test_docx_golden.py::TestGoldenDocumentXml -v -m golden_pages --golden-update -p no:xdist
```

Expected: PASS (regeneration mode writes `tests/golden/export/baselines/docx-manuscript.json`). Inspect the written file — it must contain exactly:

```json
{
  "document_xml_sha256": "<64 hex chars>",
  "schema_version": 1
}
```

- [ ] **Step 4: Run the golden test to verify it passes**

Run: `just test-file tests/golden/export/test_docx_golden.py`
Expected: PASS — 5 tests (assert mode; determinism probe + golden + styles + content + reproducibility).

- [ ] **Step 5: Run the existing golden suites for regressions**

Run: `just test-file tests/golden/export/test_golden_pages.py` (needs typst + pandoc; SKIP-only on machines without typst — CI runs it fully)
Expected: PASS / SKIP-per-binary — the DOCX slice touches nothing the PDF golden measures.

- [ ] **Step 6: Commit (via Platform, verbatim)**

```bash
git add tests/golden/export/test_docx_golden.py \
        tests/golden/export/baselines/docx-manuscript.json
```

Commit message:

```
test(export): golden document.xml test for the DOCX renderer

C3 §6.2/§12 gate: verification on the UNZIPPED word/document.xml —
analogous to the Golden-Pages procedure (committed baseline + sha256 +
--golden-update regeneration path).

- Normalization ruling (evidence-based): pandoc 3.10.1 emits a
  BYTE-DETERMINISTIC word/document.xml under a fixed --reference-doc (only
  docProps/core.xml created/modified timestamps vary; no rsids, no dates
  in document.xml) → the golden extracts the entry and compares sha256 —
  strip nothing. Zip container timestamps live in the zip directory,
  never in the entry bytes.
- Five tiers: two-render determinism probe; THE golden against
  baselines/docx-manuscript.json; manuscript-format style assertions on
  the OUTPUT styles.xml (document.xml only references styles — without
  this class the headline property would be unverified); content
  assertions (Title/Heading2 chapters/bookmarks/prose incl. UTF-8 German);
  reference-asset reproducibility (committed reference.docx ==
  generator(pandoc default) — tests/ spawn, RULE-08-exempt).
- Pandoc-version coupling documented honestly: tiers golden +
  reproducibility are pinned to the installed pandoc (CI: 3.10.1); drift
  after a pin bump is blessed via the documented regeneration procedure.

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §6 + §12 (C3)
```

---

### Task 5: i18n — DOCX format keys (en/de/fr)

**Files:**
- Modify: `packages/i18n/messages/en/export.json`
- Modify: `packages/i18n/messages/de/export.json`
- Modify: `packages/i18n/messages/fr/export.json`

(Exactly the 3-locale cap — the C2 Task-8 precedent. The frontend consumes the keys in Task 6.)

**Interfaces:**
- Consumes: the existing `format` object in each locale (verified anchor: its `markdownDescription` entry, directly before `unavailable`).
- Produces (verbatim for Task 6): keys `export.format.docx` (label) and `export.format.docxDescription` (card description).

- [ ] **Step 1: Add the keys to all three locales**

In each file, locate the `format` object's `"markdownDescription": "…",` line (directly before `"unavailable"`) and insert the two DOCX keys AFTER it.

en (`packages/i18n/messages/en/export.json`):

```json
    "docx": "Word (DOCX)",
    "docxDescription": "Manuscript format for editors — Times 12 pt, 1.5 line spacing.",
```

de (`packages/i18n/messages/de/export.json`):

```json
    "docx": "Word (DOCX)",
    "docxDescription": "Manuskript-Format für Lektoren — Times 12 pt, 1,5-zeilig.",
```

fr (`packages/i18n/messages/fr/export.json`):

```json
    "docx": "Word (DOCX)",
    "docxDescription": "Format manuscrit pour les éditeurs — Times 12 pt, interligne 1,5.",
```

- [ ] **Step 2: Verify JSON validity + locale parity**

Run: `python3 -c "import json; [json.load(open(f'packages/i18n/messages/{l}/export.json')) for l in ('en','de','fr')]; print('ok')"`
Expected: `ok` (the i18n pre-commit hook enforces locale parity again at commit time).

- [ ] **Step 3: Commit (via Platform, verbatim)**

```bash
git add packages/i18n/messages/en/export.json \
        packages/i18n/messages/de/export.json \
        packages/i18n/messages/fr/export.json
```

Commit message:

```
feat(i18n): add export format.docx keys (en/de/fr)

C3: card label + description for the DOCX format option in the export
panel — the manuscript format for editors (Times 12 pt, 1.5 line spacing)
is the use case that justifies DOCX at all (design §6.1).
```

---

### Task 6: Frontend — DOCX format option in the export panel

**Files:**
- Modify: `packages/web/types/export.ts` (121 lines)
- Modify: `packages/web/components/studio/export/ExportFormatSelector.tsx` (84 lines)
- Test: extend `packages/web/lib/api/__tests__/types-parity.test.ts`; extend `packages/web/components/studio/export/__tests__/ExportPanel.test.tsx`

**Interfaces:**
- Consumes: i18n keys `export.format.docx` / `export.format.docxDescription` (Task 5); `FormatAvailability[]` from `GET /export/formats` (already includes DOCX after Task 3 — availability-driven like every sibling card; NO client change needed in `lib/api/export.ts`).
- Produces: `ExportFormat` TS union includes `"docx"`; the format card group renders a fourth card (`data-testid="format-docx"`, `FileType` icon) that is disabled + labelled when the backend reports DOCX unavailable.

- [ ] **Step 1: Extend the type union**

In `packages/web/types/export.ts`, replace:

```typescript
/** Output format produced by a renderer. Mirrors `ExportFormat` StrEnum. */
export type ExportFormat = "pdf" | "epub" | "md";
```

with:

```typescript
/** Output format produced by a renderer. Mirrors `ExportFormat` StrEnum. */
export type ExportFormat = "pdf" | "epub" | "md" | "docx";
```

(`ExportOptions` is deliberately UNCHANGED — there is no `docx_options`: zero v1 DOCX options by design, ruling 1. The header comment's Pydantic model list stays accurate — no new model was added.)

- [ ] **Step 2: Update the types-parity test**

In `packages/web/lib/api/__tests__/types-parity.test.ts`, replace:

```typescript
    const formats: ExportFormat[] = ["pdf", "epub", "md"];
    expect(formats).toEqual(["pdf", "epub", "md"]);
```

with:

```typescript
    const formats: ExportFormat[] = ["pdf", "epub", "md", "docx"];
    expect(formats).toEqual(["pdf", "epub", "md", "docx"]);
```

- [ ] **Step 3: Add the format card**

In `packages/web/components/studio/export/ExportFormatSelector.tsx`:

3a. Replace the icon import:

```typescript
import { BookOpen, FileText, FileType2 } from "lucide-react";
```

with:

```typescript
import { BookOpen, FileText, FileType, FileType2 } from "lucide-react";
```

3b. Replace the card array:

```typescript
const FORMAT_CARDS: { value: ExportFormat; icon: LucideIcon; labelKey: string; descKey: string }[] =
  [
    { value: "pdf", icon: FileText, labelKey: "format.pdf", descKey: "format.pdfDescription" },
    { value: "epub", icon: BookOpen, labelKey: "format.epub", descKey: "format.epubDescription" },
    {
      value: "md",
      icon: FileType2,
      labelKey: "format.markdown",
      descKey: "format.markdownDescription",
    },
  ];
```

with:

```typescript
const FORMAT_CARDS: { value: ExportFormat; icon: LucideIcon; labelKey: string; descKey: string }[] =
  [
    { value: "pdf", icon: FileText, labelKey: "format.pdf", descKey: "format.pdfDescription" },
    { value: "epub", icon: BookOpen, labelKey: "format.epub", descKey: "format.epubDescription" },
    {
      value: "md",
      icon: FileType2,
      labelKey: "format.markdown",
      descKey: "format.markdownDescription",
    },
    { value: "docx", icon: FileType, labelKey: "format.docx", descKey: "format.docxDescription" },
  ];
```

Line-width check (review NIT): `packages/web/biome.json` configures `formatter.lineWidth: 100`; the `docx` card line measures 98 columns — exactly the length of the existing `epub` card line, with 2 columns of headroom — so it stays unwrapped.

NO other frontend change: `ExportOptionsForm` needs no docx branch (DOCX has no format-specific options group — the content toggles still render), `useExportSettings.defaultExportOptions` needs no docx default (no `docx_options` field exists), and `ExportFormatSelector`'s availability gating already covers the new card generically.

- [ ] **Step 4: Extend the panel tests**

In `packages/web/components/studio/export/__tests__/ExportPanel.test.tsx`:

4a. In the `panelReturn` mock, replace:

```typescript
  formats: [
    { format: "pdf" as const, available: true },
    { format: "epub" as const, available: true },
    { format: "md" as const, available: false },
  ],
```

with:

```typescript
  formats: [
    { format: "pdf" as const, available: true },
    { format: "epub" as const, available: true },
    { format: "md" as const, available: false },
    { format: "docx" as const, available: true },
  ],
```

4b. In the `renders the panel title + format cards` test, replace:

```typescript
    expect(screen.getByTestId("format-md")).toBeInTheDocument();
```

with:

```typescript
    expect(screen.getByTestId("format-md")).toBeInTheDocument();
    expect(screen.getByTestId("format-docx")).toBeInTheDocument();
```

4c. Append inside the same `describe("ExportPanel", …)` block (after the `calls setOptions with the new format when a card is clicked` test):

```typescript
  it("calls setOptions with docx when the DOCX card is clicked (C3)", () => {
    renderPanel();
    fireEvent.click(screen.getByTestId("format-docx"));
    expect(panelReturn.setOptions).toHaveBeenCalledWith(
      expect.objectContaining({ format: "docx" }),
    );
  });
```

- [ ] **Step 5: Run the web gates**

Run: `cd packages/web && pnpm test components/studio/export/__tests__/ExportPanel.test.tsx lib/api/__tests__/types-parity.test.ts && pnpm type-check && pnpm lint:check`
Expected: PASS all (panel tests mock next-intl — the i18n keys landed in Task 5 regardless).

- [ ] **Step 6: Commit (via Platform, verbatim)**

```bash
git add packages/web/types/export.ts \
        packages/web/components/studio/export/ExportFormatSelector.tsx \
        packages/web/lib/api/__tests__/types-parity.test.ts \
        packages/web/components/studio/export/__tests__/ExportPanel.test.tsx
```

Commit message:

```
feat(web): add DOCX format option to the export panel

C3: the fourth format card (FileType icon, availability-driven like its
siblings — disabled + labelled when the backend reports pandoc missing).
RULE-17: ExportFormat union gains "docx", pinned by the types-parity
sample. Deliberately NO other change: DOCX has zero format-specific
options (no docx_options — the manuscript reference.docx IS the format),
so ExportOptionsForm needs no branch and defaultExportOptions no default.

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §6 (C3)
```

---

### Task 7: Docs closure — IO-001 spec + ADR-081 review trigger + CURRENT_STATE + INDEX + slice gates

**Files:**
- Modify: `docs/features/io/IO-001-export.md`
- Modify: `docs/architecture/decisions/ADR-081-export-pipeline-typst.md`
- Modify: `docs/_shared/CURRENT_STATE.md`
- Modify: `docs/features/INDEX.md`

(Docs only — does not count toward the file cap. **No new ADR** — design §6: "ADR-081's engine decision applies unchanged"; ADR-081's own out-of-scope note says a DOCX addition "is a feature-spec change, not an engine decision, and does not require re-opening this ADR", and its Review-Trigger checklist anticipated exactly this. The RULE-21 row's generic "adding DOCX" example is superseded by that specific carve-out — do NOT touch the RULE-21 row.)

**Interfaces:**
- Consumes: everything landed in Tasks 1–6.
- Produces: honest doc state (IO-001 un-deferred everywhere, ADR-081 review trigger closed with a dated note, CURRENT_STATE + INDEX entries); the slice-final gate run.

- [ ] **Step 1: Update the IO-001 feature spec**

In `docs/features/io/IO-001-export.md`:

1a. Replace the status line's tail (line with `**Status:** ✅ Implemented / Stable`):

```
Shipped formats: **PDF** (Typst + `narrare-roman`, drop cap optional default off), **EPUB** (pandoc EPUB3, isbn/description metadata), **Markdown** (pandoc). Deferred: DOCX only.
```

with:

```
Shipped formats: **PDF** (Typst + `narrare-roman`, drop cap optional default off), **EPUB** (pandoc EPUB3, isbn/description metadata), **Markdown** (pandoc), **DOCX** (pandoc `--reference-doc` manuscript format, C3). No formats remain deferred.
```

1b. In the Architecture Decision bullet list, replace:

```
- **DOCX is the only remaining deferred format** (out of scope for ADR-081).
  pandoc can add it trivially later — a feature-spec change, not an engine decision.
```

with:

```
- **DOCX shipped 2026-08-17 (C3)** — `PandocDocxRenderer` passes the committed
  `apps/api/narrare/export/pandoc/reference.docx` via `--reference-doc`:
  the classic publishing manuscript format (Times 12 pt, 1.5 line spacing,
  0.5″ first-line indent, centred chapter headings). Verified by a golden test
  on the unzipped `word/document.xml` (byte-deterministic under a fixed
  reference — only `docProps/core.xml` timestamps vary). No new ADR: ADR-081's
  engine decision applies unchanged (its own out-of-scope note classified this
  as a feature-spec change).
```

1c. In the "How it works (User perspective)" options list, replace:

```
   - **DOCX:** heading styles, page breaks between chapters
```

with:

```
   - **DOCX:** none — one maintained manuscript format (Times 12 pt, 1.5
     line spacing, first-line indent, centred chapter headings)
```

1d. In Stage 2 of the technical pipeline, replace:

```
   `--to=typst --shift-heading-level-by=-1` for PDF; EPUB3 for ePub; Markdown
   for `.md`. (DOCX deferred — pandoc can add it trivially later.)
```

with:

```
   `--to=typst --shift-heading-level-by=-1` for PDF; EPUB3 for ePub; Markdown
   for `.md`; `--to=docx --reference-doc=<vendored reference.docx>` for DOCX
   (manuscript format, C3 — no `--toc`: submission manuscripts carry none).
```

1e. In Stage 3's renderer list, replace:

```
    - **Markdown** → `PandocMarkdownRenderer`: pandoc.
```

with:

```
    - **Markdown** → `PandocMarkdownRenderer`: pandoc.
    - **DOCX** → `PandocDocxRenderer`: pandoc with the committed
      manuscript-format `reference.docx` (golden `document.xml` test — C3).
```

1f. In the options-schema code block, replace:

```python
class ExportFormat(StrEnum):
    PDF = "pdf"
    EPUB = "epub"
    MARKDOWN = "md"
```

with:

```python
class ExportFormat(StrEnum):
    PDF = "pdf"
    EPUB = "epub"
    MARKDOWN = "md"
    DOCX = "docx"
```

(There is intentionally no `docx_options` line to add — zero v1 DOCX options.)

1g. In Constraints & Edge Cases, replace:

```
- DOCX is **deferred** (out of scope for ADR-081); pandoc can add it trivially
  later. The normalizer strips Narrare-specific markup (AIAnnotation, GhostText)
  from all formats
```

with:

```
- DOCX renders via the committed manuscript-format `reference.docx` — one
  maintained format, no user-selectable template (YAGNI, program design §11);
  a missing asset fast-fails (no silent fallback to pandoc's default styles).
  The normalizer strips Narrare-specific markup (AIAnnotation, GhostText)
  from all formats
```

1h. In Status & History, append a new dated entry after the last one:

```markdown
- `2026-08-17` — **DOCX shipped (C3 — Post-Export Follow-ups §6)**:
  `PandocDocxRenderer` (RULE-08 adapter, same seam as PDF/EPUB/MD) renders
  via `--reference-doc` with the committed
  `apps/api/narrare/export/pandoc/reference.docx` (deterministic generator
  `scripts/generate_reference_docx.py`, pure stdlib). Manuscript format:
  Times 12 pt, 1.5 line spacing, 0.5″ first-line indent (every paragraph),
  centred chapter headings, Times 14 pt title page. Golden verification on
  the unzipped `word/document.xml` (byte-deterministic; sha256 baseline +
  `--golden-update` regeneration path) + manuscript-format style assertions
  on the output `styles.xml`. Frontend: fourth format card + i18n en/de/fr.
  No DocxOptions model (zero v1 options), no migration, no ADR change —
  ADR-081's Review-Trigger DOCX item closed.
```

1i. Sweep for stragglers:

Run: `rg -n "DOCX" docs/features/io/IO-001-export.md`
Expected: every remaining match is either historical (the `2026-08-10`/`2026-08-14` Status & History entries and the "Supersedes the earlier … `python-docx` … sketch" note — preserved verbatim) or updated prose. No live "deferred" claim about DOCX remains outside the historical entries.

- [ ] **Step 2: Close ADR-081's Review-Trigger item**

In `docs/architecture/decisions/ADR-081-export-pipeline-typst.md`, in the Review Trigger checklist, replace:

```
- [ ] When DOCX or other formats are needed → add a renderer (pandoc-backed);
      feature-spec change, not an engine decision.
```

with:

```
- [x] ~~When DOCX or other formats are needed → add a renderer (pandoc-backed);
      feature-spec change, not an engine decision.~~ **Done 2026-08-17 (C3):**
      `PandocDocxRenderer` + the committed manuscript-format `reference.docx`
      (`--reference-doc`), golden `document.xml` test. Engine decision
      unchanged — closed per this ADR's own out-of-scope note (no re-open).
```

- [ ] **Step 3: Add the CURRENT_STATE entry**

In `docs/_shared/CURRENT_STATE.md`, add a new dated entry ABOVE the current top entry (the 2026-08-16 C2 drift-persistence entry), following the file's established single-paragraph style:

```markdown
Date: 2026-08-17 (**C3 — DOCX Export — implemented**; program item §6 of the [Post-Export Follow-ups program](superpowers/specs/2026-08-14-post-export-followups-design.md); plan [2026-08-17-c3-docx-export.md](superpowers/plans/2026-08-17-c3-docx-export.md)). IO-001 ships its fourth format: **DOCX in the classic publishing manuscript format** via pandoc `--reference-doc` (binding §6.1 — Times 12 pt, 1.5 line spacing, 0.5″ first-line indent on every paragraph, centred Heading2 chapter headings, Times 14 pt title page). New RULE-08 adapter `PandocDocxRenderer` (`export/renderers/pandoc_docx.py`, same seam as PDF/EPUB/MD: structural `ManuscriptRenderer`, `run_pandoc` helper, cached availability probe, graceful binary-absence degradation), registered in `dependencies.get_export_renderers` + the runner's `_resolve_runner_deps`; `ExportFormat.DOCX` enum member; **no DocxOptions model — zero v1 options by design** (no template toggle, §11 YAGNI; isbn/description stay EPUB-only); no `--toc` (submission-manuscript convention). New pandoc vendor area `apps/api/narrare/export/pandoc/` (mirrors `typst/`): committed binary `reference.docx` produced by `scripts/generate_reference_docx.py` (pure-stdlib zipfile+xml.etree patch of pandoc's default reference — schema-ordered style insertions; deterministic zip: fixed 1980-01-01 timestamps + sorted entries; the script never spawns pandoc — RULE-08 clean; provenance + regeneration in the vendor README). **Golden verification (§6.2/§12):** `tests/golden/export/test_docx_golden.py` — empirically `word/document.xml` is byte-deterministic under a fixed `--reference-doc` (pandoc 3.10.1: only `docProps/core.xml` timestamps vary; no rsids/dates in document.xml) → golden compares the EXTRACTED entry's sha256 against `baselines/docx-manuscript.json` with NO normalization beyond extraction (`--golden-update` regeneration path); plus two-render determinism probe, content assertions (Title/Heading2 chapters/bookmarks/UTF-8 prose), manuscript-format style assertions on the OUTPUT `styles.xml` (document.xml only references styles — the ruling closing that verification gap), and a generator-reproducibility check pinning committed asset == generator(pandoc default); asset itself pinned by no-pandoc unit tests. Frontend: `ExportFormat` union + `"docx"` (types-parity pinned), fourth format card (`FileType` icon, availability-driven), i18n `format.docx`/`format.docxDescription` en/de/fr. **No new ADR** — ADR-081's own out-of-scope note ("feature-spec change, not an engine decision") applies; its Review-Trigger DOCX item ticked with a dated note. IO-001 spec un-deferred everywhere. No Alembic migration, no DB, no service/router/contract change. §12 gates: golden `document.xml` test ✓, i18n en/de/fr ✓, RULE-08 checker ✓.
```

- [ ] **Step 4: Update the features INDEX changelog**

In `docs/features/INDEX.md`, replace the head of the long "Last updated" note (line starting `> Last updated: 2026-08-15 — SERIES-005 …`):

```
> Last updated: 2026-08-15 — SERIES-005 (Series Export) retired as YAGNI
```

with a new head prepended and the old head demoted to "Prior" (keep the ENTIRE existing text after the old date verbatim):

```
> Last updated: 2026-08-17 — IO-001 gains **DOCX** (C3 of the post-export-followups program: fourth export format — pandoc `--reference-doc` manuscript format [Times 12 pt, 1.5 spacing, first-line indent, centred chapter headings], golden `document.xml` test; plan 2026-08-17-c3-docx-export.md; ADR-081 review-trigger item closed, no new ADR). Prior 2026-08-15 — SERIES-005 (Series Export) retired as YAGNI
```

- [ ] **Step 5: Run the slice-final gates**

Run, in order:

```bash
just check-architecture
just typecheck
just lint-check
just test-unit
just test-integration
cd packages/web && pnpm type-check && pnpm lint:check && cd ../..
just test-frontend
```

Expected: PASS on every gate. Additionally verify the design §12 C3 gates are covered by named tests (they are, by construction): golden `document.xml` test — `tests/golden/export/test_docx_golden.py::TestGoldenDocumentXml::test_document_xml_matches_committed_baseline`; i18n keys en/de/fr — Task 5's three files (parity hook-enforced); RULE-08 checker green — `just check-architecture` (first command).

- [ ] **Step 6: Commit (via Platform, verbatim)**

```bash
git add docs/features/io/IO-001-export.md \
        docs/architecture/decisions/ADR-081-export-pipeline-typst.md \
        docs/_shared/CURRENT_STATE.md \
        docs/features/INDEX.md
```

Commit message:

```
docs(io): C3 closure — IO-001 DOCX shipped, ADR-081 review trigger, CURRENT_STATE

C3 (design §6): documents the DOCX export slice.

- IO-001: DOCX un-deferred everywhere it was a live claim (status line,
  architecture bullet, user options, pipeline stages 2+3, options schema,
  constraints) + a dated Status & History entry. Historical entries
  preserved verbatim.
- ADR-081: Review-Trigger DOCX item ticked with a dated note — closed per
  the ADR's own out-of-scope carve-out ("feature-spec change, not an
  engine decision"); no re-open, RULE-21 row untouched.
- CURRENT_STATE: dated C3 entry (program order C0→C5→C1→C2→C3→…; next C4).
- features INDEX: changelog head notes the fourth format.

Refs: docs/superpowers/specs/2026-08-14-post-export-followups-design.md §6 + §12
```

---

## Self-Review (performed at plan time — findings recorded honestly)

**1. Spec coverage (design §6 binding decisions → tasks):**

| Binding requirement | Task(s) |
|---|---|
| Manuscript format via `--reference-doc`, not plain default, not configurable | 1 (asset + generator), 2 (`--reference-doc` argv, unconditional; no toggle), rulings 1/5 |
| One maintained `reference.docx` (Times 12 pt, 1.5 spacing, first-line indent, centred chapter headings) in the export vendor area | 1 (`apps/api/narrare/export/pandoc/`, committed binary + deterministic generator + README; four properties pinned by unit + golden tests) |
| New `PandocDocxRenderer` (RULE-08 adapter, same seam as PDF/EPUB/MD) | 2 (adapter), 3 (both registration sites) |
| Format option in the existing export UI + i18n (en/de/fr) | 5 (i18n ×3), 6 (type union + card + tests) |
| Verification: golden test on the unzipped `document.xml`, analogous to Golden-Pages | 4 (sha256 baseline + `--golden-update`; determinism probe; + styles/content/reproducibility classes per rulings 2–3) |
| IO-001 feature spec gains the DOCX format; no new ADR | 7 (spec sweep + ADR-081 review-trigger tick + CURRENT_STATE + INDEX) |
| §12 gates: golden test / i18n en/de/fr / RULE-08 checker green | 4 / 5 / 2+3+7 (checker runs per-task + slice-final) |

No gaps found.

**2. Placeholder scan:** every code step carries verbatim code (renderer, generator, all five test files, all frontend edits, all doc replacements); no TBD/TODO/"similar to Task N" shortcuts; commit messages complete.

**3. Type consistency (cross-task names):** `ExportFormat.DOCX`/`"docx"` (T2 enum = T3 dicts = T4 options = T6 union + parity sample); `PandocDocxRenderer` + `_REFERENCE_DOC_PATH` (T2 = T3 import = T4 redirect target pattern); `build_reference_docx(base_docx: bytes) -> bytes` (T1 = T4 import); `_REFERENCE_DOC` resolution `parent.parent / "pandoc" / "reference.docx"` (T2 code = T1 asset location = T4 `_COMMITTED_REFERENCE` cross-check); i18n keys `format.docx`/`format.docxDescription` (T5 = T6 card `labelKey`/`descKey`); `data-testid="format-docx"` (T6 card = T6 tests). The golden baseline JSON keys (`schema_version`, `document_xml_sha256`) match between writer and assertion. Verified consistent.

**4. Empirical basis (probes run 2026-08-17, pandoc 3.10.1, this machine):** (a) `word/document.xml` byte-identical across renders, with and without `--reference-doc` — only `docProps/core.xml` differs (timestamps); (b) the reference's patched styles flow into the output `word/styles.xml` (Normal/BodyText/Heading2/Title verified in rendered output); (c) REVIEW-FIX (2026-08-17, pandoc 3.10.1): the plan-time claim "pandoc accepts the ElementTree-serialized reference" was never true of the plan's code — the throwaway probe had exercised a different, append-based (schema-invalid) insertion path, and the plan's first `_insert_ordered` draft even called the lxml-only `addprevious` (AttributeError on stdlib Elements — CRITICAL review finding, fixed to `parent.insert`); the shipped `_insert_ordered` path has since been executed end-to-end exactly as written in this plan: the generator built the asset from `pandoc --print-default-data-file reference.docx` (10961 bytes), the output re-loaded via zipfile with all 16 XML entries parsed by ElementTree, and two consecutive runs were byte-identical (`REPRODUCIBLE`); (d) `docProps/app.xml`, `custom.xml` stable across runs. One probe artifact corrected at plan time: the throwaway probe inserted `rPr` before `w:name` and `w:jc` after `w:outlineLvl` (schema-invalid order that pandoc happened to tolerate) — the plan's generator uses schema-ordered insertion (`_PPR_ORDER`/`_RPR_ORDER`) so Word cannot reject the reference on element order.

**5. Design-doc discrepancies found during investigation (reported to the coordinator, resolved by the locked rulings in Global Constraints):** (a) the design's anticipated normalization need ("rsid/date metadata") is empirically moot — resolved by the extract-only ruling 2; (b) a `document.xml`-only golden cannot verify the manuscript format (styles live in `styles.xml`) — resolved by adding the styles/content/reproducibility classes (ruling 3); (c) the design names no DOCX options — resolved as zero-options/no-model (ruling 1); (d) TOC policy unstated — resolved no-`--toc` (ruling 4). ADR-081's RULE-21 row lists "adding DOCX" among re-review-triggering deviations while the ADR's own out-of-scope note says the opposite for DOCX specifically — resolved by following the specific carve-out (review-trigger tick, no re-open), documented in Task 7.
