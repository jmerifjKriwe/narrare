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
// the request falls through MSW (`onUnhandledRequest: "bypass"`, setupTests.ts)
// and attempts a real network connection against the happy-dom origin
// `http://localhost:3000` → `ECONNREFUSED` noise in every gate log (the
// defect fixed 2026-08-18; suite-wide diagnostic showed this is the ONLY
// unhandled endpoint).
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
