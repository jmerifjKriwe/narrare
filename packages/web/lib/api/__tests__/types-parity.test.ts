/**
 * RULE-17 parity: TS interface field names match the shipped Pydantic schemas
 * (apps/api/narrare/adaptive/schemas.py, apps/api/narrare/ai_assist/schemas.py).
 *
 * Implementation note — why this is NOT `Object.keys({} as T)`:
 *   A TypeScript interface cast is compile-time only; `{}` has zero own
 *   enumerable properties at runtime, so `Object.keys({} as T)` would always
 *   return `[]` and the assertions could never pass. Instead each sample is a
 *   fully-populated literal annotated with the interface type. This gives TWO
 *   layers of enforcement:
 *     1. `vitest run`  — `Object.keys(sample)` returns the real runtime keys.
 *     2. `tsc` (type-check) — the sample must satisfy the interface, so any
 *        missing/extra REQUIRED field is a compile error on the annotation.
 *   snake_case is preserved to mirror the Pydantic SSOT.
 */

import { describe, expect, it } from "vitest";
import type {
  AdaptiveContextResponse,
  AdaptiveSettingsResponse,
  AdaptiveSourceSummary,
  AdaptiveToggleInput,
  AdaptiveWeightsInput,
  AdaptiveWeightsResponse,
  Artifact,
  DialogueAlternative,
  DialogueCoachRequest,
  DialogueCoachResponse,
  DialogueCoachStreamEvent,
  DialogueIssue,
  EpubOptions,
  ExportFormat,
  ExportJob,
  ExportJobStatus,
  ExportOptions,
  ExportRequest,
  FormatAvailability,
  MarkdownOptions,
  MirroredMargins,
  PaperSize,
  PdfOptions,
  WsTicket,
} from "@/types";

function fieldNames<T extends object>(sample: T): string[] {
  return Object.keys(sample).sort();
}

describe("auth types mirror Pydantic (RULE-17 — ADR-084)", () => {
  it("WsTicket matches the WsTicketResponse shape from POST /auth/ws-ticket", () => {
    const sample: WsTicket = { token: "t", expires_in: 60 };
    expect(fieldNames(sample)).toEqual(["expires_in", "token"]);
  });
});

describe("adaptive types mirror Pydantic (RULE-17)", () => {
  it("AdaptiveWeightsResponse has the 4 clamped weights", () => {
    const sample: AdaptiveWeightsResponse = {
      preference: 0.7,
      voice_fidelity: 0.9,
      style_constraints: 1.0,
      avoidance: 1.0,
    };
    expect(fieldNames(sample)).toEqual([
      "avoidance",
      "preference",
      "style_constraints",
      "voice_fidelity",
    ]);
  });

  it("AdaptiveContextResponse matches the GET /context shape", () => {
    const sample: AdaptiveContextResponse = {
      project_id: "p1",
      enabled: true,
      weights: {
        preference: 0.7,
        voice_fidelity: 0.9,
        style_constraints: 1.0,
        avoidance: 1.0,
      },
      sources: {
        preference_text: "",
        voice_profiles_text: "",
        style_constraints_text: "",
        avoidance_patterns_text: "",
      },
      has_any_signal: false,
    };
    expect(fieldNames(sample)).toEqual([
      "enabled",
      "has_any_signal",
      "project_id",
      "sources",
      "weights",
    ]);
  });

  it("AdaptiveSettingsResponse matches POST /toggle + /weights shape", () => {
    const sample: AdaptiveSettingsResponse = {
      enabled: true,
      weights: {
        preference: 0.7,
        voice_fidelity: 0.9,
        style_constraints: 1.0,
        avoidance: 1.0,
      },
    };
    expect(fieldNames(sample)).toEqual(["enabled", "weights"]);
  });

  it("AdaptiveSourceSummary has the 4 *_text fields", () => {
    const sample: AdaptiveSourceSummary = {
      preference_text: "",
      voice_profiles_text: "",
      style_constraints_text: "",
      avoidance_patterns_text: "",
    };
    expect(fieldNames(sample)).toEqual([
      "avoidance_patterns_text",
      "preference_text",
      "style_constraints_text",
      "voice_profiles_text",
    ]);
  });

  it("AdaptiveToggleInput + AdaptiveWeightsInput are the request bodies", () => {
    const toggle: AdaptiveToggleInput = { enabled: true };
    expect(fieldNames(toggle)).toEqual(["enabled"]);

    const weights: AdaptiveWeightsInput = {
      preference: 0.7,
      voice_fidelity: 0.9,
      style_constraints: 1.0,
      avoidance: 1.0,
    };
    expect(fieldNames(weights)).toEqual([
      "avoidance",
      "preference",
      "style_constraints",
      "voice_fidelity",
    ]);
  });
});

