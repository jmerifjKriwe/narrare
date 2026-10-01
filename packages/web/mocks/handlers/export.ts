import { HttpResponse, http } from "msw";
import type { FormatAvailability } from "@/types";

// ---------------------------------------------------------------------------
// Export — IO-001 / ADR-081
// ---------------------------------------------------------------------------
//
// Default handler(s) for the export domain. `GET /export/formats` is fired on
// MOUNT by useExportPanel (composed into every EditorView render via
// EditorOverlays → ExportPanel), so ANY test rendering the editor without a
// per-test `server.use` override hits this endpoint. Without a default handler
// the request is unhandled (`onUnhandledFrame: "error"`, setupTests.ts) and
// the running test FAILS via the mechanical request:unhandled guard — the
// defect class fixed 2026-08-18 (ECONNREFUSED noise, commit 0006ec86); the
// error-policy hardening then proved this is the ONLY default-handler gap the
// suite had.
//
// The interactive endpoints (POST /export, GET /export/jobs/:id, artifact
// download) are only fired on explicit user action and are covered per-test
// via `server.use` (see lib/api/__tests__/export.test.ts) — no defaults here,
// so those tests keep asserting their own responses.

/** All four formats available — deterministic happy-path default. */
const FORMAT_AVAILABILITY: FormatAvailability[] = [
  { format: "pdf", available: true },
  { format: "epub", available: true },
  { format: "md", available: true },
  { format: "docx", available: true },
];

export const handlers = [
  http.get("*/api/v1/export/formats", () => HttpResponse.json(FORMAT_AVAILABILITY)),
];
