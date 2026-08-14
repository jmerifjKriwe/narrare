# ADR-081 — Manuscript Export Pipeline: Narrare Normalizer + Typst (`narrare-roman`)

> **Status:** ✅ Implemented (2026-08-14; IO-001; PR #163)
> **Date:** 2026-08-10
> **Deciders:** Architecture Agent, Coordinator, User (engine pick)
> **Supersedes:** the PDF approach sketched in `docs/features/io/IO-001-export.md`
> (WeasyPrint / `python-docx` / `ebooklib`) — that section is superseded by this
> ADR's pipeline; IO-001 is updated to point here.
> **Related:** ADR-006 (Tech Stack — adds Typst + pandoc as the export toolchain),
> ADR-080 (in-process execution boundary — export jobs run post-ADR-080),
> ADR-029 (VM-first setup — Typst binary is a deploy-time dependency),
> IO-001 (Manuscript Export — the feature this ADR feeds)

---

## Context

Narrare stores chapter prose as **TipTap HTML** (`Chapter.content: Text`; the
frontend persists via `editor.getHTML()`). That HTML carries four Narrare-specific
custom extensions that are essential to the *editor* but must **never** reach an
*export*:

| Extension | Role in editor | Why it must not export |
|-----------|----------------|------------------------|
| `AIAnnotation` | modify-tracking of AI edits | Editing artifact |
| `GhostText` | inline AI suggestions (ghost text) | Suggestion artifact |
| `SceneBreak` | explicit scene delimiter | Must render as a clean scene break |
| `DialogueMark` | dialogue styling/annotation | Must render as clean dialogue |

Writers need to take a finished manuscript **out** of Narrare as **PDF** (primary —
"sehr hochwertiger" literary Buchsatz), **EPUB** (re-flowable e-book), and
**Markdown** (portable plain text). The export must be **fire&forget**: a writer
exports a novel and gets a correct, book-quality file with **zero per-document
hand-tuning**. DOCX is explicitly **out of scope** for this ADR (pandoc can add it
trivially later; it is not part of the typeset-quality decision).

A three-way **export-engine bake-off** (Typst / SILE / LaTeX+microtype) plus a
**pandoc+community-template fire&forget spike** were run to choose the PDF engine
and the pipeline shape. The evidence lives in disposable spike artifacts under
`_scratch/bake-off/`; this ADR captures the decisions **inline** so it is
self-contained (those scratch files are gitignored and may not persist).

### Decision-relevant evidence (self-contained summary)

**3-way bake-off** — identical reference manuscript (de prose + long compounds +
en/fr dialogue + smart quotes), identical font/measure/Satzspiegel (EB Garamond
11 pt, 96 mm measure, B-format 129×198 mm, mirrored), measured by one harness
(PyMuPDF word-gap / right-edge / protrusion probes):

| Metric | Typst 0.15.1 | SILE 0.15.12 | LaTeX + microtype |
|---|---|---|---|
| inter-word gap **stdev** (grey-value uniformity) | 0.992 pt | 1.106 pt | **0.289 pt** |
| **hardest-compound-line max gap** (Belastungsprobe) | 7.50 pt | 9.64 pt | **3.10 pt** |
| right-edge **max** error | 35.1 pt | 5.85 pt | **2.08 pt** |
| glyph **expansion** (microtype) | no | no | **yes** |
| line-break algorithm | Knuth-Plass | Knuth-Plass | Knuth-Plass |
| PDF text layer / ToUnicode | correct | **f-ligatures broken** (§6.2) | correct |
| render reproducibility | **byte-reproducible** | deterministic (not byte-verified) | **no** (TeX timestamp/cache) |
| toolchain weight | ~15 MB single binary | ~60 MB + ICU/Lua | ~250–600 MB TeX Live + `tlmgr` |

The **one** quality differentiator is **glyph expansion**, which only LaTeX has —
it holds the compound-heavy Belastungsprobe at 3.10 pt vs Typst's 7.50 pt and
drives the 3.4–3.8× tighter grey-value stdev. The line **breaker is a tie at the
Knuth-Plass class** across all three; the gap to LaTeX is the post-breaking
refinement layer (expansion), not the breaker. Protrusion was found **marginal**
(SILE posts the lowest right-edge mean with *no* protrusion at all).

**pandoc + community-template spike** (Bergfink Typst / Eisvogel LaTeX) was
**empirically refuted** as a fire&forget book shortcut: both are general/lecture-
notes document templates — A4, no drop cap, no recto chapter starts, no mirrored
Satzspiegel, no frontmatter roman→arabic, silent font fallback (Eisvogel ships a
**sans-serif** body by default). Reaching a book means re-authoring the template,
i.e. the bespoke work, plus ~25-package iterative install friction (LaTeX) /
network deps + silent font fallback (Typst). Conclusion: *"pandoc+template
relocates hand-tuning, it doesn't remove it."*

**Community Typst templates evaluated** for *patterns to borrow* (not forks —
re-implemented in a bespoke package): `folklore` (EB Garamond default, literary
smallcaps aesthetic, `major-break` scene ornament), `tieffiction` (TiefLang i18n,
header/footer presets, 4-phase röm→arab numbering model — *strongest functional
base*), `wonderous-book` (`is-page-empty` blank-page header suppression — the
cleanest blank fillers). **None ships a drop cap** (all four rendered `[Drop cap …]`
as literal text) and none was adopted wholesale. The spike also surfaced three
**render-confirmed seam bugs** (F-1/F-6/F-7) baked into this ADR's pipeline.

---

## Decision Drivers

- **Fire&forget robustness** — a writer exports and gets a correct book with no
  per-document tuning; a bespoke, owned template is the only way to guarantee this.
- **"Sehr hochwertig" bar (~95%)** — the user set the quality bar at ~95% of best-
  in-class, explicitly accepting slightly looser compound-heavy German to avoid
  LaTeX's ~300–600 MB footprint + maintenance fragility.
- **Reproducibility & deploy weight** — Typst is a single ~15 MB static binary and
  produces **byte-reproducible** PDFs (decisive for a CI acceptance test and for a
  local-first self-hosted product per ADR-029).
- **Search/copy accessibility** — the exported PDF must be reliably searchable and
  copy-pasteable; a broken text-layer ToUnicode (SILE's f-ligature defect) is
  disqualifying for an export *product*.
- **RULE-08 (external integrations abstracted)** — Typst and pandoc are external
  binaries; each must live behind a dedicated adapter.
- **RULE-03 (contract-first)** — the normalizer, the export service, the renderers,
  and the Typst package's config keys must all be Protocols/contracts before
  implementation.
- **RULE-11 (no silent failures / graceful degradation)** — missing Typst/pandoc
  binaries must degrade gracefully, never silently produce a wrong-font fallback.
- **RULE-20 (no half-implementations)** — the bespoke template must be hardened by a
  repeatable acceptance test; bespoke templates can corrupt content unattended.

---

## Options Considered

### Option A — LaTeX + microtype (best measured quality)

Highest body quality (glyph expansion: gap stdev 0.289, hardest line 3.10 pt,
right-edge max 2.08 pt); mature furniture (`scrbook` + `scrlayer-scrpage` +
`lettrine`); genuine protrusion.

**Pros:** Measurably the best typesetting; the only engine that dissolves the
compound-German rivers via glyph expansion.

**Cons:** ~300–600 MB TeX Live footprint + `tlmgr` maintenance/fragility;
**non-reproducible** output (TeX embeds build timestamps / font-cache state →
differing bytes run-to-run, which also weakens a byte-stable CI acceptance test);
pre-1.0-fragile-adjacent ecosystem (annual TeX Live freezes). Four multimodal AIs
split 2:2 on whether this is "worth ~10–20× the footprint".

### Option B — SILE

Knuth-Plass-class breaking; lowest right-edge mean error (0.077 pt); full Lua
programmability.

**Pros:** Hackable/extensible; clean flush right edge without protrusion.

**Cons:** **DISQUALIFIED** — f-ligature ToUnicode text-layer defect: copy/search of
`fi`/`fl` words ("find"→`ϥnd`, "Flame"→`Ϩame`) yields Greek-block garbage because the
PDF back-maps ligature glyph IDs to placeholder codepoints. For a literary tool
whose PDFs readers search and copy, this is unacceptable. (Also shipped an empty TOC
via a package bug and the loosest worst-line at 9.64 pt.)

### Option C — Typst, via a bespoke `narrare-roman` package (chosen)

Knuth-Plass-class breaking, no glyph expansion, no genuine protrusion — ~95% quality
tier. Rendered via `pandoc --to=typst --shift-heading-level-by=-1` → a **thin Narrare
wrapper** (imports the bespoke `narrare-roman` package + feeds the pandoc-generated
body) → Typst compiles PDF. EPUB + Markdown via pandoc from the normalized form.

**Pros:** Single ~15 MB static binary; **byte-reproducible** output (enables a
deterministic CI acceptance test); fast deterministic builds; correct PDF text
layer; a small, single-purpose, *owned* Typst library gives full control over every
book feature (recto chapter starts, mirrored Satzspiegel, running heads, 4-phase
numbering) with zero community-template dependency; the three validated seam-fixes
(F-1/F-6/F-7) make the pipeline render-confirmed.

**Cons:** No glyph expansion → compound-heavy German lines stretch to ~7.5 pt (rivers)
where LaTeX holds ~3.1 pt (the accepted ~5–10% quality gap); Typst is **pre-1.0**
(v0.15.x) → breaking changes possible on majors (mitigated by exact version pin +
Golden-Pages test); bespoke templates can harbor content-corruption bugs unattended
(mitigated by the mandatory Golden-Pages Acceptance Test).

### Option D — pandoc + community template as a fire&forget shortcut

Use pandoc with a community book template (Bergfink Typst / Eisvogel LaTeX).

**Pros:** Minimal bespoke authoring.

**Cons:** **Empirically refuted** (see Context). Both are general/lecture-notes
document templates lacking every literary-book feature; ~25-package iterative
install friction (LaTeX) / network deps + silent font fallback (Typst); they add no
typesetting quality beyond what the underlying engine already provides (protrusion/
expansion are engine-inherited, not template-inherited). *"Relocates hand-tuning,
doesn't remove it."*

### Option E — bespoke-per-engine templates (custom IR + Typst + LaTeX + …)

Build a Narrare intermediate representation and a bespoke template per engine.

**Pros:** Maximum per-engine quality.

**Cons:** Excessive maintenance for a feature whose bar is ~95%, not best-in-class.
pandoc's AST already serves as the intermediate representation; one bespoke Typst
template reaches the bar. Rejected as over-engineering.

### Option F — `pandoc --template=` mechanism

Drive Typst/LaTeX output via pandoc's native `--template=`.

**Pros:** Single pandoc invocation.

**Cons:** **Unhandy for complex book layouts** — pandoc templates are general-
document oriented and cannot express recto chapter starts, mirrored Satzspiegel, or
4-phase numbering cleanly. The thin-wrapper approach (`pandoc --to=typst` + own
wrapper) is more direct and was render-confirmed.

---

## Decision

**We choose Option C — Typst via a bespoke `narrare-roman` package.**

The export pipeline is a **deterministic, non-LLM** render pipeline (no
`RULE-01b`/`RULE-02`/`RULE-02b`/`RULE-13` concern — export never calls an LLM and
never builds a prompt). It is a four-stage pipeline, with only **stage 1 being
Narrare-specific** and everything downstream generic:

```
TipTap HTML
   │
   ▼  [1] Narrare Normalizer  (Core, pure, no I/O)
   │     strip AIAnnotation + GhostText
   │     normalize SceneBreak → explicit scene break
   │     normalize DialogueMark → clean dialogue
   │     → clean semantic HTML / Markdown
   ▼
   │  [2] pandoc  (HTML → target AST: typst | epub | markdown)
   │     with baked-in seam-fixes F-1/F-6/F-7
   ▼
   │  [3] Format renderer  (RULE-08 adapter per external tool)
   │     PDF  → Typst + narrare-roman package (thin Narrare wrapper)
   │     EPUB → pandoc (EPUB3, EPUBCheck-validated)
   │     MD   → pandoc
   ▼
   [4] Delivery  (artifact → signed download URL → client)
```

### The validated PDF pipeline (render-confirmed)

`pandoc --to=typst --shift-heading-level-by=-1` produces the Typst body; a **thin
Narrare wrapper** (`#import`-ing `narrare-roman` and feeding the pandoc body) is the
entry point Typst compiles. This is **not** the `pandoc --template=` mechanism
(Option F, rejected).

**Three baked-in seam-fixes** (discovered empirically; must never regress):

- **F-1** — `--shift-heading-level-by=-1`. Without it, manuscript `## CHAPTER n`
  renders as a flat section; with it, chapters become level-1 openers (recto
  pagebreak, ToC entry).
- **F-6** — escape `\@` in any prose content block. Typst parses bare
  `@preview/…` as a *reference to a label* `<preview>` and errors. The wrapper must
  escape literal `@` in prose.
- **F-7** — pass `author` as a **scalar string**, never an array. (Surfaced as a
  tieffiction header-stringification bug; generalized as a rule: **all metadata
  passed to the wrapper is scalar strings**.)

### The `narrare-roman` package

A **small, single-purpose, owned Typst library** — **not a fork** of any community
template. It re-implements (borrows patterns from, not copies of):

- `wonderous-book`'s **`is-page-empty`** blank-page header-suppression (the cleanest
  blank-fillers observed);
- `tieffiction`'s **4-phase numbering** (frontmatter römisch → body arabisch) +
  header/footer presets;
- `folklore`'s **`major-break`** scene-break ornament.

**Aesthetic direction: clean / minimal / official** (the user's `wonderous-book`
preference), **not** the smallcaps-heavy literary look. Book features: recto chapter
starts + blank verso; mirrored Satzspiegel (inside/outside); running heads
recto≠verso, suppressed on chapter openers and blank pages; TOC; frontmatter römisch
→ body arabisch; justified body; per-language (de/en/fr) smart quotes + hyphenation;
widow/orphan protection; configurable B-format (**129×198 mm default**).

**Drop caps: OPTIONAL, default OFF** ("die mag nicht jeder") via the
`@preview/droplet` package when enabled.

**Font: Libertinus Serif, bundled** (OFL) — for reproducible output with **no silent
font fallback** (the spike's headline fire&forget failure was templates silently
falling back to the wrong font). EB Garamond was the *bake-off comparison font* only;
Libertinus Serif is the *production font*. License: **OFL** — confirm at vendoring.

### EPUB + Markdown

pandoc, from the normalized form. EPUB3, validated by **EPUBCheck**. Markdown via
pandoc. (pandoc is robust fire&forget for these simpler formats — validated.)

### Execution model (post-ADR-080)

Export is an **off-request job** — PDF compile + normalization of large manuscripts
is CPU-bound. Following **ADR-080's in-process execution boundary**, the job is
dispatched via `asyncio.create_task` (process-lifetime; in-flight export lost on
restart — acceptable for a regenerable artifact; RULE-11: logged, not silent).
Typst and pandoc run as **subprocesses** (naturally off the event loop to OS
processes); the **Narrare Normalizer** runs in-process — for a 500-page manuscript
that proves to bottleneck the event loop, escalate normalization to a
`ProcessPoolExecutor` via `loop.run_in_executor(...)`. That escalation is the
**documented contingency**, not the default. Each job builds its own DB session
(never the request session), mirroring ADR-080's task-wrapper pattern.

### Quality gate — Golden-Pages Acceptance Test

Because bespoke templates can harbor content-corruption bugs unattended (the spike
showed drop-cap collisions, dropped quotes, ragged paragraphs in community
templates), the `narrare-roman` package **must** be hardened by a repeatable
**Golden-Pages Acceptance Test** run in CI. A defined set of "golden pages" —
normal de prose; long-compound stress (Belastungsprobe); de/en/fr mixed dialogue;
chapter opener (with optional drop cap); scene break — rendered on a **varied
corpus** and checked both **visually and objectively** (byte/folio/running-header/
right-edge/text-layer regressions via the same PyMuPDF harness proven in the bake-
off). This test **is** the fire&forget robustness assurance.

### Version discipline

Typst is **pre-1.0** (v0.15.x). **Pin Typst exact version**; pin pandoc; pin the
`narrare-roman` package + `@preview/droplet` (when drop caps are enabled). Plan
migration effort on Typst majors. The Golden-Pages test is the regression net across
version bumps.

---

## Rationale

The root-cause chain (minimum 2× Why):

1. **Symptom:** A writer needs a book-quality PDF out of Narrare with no hand-tuning.
2. **Why must it be hand-tuning-free?** Because a community template + manual
   configuration is exactly the "relocated hand-tuning" the spike refuted — and a
   local-first, single-user product cannot rely on silent font fallback or 25-package
   install loops.
3. **Why Typst and not LaTeX?** The user's bar is ~95% ("sehr hochwertig"), not best-
   in-class. LaTeX's quality lead (glyph expansion) buys the last 5–10% on compound-
   heavy German at the cost of ~300–600 MB footprint + non-reproducible output + TeX
   maintenance — a trade the user explicitly declined. Typst reaches the bar, is
   byte-reproducible (decisive for the CI acceptance test), and is a single ~15 MB
   binary.
4. **Why Typst and not SILE?** SILE is disqualified by an output defect (broken
   f-ligature ToUnicode) that breaks PDF search/copy — unacceptable for an export
   product.
5. **Why a bespoke package and not a community template?** Fire&forget requires
   owning every book feature. The spike proved community templates are general-
   document skeletons lacking all literary-book features, with silent font fallback.
   A bespoke, owned `narrare-roman` package is the only way to guarantee a correct
   book unattended — and borrowing *patterns* (not forks) from the three evaluated
   templates avoids re-deriving the hard bits (`is-page-empty`, 4-phase numbering,
   `major-break`).

This is the **simplest *correct*** solution: one bespoke Typst template reaches the
~95% bar, reuses pandoc as the intermediate (no custom Narrare IR), and is hardened
by a repeatable acceptance test. The accepted cost (no glyph expansion; pre-1.0
Typst) is bounded and explicit (next section).

---

## Consequences

**Positive:**

- A **fire&forget** book export: writers get a correct, book-quality PDF/EPUB/MD with
  no per-document tuning.
- **Byte-reproducible** PDFs → deterministic CI acceptance test + cacheable artifacts.
- Single ~15 MB Typst binary + pandoc → small deploy footprint (fits ADR-029 VM-first).
- The normalizer is the **only** Narrare-specific code; everything downstream is
  generic and swappable.
- pandoc's AST as the intermediate → no custom Narrare IR to maintain.
- Clean RULE-08 layering: each external tool behind a dedicated renderer adapter.

**Negative / Trade-offs:**

- **~95% body quality (no glyph expansion)** — visible on compound-heavy German
  (worst lines stretch to ~7.5 pt vs LaTeX's ~3.1 pt). **Accepted** by the user; the
  last 5–10% is not worth LaTeX's cost to this product.
- **Typst pre-1.0 (v0.15.x)** — breaking changes possible on majors. Mitigated by
  exact version pin + Golden-Pages regression test + planned migration effort.
- **`narrare-roman` must be hardened** — bespoke templates can corrupt content
  unattended. Mitigated by the mandatory Golden-Pages Acceptance Test on a varied
  corpus.
- **Two new external binaries** (Typst, pandoc) become deploy-time dependencies
  (TECH_STACK update required at implementation; the renderer adapters degrade
  gracefully if absent — RULE-11).
- **In-flight export lost on restart** (ADR-080 in-process boundary). Acceptable:
  export is regenerable, non-destructive (the project is never modified).

**Constraints introduced / touched:**

- **RULE-08** — Typst and pandoc are external integrations; each confined to a
  dedicated renderer adapter. No direct `subprocess.run([... typst ...])` outside the
  Typst renderer; no direct pandoc invocation outside the pandoc renderer.
- **RULE-03** — Protocols sketched below must be defined in `contracts.py` before
  implementation.
- **RULE-11** — missing Typst/pandoc binaries degrade gracefully (the export feature
  reports unavailable, never silently produces a wrong-font / missing-font fallback).
- **RULE-20** — the bespoke template + acceptance test are mandatory, not optional.

---

## Contract Sketches (RULE-03 — full definitions at implementation kickoff)

> These are **sketches**. The Backend Specialist writes the actual `contracts.py`
> at implementation kickoff, against these signatures. Locations are *indicative*;
> the feature spec (IO-001 update) finalizes exact paths.

### `ManuscriptNormalizer` — Core, pure (no I/O)

Home: `packages/core/narrare_core/export/normalizer.py` (+ contract in
`packages/core/narrare_core/export/contracts.py`). Pure transformation — testable
without any subprocess.

```python
class NormalizedManuscript(BaseModel):
    """Clean semantic form of a manuscript, free of editor artifacts."""
    semantic_html: str          # AIAnnotation + GhostText stripped; SceneBreak/DialogueMark normalized
    title: str                  # scalar string (F-7)
    author: str                 # scalar string (F-7)
    language: Language          # primary language; per-span langs carried inline
    chapters: list[ChapterMeta] # ordering + per-chapter metadata


class ManuscriptNormalizer(Protocol):
    """TipTap HTML → clean semantic HTML/Markdown.

    Guarantee: AIAnnotation and GhostText NEVER pass through. This is asserted
    by a unit test for every custom TipTap mark (RULE-03 + the Golden-Pages test).
    """
    async def normalize(
        self,
        raw_tiptap_html: str,
        metadata: ManuscriptMetadata,
    ) -> NormalizedManuscript: ...
```

### `ExportService` — API feature layer (the RULE-12 public API)

Home: `apps/api/narrare/export/contracts.py` + `service.py`. Consumable by all four
clients (WebUI download, MCP, A2A, CLI).

```python
class ExportFormat(StrEnum):
    PDF = "pdf"
    EPUB = "epub"
    MARKDOWN = "md"

class ExportJob(BaseModel):
    job_id: str
    novel_id: UUID
    format: ExportFormat
    status: ExportJobStatus          # pending | running | completed | failed
    artifact_url: str | None         # signed download URL when completed
    created_at: datetime

class ExportService(Protocol):
    """The only public API for manuscript export (RULE-12)."""
    async def export(
        self,
        novel_id: UUID,
        format: ExportFormat,
        options: ExportOptions,
    ) -> ExportJob: ...
    async def get_job(self, job_id: str) -> ExportJob: ...
```

### `ManuscriptRenderer` — RULE-08 adapters (one per external tool)

Home: `apps/api/narrare/export/renderers/`. Each renderer is the **sole** place its
external binary is invoked.

```python
class ManuscriptRenderer(Protocol):
    """Render a normalized manuscript to one format. RULE-08: the external
    binary (Typst / pandoc) is invoked ONLY inside its renderer."""
    async def render(
        self,
        manuscript: NormalizedManuscript,
        options: ExportOptions,
    ) -> Artifact: ...

# Implementations (each behind its own adapter file):
#   TypstPdfRenderer     — apps/api/narrare/export/renderers/typst.py
#   PandocEpubRenderer   — apps/api/narrare/export/renderers/pandoc_epub.py
#   PandocMarkdownRenderer — apps/api/narrare/export/renderers/pandoc_md.py
```

### `NarrareRomanConfig` — the Typst package config contract

This is **not** a Python Protocol (the `narrare-roman` package is a Typst artifact),
but its **config keys are a stable contract** so the Backend renderer and the Typst
package stay decoupled. The TypstPdfRenderer builds this config and feeds it to the
wrapper; changing a key is a contract change requiring a coordinated update.

```python
class NarrareRomanConfig(BaseModel):
    paper_size: PaperSize = PaperSize.B_FORMAT_129_198   # 129×198 mm default
    margins: MirroredMargins                              # inside/outside/top/bottom
    body_font: str = "Libertinus Serif"                   # bundled, OFL
    body_size_pt: float = 11.0
    leading_ratio: float = 1.2
    language: Language                                    # primary; per-span langs inline
    title: str                                            # scalar string (F-7)
    author: str                                           # scalar string (F-7)
    drop_caps: bool = False                              # OPTIONAL, default OFF
    # … TOC on/off, running-head preset, scene-break style, widow/orphan on
```

---

## RULE-XX Compliance

| Rule | Status | Nachweis |
|------|--------|----------|
| RULE-03 | ✅ | `ManuscriptNormalizer`, `ExportService`, `ManuscriptRenderer` Protocols + `NarrareRomanConfig` sketched here; full definitions in `**/contracts.py` before implementation. The normalizer's strip-guarantee (AIAnnotation/GhostText never pass through) is asserted by a unit test per custom TipTap mark. |
| RULE-04 | ✅ | Normalizer (pure Core) split from renderers (I/O adapters) split from service — one responsibility per file; no file grows past limits. |
| RULE-05 | ✅ | Core normalizer (`packages/core/narrare_core/export/`) owns pure transformation; API feature (`apps/api/narrare/export/`) owns service + renderers + router; `narrare-roman` Typst package is a vendored Typst artifact. No cross-`_internal` imports. |
| RULE-06 | ✅ | Router delegates immediately to `ExportService`; service dispatches to renderers; renderers invoke their external binary. No business logic in the router. |
| RULE-07 | ✅ | `router → service → renderer → external binary`. The pure Core normalizer never imports `apps/`. Dependency direction one-way. |
| RULE-08 | ✅ | Typst and pandoc are external integrations; **each confined to a dedicated renderer adapter**. No `subprocess`/pandoc call outside its renderer. Missing binaries degrade gracefully (RULE-11). |
| RULE-09 | ✅ | All public methods on the Protocols are fully type-annotated; `NarrareRomanConfig` is a typed Pydantic model. |
| RULE-10 | ✅ | Unit tests for the normalizer (strip-guarantee per mark); integration tests for each renderer; the Golden-Pages Acceptance Test is the cross-format regression gate in CI. |
| RULE-11 | ✅ | Missing Typst/pandoc → export reports unavailable (never a silent wrong-font fallback, the spike's headline failure). Lost-job-on-restart is logged, not swallowed. Per-job errors convert to typed `ExportError`. |
| RULE-12 | ✅ | `ExportService` is the sole public API; consumable by WebUI / MCP / A2A / CLI. A new client = a new adapter, no service change. |
| RULE-13 | N/A | Export is a deterministic render job, **not an LLM operation** — the streaming/non-streaming LLM contract does not apply. Progress reporting is via job status (RULE-12 API), not via the LLM streaming path. |
| RULE-14 | ⚠️ | Conditional. v1 jobs are process-lifetime (ADR-080) and artifacts are temp files → likely **no** DB model. **IF** a job/artifact DB model is introduced, the Alembic migration + regression test are created in the same task. |
| RULE-20 | ✅ | No half-implementation: the bespoke template + Golden-Pages test + graceful binary-absence degradation are all mandatory from day one. |
| RULE-21 | ✅ | This ADR *is* the architecture review of the export plan; material deviations (e.g. switching engine, adding DOCX, introducing a job DB model) require re-review. |
| RULE-22 | ✅ | Export *reads* chapter/KB/novel data owned by other features (read-only). The normalizer consumes `Chapter.content` (TipTap HTML) — a read-only cross-feature dependency; export never modifies the source. No new `LLMIntent`/prompt is introduced (deterministic feature). |

**Note (RULE-01b/02/02b):** export is a **non-LLM, non-prompt** feature. No `pydantic_ai.Agent`, no LLM call, no `PromptComposer`, no `LLMIntent`. These rules do not apply and are deliberately not listed as violations — they simply have no jurisdiction over a deterministic render pipeline.

---

## Sustainability Check

1. **Correct in 3 months?** Yes — as long as the ~95% bar holds (user-confirmed) and
   Typst's pinned version is honoured. The Golden-Pages test catches regressions on
   any Typst/pandoc/`narrare-roman` change.
2. **Hard-to-undo coupling?** Low. The renderer adapters are the swap seam (a future
   LaTeX renderer or a DOCX renderer is a new adapter, no service change). The
   normalizer is pure Core with a strip-guarantee contract. `narrare-roman` config
   keys are the only Typst↔Python coupling, isolated behind `NarrareRomanConfig`.
3. **Simplest correct solution?** Yes — one bespoke Typst template + pandoc as the
   intermediate (no custom IR) reaches the bar; Option E (bespoke-per-engine) and
   Option A (LaTeX) are over-engineered/beyond-bar for this product.
4. **Design intent clear?** Yes — this ADR records the engine pick, the validated
   pipeline + seam-fixes, the contract sketches, and the Golden-Pages verification.

---

## Implementation Notes

- **TECH_STACK.md update (implementation-time follow-up, flagged to Coordinator):**
  ADR-006 / TECH_STACK.md gains a new **"Export Toolchain"** section recording Typst
  (exact pin, pre-1.0 v0.15.x), pandoc (pin), `@preview/droplet` (optional, drop
  caps), and the **bundled Libertinus Serif (OFL)** font. The binaries are deploy-
  time dependencies per ADR-029 (VM-first setup contract). This doc update is **not**
  done in this ADR (it is a material TECH_STACK change tied to actually adding the
  deps); it is the first implementation task.
- **`narrare-roman` vendoring location:** a vendored Typst artifact loaded by the
  TypstPdfRenderer (exact path finalized in the IO-001 feature spec). It is
  version-controlled (pinned), not fetched at render time (no network dependency —
  the spike's Bergfink network-fetch friction is avoided).
- **Seam-fixes are load-bearing:** F-1/F-6/F-7 must never regress — they are
  asserted by Golden-Pages + normalizer/renderer unit tests. The wrapper escapes
  literal `@` in prose (F-6) and passes all metadata as scalar strings (F-7).
- **Libertinus license:** OFL — **confirm** at vendoring and record the license file.
- **Golden-Pages corpus:** a committed, varied manuscript corpus under
  `tests/` (or a dedicated fixtures dir); CI renders the golden pages and asserts
  byte/folio/running-header/right-edge/text-layer invariants via the PyMuPDF harness
  proven in the bake-off.
- **EPUB validation:** EPUBCheck is a CI gate for the EPUB renderer.
- **Async execution:** `asyncio.create_task` (ADR-080); Typst/pandoc are subprocesses
  (off the event loop); normalizer in-process with `ProcessPoolExecutor` escalation
  as the documented contingency for 500-page manuscripts.
- **`check_architecture.py` impact:** adding the export package does not relax any
  RULE-XX checker. The RULE-08 confinement (Typst/pandoc subprocess calls only inside
  their renderer adapters) is enforceable by AST scan if deemed worthwhile at
  implementation — record as an optional checker follow-up, not a blocker.
- **DOCX is out of scope** for this ADR. pandoc can add DOCX trivially later (the
  normalized form + pandoc already produce it); such an addition is a feature-spec
  change, not an engine decision, and does not require re-opening this ADR.

**ADR Implementation Completeness Gate (Gate 12):** before marking this ADR
"✅ Implemented", verify all items in the Gate 12 checklist at
`.opencode/context/narrare-dev/processes/quality-gates.md`. "Implemented" here means:
normalizer + strip-guarantee tests, all three renderers, `narrare-roman` with all
book features, Golden-Pages test green in CI, EPUBCheck green, graceful binary-
absence degradation, and the TECH_STACK update landed.

---

## Review Trigger

- [ ] When Typst reaches **1.0** (or a breaking major) → re-pin, re-run Golden-Pages,
      plan migration; revisit whether the bar can be raised.
- [ ] When a user reports compound-German quality below the accepted ~95% bar →
      revisit Option A (LaTeX) as an opt-in high-quality renderer behind the same
      `ManuscriptRenderer` adapter.
- [ ] When export of a 500-page manuscript bottlenecks the event loop → activate the
      `ProcessPoolExecutor` normalizer escalation (documented contingency).
- [ ] When multi-user/multi-worker deployment returns (ADR-080 re-introduction) →
      move export jobs off the in-process boundary via a new ADR superseding the
      relevant ADR-080 seam.
- [ ] When DOCX or other formats are needed → add a renderer (pandoc-backed);
      feature-spec change, not an engine decision.
