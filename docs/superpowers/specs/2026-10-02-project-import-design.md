# Project Import v1 (SETUP-003) — Design Spec

> **Status:** Approved design record (2026-10-02) — formalizes the binding
> brainstorm decisions with the project owner; supersedes the v0 sketch in
> `docs/features/setup/SETUP-003-import.md` (updated alongside).
> **ADR:** `docs/architecture/decisions/ADR-091-project-import-v1.md`
> **Plan:** `docs/superpowers/plans/2026-10-02-project-import.md`
> **Language of record:** English (project standard)

---

## §1 Scope

**In scope (v1):**

- Import of Markdown (`.md`) and plain-text (`.txt`) files as **chapters**
  into an existing novel, via browser multipart upload.
- Two entry points: Setup Wizard (Step 2, new projects) and the novel
  workspace sidebar ("Import chapters" action, existing novels).
- Server-side parse + preview (suggested title, word count, source file) with
  per-chapter title edit and include/exclude toggle before commit.
- Atomic append of selected chapters (`position = max+1..n`).
- Removal of the dormant server-side `import_path` mechanism (backend +
  frontend + i18n, one slice).

**Explicitly out of scope (v1):**

- DOCX (and any other format) — explicit follow-up slice via the existing
  pandoc converter (ADR-081 renderers).
- Bulk KB extraction — stays with the existing per-chapter UI
  (`POST /novels/{id}/kb/extract/{chapter_id}`); IO-002 deep analysis is a
  separate future feature.
- Split/merge boundary editing in the preview (only title edit +
  include/exclude).
- Directory upload, drag-drop-of-folders, charset detection, dedup, undo,
  volume assignment, position re-ordering.

---

## §2 Decision table (binding, from the approved brainstorm)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Entry points | Dashboard/novel workspace **and** Setup Wizard |
| D2 | Formats v1 | `.md` + `.txt` only; DOCX = explicit follow-up |
| D3 | KB extraction | Chapters only; existing per-chapter UI; **no bulk extraction** |
| D4 | Transfer | Browser multipart upload (first `UploadFile` surface); server-side `import_path` **removed** (BE+FE one slice, RULE-20) |
| D5 | Preview | Upload → server parse → preview list (title, word count, source file) with per-chapter title edit + include/exclude; **no split/merge editing** |
| D6 | Import semantics | Append: `position = max(existing)+1..n`, single atomic transaction; no dedup, no undo — documented |
| D7 | Wizard placement | Inline in WizardStep2 under the "import" starter card (replaces the `import_path` input); stepper stays 5 steps; `wizardStore` holds the selection; Step-5 completion creates the novel then calls import-commit; commit failure after novel creation → surfaced error + empty novel + retry via sidebar modal (documented degrade path) |
| D8 | Sidebar entry | "Import chapters" action in `SidebarChapterList` opening a shared `ImportModal` |
| D9 | Encoding | UTF-8 strict, BOM tolerated (`utf-8-sig`); undecodable file → 422 naming the file; **no charset detection** |
| D10 | Chapter status | frontmatter `status` if present, else `"draft"` (mirrors DemoLoader) |
| D11 | Volumes | Not assigned (`volume_id` NULL — mirrors DemoLoader) |
| D12 | Guardrails | ≤ 100 files per upload, ≤ 25 MB total, single file ≤ 5 MB, zero detected chapters → 422 |

**Parser placement ruling (architecture-owned open point):** the detection
engine lives in **pure Core** (`packages/core/narrare_core/importing/`).
Rationale: the heuristics are deterministic, I/O-free domain policy — RULE-07
places them in Core where API and any future CLI/MCP client (RULE-12) share
them, and where the deterministic re-parse contract is a property of a pure
function (ADR-081 `core/export` normalizer precedent). Alternative
(API-local `apps/api/narrare/importing/parsing/`) rejected: couples detection
policy to the HTTP layer and makes the golden tests depend on the app package.

---

## §3 Module boundary

