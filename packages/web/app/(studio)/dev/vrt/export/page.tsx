"use client";

import { ExportPanel } from "@/components/studio/export/ExportPanel";

/**
 * VRT fixture page for the Export panel (IO-001 / ADR-081).
 *
 * Renders the {@link ExportPanel} modal in its open, idle state with a fixed
 * `novelId`, so Playwright VRT can capture deterministic screenshots without
 * navigating the heavy `/novel/[id]` editor route (whose on-demand dev-server
 * compile is too slow/flaky for repeatable VRT — see the `/dev/vrt/adaptive`
 * precedent).
 *
 * Mirrors the `/dev/design-tokens` + `/dev/vrt/adaptive` precedent: a dev-only
 * (`NODE_ENV`) page under the unprotected `/dev/*` prefix (proxy.ts only guards
 * `/dashboard`, `/wizard`, `/novel`), so only the client-side AuthGate
 * `/auth/me` mock is needed.
 *
 * The panel fetches format availability via the canonical query key
 * (`["export", "formats"]`); tests mock `GET /export/formats` via
 * `page.route()` to drive the visual state (PDF selected, MD unavailable).
 */
export default function ExportVrtPage() {
  if (process.env.NODE_ENV !== "development") return null;

  return (
    <div className="min-h-screen bg-background">
      <div id="export-panel-vrt" className="min-h-screen">
        <ExportPanel novelId="vrt-novel" isOpen onClose={() => {}} />
      </div>
    </div>
  );
}