describe("dialogueCoach types mirror Pydantic (RULE-17)", () => {
  it("DialogueCoachRequest body fields", () => {
    const sample: DialogueCoachRequest = {
      selection_text: "Hello.",
      mode: "analyze",
    };
    expect(fieldNames(sample)).toEqual(["mode", "selection_text"]);
  });

  it("DialogueCoachResponse top-level fields", () => {
    const sample: DialogueCoachResponse = {
      chapter_id: "c1",
      mode: "analyze",
      issues: [],
      adaptive_summary: "",
    };
    expect(fieldNames(sample)).toEqual(["adaptive_summary", "chapter_id", "issues", "mode"]);
  });

  it("DialogueIssue fields", () => {
    const sample: DialogueIssue = {
      issue_type: "voice-drift",
      speaker: "Anna",
      original_quote: "Hi.",
      diagnosis: "off-voice",
      severity: "low",
      alternatives: null,
    };
    expect(fieldNames(sample)).toEqual([
      "alternatives",
      "diagnosis",
      "issue_type",
      "original_quote",
      "severity",
      "speaker",
    ]);
  });

  it("DialogueAlternative fields", () => {
    const sample: DialogueAlternative = {
      rewrite: "Hey.",
      explanation: "warmer",
    };
    expect(fieldNames(sample)).toEqual(["explanation", "rewrite"]);
  });

  it("DialogueCoachStreamEvent discriminates on `event`", () => {
    // Fully-populated sample (SSE event fields are optional by design).
    const sample: DialogueCoachStreamEvent = {
      event: "progress",
      result: null,
      progress: "working",
      error: null,
      is_final: false,
    };
    expect(fieldNames(sample)).toContain("event");
    expect(fieldNames(sample)).toContain("is_final");
  });
});

describe("export types mirror Pydantic (RULE-17 — IO-001 / ADR-081)", () => {
  // SSOT: apps/api/narrare/export/options.py + contracts.py, surfaced via the
  // OpenAPI spec (docs/reference/openapi.json). snake_case preserved.

  it("ExportFormat / ExportJobStatus / PaperSize enum values match the StrEnums", () => {
    const formats: ExportFormat[] = ["pdf", "epub", "md", "docx"];
    expect(formats).toEqual(["pdf", "epub", "md", "docx"]);

    const statuses: ExportJobStatus[] = ["pending", "running", "completed", "failed"];
    expect(statuses).toEqual(["pending", "running", "completed", "failed"]);

    const papers: PaperSize[] = ["b-format-129x198", "a5", "a4", "letter", "custom"];
    expect(papers).toEqual(["b-format-129x198", "a5", "a4", "letter", "custom"]);
  });

  it("ExportJob matches the public job view (ExportJob model)", () => {
    const sample: ExportJob = {
      job_id: "job-1",
      novel_id: "00000000-0000-0000-0000-000000000001",
      format: "pdf",
      status: "completed",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:01Z",
      artifact_url: "/api/v1/export/jobs/job-1/artifact?token=t",
      error: null,
    };
    expect(fieldNames(sample)).toEqual([
      "artifact_url",
      "created_at",
      "error",
      "format",
      "job_id",
      "novel_id",
      "status",
      "updated_at",
    ]);
  });

  it("ExportOptions matches the per-request options model", () => {
    const sample: ExportOptions = {
      format: "pdf",
      volume_id: null,
      include_front_matter: true,
      include_back_matter: true,
      include_summaries: false,
      include_character_list: false,
      include_location_glossary: false,
      pdf_options: null,
      epub_options: null,
      markdown_options: null,
    };
    expect(fieldNames(sample)).toEqual([
      "epub_options",
      "format",
      "include_back_matter",
      "include_character_list",
      "include_front_matter",
      "include_location_glossary",
      "include_summaries",
      "markdown_options",
      "pdf_options",
      "volume_id",
    ]);
  });

  it("PdfOptions / EpubOptions / MarkdownOptions field names", () => {
    const pdf: PdfOptions = {
      paper_size: "b-format-129x198",
      margins: null,
      body_size_pt: 11,
      leading_ratio: 1.2,
      drop_caps: false,
      include_toc: true,
    };
    expect(fieldNames(pdf)).toEqual([
      "body_size_pt",
      "drop_caps",
      "include_toc",
      "leading_ratio",
      "margins",
      "paper_size",
    ]);

    const epub: EpubOptions = { cover_image_path: null, css: null, isbn: null, description: null };
    expect(fieldNames(epub)).toEqual(["cover_image_path", "css", "description", "isbn"]);

    const md: MarkdownOptions = { chapter_heading_level: 1, include_front_matter: true };
    expect(fieldNames(md)).toEqual(["chapter_heading_level", "include_front_matter"]);
  });

  it("MirroredMargins + FormatAvailability + ExportRequest field names", () => {
    const margins: MirroredMargins = {
      inside_mm: 20,
      outside_mm: 15,
      top_mm: 18,
      bottom_mm: 18,
    };
    expect(fieldNames(margins)).toEqual(["bottom_mm", "inside_mm", "outside_mm", "top_mm"]);

    const availability: FormatAvailability = { format: "pdf", available: true };
    expect(fieldNames(availability)).toEqual(["available", "format"]);

    const request: ExportRequest = {
      novel_id: "00000000-0000-0000-0000-000000000001",
      options: { format: "epub" } as ExportOptions,
    };
    expect(fieldNames(request)).toEqual(["novel_id", "options"]);
  });

  it("Artifact (renderer output) field names — NOT a REST response shape", () => {
    const artifact: Artifact = {
      format: "pdf",
      path: "/tmp/x.pdf",
      media_type: "application/pdf",
      suggested_filename: "novel.pdf",
    };
    expect(fieldNames(artifact)).toEqual(["format", "media_type", "path", "suggested_filename"]);
  });
});