```
packages/core/narrare_core/importing/     ← pure, deterministic, no I/O
    __init__.py        public exports
    models.py          DetectedChapter (frozen dataclass)
    splitting.py       ATX heading split + TXT chapter-marker split
    detector.py        detect_chapters(filename, text) -> list[DetectedChapter]

apps/api/narrare/importing/               ← orchestration + HTTP (name avoids keyword `import`)
    __init__.py
    contracts.py       ImportPreviewerProtocol, ImportCommitterProtocol,
                       ImportChapterRepositoryProtocol   (RULE-03, written first)
    schemas.py         ImportPreviewItem/Response, ImportCommitAdjustments,
                       ImportCommitChapterInfo/Response
    constants.py       MAX_FILES=100, MAX_FILE_BYTES=5 MiB, MAX_TOTAL_BYTES=25 MiB,
                       ALLOWED_EXTENSIONS={".md", ".txt"}, TITLE_MAX_LENGTH=500
    service.py         ImportService — guard pipeline, decode, parse, gate, append
    repository.py      ImportChapterRepository — max_position + bulk append (SQLAlchemy only)
    router.py          POST /import/preview, POST /import/commit (thin, RULE-06)
    dependencies.py    get_import_service (SessionDep, RULE-19)

packages/web/
    lib/api/core.ts            + fetchApiUpload (multipart; no Content-Type override)
    lib/api/importing.ts       importApi.preview / importApi.commit
    types/importing.ts         RULE-17 mirror of the Pydantic schemas
    components/studio/importing/
        ImportPreviewPanel.tsx shared pick → preview → edit surface
        ImportModal.tsx        dialog wrapper: panel + commit + query invalidation
    components/studio/wizard/  WizardStep2 inline section, WizardStep5 summary,
                               WizardShell completion sequence
    components/studio/SidebarChapterList.tsx  action entry + failure banner
    lib/stores/wizardStore.ts importSelection state (never serialized to complete())
packages/i18n/messages/{en,de,fr}/importing.json  (+ request.ts registration)
```

**Dependency direction (RULE-07, one-way):**

```
router → ImportService → ImportChapterRepository → DB
                  ↓                        ↑ Chapter model (narrare.chapters.models,
                  ↓                         DemoLoader precedent for cross-domain write)
         narrare_core.importing.detector (pure)
         narrare.novels.ownership.verify_novel_owned (canonical gate)
         narrare.novels.contracts.NovelRepositoryProtocol
```

No DB migration: the `Chapter` model is reused unchanged (`volume_id`
already nullable; `status` String(20) default `"draft"`).

---

## §4 API contracts

All errors use the app-level `NarrareError` shape
`{"detail": <str>, "code": <str>}` (`ValidationError` → 422, `NotFoundError`
→ 404). Both endpoints require authentication (`CurrentUserIdDep`).

### 4.1 `POST /api/v1/import/preview`

**Request:** `multipart/form-data`

| Part | Type | Notes |
|------|------|-------|
| `files` | file (repeatable) | 1..100 parts; order = detected order |

**Guard pipeline (in order, all → 422 with the offending filename(s) in
`detail` where applicable):**

1. `1 ≤ len(files) ≤ MAX_FILES` (100)
2. each `file.size ≤ MAX_FILE_BYTES` (5 MiB)
3. `sum(sizes) ≤ MAX_TOTAL_BYTES` (25 MiB)
4. every extension ∈ `{".md", ".txt"}` (case-insensitive)
5. decode `utf-8-sig` strict (BOM stripped); failure → 422 naming the file
6. parse; total detected chapters ≥ 1, else 422

**Response 200:**

```json
{
  "items": [
    {
      "index": 0,
      "suggested_title": "The Thorn Wall",
      "word_count": 2412,
      "source_file": "ch-01.md"
    }
  ],
  "file_count": 1,
  "chapter_count": 1,
  "total_word_count": 2412
}
```

- `index`: 0-based position in the detected order — the stable key the
  commit adjustments refer to.
- `suggested_title` ≤ 500 chars (Chapter.title limit).
- **No DB writes.** Safe to call repeatedly.

### 4.2 `POST /api/v1/import/commit`

**Request:** `multipart/form-data`

| Part | Type | Notes |
|------|------|-------|
| `files` | file (repeatable) | MUST be the identical set+order sent to preview |
| `novel_id` | form field (UUID string) | target novel |
| `adjustments` | form field (JSON string) | see below |

```json
{
  "excluded_indices": [3, 7],
  "title_overrides": { "0": "Renamed First Chapter" }
}
```

- `excluded_indices`: 0-based indices to drop.
- `title_overrides`: index (as string, JSON object keys) → new title
  (1..500 chars).

**Processing:** guard pipeline (as preview) → ownership gate
(`verify_novel_owned`; foreign ≡ unknown → **404**, canonical IDOR pattern) →
deterministic re-parse → structural validation of adjustments (all indices in
`0..chapter_count-1`, all titles 1..500 chars, else 422) → filter + rename →
`position = max_position+1 .. +n` → bulk insert → single flush in the request
transaction (any failure rolls back all rows).

**Response 200:**

```json
{
  "novel_id": "…uuid…",
  "created_count": 2,
  "first_position": 0,
  "last_position": 1,
  "chapters": [
    { "id": "…uuid…", "title": "Renamed First Chapter", "position": 0, "word_count": 2412 }
  ]
}
```

