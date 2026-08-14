/**
 * Export-pipeline API client (IO-001 / ADR-081).
 *
 * Typed wrappers around the four export endpoints. Components never call
 * fetch directly — always use these functions (the repo convention; see
 * novels.ts).
 *
 * Endpoints (OpenAPI SSOT — docs/reference/openapi.json):
 *   GET  /api/v1/export/formats               → listFormats()
 *   POST /api/v1/export                       → createExport()
 *   GET  /api/v1/export/jobs/{job_id}         → getJob()
 *   GET  /api/v1/export/jobs/{job_id}/artifact → downloadArtifact()
 *
 * The artifact endpoint returns a proxied file stream (NOT a 302 redirect),
 * so the download is fetched with the auth header (fetchApiRaw) and turned
 * into a browser download. The temp file is single-use server-side.
 */

import type { ExportJob, ExportOptions, FormatAvailability } from "@/types";
import { fetchApi, fetchApiRaw } from "./core";

/**
 * Extract the signed single-use token from a job's `artifact_url`.
 *
 * `artifact_url` has the shape `/api/v1/export/jobs/{id}/artifact?token=…`
 * (built by the backend registry, URL-encoded). Returns null when the URL is
 * absent or malformed so callers can guard before calling downloadArtifact.
 */
export function parseArtifactToken(artifactUrl: string | null): string | null {
  if (!artifactUrl) return null;
  try {
    // artifact_url is a path-relative URL; resolve against a dummy origin so
    // the URL/URLSearchParams parsers accept it.
    const url = new URL(artifactUrl, "http://export.local");
    return url.searchParams.get("token");
  } catch {
    return null;
  }
}

/**
 * Parse the suggested filename from a Content-Disposition header.
 * Falls back to `{jobId}-export` when the header is absent / unparsable.
 */
function parseFilename(disposition: string | null, fallback: string): string {
  if (!disposition) return fallback;
  // Starlette FileResponse writes: attachment; filename="my-novel.pdf"
  const match = /filename="?([^";]+)"?/i.exec(disposition);
  return match?.[1] ?? fallback;
}

export interface DownloadedArtifact {
  readonly blob: Blob;
  readonly filename: string;
}

export const exportApi = {
  /** List every format + whether its render binary is available (RULE-11). */
  listFormats: () => fetchApi<FormatAvailability[]>("/export/formats"),

  /** Create + dispatch an export job (201; 503 if the format is unavailable). */
  createExport: (novelId: string, options: ExportOptions) =>
    fetchApi<ExportJob>("/export", {
      method: "POST",
      body: JSON.stringify({ novel_id: novelId, options }),
    }),

  /** Poll an export job's status (404 if unknown — lost on restart, D1). */
  getJob: (jobId: string) => fetchApi<ExportJob>(`/export/jobs/${jobId}`),

  /**
   * Fetch the artifact stream with auth + return a Blob + suggested filename.
   * The caller triggers the browser download (DOM concern, RULE-06).
   *
   * Single-use server-side: a second call with the same token 410s.
   */
  async downloadArtifact(jobId: string, token: string): Promise<DownloadedArtifact> {
    const endpoint = `/export/jobs/${jobId}/artifact?token=${encodeURIComponent(token)}`;
    const response = await fetchApiRaw(endpoint);
    if (!response.ok) {
      throw new Error(response.status === 410 ? "HTTP 410" : `HTTP ${response.status}`);
    }
    const blob = await response.blob();
    const filename = parseFilename(response.headers.get("Content-Disposition"), `${jobId}-export`);
    return { blob, filename };
  },
};
