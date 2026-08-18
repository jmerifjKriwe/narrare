/**
 * Export API client tests — IO-001 / ADR-081.
 *
 * Covers the four endpoints + parseArtifactToken:
 *  1. listFormats  → GET /export/formats
 *  2. createExport → POST /export with { novel_id, options }
 *  3. getJob       → GET /export/jobs/:jobId
 *  4. downloadArtifact → GET .../artifact?token=… (stream → blob + filename)
 *  5. parseArtifactToken extracts the signed token from artifact_url
 *  6. Error handling (503 unavailable, 410 gone)
 */

import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import type { ExportJob, ExportOptions } from "@/types";
import { setAccessToken } from "../client";
import { exportApi, parseArtifactToken } from "../export";

// ── Fixtures ─────────────────────────────────────────────────────────────

const BASE_JOB: ExportJob = {
  job_id: "job-1",
  novel_id: "00000000-0000-0000-0000-000000000001",
  format: "pdf",
  status: "pending",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  artifact_url: null,
  error: null,
};

const PDF_OPTIONS: ExportOptions = {
  format: "pdf",
  volume_id: null,
  include_front_matter: true,
  include_back_matter: true,
  include_summaries: false,
  include_character_list: false,
  include_location_glossary: false,
  pdf_options: {
    paper_size: "b-format-129x198",
    margins: null,
    body_size_pt: 11,
    leading_ratio: 1.2,
    drop_caps: false,
    include_toc: true,
  },
  epub_options: null,
  markdown_options: null,
};

// ── Tests ────────────────────────────────────────────────────────────────

describe("exportApi", () => {
  beforeEach(() => {
    setAccessToken("test-access-token");
  });

  describe("listFormats", () => {
    it("GETs /export/formats and returns the availability list", async () => {
      let capturedUrl = "";
      server.use(
        http.get("*/api/v1/export/formats", ({ request }) => {
          capturedUrl = new URL(request.url).pathname;
          return HttpResponse.json([
            { format: "pdf", available: true },
            { format: "epub", available: true },
            { format: "md", available: false },
          ]);
        }),
      );

      const result = await exportApi.listFormats();
      expect(capturedUrl).toBe("/api/v1/export/formats");
      expect(result).toHaveLength(3);
      expect(result[2]).toEqual({ format: "md", available: false });
    });

    it("is served by the DEFAULT handler (no server.use override)", async () => {
      // Regression (2026-08-18): useExportPanel fires this query on mount, so
      // any test rendering EditorView/ExportPanel without an override relies
      // on the default handler in mocks/handlers/export.ts. Without it the
      // request bypasses MSW and attempts a real connection to the happy-dom
      // origin http://localhost:3000 → ECONNREFUSED noise in the suite log.
      const result = await exportApi.listFormats();
      expect(result).toHaveLength(4);
      expect(result.every((f) => f.available)).toBe(true);
      expect(new Set(result.map((f) => f.format))).toEqual(new Set(["pdf", "epub", "md", "docx"]));
    });
  });

  describe("createExport", () => {
    it("POSTs { novel_id, options } to /export and returns the job (201)", async () => {
      let capturedBody: Record<string, unknown> = {};
      server.use(
        http.post("*/api/v1/export", async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ ...BASE_JOB, status: "running" }, { status: 201 });
        }),
      );

      const result = await exportApi.createExport(BASE_JOB.novel_id, PDF_OPTIONS);

      expect(capturedBody.novel_id).toBe(BASE_JOB.novel_id);
      expect((capturedBody.options as { format: string }).format).toBe("pdf");
      expect(result.status).toBe("running");
    });

    it("surfaces a 503 when the format binary is unavailable", async () => {
      server.use(
        http.post("*/api/v1/export", async () =>
          HttpResponse.json({ detail: "Format unavailable" }, { status: 503 }),
        ),
      );

      await expect(exportApi.createExport(BASE_JOB.novel_id, PDF_OPTIONS)).rejects.toThrow();
    });
  });

  describe("getJob", () => {
    it("GETs /export/jobs/:jobId", async () => {
      let capturedUrl = "";
      server.use(
        http.get("*/api/v1/export/jobs/job-1", ({ request }) => {
          capturedUrl = new URL(request.url).pathname;
          return HttpResponse.json({
            ...BASE_JOB,
            status: "completed",
            artifact_url: "/x?token=t",
          });
        }),
      );

      const result = await exportApi.getJob("job-1");
      expect(capturedUrl).toBe("/api/v1/export/jobs/job-1");
      expect(result.status).toBe("completed");
      expect(result.artifact_url).toBe("/x?token=t");
    });
  });

  describe("downloadArtifact", () => {
    it("fetches the stream + parses the filename from Content-Disposition", async () => {
      let capturedQuery = "";
      server.use(
        http.get("*/api/v1/export/jobs/job-1/artifact", ({ request }) => {
          capturedQuery = new URL(request.url).searchParams.get("token") ?? "";
          return new HttpResponse("PDF-BYTES", {
            status: 200,
            headers: {
              "Content-Type": "application/pdf",
              "Content-Disposition": 'attachment; filename="my-novel.pdf"',
            },
          });
        }),
      );

      const result = await exportApi.downloadArtifact("job-1", "signed-token");
      expect(capturedQuery).toBe("signed-token");
      expect(result.filename).toBe("my-novel.pdf");
      expect(await result.blob.text()).toBe("PDF-BYTES");
    });

    it("falls back to a jobId-based filename without Content-Disposition", async () => {
      server.use(
        http.get(
          "*/api/v1/export/jobs/job-9/artifact",
          () =>
            new HttpResponse("X", { status: 200, headers: { "Content-Type": "application/pdf" } }),
        ),
      );

      const result = await exportApi.downloadArtifact("job-9", "tok");
      expect(result.filename).toBe("job-9-export");
    });

    it("rejects on a 410 (expired / single-use token)", async () => {
      server.use(
        http.get("*/api/v1/export/jobs/job-1/artifact", () =>
          HttpResponse.json({ detail: "gone" }, { status: 410 }),
        ),
      );

      await expect(exportApi.downloadArtifact("job-1", "tok")).rejects.toThrow("HTTP 410");
    });
  });

  describe("parseArtifactToken", () => {
    it("extracts the token from a signed artifact_url", () => {
      const url = "/api/v1/export/jobs/job-1/artifact?token=abc-123_def";
      expect(parseArtifactToken(url)).toBe("abc-123_def");
    });

    it("URL-decodes a percent-encoded token", () => {
      const url = "/api/v1/export/jobs/job-1/artifact?token=a%2Bb%3Dc";
      expect(parseArtifactToken(url)).toBe("a+b=c");
    });

    it("returns null for a null / malformed url", () => {
      expect(parseArtifactToken(null)).toBeNull();
      expect(parseArtifactToken("not-a-url")).toBeNull();
    });
  });
});