**Deterministic re-parse contract (normative):** the parser is pure — the
identical file set in identical order yields the identical chapter list on
preview and commit. The server keeps **no state** between the two calls. The
client MUST send the exact `File[]` it previewed; the shared
`ImportPreviewPanel` holds the `File[]` in component state, making drift
impossible by construction. A drifted set degrades safely: structural
adjustment validation (index range, title length) surfaces mismatches as 422
rather than a silently wrong import.

---

## §5 Detection heuristics (normative)

All rules are deterministic and I/O-free (`narrare_core.importing`).

### 5.1 Common rules

- **Order** = multipart part order. The client sorts files naturally
  (`localeCompare(…, { numeric: true })`) before upload; the server never
  re-orders.
- **Accepted extensions:** `.md`, `.txt` (case-insensitive); anything else →
  422 naming the file (preview guard 4).
- **Decode:** `utf-8-sig` (strict; strips BOM when present).
- **Empty files:** whitespace-only files contribute zero chapters and are
  skipped silently (not an error). Zero chapters overall → 422 (guard 6).
- **Word count:** `len(content.split())` — mirrors DemoLoader and
  `chapters.repository.count_words`.
- **Title fallback chain (.md):** frontmatter `title` → first ATX `#`/`##`
  heading → filename stem formatted `stem.replace("-", " ").title()`
  (exact DemoLoader formatting).
- **Title fallback (.txt):** the chapter-marker line (trimmed) → filename
  stem (same formatting) for the no-marker single chapter.
- **Status:** frontmatter `status` when the value ∈
  `{"draft", "reviewed", "final"}`; any other/missing value → `"draft"`
  (documented coercion; the Chapter column is free-form String(20), but v1
  only produces known states). `.txt` files are always `"draft"`.
- **Heading/marker lines are NOT stored in `content`** — the title carries
  them; frontmatter is stripped.

### 5.2 Markdown (`.md`)

1. `parse_frontmatter` (existing `narrare_core.shared.frontmatter`) strips
   YAML frontmatter; `title`/`status` feed the rules above.
2. The body is split on ATX heading lines `^#{1,2}\s+\S` (h1/h2 only;
   `###`+ never splits and stays inside the current section).
3. **No headings** → one chapter: title from the fallback chain, content =
   entire body.
4. **Headings present** → one chapter per heading: title = heading text;
   content = text after the heading until the next h1/h2.
5. **Preamble** (non-empty text before the first heading, after strip):
   becomes its own chapter titled via the fallback chain (frontmatter title
   or filename stem). Empty preamble → nothing.

### 5.3 Plain text (`.txt`)

1. No frontmatter parsing.
2. Split on chapter-marker lines matching
   `^\s*(chapter|kapitel)\s+([0-9]+|[ivxlcdm]+)\b` (case-insensitive; EN +
   DE; Arabic and Roman numerals; spelled-out numbers excluded — documented
   limitation).
3. Marker line → chapter title (trimmed marker text). Content runs until the
   next marker.
4. **No markers** → single chapter titled from the filename stem.

### 5.4 Edge cases (test matrix seeds)

| Case | Expected |
|------|----------|
| `.md` with frontmatter only, empty body | chapter skipped (zero-content) — falls under empty-file rule if fully empty |
| `.md` heading immediately at top, no preamble | chapters = headings only |
| `###` between two `##` sections | stays inside the previous section |
| Roman numeral markers (`Kapitel IV`) | recognized (case-insensitive) |
| `Chapter one` (spelled out) | NOT a marker → single-chapter fallback |
| Marker with trailing text (`Chapter 12 — The Storm`) | whole line is the title |
| File named `my-chapter.md` with no headings/frontmatter | title `My Chapter` |
| `.MD` uppercase extension | accepted |
| `.docx` in the set | 422 naming the file |
| Latin-1 bytes in one file | 422 naming the file |
| 101 files | 422 |
| One 6 MiB file | 422 |
| Total > 25 MiB across files | 422 |
| All files whitespace-only | 422 (zero chapters) |

---

## §6 Frontend design

### 6.1 Shared surface

`ImportPreviewPanel` (stateful): file picker (multi-select, `accept=".md,.txt"`)
→ natural sort → `importApi.preview` → renders one row per item:
include-checkbox (default on), title input (default `suggested_title`),
word count, source filename. Publishes
`ImportSelection { files: File[]; excludedIndices: number[]; titleOverrides: Record<number, string> }`
upward on every change; `null` when no files are picked.

