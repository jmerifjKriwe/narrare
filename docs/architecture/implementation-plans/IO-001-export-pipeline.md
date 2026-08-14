# IO-001 — Manuscript Export Pipeline: 10-Slice Implementation Plan

> **Type:** Implementation plan (companion to ADR-081). NOT an ADR.
> **Author:** Architecture Specialist
> **Date:** 2026-08-10
> **Branch:** `feat/io-001-export-pipeline`
> **Decision ADR:** `docs/architecture/decisions/ADR-081-export-pipeline-typst.md`
> **Feature spec:** `docs/features/io/IO-001-export.md`
> **Status:** ✅ Executed (Slices 0–8 landed; 5g drop cap deferred as fast-follow; PR #163)
> **Related:** ADR-006 (Tech Stack — adds the Export Toolchain section drafted here),
> ADR-080 (in-process execution boundary — export jobs register in the drain),
> ADR-029 (VM-first — Typst/pandoc are deploy-time deps), IO-001 (feature).
> **RULE-XX in force:** RULE-03/04/05/06/07/08/10/11/12/14/16/17/20/22.

This plan executes ADR-081. It finalizes the contract sketches from the ADR into
real Python signatures (RULE-03), designs the in-memory job registry, the
renderer adapter boundary (RULE-08), the bespoke `narrare-roman` Typst package
layout, the Golden-Pages Acceptance Test, and the binary-provisioning path, then
slices the work into 10 complete increments (Slices 0–9).

**Invariant after every slice:** the full test suite (`just verify`),
`scripts/check_architecture.py`, `pyright`, and the frontend typecheck/build are
green. No slice is "done" until green. No `git commit` is performed by this
author — the Platform Specialist commits per slice (one commit per slice
boundary).

**Scope guard (RULE-20):** the pipeline is complete only when (a) the Narrare
Normalizer strips every custom TipTap mark (asserted per mark), (b) all three
renderers (Typst PDF, pandoc EPUB, pandoc Markdown) produce validated output,
(c) `narrare-roman` implements every book feature in its scope floor, (d) the
Golden-Pages test is green in CI, (e) EPUBCheck is green in CI, (f) the binaries'
absence degrades gracefully (RULE-11), and (g) the TECH_STACK "Export Toolchain"
section has landed. That completeness check is Slice 9.

**Non-LLM feature confirmation (call-out for implementers):** export is a
**deterministic render pipeline**. It makes **no** LLM call, builds **no** prompt,
and defines **no** `LLMIntent`. RULE-01b/02/02a/02b/13 have **no jurisdiction**
here — do **not** reach for the agent pattern (`ModelRegistry`, `PromptComposer`,
`NarrareAgent`) anywhere in `packages/core/narrare_core/export/` or
`apps/api/narrare/export/`. Importing `narrare_core.agents` or
`narrare_core.prompts` from the export package is a layering bug, not a shortcut.
The only cross-feature dependency is **read-only** access to `Chapter.content`
(TipTap HTML) + novel metadata (RULE-22 — read-only, never modifies the source).

---

## Execution-Boundary Summary (what changes, semantically)

| Concern | Before | After |
|--------|--------|-------|
| Chapter export | (none — manuscript is locked in Narrare) | TipTap HTML → Narrare Normalizer → pandoc AST → renderer → artifact → signed-token download |
| LLM dependency | (features depend on the agent pattern) | **None.** Export is a non-LLM deterministic pipeline (call-out above) |
| Job execution | ADR-080 pattern: `asyncio.create_task` + `_INFLIGHT_TASKS` GC guard in `kb/embedding_hooks.py`, `series/tasks.py` | + `apps/api/narrare/export/tasks.py` mirroring that pattern; registered in `_DRAIN_SOURCES` |
| Artifact delivery | (none) | Temp file + single-use/TTL signed token via `GET /api/v1/export/jobs/{job_id}/artifact?token=…` |
| External binaries | (none in the export path) | Typst + pandoc (production render binaries, each confined to its renderer adapter — RULE-08, AST-enforced D6) + EPUBCheck (CI-only, invoked from the test harness — NOT a renderer adapter) |
| DB schema | — | **Unchanged.** v1 is in-memory jobs + temp-file artifacts (RULE-14 conditional → resolved "none"; no Alembic migration) |
| Frontend | (no export surface) | Export panel (format + options, job polling, download); i18n en/de/fr |
| Deploy image | Python + Node only | + Typst binary, pandoc binary, vendored `narrare-roman` + Libertinus Serif (OFL) |
| CI | (no render tests) | + toolchain install step + Golden-Pages job + EPUBCheck gate |

---

## Resolved Implementation Decisions (user-approved — baked in, NOT re-litigatable)

These five decisions were resolved before this plan was written. They are
**inputs**, not open questions. Any deviation requires Coordinator escalation +
re-review (RULE-21).

### D1 — Job/artifact persistence: IN-MEMORY (no DB model in v1)

- Jobs live in a module-level dict, process-lifetime (ADR-080 boundary).
- Artifacts are temp files served via a short-lived signed-token route
  `GET /api/v1/export/jobs/{job_id}/artifact?token=…`.
- **No SQLAlchemy model, no Alembic migration** (RULE-14 conditional →
  resolved "none"). Lost-job-on-restart is logged at info, not silent (RULE-11).
  See §"In-Memory Job Registry Design".

### D2 — Binary provisioning: shared toolchain script (NO DevContainer overlay)

- `scripts/install_export_toolchain.sh` installs Typst + pandoc (+ EPUBCheck for
  CI). Invoked by **both** the release `Dockerfile` **and** the CI workflow —
  one SSOT, two consumers.
- Local dev: run the script (or install manually — documented).
- See §"Binary Provisioning Design".

### D3 — Vendoring location: `apps/api/narrare/export/typst/`

- The bespoke `narrare-roman` Typst package lives at
  `apps/api/narrare/export/typst/` (cohesive with `TypstPdfRenderer`; RULE-08).
- Bundled Libertinus Serif (OFL) at `apps/api/narrare/export/typst/fonts/` with
  `LICENSE-OFL.txt` recorded at vendoring.
- Version-controlled (pinned), **not** fetched at render time (no network dep —
  avoids the bake-off's Bergfink network-fetch friction).

### D4 — Version pins: exact, locked at Slice 0

- Pin strategy: **exact tag** in a single SSOT
  (`scripts/install_export_toolchain.sh`), overridable by env var for testing
  bumps. Pin Typst (pre-1.0, bake-off-verified floor **v0.15.1**), pandoc
  (latest stable), `@preview/droplet` (latest stable, optional).
- **Platform confirms the exact latest stable tags at Slice 0 kickoff** and locks
  them in the script. The Golden-Pages test (Slice 7) is the regression net
  across bumps.

### D5 — `narrare-roman` scope floor (first USABLE PDF = Slice 6)

Recto chapter starts + blank verso + mirrored Satzspiegel + running heads
recto≠verso (suppressed on openers/blanks via `is-page-empty`) + 4-phase
numbering (römisch → arabisch) + TOC + per-language (de/en/fr) smart quotes +
hyphenation + widow/orphan protection. **Drop cap = fast-follow** (optional,
default OFF, `@preview/droplet`).

### D6 — RULE-08 AST confinement checker is MANDATORY in Slice 0 (not optional)

RULE-08 (each external binary confined to its renderer adapter) is a hard
architectural constraint and is **mechanically enforced in CI from the first
subprocess call** — not deferred to review. The user rejected "defer the
checker, rely on code review" as a quick fix. ADR-081 anticipated this
("enforceable by AST scan if deemed worthwhile at implementation"); the user has
now deemed it worthwhile, so this **does not require ADR re-review** (RULE-21) —
it exercises the ADR's own conditional. This is a **stricter enforcement of an
existing rule**, consistent with the project principle that architectural rules
are mechanically enforced, not left to review. Full design in
§"Renderer Adapter Boundary → RULE-08 AST confinement checker".

### D7 — Libertinus Serif is the embedded font for PDF **and EPUB** (one bundled font)

PDF uses Libertinus (already D3); **EPUB embeds the same bundled files** via
pandoc `--epub-embed-font` (regular/italic/bold/bolditalic); **Markdown is plain
text and carries no font** (stated explicitly). This extends ADR-081's "no silent
font fallback" principle to EPUB — the bake-off's headline failure was silent
font fallback, and embedding in EPUB closes that gap there too. This is an
implementation-time refinement **within ADR-081's scope** (the ADR's EPUB section
said "pandoc, from the normalized form. EPUB3, validated by EPUBCheck" without
deciding fonts), so it does **not** require ADR re-review (RULE-21). The IO-001
spec line "ePub does not support custom fonts embedded from Narrare" is
**superseded** by this decision; Slice 0 corrects it (see Slice 0 scope + Slice 9
verification). Pandoc mechanism + `EpubOptions` decision in §"Slice 4" and the
`EpubOptions` contract.

---

## Contract Decisions Finalized (RULE-03 deliverable)

The ADR carries *sketches*. Below are the **real** signatures the implementers
write. Every type is fully annotated (RULE-09); every Protocol lives in a
`contracts.py` before its implementation (RULE-03).

### Non-LLM call-out (applies to ALL contracts below)

Export defines **no** `LLMIntent`, **no** `PromptContext`, **no** agent, **no**
`ModelRegistry`/`PromptComposer` injection. If an implementer finds themselves
importing `narrare_core.agents` or `narrare_core.prompts` into any export module,
**stop** — that is a layering violation of this plan. The normalizer is pure
transformation; the renderers are subprocess adapters; the service is job
orchestration. None of these is an LLM operation.

### Core contracts — `packages/core/narrare_core/export/contracts.py`

Home of the pure-Narrare layer: the normalizer Protocol + the data shapes it
produces. **Pure Core** (RULE-05: no `apps/` imports, no I/O, no subprocess —
testable in isolation).

```python
from __future__ import annotations
from datetime import datetime
from enum import StrEnum
from uuid import UUID
from typing import Protocol
from pydantic import BaseModel


class Language(StrEnum):
    """Primary manuscript language. Drives Typst text(lang:) + hyphenation.

    The three languages the DialogueMark extension detects quotes for (de/en/fr).
    Per-span languages inside the manuscript are carried inline as lang="xx"
    attributes in `NormalizedManuscript.semantic_html` — NOT as a separate
    structure — so pandoc and Typst handle them natively.
    """
    DE = "de"
    EN = "en"
    FR = "fr"


class ChapterMeta(BaseModel):
    """Per-chapter metadata, in position order."""
    chapter_id: UUID
    title: str                 # scalar string (F-7)
    position: int              # 0-based, ordering source
    volume_id: UUID | None     # None = ungrouped


class ManuscriptMetadata(BaseModel):
    """Manuscript-level metadata assembled by the Backend from novel/project data.

    The Backend reads this (read-only, RULE-22) from the novels/chapters/settings
    features and hands it to the Core normalizer. All fields are scalar strings
    (F-7: never arrays) so they pass straight through to the Typst wrapper.
    """
    title: str
    author: str
    language: Language
    # Optional EPUB metadata (ignored by the PDF/MD renderers):
    isbn: str | None = None
    description: str | None = None


class NormalizedManuscript(BaseModel):
    """Clean semantic form of a manuscript, free of editor artifacts.

    GUARANTEE (asserted by a unit test per custom TipTap mark — Slice 1):
    `semantic_html` NEVER contains AIAnnotation or GhostText residue.
    SceneBreak and DialogueMark are normalized to clean semantic equivalents.
    """
    semantic_html: str         # clean HTML (AIAnnotation + GhostText stripped)
    title: str                 # scalar string (F-7)
    author: str                # scalar string (F-7)
    language: Language         # primary language; per-span langs inline in HTML
    chapters: list[ChapterMeta]   # ordering + per-chapter metadata


class ManuscriptNormalizer(Protocol):
    """TipTap HTML → clean semantic HTML (Core, pure, no I/O).

    The strip-guarantee is the contract's central invariant:
      - AIAnnotation  (`<span data-ai-generated="true" ...>`)        → STRIPPED
      - GhostText     (decoration-based; defensively stripped if any residue) → STRIPPED
      - SceneBreak    (`<p class="scene-break">* * *</p>` | `<hr class="scene-break">`)
                                                                       → normalized scene break
      - DialogueMark  (`<span class="dialogue">…</span>`)            → clean dialogue
    The four exact selector strings are part of this contract; the strip-guarantee
    unit tests assert each one.
    """

    async def normalize(
        self,
        raw_tiptap_html: str,
        metadata: ManuscriptMetadata,
    ) -> NormalizedManuscript: ...
```

**Refinement beyond the ADR sketch:**
- `Language` is a `StrEnum` (de/en/fr) — the ADR said "Language handling" without
  fixing the type. The three members match the `DialogueMark` quote detectors
  (English `"`, French `«»`, German `„"`).
- `ChapterMeta`/`ManuscriptMetadata` are explicit (the ADR named them without
  fields). `ManuscriptMetadata` carries optional EPUB fields; the normalizer is
  format-agnostic and passes them through.
- The four **exact HTML selectors** the normalizer must handle are written into
  the contract (derived from reading the TipTap extension source — see Slice 1).
  This makes the strip-guarantee test unambiguous.

### Backend contracts — `apps/api/narrare/export/contracts.py`

Home of the RULE-12 public API (`ExportService`), the job/options models, the
RULE-08 renderer Protocol, the Typst-package config contract, and the typed
error hierarchy.

```python
from __future__ import annotations
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID
from typing import Protocol
from pydantic import BaseModel

from narrare_core.export.contracts import (
    Language,
    NormalizedManuscript,  # the renderer consumes the Core output
)


# ── Formats & options ───────────────────────────────────────────────────────

class ExportFormat(StrEnum):
    PDF = "pdf"
    EPUB = "epub"
    MARKDOWN = "md"


class PaperSize(StrEnum):
    """Paper sizes narrare-roman supports. CUSTOM carries width/height in mm."""
    B_FORMAT_129_198 = "b-format-129x198"   # default (ADR-081)
    A5 = "a5"
    A4 = "a4"
    LETTER = "letter"
    CUSTOM = "custom"


class MirroredMargins(BaseModel):
    """Mirrored Satzspiegel (inside/outside, not left/right). Units: mm."""
    inside_mm: float
    outside_mm: float
    top_mm: float
    bottom_mm: float


class PdfOptions(BaseModel):
    """PDF-specific options. Maps 1:1 to NarrareRomanConfig keys."""
    paper_size: PaperSize = PaperSize.B_FORMAT_129_198
    margins: MirroredMargins | None = None        # None → narrare-roman default for the paper
    body_size_pt: float = 11.0
    leading_ratio: float = 1.2
    drop_caps: bool = False                       # OPTIONAL, default OFF (D5)
    include_toc: bool = True


class EpubOptions(BaseModel):
    """EPUB-specific options (pandoc).

    Libertinus Serif (the bundled OFL font — the same files PDF uses, D3) is
    embedded **unconditionally** via pandoc `--epub-embed-font`
    (regular/italic/bold/bolditalic). There is intentionally NO `embed_fonts`
    flag: PDF embeds the font structurally (Typst compiles it in — no toggle),
    and EPUB matches that one-font-policy structure so there is a single,
    footgun-free embedding model across both binary formats. A v1 toggle would
    only reintroduce the silent-fallback failure mode the no-silent-fallback
    principle exists to prevent (D7). Markdown is plain text and carries no font.
    """
    cover_image_path: str | None = None           # user-provided; no cover generator
    css: str | None = None


class MarkdownOptions(BaseModel):
    """Markdown-specific options (pandoc)."""
    chapter_heading_level: int = 1                # H1 for chapters
    include_front_matter: bool = True


class ExportOptions(BaseModel):
    """Per-export request options. Only the block matching `format` is consumed."""
    format: ExportFormat
    volume_id: UUID | None = None                 # None = all volumes
    include_front_matter: bool = True
    include_back_matter: bool = True
    include_summaries: bool = False               # v1: may be False-only (fast-follow)
    include_character_list: bool = False
    include_location_glossary: bool = False
    pdf_options: PdfOptions | None = None
    epub_options: EpubOptions | None = None
    markdown_options: MarkdownOptions | None = None


# ── Job lifecycle (in-memory; D1) ───────────────────────────────────────────

class ExportJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExportJob(BaseModel):
    """Public job view returned by ExportService. The artifact_url is set only
    on COMPLETED and carries the signed token (D1)."""
    job_id: str
    novel_id: UUID
    format: ExportFormat
    status: ExportJobStatus
    created_at: datetime
    updated_at: datetime
    artifact_url: str | None = None               # signed token URL when COMPLETED
    error: str | None = None                      # typed failure reason when FAILED


# ── Renderer adapter contract (RULE-08) ─────────────────────────────────────

class Artifact(BaseModel):
    """Renderer output. `path` is a temp file the service registers for cleanup."""
    format: ExportFormat
    path: Path                                    # temp file written by the renderer
    media_type: str                               # e.g. "application/pdf"
    suggested_filename: str                       # e.g. "my-novel.pdf"


class ManuscriptRenderer(Protocol):
    """RULE-08: the external binary (Typst / pandoc) is invoked ONLY inside the
    renderer module that implements this Protocol.

    `is_available()` is the RULE-11 graceful-degradation contract: a renderer
    whose binary is missing returns False; the service reports the format
    unavailable (never silently produces a wrong-font / missing-font fallback —
    the bake-off's headline fire&forget failure).
    """

    @property
    def format(self) -> ExportFormat: ...
    def is_available(self) -> bool: ...
    async def render(
        self,
        manuscript: NormalizedManuscript,
        options: ExportOptions,
    ) -> Artifact: ...


# ── Typst-package config contract (stable Python↔Typst coupling) ────────────

class NarrareRomanConfig(BaseModel):
    """Config keys the TypstPdfRenderer builds and feeds to the narrare-roman
    wrapper. NOT a Python Protocol (narrare-roman is a Typst artifact) — but its
    keys are a stable contract: changing a key is a coordinated Python+Typst
    change. Mirrors PdfOptions + manuscript metadata (scalar strings — F-7)."""
    paper_size: PaperSize = PaperSize.B_FORMAT_129_198
    margins: MirroredMargins | None = None
    body_font: str = "Libertinus Serif"           # bundled, OFL (D3)
    body_size_pt: float = 11.0
    leading_ratio: float = 1.2
    language: Language
    title: str                                    # scalar string (F-7)
    author: str                                   # scalar string (F-7)
    drop_caps: bool = False                       # OPTIONAL, default OFF (D5)
    include_toc: bool = True
    running_head_preset: str = "default"          # recto≠verso, suppressed on openers/blanks
    scene_break_style: str = "asterism"           # "* * *" ornament (folklore pattern)
    widow_orphan_protection: bool = True


# ── Typed error hierarchy (RULE-11) ─────────────────────────────────────────

class ExportError(Exception):
    """Base for all export-domain errors."""


class ExportFormatUnavailableError(ExportError):
    """Binary for the requested format is missing (RULE-11 graceful degradation).
    Raised synchronously by ExportService.export() — the client gets an immediate
    structured error instead of polling a doomed job."""


class ExportJobNotFoundError(ExportError):
    """Unknown job_id (e.g. lost on restart — D1)."""


class ExportArtifactExpiredError(ExportError):
    """Artifact token already consumed or TTL-expired."""


class ExportRenderError(ExportError):
    """A renderer subprocess failed. Wraps the format + a stderr tail."""


# ── The RULE-12 public API ──────────────────────────────────────────────────

class ExportService(Protocol):
    """The ONLY public API for manuscript export (RULE-12).

    Consumable by all four clients (WebUI download, MCP, A2A, CLI) — a new client
    is a new adapter, never a service change. NOT an LLM operation (see the
    non-LLM call-out): no ModelRegistry, no PromptComposer, no agent.
    """

    async def list_formats(self) -> list[tuple[ExportFormat, bool]]:
        """Formats + their availability (is_available()). Lets the UI disable
        unavailable formats before the user clicks Export."""

    async def export(
        self,
        novel_id: UUID,
        options: ExportOptions,
    ) -> ExportJob:
        """Create + dispatch an export job. Raises ExportFormatUnavailableError
        synchronously if the format's binary is missing (RULE-11 fast-fail)."""

    async def get_job(self, job_id: str) -> ExportJob:
        """Poll job status. Raises ExportJobNotFoundError for unknown ids."""

    async def consume_artifact(self, job_id: str, token: str) -> Artifact:
        """Validate the signed token, return the Artifact (single-use), and
        schedule temp-file cleanup. Raises ExportArtifactExpiredError."""
```

**Refinements beyond the ADR sketch:**
- `ManuscriptRenderer` gains `is_available() -> bool` + a `format` property
  (the ADR sketch had `render()` only). These two are the RULE-11 + RULE-12
  enabling surface: the service queries availability to fast-fail and to power
  `list_formats()`.
- `ExportService` gains `list_formats()` + `consume_artifact(job_id, token)`.
  The ADR sketch had `export()` + `get_job()`. The two additions are forced by D1
  (token-route artifact delivery + UI availability discovery).
- `ExportJobStatus` stays `pending|running|completed|failed` (no `unavailable`
  status) — binary-absence is a **synchronous** `ExportFormatUnavailableError`,
  not a job state. This gives the client an immediate signal rather than a
  polling cycle.
- A typed error hierarchy (`ExportError` + 4 children) is added; the ADR only
  mentioned "typed `ExportError`". RULE-11 requires every failure to convert to
  a typed domain error, so the children are named now.
- `NarrareRomanConfig` gets explicit keys the ADR left as a comment
  (`running_head_preset`, `scene_break_style`, `widow_orphan_protection`,
  `include_toc`). These are the narrare-roman scope floor (D5) made contractual.
- `Artifact` carries `path` (a temp file) + `media_type` + `suggested_filename`
  rather than raw bytes — the renderer writes the file once, the service streams
  it via the token route (no double-buffering a 500-page PDF in memory).
- `EpubOptions` gains **no** `embed_fonts` flag — Libertinus embedding is
  always-on (D7). Justification: PDF embeds Libertinus structurally with no
  toggle, so EPUB matches that one-font-policy structure; a v1 flag would only
  reintroduce the silent-fallback failure mode the principle forbids. Markdown is
  font-less. See §"Slice 4" for the pandoc mechanism.

---

## In-Memory Job Registry Design (D1)

**No Alembic migration** (RULE-14 conditional → resolved "none"). Jobs + artifact
metadata live in process memory for the API process's lifetime.

### Data structure

Two modules, mirroring the ADR-080 pattern split between `series/tasks.py`
(dispatch) and a data store:

- `apps/api/narrare/export/tasks.py` — the **dispatch** layer. Owns
  `_INFLIGHT_TASKS: set[asyncio.Task[None]]` (the running export coroutines),
  `enqueue_export(job_id, novel_id, options)` (production enqueuer, DI-injected
  for testability), and `run_export_inprocess(job_id, novel_id, options)` (the
  in-process runner that builds its **own** DB session via
  `get_session_factory()`, normalizes, renders, and registers the artifact).
  Exactly mirrors `series/tasks.py`.

- `apps/api/narrare/export/registry.py` — the **data** store. Owns
  `_JOBS: dict[str, _JobRecord]` (job_id → record). NOT drained — it's data, not
  a task. Provides:
  - `create(novel_id, format) -> ExportJob` (status=pending)
  - `get(job_id) -> ExportJob` (raises `ExportJobNotFoundError`)
  - `mark_running(job_id)` / `mark_completed(job_id, artifact_path, token)` /
    `mark_failed(job_id, error)`
  - `consume_artifact(job_id, token) -> Artifact` (validates token, marks
    consumed, schedules cleanup; raises `ExportArtifactExpiredError`)
  - `sweep_expired()` (idempotent; drops jobs past their TTL + deletes their
    temp files)

  ```python
  @dataclass
  class _JobRecord:
      job: ExportJob
      artifact_path: Path | None        # set on COMPLETED
      artifact_token_hash: str | None   # sha256 of the token (never store raw)
      artifact_expires_at: datetime | None
      artifact_consumed: bool           # single-use
  ```

### Token generation, expiry, cleanup

- **Token:** `secrets.token_urlsafe(32)`; stored as **sha256 hash** (never the
  raw token). Validated by comparing `sha256(provided) == stored_hash`.
- **Expiry:** artifact TTL = **30 minutes** from `mark_completed` (configurable
  via settings). Single-use: the first successful `consume_artifact` invalidates
  the token; the temp file is deleted shortly after (streamed, then unlinked).
- **Cleanup:** two mechanisms (belt + braces):
  1. **On-consume:** `consume_artifact` unlinks the temp file after the response
     stream completes (or schedules it via a done-callback).
  2. **Periodic sweep:** the registry hooks into the existing lifespan periodic
     cleanup task (the same one cancelled in `_app/lifespan.py` shutdown) —
     `sweep_expired()` runs every 5 minutes, dropping expired jobs + unlinking
     their temp files. This catches artifacts that were never downloaded.

### Drain integration (ADR-080 boundary)

- Add `"narrare.export.tasks"` to `_DRAIN_SOURCES` in
  `apps/api/narrare/_app/inflight.py` (the tuple of modules exposing
  `_INFLIGHT_TASKS`). The existing `drain_inflight_tasks()` then cancels +
  awaits in-flight export tasks **before** `dispose_database()` — no export
  coroutine touches a disposed pool.
- The export `_on_done` callback (mirroring `series/tasks.py`) checks
  `task.cancelled()` and, if so, flips the job to `FAILED` with
  `error="cancelled (server shutdown)"` — so a polled job returns a typed
  failure instead of hanging in `RUNNING`. This is the RULE-11 "lost-job-on-
  restart is logged, not silent" guarantee made queryable.

### RULE-14 confirmation

v1 introduces **no** SQLAlchemy model and **no** Alembic migration. The
RULE-14 conditional ("IF a job/artifact DB model is introduced…") is resolved to
**"none"** by D1. If a future version moves jobs to Postgres (e.g. for
multi-worker durability post-ADR-080 re-introduction), that change carries its
own migration + regression test in the same task — not this plan.

---

## Renderer Adapter Boundary (RULE-08)

**Each external binary is invoked inside exactly one renderer module.** No other
module in the codebase may spawn a Typst or pandoc subprocess.

| Binary | Sole allowed location | Renderer class |
|--------|----------------------|----------------|
| Typst | `apps/api/narrare/export/renderers/typst.py` | `TypstPdfRenderer` |
| pandoc (shared) | `apps/api/narrare/export/renderers/pandoc_base.py` | — (helper) |
| pandoc (Markdown) | `apps/api/narrare/export/renderers/pandoc_md.py` | `PandocMarkdownRenderer` |
| pandoc (EPUB) | `apps/api/narrare/export/renderers/pandoc_epub.py` | `PandocEpubRenderer` |

- `pandoc_base.py` holds the shared subprocess invocation (the single place
  `asyncio.create_subprocess_exec("pandoc", …)` lives); the two pandoc
  renderers import the helper, not `asyncio.create_subprocess_exec` directly.
- **EPUBCheck** (CI-only) is invoked from the test harness
  (`tests/golden/export/`), NOT from production code — it is a validation tool,
  not a render dependency.

### `is_available()` — the graceful-degradation contract (RULE-11)

Each renderer implements `is_available()` via `shutil.which(...)` (cached on the
instance, refreshable). The semantics:

- **Service startup:** no hard failure if binaries are missing. The API boots.
- **`list_formats()`:** returns `(format, is_available())` so the UI disables
  unavailable formats.
- **`export()`:** calls `renderer.is_available()` synchronously; if False,
  raises `ExportFormatUnavailableError` **before** creating a job. The client
  gets an immediate structured error (409 Conflict / 503 Service Unavailable),
  not a polling cycle on a doomed job.
- **Mid-job binary disappearance** (rare — e.g. binary removed while running):
  the renderer's subprocess raises; the runner catches it, converts to
  `ExportRenderError`, and marks the job `FAILED` with the stderr tail.

**Never** a silent wrong-font / missing-font fallback (the bake-off's headline
fire&forget failure). Missing Libertinus Serif at Typst compile time is a
hard `ExportRenderError` — the bundled font (D3) exists precisely to make this
impossible under normal operation.

### RULE-08 AST confinement checker (MANDATORY, CI-enforced from Slice 0)

RULE-08 (each external binary confined to its renderer adapter) is
**mechanically enforced in CI from the first subprocess call** — not deferred to
review (D6). This is a **stricter enforcement of an existing rule**, consistent
with the project principle that architectural rules are mechanically enforced,
not left to review. ADR-081 anticipated this ("enforceable by AST scan if deemed
worthwhile at implementation"); the user has deemed it worthwhile — this exercises
the ADR's own conditional, so it is **not** an ADR re-review trigger (RULE-21).

**Design — matches the existing checker pattern (RULE-01b in
`scripts/architecture/_checkers/llm.py` is the template):**

- **Location:** a new checker module
  `scripts/architecture/_checkers/export_binary_confinement.py` exposing
  `check_export_binary_confinement(rel_path, tree, source_lines,
  allowed_modules) -> list[Violation]`, wired into `scan_file()` in
  `scripts/architecture/_checkers/__init__.py` and re-exported via
  `scripts/architecture/checkers.py`. Add `"RULE-08"` to the `ENFORCED_RULES`
  self-report constant in `scripts/check_architecture.py`. This is the
  established pattern — a per-file AST rule belongs inside `scan_file()` next to
  RULE-01b/07/11, **not** a standalone `scripts/checks/*.py` script (those are
  for separate-process gates like `check_doc_drift.py`).
- **Allowed-modules config:** a new `[tool.narrare.architecture]` key
  `export_binary_allowed_modules` listing exactly the four renderer files
  (mirrors the `llm_allowed_modules` / `agent_allowed_modules` shape).
- **AST-based, not grep:** the checker parses each file with the `ast` module,
  builds an import-alias map (so `import subprocess as sp` → `sp.run`, and
  `from asyncio import create_subprocess_exec as cspe` → `cspe`, resolve
  correctly), and flags any `ast.Call` whose resolved target is one of the eight
  subprocess entry points **and** whose argv contains the string-literal
  `"typst"` or `"pandoc"`. Entry points resolved through aliases:
  `subprocess.run`, `subprocess.Popen`, `subprocess.call`,
  `subprocess.check_call`, `subprocess.check_output`,
  `asyncio.create_subprocess_exec`, `asyncio.create_subprocess_shell`
  (+ `os.system` / `os.popen` as a belt-and-braces against shell-based
  invocation). Aliased imports cannot evade it; string grep can be fooled by a
  renamed import — AST resolution cannot.
- **Flagged binaries:** `"typst"` and `"pandoc"` only — the two **production**
  render binaries. **EPUBCheck is deliberately out of scope:** it is CI-only
  (invoked from the test harness `tests/golden/export/`, never from production),
  so confining it to a renderer adapter would be wrong — it belongs in tests; the
  production-path checker covers only the two production binaries. (If a future
  production binary is added, it joins this set + its renderer adapter file joins
  `export_binary_allowed_modules`.)
- **Allowed locations:** exactly
  `apps/api/narrare/export/renderers/{typst,pandoc_base,pandoc_md,pandoc_epub}.py`.
  Any `typst`/`pandoc` subprocess call anywhere else = violation. A confinement
  breach is **not** an inline-exception candidate (the `# narrare: allow` marker
  does not apply) — a genuine need to spawn these binaries outside the adapters
  requires an ADR, not a marker.
- **CI:** rides inside the existing `Check architecture constraints` step in the
  `architecture` job (`scripts/check_architecture.py`) — static AST analysis, no
  binaries needed. **Green from landing:** the four renderer skeletons are the
  only allowed files, and they raise `NotImplementedError` in Slice 0 (no real
  subprocess call exists yet), so the checker passes trivially and tightens as
  the renderers fill in across Slices 3/4/6.

Add `typst`/`pandoc` to the RULE-08 adapter table in `CONSTRAINTS.md` §2 in the
same Slice-0 change.

---

## `narrare-roman` Package Layout + Sub-Slice Map (Slice 5)

Vendored Typst artifact (D3). Loaded by `TypstPdfRenderer`; never fetched at
render time.

```
apps/api/narrare/export/typst/
├── typst.toml                       # package manifest: name = "narrare-roman"
├── lib.typ                          # public entry: #import "narrare-roman": *
├── src/
│   ├── paper.typ                    # PaperSize, B-format, mirrored Satzspiegel
│   ├── margins.typ                  # MirroredMargins, inside/outside page setup
│   ├── opener.typ                   # recto chapter start + blank verso
│   ├── heads.typ                    # running heads recto≠verso; is-page-empty suppression
│   ├── numbering.typ                # 4-phase: frontmatter römisch → body arabisch
│   ├── toc.typ                      # TOC generation
│   ├── quotes.typ                   # per-language (de/en/fr) smart quotes
│   ├── hyphenation.typ              # per-language hyphenation patterns
│   ├── scene_break.typ              # major-break ornament (folklore "major-break" pattern)
│   ├── body.typ                     # justified body + widow/orphan protection
│   ├── drop_cap.typ                 # OPTIONAL, default off (@preview/droplet)
│   └── wrapper.typ                  # the thin Narrare wrapper (F-6/F-7 seam-fixes; F-1 at pandoc)
├── fonts/
│   ├── libertinus-serif-regular.otf
│   ├── libertinus-serif-italic.otf
│   ├── libertinus-serif-bold.otf
│   ├── libertinus-serif-bolditalic.otf
│   └── LICENSE-OFL.txt              # OFL license file (recorded at vendoring — D3)
└── README.md                        # package docs + feature list + version
```

**Borrowed patterns (not forks)** — per ADR-081: `wonderous-book`'s
`is-page-empty` blank-page header suppression; `tieffiction`'s 4-phase
numbering + header presets; `folklore`'s `major-break` scene ornament.

### Slice 5 sub-slices (each a complete, probe-verified increment — RULE-20)

| Sub-slice | Feature | Files | Verified by |
|-----------|---------|-------|-------------|
| 5a | Geometric spine: paper + mirrored margins + recto chapter starts + blank verso | `paper.typ`, `margins.typ`, `opener.typ` | folio-count probe + recto-start probe |
| 5b | Running heads recto≠verso + suppression on openers/blanks (`is-page-empty`) | `heads.typ` | running-header probe (present on body, absent on openers/blanks) |
| 5c | 4-phase numbering (frontmatter römisch → body arabisch) | `numbering.typ` | folio-numbering probe |
| 5d | TOC | `toc.typ` | toc-entry probe |
| 5e | Per-language (de/en/fr) smart quotes + hyphenation | `quotes.typ`, `hyphenation.typ` | quote-form probe + hyphenation probe |
| 5f | Scene-break ornament | `scene_break.typ`, `body.typ` (widow/orphan) | scene-break-presence probe |
| 5g (fast-follow) | Drop cap, default OFF (`@preview/droplet`) | `drop_cap.typ` | drop-cap-presence probe (only when `drop_caps=true`) |

Sub-slices 5a–5f are **in-scope for the scope floor** (D5); 5g is optional.
Each sub-slice lands with its Golden-Pages probe green (Slice 7 hardens the full
harness; Slice 5 uses a lightweight inline check per feature so 5a–5f are
independently verifiable before the full harness exists).

---

## Golden-Pages Acceptance Test Harness (Slice 7)

The fire&forget robustness gate (ADR-081 §"Quality gate"). Promoted from the
disposable `_scratch/bake-off/` PyMuPDF probes (gitignored) to a committed
harness + corpus in `tests/golden/export/`.

### Corpus (`tests/golden/export/corpus/`)

Committed, varied manuscript fixtures (normalized TipTap HTML, exactly the
`NormalizedManuscript.semantic_html` shape):

| Fixture | Exercises |
|---------|-----------|
| `de-prose.html` | normal German prose |
| `de-long-compounds-belastungsprobe.html` | long-compound stress (the bake-off Belastungsprobe) |
| `mixed-dialogue-de-en-fr.html` | de/en/fr dialogue + per-span `lang` |
| `chapter-opener.html` | chapter opener (recto start, optional drop cap) |
| `scene-break.html` | scene break ornament |
| `novella/` (multi-chapter) | TOC, 4-phase numbering, running heads across a real booklet |

### Harness (`tests/golden/export/harness/`)

PyMuPDF-based probe library (promoted + hardened from the bake-off). Each probe
returns an objective metric:

| Probe | Asserts |
|-------|---------|
| `byte_reproducibility` | sha256 of two consecutive Typst renders is **identical** (the decisive Typst property) |
| `text_layer_tounicode` | copy of "find"/"Flame" yields correct codepoints (the SILE-disqualifying test — run against Typst to catch any ToUnicode regression) |
| `folio_numbering` | frontmatter folios are roman numerals; body folios are arabic (4-phase) |
| `running_header` | present on body recto+verso; **absent** on chapter openers + blank versos |
| `recto_start` | every chapter opener is on a recto (odd) page |
| `right_edge_max_error` | ≤ committed baseline (drift detection — Typst has no expansion) |
| `word_gap_stdev` | ≤ committed baseline (grey-value uniformity) |
| `scene_break_present` | the asterism renders (not as literal `* * *` text) |

### Baselines (`tests/golden/export/baselines/`)

Committed expected values (sha256 of golden PDFs per fixture, max right-edge
error, expected folio counts). **Regenerated intentionally** via a documented
`golden-update` recipe (mirrors the VRT baseline workflow; added in Slice 7); unintentional
drift = CI failure. Drift is the signal that `narrare-roman`, Typst, or pandoc
changed rendering — a human reviews and either fixes the regression or blesses
the new baseline.

### CI wiring

- New pytest marker `@pytest.mark.golden_pages`. Collected in the
  `test-integration` job (it needs Postgres for the novel/chapter fixtures +
  the toolchain binaries).
- A new CI step **"Install export toolchain"** runs
  `scripts/install_export_toolchain.sh` before the golden subset.
- EPUBCheck gating: the EPUB-renderer golden test invokes `epubcheck` on the
  rendered EPUB; any validation error fails the test. EPUBCheck is provisioned
  by the toolchain script (CI) — not bundled in the release image (PDF/EPUB/MD
  don't need it at runtime; only CI validates).

---

## Binary Provisioning Design (D2)

**One script, two consumers** (Dockerfile + CI). No DevContainer overlay.

### `scripts/install_export_toolchain.sh`

Idempotent, POSIX-sh. Installs to `/usr/local/bin` (root) or `~/.local/bin`
(user). Exact-version-pinned (D4); the pin is the SSOT.

```sh
# scripts/install_export_toolchain.sh (sketch — Platform finalizes exact tags)
set -eu
TYPST_VERSION="${TYPST_VERSION:-<Platform-locks-at-Slice-0>}"   # bake-off floor: v0.15.1
PANDOC_VERSION="${PANDOC_VERSION:-<Platform-locks-at-Slice-0>}" # latest stable
EPUBCHECK_VERSION="${EPUBCHECK_VERSION:-<Platform-locks-at-Slice-0>}"  # CI-only

install_typst()   { … download typst-x86_64-unknown-linux-musl.tar.xz … }
install_pandoc()  { … download pandoc-${PANDOC_VERSION}-amd64.deb … }
install_epubcheck() { … download epubcheck-${EPUBCHECK_VERSION}.zip (CI only) … }

install_typst
install_pandoc
[ "${INSTALL_EPUBCHECK:-0}" = "1" ] && install_epubcheck

typst --version && pandoc --version | head -1
```

The script is the single source of truth for the exact tags. The TECH_STACK
section (below) records only the major-version commitment and points here
(mirroring the existing TECH_STACK convention of "no hard numbers in prose").

### Dockerfile change (release `runtime` stage)

```dockerfile
# --- Export toolchain (ADR-081) ---
COPY scripts/install_export_toolchain.sh /tmp/install_export_toolchain.sh
RUN chmod +x /tmp/install_export_toolchain.sh \
    && /tmp/install_export_toolchain.sh \
    && rm /tmp/install_export_toolchain.sh
# Vendored narrare-roman + Libertinus Serif travel inside apps/api/narrare/export/typst/
# (already COPYied via the existing source copy).
```

No EPUBCheck in the release image (`INSTALL_EPUBCHECK=0` default) — it is
CI-only.

### CI change (`.github/workflows/ci.yml`)

- **`test-integration` job:** add an **"Install export toolchain"** step
  (`INSTALL_EPUBCHECK=1 bash scripts/install_export_toolchain.sh`) before the
  pytest step, so the golden + EPUBCheck tests have the binaries.
- **`test-e2e` job (main only):** same install step (a real export E2E can run).
- **`architecture` job:** unchanged at the step level — the RULE-08 AST
  confinement checker (D6) rides **inside** the existing
  `Check architecture constraints` step (`scripts/check_architecture.py`); no
  new step, no binaries needed (static AST analysis).
- The `paths` filter for the `backend` change-detection already covers
  `scripts/**`, so edits to the toolchain script trigger CI.

### Local dev

The deployment guide + a new section in the export feature spec document:
`bash scripts/install_export_toolchain.sh` once (or `brew install typst pandoc`
on macOS). The `is_available()` contract means the API boots fine without them —
only export is unavailable until they're installed.

---

## TECH_STACK.md "Export Toolchain" Section Draft (applied in Slice 0)

> Drafted here inside the plan. Slice 0 applies it to `docs/_shared/TECH_STACK.md`
> (new `## Export Toolchain` section, placed after `## Background Processing`),
> and adds Typst/pandoc/EPUBCheck to the RULE-08 adapter table in
> `docs/_shared/CONSTRAINTS.md` §2.

```markdown
## Export Toolchain

> Added by ADR-081 (2026-08-10). Manuscript export is a deterministic, non-LLM
> render pipeline (no ModelRegistry, no PromptComposer, no agent — see the
> non-LLM call-out in ADR-081).

### Typst (pre-1.0, exact-pinned)
**Why:** Chosen PDF engine for manuscript export (ADR-081). Single ~15 MB static
binary; **byte-reproducible** output (decisive for the Golden-Pages CI
acceptance test); correct PDF text layer (ToUnicode). Knuth-Plass-class line
breaking; no glyph expansion (the accepted ~5–10% gap vs LaTeX on compound-heavy
German — user bar = ~95%, "sehr hochwertig"). Pre-1.0 (v0.15.x) → exact version
pin mandatory; Golden-Pages test is the regression net across bumps.
**Role:** PDF rendering via a bespoke `narrare-roman` Typst package (vendored at
`apps/api/narrare/export/typst/`, owned — not a community template fork).
**Location:** Invoked ONLY inside `apps/api/narrare/export/renderers/typst.py`
(RULE-08).
**Canonical source:** `scripts/install_export_toolchain.sh` pins the exact tag
(bake-off-verified floor: v0.15.1; Platform locks the latest stable at IO-001
Slice 0). This document records only the major-version commitment (pre-1.0
v0.15.x); check the script for the installed tag.
**Not:** LaTeX (footprint + non-reproducible), SILE (f-ligature ToUnicode
defect), WeasyPrint / `python-docx` / `ebooklib` (superseded by ADR-081).

### pandoc (exact-pinned)
**Why:** Intermediate converter for all three export formats: HTML → Typst AST
(PDF, with `--to=typst --shift-heading-level-by=-1`), HTML → EPUB3, HTML →
Markdown. Robust fire&forget for the simpler formats.
**Role:** HTML → target AST.
**Location:** Invoked ONLY inside
`apps/api/narrare/export/renderers/pandoc_*.py` (RULE-08).
**Canonical source:** `scripts/install_export_toolchain.sh`.

### EPUBCheck (CI gate, not in release image)
**Why:** The EPUB validation standard. CI gate for the EPUB renderer
(no half-implementations — RULE-20).
**Role:** CI-only validation of rendered EPUBs. Not a runtime dependency.
**Canonical source:** `scripts/install_export_toolchain.sh` (installed only when
`INSTALL_EPUBCHECK=1`, i.e. CI).

### `@preview/droplet` (optional, pinned)
**Why:** Drop-cap support in `narrare-roman`, OFF by default ("die mag nicht jeder").
**Role:** Optional Typst preview package imported by `narrare-roman` only when
`drop_caps: true`.
**Canonical source:** pinned in `apps/api/narrare/export/typst/` (vendored or
version-locked in the wrapper).

### Libertinus Serif (bundled, OFL)
**Why:** Production body font for PDF **and EPUB** export. Bundled for
reproducible output with **NO silent font fallback** in either binary format
(the bake-off's headline fire&forget failure was templates silently falling back
to the wrong font — D7 extends the no-silent-fallback principle to EPUB).
Markdown is plain text and carries no font. EB Garamond was the bake-off
comparison font only.
**Role:** Body font in `narrare-roman` (PDF — compiled in by Typst) **and**
embedded in EPUB via pandoc `--epub-embed-font` (regular/italic/bold/bolditalic
variants) — one bundled font, two embedding mechanisms, one font policy.
**Location:** `apps/api/narrare/export/typst/fonts/` + `LICENSE-OFL.txt`
(recorded at vendoring). Both renderers read from this single directory (D3).
**Not:** EB Garamond (comparison font only); system fonts (silent fallback risk).
```

---

## Slice 0 — Pre-Implementation Gate (contracts, pins, vendoring, infra)

**Goal:** lay every RULE-03 contract, every pin, every vendored asset, the
TECH_STACK edit, and the toolchain/CI/Dockerfile wiring **before** any
production logic. No renderer produces a PDF yet; the foundation is complete.

### Scope
- Finalize the two `contracts.py` files (signatures above) — real Python modules,
  importable, pyright-clean. **No implementations** — only Protocols, Pydantic
  models, the StrEnums, and the error hierarchy.
- `scripts/install_export_toolchain.sh` — idempotent, version-pinned (Platform
  confirms + locks the exact tags here).
- Vendored `narrare-roman` skeleton at `apps/api/narrare/export/typst/`:
  `typst.toml`, `lib.typ` (empty re-exports), `fonts/` with Libertinus Serif +
  `LICENSE-OFL.txt`. No book features yet (those land in Slice 5) — just the
  package shape that Typst can `--import` without error.
- TECH_STACK.md "Export Toolchain" section (draft above) lands.
- CONSTRAINTS.md §2 RULE-08 table gains Typst / pandoc / EPUBCheck rows pointing
  at their renderer-adapter homes.
- Dockerfile release stage: add the toolchain install step.
- `.github/workflows/ci.yml` `test-integration` job: add the "Install export
  toolchain" step (`INSTALL_EPUBCHECK=1`).
- Renderer adapter skeleton: three renderer modules (`typst.py`,
  `pandoc_md.py`, `pandoc_epub.py`) + `pandoc_base.py`, each exposing a class
  that declares `format`, `is_available()` (via `shutil.which`), and a
  `render()` that raises `NotImplementedError` (Slice 0 = boundary only).
- Golden-Pages harness **design** committed: create the empty directory tree
  `tests/golden/export/{corpus,harness,baselines}/` + a `README.md` describing
  the probe→assertion map (above). No probes yet (Slice 7).
- **MANDATORY: the RULE-08 AST confinement checker (D6)** — implemented to the
  design in §"Renderer Adapter Boundary → RULE-08 AST confinement checker": new
  module `scripts/architecture/_checkers/export_binary_confinement.py`, wired
  into `scan_file()`, `"RULE-08"` added to `ENFORCED_RULES`, new
  `export_binary_allowed_modules` key in `pyproject.toml`. Green from landing
  (renderer skeletons make no real subprocess call in Slice 0, so the checker
  passes trivially and tightens as the renderers fill in).
- **IO-001 spec text correction (D7):** the current IO-001 line "ePub does not
  support custom fonts embedded from Narrare; the reader's font settings apply"
  (`docs/features/io/IO-001-export.md:198`) is **superseded** by D7 (Libertinus
  is embedded in EPUB). Correct the line in this same docs-sync change so the
  feature spec matches the contract + TECH_STACK. (Implementation-time
  refinement within ADR-081 scope — no ADR re-review per RULE-21.)

### Files created/changed
- **New:** `packages/core/narrare_core/export/__init__.py`,
  `packages/core/narrare_core/export/contracts.py`
- **New:** `apps/api/narrare/export/__init__.py`,
  `apps/api/narrare/export/contracts.py`,
  `apps/api/narrare/export/renderers/__init__.py`,
  `apps/api/narrare/export/renderers/typst.py`,
  `apps/api/narrare/export/renderers/pandoc_base.py`,
  `apps/api/narrare/export/renderers/pandoc_md.py`,
  `apps/api/narrare/export/renderers/pandoc_epub.py`
- **New:** `apps/api/narrare/export/typst/typst.toml`,
  `apps/api/narrare/export/typst/lib.typ`,
  `apps/api/narrare/export/typst/fonts/LICENSE-OFL.txt` + Libertinus otf files,
  `apps/api/narrare/export/typst/README.md`
- **New:** `scripts/install_export_toolchain.sh`
- **New:** `scripts/architecture/_checkers/export_binary_confinement.py`
  (RULE-08 AST confinement checker — D6)
- **New:** `tests/unit/architecture/test_export_binary_confinement.py`
  (checker self-test — D6)
- **New:** `tests/golden/export/README.md` (+ empty `corpus/`, `harness/`,
  `baselines/` dirs with `.gitkeep`)
- **Changed:** `docs/_shared/TECH_STACK.md` (new section),
  `docs/_shared/CONSTRAINTS.md` (RULE-08 table rows),
  `docs/features/io/IO-001-export.md` (superseded EPUB-font line — D7),
  `Dockerfile` (release stage toolchain step),
  `.github/workflows/ci.yml` (integration job toolchain step),
  `scripts/architecture/_checkers/__init__.py` +
  `scripts/architecture/checkers.py` (wire the RULE-08 checker into `scan_file`),
  `scripts/check_architecture.py` (`ENFORCED_RULES` += `"RULE-08"`),
  `pyproject.toml` (`[tool.narrare.architecture] export_binary_allowed_modules`)

### Tests
- Import-smoke test: both `contracts.py` modules import cleanly; every
  Protocol/model/Enum is constructable.
- `shutil.which`-based availability test: each renderer skeleton's
  `is_available()` returns a bool (True if the binary is present in the CI env
  after the toolchain step, False if unset — test both by monkeypatching).
- Toolchain script: a CI step asserts `typst --version` + `pandoc --version`
  succeed after the install step.
- `check_architecture.py` green — now **includes** the RULE-08 confinement
  checker (no longer conditional).
- **RULE-08 checker self-test** (`tests/unit/architecture/test_export_binary_confinement.py`,
  D6): synthetic AST fixtures for every evasion/resolution case — direct
  `subprocess.run`, aliased `import subprocess as sp` and
  `from asyncio import create_subprocess_exec as cspe`, the shell variants, a
  `typst`/`pandoc` call **inside** an allowed renderer file (no violation), the
  same call **outside** the renderers (violation), and an `epubcheck` call
  anywhere (NOT flagged — out of scope by design).

### Definition of Done — green = `just verify` + `scripts/check_architecture.py`
- [ ] Both `contracts.py` modules pyright-clean and importable.
- [ ] Toolchain script idempotent; CI integration job installs Typst + pandoc +
      EPUBCheck and `--version`s succeed.
- [ ] Vendored `narrare-roman` package `typst.toml` valid; `typst --import`
      (or equivalent) does not error on the skeleton.
- [ ] TECH_STACK + CONSTRAINTS edits land and `check_doc_drift.py` is green.
- [ ] Renderer skeletons declare `format` + `is_available()`; `render()` raises
      `NotImplementedError`.
- [ ] **RULE-08 AST confinement checker lands (D6)** — wired into `scan_file()`,
      `"RULE-08"` in `ENFORCED_RULES`, runs green in the `architecture` CI job,
      and its self-test passes (every alias/evasion case covered; `epubcheck`
      correctly out of scope).
- [ ] **IO-001 EPUB-font line corrected (D7)** — feature spec matches the
      EPUB-embeds-Libertinus contract; `check_doc_drift.py` green.

---

## Slice 1 — Narrare Normalizer (Core, pure) + strip-guarantee tests

**Goal:** implement the only Narrare-specific layer — pure transformation from
TipTap HTML to clean semantic HTML. Zero I/O, zero subprocess — testable in
isolation. The strip-guarantee is the central invariant.

### Scope
- `packages/core/narrare_core/export/normalizer.py` — implements
  `ManuscriptNormalizer`. Likely split into focused sub-modules under
  `packages/core/narrare_core/export/_internal/` (RULE-04: keep `normalizer.py`
  under the 250-line soft target):
  - `_strip.py` — removes AIAnnotation + GhostText residue (the hard guarantee).
  - `_normalize.py` — normalizes SceneBreak + DialogueMark to clean equivalents.
  - `_structure.py` — assembles `chapters: list[ChapterMeta]` in position order.
- The exact selectors (from reading the TipTap extension source — part of the
  Core contract):
  - **AIAnnotation** → strip `<span data-ai-generated="true"…>` (mark name
    `aiGenerated`; emits `class="ai-generated-text ai-generated-{status}"` +
    `data-request-id` / `data-source` / `data-original-text` / `data-status` /
    `data-created-at`). Strip the wrapper, **keep** the inner text (the accepted
    edit becomes plain prose).
  - **GhostText** → decoration-based extension (ProseMirror decorations are NOT
    persisted in `editor.getHTML()`). Defensively strip any residue matching
    `data-ghost-text` / `class*="ghost-text"` if present; normally a no-op.
  - **SceneBreak** → normalize `<p class="scene-break">* * *</p>` **or**
    `<hr class="scene-break">` to a single canonical form (the renderer decides
    the visual; the normalizer produces one stable representation).
  - **DialogueMark** → unwrap `<span class="dialogue">…</span>` to plain text
    (the quotes themselves carry the dialogue semantics; the class is a styling
    hook that must not reach pandoc/Typst).
- Front/back matter assembly from `ManuscriptMetadata` (title, author) — the
  title page block. Optional appendices (summaries, character list, glossary)
  are v1 `False`-only stubs (fast-follow) — the normalizer accepts the flags
  but emits nothing extra until the source data wiring lands.

### Files created/changed
- **New:** `packages/core/narrare_core/export/normalizer.py`,
  `packages/core/narrare_core/export/_internal/__init__.py`,
  `packages/core/narrare_core/export/_internal/_strip.py`,
  `packages/core/narrare_core/export/_internal/_normalize.py`,
  `packages/core/narrare_core/export/_internal/_structure.py`
- **Changed:** `packages/core/narrare_core/export/__init__.py` (export the
  implementation + the contract types)

### Tests (`tests/unit/core/export/`)
- **One strip-guarantee test per custom TipTap mark** (RULE-03 + the contract's
  central invariant):
  - `test_strip_ai_annotation.py` — input with `<span data-ai-generated=…>`
    → output has zero such spans; inner text preserved.
  - `test_strip_ghost_text.py` — defensively: if ghost-text residue is present,
    it is gone; if absent (the normal case), the output is unchanged.
  - `test_normalize_scene_break.py` — both `<p class="scene-break">` and
    `<hr class="scene-break">` → the single canonical form.
  - `test_normalize_dialogue_mark.py` — `<span class="dialogue">` unwrapped;
    quotes preserved.
- **Structural tests:** chapters in position order; `ManuscriptMetadata` scalar
  strings pass through; per-span `lang="xx"` attributes preserved in
  `semantic_html`.
- **Round-trip property test** (optional, if cheap): random AIAnnotation/
  GhostText insertion never survives normalization.
- Core coverage ≥ 90% (RULE-10) for the new `export/` package.

### Definition of Done — green
- [ ] All four strip/normalize tests green; the strip-guarantee is asserted for
      every mark.
- [ ] `normalized.semantic_html` contains zero AIAnnotation/GhostText selectors
      (asserted by a regex negative match in every strip test).
- [ ] `pyright` clean; `check_architecture.py` green; core coverage ≥ 90%.

---

## Slice 2 — ExportService skeleton + in-process job infra + router + DI + drain

**Goal:** stand up the RULE-12 public API, the in-memory job registry (D1), the
ADR-080-style dispatch, the FastAPI router (RULE-06: delegates immediately), DI
factories, graceful binary-absence (RULE-11), and the drain registration.
Renderers remain unavailable stubs (Slice 0) — the service end-to-end is wired
but produces no real artifact until Slice 3.

### Scope
- `apps/api/narrare/export/registry.py` — the `_JOBS` dict, `_JobRecord`, token
  generation (sha256-hashed), `create`/`get`/`mark_*`/`consume_artifact`/
  `sweep_expired`. Hooks into the lifespan periodic cleanup task.
- `apps/api/narrare/export/tasks.py` — `_INFLIGHT_TASKS` GC-guard set,
  `enqueue_export()` (DI-injected), `run_export_inprocess()` (own DB session via
  `get_session_factory()`), `_on_done` callback (flips job to FAILED on
  cancellation — RULE-11 queryable lost-job). Mirrors `series/tasks.py`.
- `apps/api/narrare/export/service.py` — `ExportServiceImpl` implementing the
  `ExportService` Protocol. Resolves renderers via DI; calls `is_available()`
  for fast-fail; normalizes (Core), renders (adapter), registers artifact,
  dispatches via `enqueue_export`.
- `apps/api/narrare/export/repository.py` — **read-only** chapter/novel fetching
  (RULE-22: export never modifies the source). Loads `Chapter.content` +
  metadata in position order.
- `apps/api/narrare/export/dependencies.py` — DI factories (SessionDep —
  RULE-19; renderer injection; the `enqueue_export` callable for testability).
- `apps/api/narrare/export/router.py` — thin (RULE-06):
  - `GET  /api/v1/export/formats` → `list_formats()`
  - `POST /api/v1/export`         → `export()` (201 + ExportJob)
  - `GET  /api/v1/export/jobs/{job_id}` → `get_job()`
  - `GET  /api/v1/export/jobs/{job_id}/artifact?token=…` →
    `consume_artifact()` (streaming response; 200, 404, or 410)
- Register `"narrare.export.tasks"` in `_DRAIN_SOURCES` in
  `apps/api/narrare/_app/inflight.py`.
- Mount the router in the app.
- Graceful binary-absence: `list_formats()` returns `(format, False)` when the
  toolchain isn't installed; `POST /export` with an unavailable format returns a
  structured 409/503 (`ExportFormatUnavailableError`).

### Files created/changed
- **New:** `apps/api/narrare/export/{registry,tasks,service,repository,
  dependencies,router,schemas}.py`
- **Changed:** `apps/api/narrare/_app/inflight.py` (`_DRAIN_SOURCES` += export),
  the app router mount, the lifespan periodic-cleanup hook (calls
  `sweep_expired()`)

### Tests (`tests/unit/api/export/`)
- Job-lifecycle tests: create → mark_running → mark_completed →
  consume_artifact (single-use: second consume raises
  `ExportArtifactExpiredError`).
- Token tests: raw token never stored; sha256 match required; TTL expiry →
  `sweep_expired()` drops the job + unlinks the temp file.
- Fast-fail test: `POST /export` with a missing binary → 409/503
  (`ExportFormatUnavailableError`), no job created.
- Dispatch test: `enqueue_export` launches via `asyncio.create_task` with a
  GC-guarded ref (monkeypatch the renderer to a fake).
- Drain test: `drain_inflight_tasks()` cancels an in-flight export task; the
  job is flipped to `FAILED` with `"cancelled (server shutdown)"`.
- Router-purity test (RULE-06): router handlers contain no business logic
  (complexity heuristic — already enforced by `check_architecture.py`).
- DI factory test: session params use `SessionDep`, not bare `AsyncSession`
  (RULE-19 — enforced by the checker).

### Definition of Done — green
- [ ] Full job lifecycle (create → poll → consume) works end-to-end with a
      fake renderer.
- [ ] `list_formats()` reflects real `is_available()` in the test env.
- [ ] Drain registration lands; a tracked export task is cancelled + the job
      marked FAILED on shutdown.
- [ ] `pyright` + `check_architecture.py` green; coverage ≥ 80% (apps/api).

---

## Slice 3 — Markdown renderer (pandoc)

**Goal:** the first real renderer. Validates the whole normalizer → pandoc →
delivery pipeline end-to-end on the simplest format (Markdown). De-risks the
pipeline before EPUB and the high-risk Typst package.

### Scope
- `apps/api/narrare/export/renderers/pandoc_base.py` — the shared pandoc
  subprocess invocation (the single `asyncio.create_subprocess_exec("pandoc",
  …)` site). Handles stdin (semantic HTML) / stdout / stderr capture, timeout,
  non-zero-exit → `ExportRenderError` with stderr tail.
- `apps/api/narrare/export/renderers/pandoc_md.py` — `PandocMarkdownRenderer`
  implementing `ManuscriptRenderer`. Calls `pandoc_base` with
  `--from=html --to=gfm` (GitHub-Flavored Markdown) +
  `--shift-heading-level-by=-1` where appropriate + `MarkdownOptions`.
- Wire `ExportServiceImpl` to dispatch MARKDOWN to this renderer.

### Files created/changed
- **Changed:** `apps/api/narrare/export/renderers/pandoc_base.py` (real impl),
  `apps/api/narrare/export/renderers/pandoc_md.py` (real impl),
  `apps/api/narrare/export/service.py` (dispatch)

### Tests (`tests/integration/export/test_markdown.py` + `tests/unit/api/export/`)
- Integration: a normalized manuscript → `PandocMarkdownRenderer.render()` →
  Artifact whose temp file is valid GFM with correct heading levels (H1 for
  chapters — `MarkdownOptions.chapter_heading_level`).
- Normalizer→renderer integration: feed real TipTap HTML through the normalizer
  → renderer; assert AIAnnotation/GhostText absent in the output Markdown.
- `is_available()` returns False when `shutil.which("pandoc")` is None
  (monkeypatched).
- Failure path: pandoc exits non-zero → `ExportRenderError` with the stderr tail;
  the job is marked FAILED.
- End-to-end via the router: `POST /export` (md) → poll →
  `GET …/artifact?token=…` returns the Markdown file with the right media_type.

### Definition of Done — green
- [ ] A real Markdown artifact is produced, downloaded, and cleaned up.
- [ ] The pipeline (normalizer → pandoc → artifact → token download) is
      demonstrated end-to-end.

---

## Slice 4 — EPUB renderer (pandoc) + EPUBCheck CI gate

**Goal:** the second format. EPUB3 via pandoc, validated by EPUBCheck as a CI
gate (no half-implementations — RULE-20).

### Scope
- `apps/api/narrare/export/renderers/pandoc_epub.py` — `PandocEpubRenderer`.
  Calls `pandoc_base` with `--from=html --to=epub3 --toc` + `EpubOptions`
  (cover image, css, metadata: title/author/language/isbn). **Embeds the bundled
  Libertinus Serif (D7)** via pandoc's `--epub-embed-font` mechanism — one
  invocation per variant (regular/italic/bold/bolditalic), pointing at the four
  `.otf` files at `apps/api/narrare/export/typst/fonts/` (the same files PDF
  uses — D3; one bundled font, two embedding mechanisms, one font policy).
  `--epub-embed-font` is chosen over hand-written `@font-face` CSS + `--css`
  because it is pandoc's purpose-built route: pandoc copies the files into
  `EPUB/fonts/`, generates the `@font-face` rules, and registers the OPF
  manifest entries — exactly the declarations EPUBCheck validates (hand-rolling
  the CSS would duplicate that bookkeeping and is more error-prone). Embedding is
  unconditional (no `embed_fonts` flag — see the `EpubOptions` contract).
  *(Scope note: this stays within ADR-081 — the ADR's EPUB section said
  "pandoc, from the normalized form. EPUB3, validated by EPUBCheck" without
  deciding fonts; embedding is an implementation-time refinement, not a material
  deviation — no ADR re-review per RULE-21.)*
- `tests/golden/export/test_epubcheck.py` — invokes `epubcheck` on the rendered
  EPUB; any validation error fails the test. Marked `@pytest.mark.golden_pages`
  so it runs in the integration job where EPUBCheck is installed. **Asserts the
  embedded Libertinus fonts are correctly declared** (present in the OPF
  manifest + `EPUB/fonts/`, referenced by valid `@font-face` rules).

### Files created/changed
- **Changed:** `apps/api/narrare/export/renderers/pandoc_epub.py` (real impl),
  `apps/api/narrare/export/service.py` (dispatch EPUB)

### Tests
- Integration: normalized manuscript → EPUB → EPUBCheck passes.
- Cover-image handling: `EpubOptions.cover_image_path` → embedded cover;
  absence → pandoc default (no crash).
- Metadata: title/author/language/isbn reach the EPUB opf.
- **Font-embedding test (D7):** the four Libertinus variants are embedded +
  declared in the OPF manifest + referenced by valid `@font-face` rules; the
  rendered EPUB body resolves to Libertinus Serif (no silent fallback to a
  reader system font — the no-silent-fallback principle extended to EPUB).
- Failure path: malformed input → `ExportRenderError`.

### Definition of Done — green
- [ ] EPUBCheck passes on the rendered EPUB in CI.
- [ ] **Libertinus Serif embedded + declared (EPUBCheck-green) — no silent
      fallback (D7).**
- [ ] End-to-end EPUB download via the token route.

---

## Slice 5 — `narrare-roman` Typst package (HIGH RISK, sub-sliced)

**Goal:** the bespoke Typst package — the single biggest risk in the pipeline.
Built feature-by-feature (sub-slices 5a–5g, above), each verified by a
lightweight inline probe before the full Golden-Pages harness lands in Slice 7.
No Python changes here (the renderer wrapper is Slice 6); this slice is pure
Typst authoring + direct `typst compile` verification.

### Scope
- Implement `src/*.typ` per the sub-slice map. Each sub-slice is a complete,
  renderable increment: after 5a, a PDF with correct paper/margins/recto starts
  compiles; after 5b, running heads appear correctly; etc.
- `wrapper.typ` — the thin Narrare wrapper: `#import` narrare-roman, accept the
  pandoc-generated body, escape literal `@` in prose (F-6), pass scalar-string
  metadata (F-7). F-1 (`--shift-heading-level-by=-1`) is applied at the pandoc
  invocation in Slice 6, not here.
- A small `tests/golden/export/corpus/`-style scratch manuscript rendered
  directly with `typst compile` after each sub-slice, with the inline probe
  (folio count, recto-start, running-header presence) checked by a Slice-5-local
  test. (Slice 7 promotes these to the full harness.)

### Files created/changed
- **Changed:** `apps/api/narrare/export/typst/src/*.typ` (one per sub-slice),
  `apps/api/narrare/export/typst/lib.typ` (public exports),
  `apps/api/narrare/export/typst/README.md` (feature list)

### Tests (`tests/unit/api/export/typst/` or `tests/golden/export/`)
- One inline render+probe test per sub-slice (5a–5f). Each renders a tiny
  manuscript via `typst compile` (subprocess — confined to the test, not
  production) and asserts the sub-slice's invariant.
- 5g (drop cap) is gated behind `drop_caps=true`; default-OFF asserted (no
  drop-cap probe fires when the flag is unset).

### Definition of Done — green (per sub-slice, then the whole slice)
- [ ] 5a: recto chapter starts + blank verso + mirrored Satzspiegel — folio +
      recto-start probes green.
- [ ] 5b: running heads recto≠verso, suppressed on openers/blanks.
- [ ] 5c: 4-phase numbering (römisch → arabisch).
- [ ] 5d: TOC renders.
- [ ] 5e: de/en/fr smart quotes + hyphenation per language.
- [ ] 5f: scene-break ornament + widow/orphan protection.
- [ ] (optional) 5g: drop cap when enabled; default OFF confirmed.
- [ ] All sub-slice probes green; the package compiles standalone.

**Risk note:** this slice is where the bake-off's "bespoke templates can corrupt
content unattended" risk lives. The inline probes are the mitigation; the full
Golden-Pages harness (Slice 7) is the durable guardrail.

---

## Slice 6 — Typst PDF renderer (thin wrapper, seam-fixes, Libertinus)

**Goal:** wire `narrare-roman` to the pipeline. The `TypstPdfRenderer` is a thin
adapter: pandoc → Typst body (F-1 at the pandoc call), wrapper (F-6/F-7), Typst
compile to PDF. Bundled Libertinus Serif is the body font.

### Scope
- `apps/api/narrare/export/renderers/typst.py` — `TypstPdfRenderer` implementing
  `ManuscriptRenderer`. The **sole** production site that invokes the Typst
  subprocess. Steps:
  1. Build `NarrareRomanConfig` from `PdfOptions` + manuscript metadata (scalar
     strings — F-7).
  2. Invoke pandoc (`pandoc_base`) with `--to=typst --shift-heading-level-by=-1`
     (F-1) on `semantic_html`.
  3. Emit the wrapper Typst file: `#import "narrare-roman": *` + the config + the
     pandoc body with literal `@` escaped (F-6).
  4. `asyncio.create_subprocess_exec("typst", "compile", …)` with the font path
     pointing at the bundled Libertinus Serif. Capture stdout PDF / stderr.
  5. Non-zero exit → `ExportRenderError` with the Typst stderr tail.
- Wire `ExportServiceImpl` to dispatch PDF to this renderer.

### Files created/changed
- **Changed:** `apps/api/narrare/export/renderers/typst.py` (real impl),
  `apps/api/narrare/export/service.py` (dispatch PDF)

### Tests (`tests/integration/export/test_pdf.py`)
- Integration: normalized manuscript → `TypstPdfRenderer.render()` → Artifact
  whose temp file is a valid PDF (PyMuPDF opens it; page count > 0).
- **Seam-fix regression tests** (F-1/F-6/F-7 must never regress — ADR-081):
  - F-1: a `## CHAPTER n` becomes a level-1 opener (recto pagebreak + ToC entry).
  - F-6: literal `@` in prose does not error (prose containing `\@preview/…`
    survives).
  - F-7: `author` passed as a scalar string renders correctly in the title page.
- Font test: the bundled Libertinus Serif is the embedded body font (no silent
  fallback — PyMuPDF font probe). Missing font at compile time → hard
  `ExportRenderError`.
- Byte reproducibility: two consecutive renders of the same input produce
  byte-identical PDFs (sha256 equal) — the decisive Typst property.
- Failure path: Typst non-zero exit → `ExportRenderError`.

### Definition of Done — green
- [ ] A real book-quality PDF artifact is produced + downloaded via the token
      route.
- [ ] All three seam-fix regression tests green.
- [ ] Byte reproducibility asserted.
- [ ] No silent font fallback.

---

## Slice 7 — Golden-Pages Acceptance Test (committed harness + corpus + CI)

**Goal:** promote the Slice-5/6 inline probes + the bake-off PyMuPDF probes to a
committed, CI-gated harness on a varied corpus. This slice **is** the
fire&forget robustness assurance (ADR-081 §"Quality gate").

### Scope
- Commit the corpus (`tests/golden/export/corpus/`): de-prose,
  de-long-compounds-Belastungsprobe, mixed-dialogue-de-en-fr, chapter-opener,
  scene-break, `novella/` (multi-chapter).
- Commit the harness (`tests/golden/export/harness/`): the probe library
  (`byte_reproducibility`, `text_layer_tounicode`, `folio_numbering`,
  `running_header`, `recto_start`, `right_edge_max_error`, `word_gap_stdev`,
  `scene_break_present`).
- Commit baselines (`tests/golden/export/baselines/`): expected sha256s, max
  right-edge errors, folio counts per fixture.
- `tests/golden/export/test_golden_pages.py` — `@pytest.mark.golden_pages`;
  renders every corpus fixture via the real pipeline and asserts every probe
  against its baseline.
- `golden-update` recipe (mirrors VRT) to intentionally regenerate
  baselines.
- Confirm the CI `test-integration` job runs the golden subset (toolchain step
  from Slice 0 + EPUBCheck from Slice 4).

### Files created/changed
- **New:** `tests/golden/export/corpus/*.html`, `tests/golden/export/harness/*.py`,
  `tests/golden/export/baselines/*.json`,
  `tests/golden/export/test_golden_pages.py`
- **Changed:** `justfile` (`golden-update` recipe)

### Tests
- The Golden-Pages test itself is the test. It runs in CI (integration job).

### Definition of Done — green
- [ ] Golden-Pages test green in CI across the full corpus.
- [ ] Every probe asserts its invariant; baselines committed.
- [ ] the `golden-update` recipe regenerates baselines cleanly; an intentional
      narrare-roman change → baseline drift → human review path documented.

---

## Slice 8 — Frontend Export panel (format/options, polling, download, i18n)

**Goal:** the user-facing surface. Format + options UI, job polling, download,
and i18n en/de/fr (RULE-16/17).

### Scope
- `packages/web/components/studio/export/ExportPanel.tsx` + supporting
  components (format selector, PDF/EPUB/MD option groups, job status, download
  button).
- API client (`packages/web/lib/api/export.ts`) + TypeScript types mirroring the
  backend schemas **exactly** (RULE-17 — field names match). `list_formats` →
  disable unavailable formats; `export` → create job; poll `get_job` until
  COMPLETED/FAILED; `consume_artifact` → download.
- TanStack Query for job polling (the stack's server-state pattern).
- Settings persistence ("remembered for next time") — local, via existing
  settings patterns.
- i18n: new namespace `export` registered in `packages/web/lib/i18n/request.ts`;
  `packages/i18n/messages/{en,de,fr}/export.json` with full parity (RULE-16).
- Entry point: dashboard + editor menu (per IO-001 spec).

### Files created/changed
- **New:** `packages/web/components/studio/export/*.tsx`,
  `packages/web/lib/api/export.ts`, `packages/web/types/export.ts`
- **Changed:** dashboard/editor menu wiring,
  `packages/web/lib/i18n/request.ts` (namespace),
  `packages/i18n/messages/{en,de,fr}/export.json` (new),
  `packages/web/__tests__/i18n-namespace-registry.test.ts` baseline (if needed)
- **Changed:** `packages/web/types/export.ts` + a contract test asserting
  field-name parity with the backend schemas (RULE-17)

### Tests
- Component tests (vitest): format selection, option groups, polling states
  (pending → running → completed), download on completed, error on failed.
- i18n parity test (RULE-16): `export` namespace in `request.ts` + all 3 locales.
- Contract test (RULE-17): TS types match backend `ExportJob`/`ExportOptions`/
  `ExportFormat` field names.
- VRT baseline for the panel (the frontend job's existing VRT workflow).

### Definition of Done — green
- [ ] A user can export a novel to PDF/EPUB/MD end-to-end via the UI.
- [ ] Unavailable formats disabled; errors surface.
- [ ] i18n en/de/fr green; namespace registered; VRT baseline committed.

---

## Slice 9 — Gate closure (IO-001 stable, ADR-081 ✅ Implemented, Gate 12)

**Goal:** prove completeness (RULE-20) and close the architecture gate.

### Scope
- Run the full Gate 12 checklist (`.opencode/context/narrare-dev/processes/quality-gates.md`).
- Manual cross-feature verification (RULE-22): export a real novel; confirm the
  source project is unmodified (read-only).
- Confirm no half-implementation: normalizer strip-guarantee green; all three
  renderers produce validated output; narrare-roman scope floor complete;
  Golden-Pages + EPUBCheck green in CI; graceful binary-absence; TECH_STACK
  landed.

### Verification
- `just verify` + `scripts/check_architecture.py` green.
- Golden-Pages test green in CI.
- EPUBCheck green in CI.
- **RULE-08 confinement enforced by the AST checker (D6)** in CI on every commit
  — no `typst`/`pandoc` subprocess call exists outside the four renderer adapter
  files. (The mechanical gate supersedes the one-off manual project-wide search;
  the checker is the durable enforcement.)
- **IO-001 spec line 198 corrected (D7)** — the "ePub does not support custom
  fonts…" text is gone; the feature spec matches the EPUB-embeds-Libertinus
  contract + TECH_STACK.
- ADR-081 marked ✅ Implemented; IO-001 status → stable.

### Definition of Done — for this plan
- [ ] Slices 0–8 each landed with a green suite at their boundary.
- [ ] Gate 12 checklist complete.
- [ ] ADR-081 ✅ Implemented; IO-001 stable.
- [ ] No code outside the scope described above (no scope creep, no workarounds
      — RULE-20).

---

## Risk Register + Contingency

| Risk | Mitigation / Contingency |
|------|--------------------------|
| **`narrare-roman` content-corruption** (bespoke-template bugs: drop-cap collisions, dropped quotes, ragged paragraphs — observed in the bake-off) | The Golden-Pages Acceptance Test (Slice 7) on a varied corpus is the **mandatory** mitigation. Inline probes per Slice-5 sub-slice catch regressions before the full harness exists. |
| **Typst pre-1.0 version bump breaks rendering** | Exact version pin (D4, Slice 0). Golden-Pages test is the regression net across bumps (ADR-081 §"Version discipline"). Review trigger: Typst 1.0 or a breaking major → re-pin + re-run Golden-Pages. |
| **500-page manuscript bottlenecks the event loop** (normalizer in-process) | **Documented contingency** (ADR-081): escalate the normalizer to `ProcessPoolExecutor` via `loop.run_in_executor(...)`. **Not the default** — activate only when a real 500-page export proves to starve the request loop. Typst/pandoc are already subprocesses (off the loop). |
| **Lost export job on restart** (ADR-080 in-process boundary) | Acceptable: export is regenerable + non-destructive (the project is never modified). Logged at info on drain (RULE-11) + the job is flipped to FAILED so a poll returns a typed failure, not a hang. The user re-clicks Export. |
| **Silent font fallback** (the bake-off's headline fire&forget failure) | Bundled Libertinus Serif (D3) embedded in **both** PDF (compiled in by Typst) and EPUB (`--epub-embed-font`, D7); a hard `ExportRenderError` if Typst can't find it (RULE-11). The `is_available()` + font-probe test (Slice 6, PDF) and the EPUBCheck font-declaration test (Slice 4, EPUB) assert no fallback in either format. Markdown is font-less. |
| **Token route abuse** (artifact enumeration) | `secrets.token_urlsafe(32)` (256-bit), sha256-hashed at rest, single-use + 30-min TTL, periodic sweep. Job_ids are also `secrets.token_urlsafe` (not enumerable). |
| **EPUBCheck JVM weight in CI** | EPUBCheck is CI-only (not in the release image). Install step is opt-in (`INSTALL_EPUBCHECK=1`). |
| **pandoc/Typst seam regressions** (F-1/F-6/F-7) | Dedicated regression tests (Slice 6) + Golden-Pages. The seam-fixes are load-bearing per ADR-081. |

---

## Residual Open Questions for the Coordinator/User (before Slice 1)

These do **not** block Slice 0 (Slice 0 is the gate that resolves most of them),
but the Coordinator should confirm direction before Slice 1 begins:

1. **Exact toolchain version tags (D4).** The plan pins the *strategy* (exact tag
   in `scripts/install_export_toolchain.sh`) and cites the bake-off-verified
   Typst floor (v0.15.1). The **Platform Specialist confirms the exact latest
   stable tags** for Typst, pandoc, EPUBCheck, and `@preview/droplet` at Slice 0
   kickoff and locks them. Q: any constraint on pinning to the bake-off-exact
   Typst 0.15.1 vs. bumping to the newest stable before any code depends on it?
2. **Optional appendices in v1.** `ExportOptions.include_summaries /
   include_character_list / include_location_glossary` are in the contract but
   the normalizer emits nothing extra for them in Slice 1 (the source-data wiring
   is a fast-follow). Q: ship the UI checkboxes disabled, or omit them in v1?
3. **Token-route response shape.** The plan uses
   `GET /api/v1/export/jobs/{job_id}/artifact?token=…` returning the file stream
   directly (200) with `Content-Disposition: attachment`. Q: any preference for a
   302 redirect to a short-lived signed URL vs. a proxied stream? (Proxied stream
   is simpler + keeps the artifact temp-file-only; recommended.)

> **Resolved since this plan was first drafted (folded in as D6/D7, no longer
> open):** the former "RULE-08 AST checker — implement in Slice 0 or defer?" is
> now **D6 (mandatory in Slice 0)**; the former "EPUB custom fonts — confirm no
> embedded-font variant is wanted" is now **D7 (Libertinus embedded in EPUB)**.
> Both were user-approved 2026-08-10.

---

## Non-LLM, Non-Prompt Confirmation

Export is correctly modeled as a **deterministic render pipeline**, not an LLM
operation. Concretely:

- **RULE-01b (agents/models):** no `pydantic_ai.Agent`, no `ModelRegistry`, no
  provider/model import anywhere in `packages/core/narrare_core/export/` or
  `apps/api/narrare/export/`. The checker has nothing to flag.
- **RULE-02 / 02a / 02b (prompts):** no prompt is built, resolved, or injected.
  `narrare_core.prompts` is never imported by any export module. The Typst
  wrapper + pandoc AST are **render templates**, not LLM prompts — they are
  parameterized by `NarrareRomanConfig` (a Pydantic model), not by
  `PromptComposer`.
- **RULE-13 (streaming/non-streaming registry):** export is not an LLM
  operation; the streaming/non-streaming contract does not apply. Progress
  reporting is via the RULE-12 job-status API (`get_job` polling), not via any
  LLM streaming path.

Any implementer who finds themselves reaching for the agent pattern in the
export package has misread this plan — escalate before proceeding.
