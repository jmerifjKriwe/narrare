"use client";

import { AdaptiveStatusIndicator } from "@/components/studio/editor-view/AdaptiveStatusIndicator";
/**
 * VRT fixture page for the adaptive-context components (ADR-059).
 *
 * Renders {@link AdaptiveStatusIndicator} and {@link AdaptiveDashboard} in
 * isolation with a fixed `novelId`, so Playwright VRT can capture deterministic
 * screenshots without navigating the heavy `/novel/[id]` editor or `/novel/[id]/
 * settings` routes (whose on-demand dev-server compile is too slow/flaky for
 * repeatable VRT — see `.superpowers/sdd/phase5-task-13-report.md`).
 *
 * Mirrors the `/dev/design-tokens` precedent: a dev-only (`NODE_ENV`) page under
 * the unprotected `/dev/*` prefix (proxy.ts only guards `/dashboard`, `/wizard`,
 * `/novel`), so the server-side JWT cookie check is bypassed and only the
 * client-side AuthGate `/auth/me` mock is needed.
 *
 * The components fetch their own data via the canonical TanStack Query key
 * (ADR-069 D15); tests mock `GET /adaptive/{novelId}/context` via `page.route()`
 * to drive each visual state. Both sections carry stable `id`s for screenshot
 * scoping (same convention as the design-tokens page sections).
 */
import { AdaptiveDashboard } from "@/components/studio/settings/AdaptiveDashboard";

/** Fixed project id — tests mock `/adaptive/vrt-novel/context`. */
const VRT_NOVEL_ID = "vrt-novel";

export default function AdaptiveVrtPage() {
  if (process.env.NODE_ENV !== "development") return null;

  return (
    <div className="mx-auto max-w-4xl px-8 py-10 space-y-12">
      <header className="space-y-1">
        <h1 className="text-2xl font-medium">Adaptive Context — VRT</h1>
        <p className="text-sm text-muted-foreground">
          Visual-regression fixture for AdaptiveStatusIndicator + AdaptiveDashboard. Dev-only.
        </p>
      </header>

      {/* AdaptiveStatusIndicator — captured in 3 states × light/dark.
          Scoped via #adaptive-indicator. */}
      <section
        id="adaptive-indicator"
        className="flex items-center gap-4 rounded-lg border border-border bg-card p-4"
      >
        <AdaptiveStatusIndicator novelId={VRT_NOVEL_ID} />
      </section>

      {/* AdaptiveDashboard — captured in 4 theme variants.
          Scoped via #adaptive-dashboard. */}
      <section id="adaptive-dashboard">
        <AdaptiveDashboard novelId={VRT_NOVEL_ID} />
      </section>
    </div>
  );
}