`ImportModal` (dialog): renders the panel; Confirm → `importApi.commit(files,
novelId, adjustments)` → on success invalidate `["novels", novelId, "chapters"]`
and close; on failure keep the modal open with the error and the files intact
(retry possible).

### 6.2 Sidebar entry (existing novels)

`SidebarChapterList` gains an "Import chapters" button (next to "New
chapter"); opens `ImportModal` with the current `novelId`. Additionally shows
a dismissible warning banner when `sessionStorage["narrare:importFailed:{novel_id}"]`
is set (see 6.3), offering "Retry import" (reopens the modal). The key is
cleared on successful import or dismissal.

### 6.3 Wizard integration (new projects)

- `wizardStore`: new top-level state `importSelection: ImportSelection | null`
  + setter; cleared by `reset()`. **Never** part of `WizardState` sent to
  `setupApi.complete` (`File` is not serializable).
- `WizardStep2`: selecting the "import" starter card renders the
  `ImportPreviewPanel` inline under the card (replacing the removed
  `import_path` input). Selection updates the store. `handleNext` keeps
  calling `setupApi.validateStep3({ starter: "import" })` (trivially valid).
- `WizardStep5`: starter summary row for import shows
  `{fileCount} files · {includedCount} chapters` (replaces `importFrom {path}`).
- `WizardShell.handleComplete` (order matters):
  1. capture `importSelection` from the store **before** `reset()`;
  2. `setupApi.complete(state)` → `novel_id` (backend creates an empty novel
     for `starter="import"` — post-removal semantics);
  3. if `starter === "import"` and a selection exists:
     `importApi.commit(files, novel_id, adjustments)` — on failure set
     `sessionStorage["narrare:importFailed:{novel_id}"] = "1"` (degrade path:
     user lands in the empty novel, banner + sidebar retry);
  4. `reset()`; `router.push(/novel/{novel_id})`.

### 6.4 API client

`fetchApiUpload(endpoint, { body: FormData })` in `lib/api/core.ts`:
same auth header + 401-refresh-retry logic as `fetchApi`, but **does not set
`Content-Type`** (the browser must set the multipart boundary). Returns parsed
JSON; error body shape identical to `fetchApi`.

### 6.5 i18n (RULE-16)

New namespace `importing` registered in `packages/web/lib/i18n/request.ts`
with `en/de/fr` files. Removed keys: `studio:wizard.step2.importPath`,
`wizard.step2.importPathPlaceholder`, `wizard.step5.importFrom` (all three
locales). Updated keys: `wizard.step2.importDescription` (upload wording);
new `studio:wizard.step5.importSummary`, `studio:sidebar.importChapters` +
banner strings.

---

## §7 Risks & assumptions

| # | Risk / open point | Mitigation / status |
|---|------------------|---------------------|
| R1 | **Multipart through the Next.js rewrite** (`next.config.ts` `/api/v1/:path*` → API). Verified: `proxy.ts` is route-protection only — its matcher never matches `/api`, so it is **not** the relevant hop. Starlette/uvicorn impose no default body limit; Next.js `bodySizeLimit` applies to Server Actions only. **Residual assumption:** the rewrite streams large multipart bodies unmodified. Production CORS is closed, so the rewrite is the only browser→API path — it must work. | Plan T2 contains an explicit verification step: real > 1 MB and ~5 MB multipart uploads through the Next dev server rewrite (`curl` against `localhost:3000/api/v1/import/preview`). If it fails: Next Route Handler streaming proxy or `experimental.proxyTimeout`-class config fix — escalation to Architecture (RULE-21: material change ⇒ re-review). |
| R2 | Double upload cost (≤ 25 MB × 2) | Accepted (ADR-091); local-first LAN latency. |
| R3 | Adjustments refer to a stale preview (files re-picked between preview and commit) | Impossible by construction in the shared panel (File[] held in state); server enforces index-range/title-length validity → 422 on drift. |
| R4 | Import duplicates on re-run (no dedup/undo) | Documented in UI copy + feature file; preview is the verification gate. |
| R5 | Position race (concurrent chapter creation) | Single-user local-first; request-scoped transaction; acceptable (same exposure as existing chapter-create). |
| R6 | `UploadFile.size` spoofing (declared vs actual size) | Guardrail is UX bounding, not a security boundary (authenticated, local-first); Starlette materializes actual bytes regardless. Accepted. |
| R7 | Wire break: `Step3StarterRequest.import_path` / `WizardState.import_path` removed | 0.x no-users precedent (Q-012 class); no deprecation shim. |

**Assumptions ratified:** guardrail values (D12) are protocol constants, not
user settings — no settings surface, no RULE-18b matrix entry; they live in
`importing/constants.py` with regression tests pinning them (ADR-004 pattern).
