// Export-pipeline types — mirror the backend Pydantic schemas EXACTLY (RULE-17).
//
// SSOT (field names, enum values, nullability): the OpenAPI spec
// (docs/reference/openapi.json) which is generated from
//   apps/api/narrare/export/contracts.py  (ExportJob, ExportJobStatus, Artifact,
//                                           FormatAvailability)
//   apps/api/narrare/export/options.py     (ExportFormat, PaperSize,
//                                           MirroredMargins, PdfOptions,
//                                           EpubOptions, MarkdownOptions,
//                                           ExportOptions)
//   apps/api/narrare/export/router.py      (ExportRequest body)
//
// snake_case is preserved so the wire payload maps 1:1 (the established repo
// convention — see types/settings.ts). Field-name parity is mechanically
// enforced by lib/api/__tests__/types-parity.test.ts.

/** Output format produced by a renderer. Mirrors `ExportFormat` StrEnum. */
export type ExportFormat = "pdf" | "epub" | "md" | "docx";

/** Export job lifecycle states. Mirrors `ExportJobStatus` StrEnum. */
export type ExportJobStatus = "pending" | "running" | "completed" | "failed";

/**
 * Paper sizes narrare-roman supports. CUSTOM carries width/height in mm.
 * Mirrors `PaperSize` StrEnum.
 */
export type PaperSize = "b-format-129x198" | "a5" | "a4" | "letter" | "custom";

/** Mirrored Satzspiegel (inside/outside, not left/right). Units: mm. */
export interface MirroredMargins {
  readonly inside_mm: number;
  readonly outside_mm: number;
  readonly top_mm: number;
  readonly bottom_mm: number;
}

/** PDF-specific options. Maps 1:1 to NarrareRomanConfig keys. */
export interface PdfOptions {
  paper_size: PaperSize;
  margins: MirroredMargins | null;
  body_size_pt: number;
  leading_ratio: number;
  drop_caps: boolean;
  include_toc: boolean;
}

/**
 * EPUB-specific options (pandoc). Font embedding is unconditional (no flag).
 * `isbn` / `description` are request-level, user-optional metadata (IO-001
 * follow-up): null = unset → the EPUB renderer omits dc:identifier/description.
 */
export interface EpubOptions {
  cover_image_path: string | null;
  css: string | null;
  isbn: string | null;
  description: string | null;
}

/** Markdown-specific options (pandoc). */
export interface MarkdownOptions {
  chapter_heading_level: number;
  include_front_matter: boolean;
}

/**
 * Per-export request options. Only the block matching `format` is consumed.
 * Mirrors `ExportOptions` (defaults intentionally NOT expressed here — the
 * caller builds a fully-populated object; the backend fills any omitted field).
 */
export interface ExportOptions {
  format: ExportFormat;
  volume_id: string | null;
  include_front_matter: boolean;
  include_back_matter: boolean;
  include_summaries: boolean;
  include_character_list: boolean;
  include_location_glossary: boolean;
  pdf_options: PdfOptions | null;
  epub_options: EpubOptions | null;
  markdown_options: MarkdownOptions | null;
}

/** Body of POST /api/v1/export: which novel + which options. */
export interface ExportRequest {
  novel_id: string;
  options: ExportOptions;
}

/**
 * Public job view returned by ExportService. `artifact_url` is set only on
 * COMPLETED and carries the signed single-use token (D1).
 */
export interface ExportJob {
  job_id: string;
  novel_id: string;
  format: ExportFormat;
  status: ExportJobStatus;
  created_at: string;
  updated_at: string;
  artifact_url: string | null;
  error: string | null;
}

/** One row of GET /export/formats: a format + its availability flag. */
export interface FormatAvailability {
  format: ExportFormat;
  available: boolean;
}

/**
 * Renderer output model (backend `Artifact`). NOT a REST response shape — the
 * artifact endpoint (GET .../artifact?token=…) streams the file bytes; it never
 * serializes this object. Mirrored here only for RULE-17 documentation parity;
 * `path` is a server-side temp file and MUST NOT be exposed to end users.
 */
export interface Artifact {
  format: ExportFormat;
  path: string;
  media_type: string;
  suggested_filename: string;
}
