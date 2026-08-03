/**
 * VRT Screenshot Tests: AdaptiveDashboard (ADR-059, ADR-069 §25 / D12, ADR-070)
 *
 * Captures the LEARN-002 settings dashboard (toggle + 4 weight sliders + source
 * summary + recent-activity timeline) across 4 theme variants: light/dark ×
 * neutral/narrare.
 *
 * The dashboard is mounted on the dev VRT fixture page (`/dev/vrt/adaptive` —
 * same precedent as `/dev/design-tokens`). Each test mocks the canonical
 * adaptive-context query AND the ADR-070 adaptive-snapshots query with
 * deterministic fixtures, and scopes the screenshot to the `#adaptive-dashboard`
 * section. The real `/novel/[id]/settings` route is deliberately avoided: its
 * on-demand dev-server compile is too slow/flaky for repeatable VRT (see
 * phase5-task-13-report.md).
 *
 * Theme selection: the theme store (`narrare-theme` localStorage, zustand
 * persist) drives both axes — `theme` (neutral|narrare) and `colorMode`
 * (light|dark). We pin both via addInitScript before first paint, and also
 * emulateMedia so native form controls render in the matching scheme.
 *
 * Determinism guarantees:
 *  - Every `/api/v1/**` request is explicitly mocked. A catch-all route
 *    (registered FIRST — Playwright matches routes in reverse registration
 *    order, so specific mocks always win) records any unmocked call; the test
 *    polls the list and fails with the offending URLs before the screenshot.
 *    Without this guard, a component query that is forgotten to mock silently
 *    proxies through the Next rewrite to `localhost:8000` (ECONNREFUSED — the
 *    VRT job runs no API) and renders a degraded state that pollutes the
 *    baseline. That is exactly the failure class CI run 30758014183 caught
 *    when ADR-069 §25 added the history timeline (`/snapshots`) without
 *    updating this spec.
 *  - `requestfailed` is NOT usable for that guard: the Next dev rewrite turns
 *    an unreachable upstream into an HTTP 500 response, so the browser fetch
 *    resolves normally and no `requestfailed` event fires. Only a catch-all
 *    route intercepts the request before it reaches the network.
 *  - The activity timeline formats timestamps via `Intl.DateTimeFormat` in the
 *    browser timezone, so `timezoneId` is pinned to UTC (CI runners are UTC) to
 *    keep baselines host-independent.
 *
 * @see packages/web/components/studio/settings/AdaptiveDashboard.tsx
 * @see packages/web/app/(studio)/dev/vrt/adaptive/page.tsx
 */

import { expect, type Page, test } from "@playwright/test";

const VRT_NOVEL_ID = "vrt-novel";

/** Deterministic adaptive-context fixture — fully populated dashboard. */
const CONTEXT_FIXTURE = {
  project_id: VRT_NOVEL_ID,
  enabled: true,
  weights: { preference: 0.8, voice_fidelity: 0.6, style_constraints: 0.5, avoidance: 0.3 },
  sources: {
    preference_text: "Prefers concise prose with vivid sensory detail.",
    voice_profiles_text: "Elena: contemplative, measured; Marcus: terse, sardonic.",
    style_constraints_text: "Avoid adverb stacks; limit dialogue tags to 'said'.",
    avoidance_patterns_text: "Clichés: 'silent as the grave', 'eyes like fire'.",
  },
  has_any_signal: true,
};

/**
 * Deterministic adaptive-snapshots fixture (ADR-070) — 3 timeline rows with
 * deliberate variety so every render branch of `SnapshotRow` is exercised:
 * two fully-populated rows (mode + weights + source summary) and one sparse row
 * (no mode/weights/sources). Newest first, matching the component's defensive
 * sort — but the spec asserts the rendered count, not the order.
 *
 * Payload mirrors the wire contract 1:1: `source_summary` uses the single
 * `summary` key the backend actually writes
 * (`adaptive_context_provider._record_snapshot`), not per-source keys — the UI
 * renders that key as the chip label.
 */
const SNAPSHOTS_FIXTURE = {
  project_id: VRT_NOVEL_ID,
  items: [
    {
      invocation_id: "inv-vrt-2026-07-24T10:15:00Z",
      novel_id: VRT_NOVEL_ID,
      intent: "write",
      mode: "continue",
      created_at: "2026-07-24T10:15:00Z",
      source_summary: { summary: "preference; voice profiles; style constraints" },
      weights: { preference: 0.8, voice_fidelity: 0.6, style_constraints: 0.5, avoidance: 0.3 },
    },
    {
      invocation_id: "inv-vrt-2026-07-23T16:42:00Z",
      novel_id: VRT_NOVEL_ID,
      intent: "dialogue_coach",
      mode: "refine",
      created_at: "2026-07-23T16:42:00Z",
      source_summary: { summary: "voice profiles; preference" },
      weights: { preference: 0.7, voice_fidelity: 0.9, style_constraints: 0.6, avoidance: 0.4 },
    },
    {
      invocation_id: "inv-vrt-2026-07-22T09:05:00Z",
      novel_id: VRT_NOVEL_ID,
      intent: "worldbuilding",
      mode: null,
      created_at: "2026-07-22T09:05:00Z",
      source_summary: null,
      weights: null,
    },
  ],
};

type ThemeAxis = "neutral" | "narrare";
type ColorAxis = "light" | "dark";

/** Unmocked /api/v1/** requests observed by the catch-all route (reset per test). */
const unmockedApiCalls: string[] = [];

/** Pre-paint the zustand-persisted theme store so first render is correct. */
async function pinTheme(page: Page, theme: ThemeAxis, mode: ColorAxis) {
  await page.addInitScript(
    ([t, m]) => {
      localStorage.setItem(
        "narrare-theme",
        JSON.stringify({ state: { theme: t, colorMode: m }, version: 0 }),
      );
    },
    [theme, mode] as const,
  );
  await page.emulateMedia({ colorScheme: mode });
}

test.describe("AdaptiveDashboard VRT", () => {
  // First on-demand dev-server compile of the `/dev/vrt/adaptive` route can
  // exceed the default 30s test timeout; 120s gives the cold compile room.
  test.describe.configure({ timeout: 120000 });

  // Timeline timestamps render via Intl.DateTimeFormat in the browser timezone —
  // pin UTC so baselines are identical on CI (UTC) and local machines.
  test.use({ timezoneId: "UTC" });

  test.beforeEach(async ({ page }) => {
    // Systemic guard: every /api/v1/** request must be explicitly mocked below.
    // Registered FIRST — Playwright tries routes in reverse registration order,
    // so the specific mocks are always checked before this catch-all. Unmocked
    // calls are recorded and asserted empty before the screenshot.
    unmockedApiCalls.length = 0;
    await page.route("**/api/v1/**", async (route) => {
      unmockedApiCalls.push(`${route.request().method()} ${route.request().url()}`);
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Unmocked API request in VRT" }),
      });
    });

    // `/dev/*` is NOT protected by proxy.ts — only the client-side AuthGate
    // `/auth/me` mock is needed (same as the design-tokens VRT setup).
    await page.route("**/api/v1/auth/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "user-1",
          email: "test@example.com",
          display_name: "Test User",
          avatar_url: null,
          created_at: "2024-01-01T00:00:00Z",
        }),
      });
    });
    await page.route("**/api/v1/auth/refresh", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ access_token: "mock-vrt-token", token_type: "bearer" }),
      });
    });

    // Canonical adaptive-context query (the dashboard's own data source).
    await page.route(`**/api/v1/adaptive/${VRT_NOVEL_ID}/context`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(CONTEXT_FIXTURE),
      });
    });

    // Canonical adaptive-snapshots query (ADR-070) — the activity timeline.
    await page.route(`**/api/v1/adaptive/${VRT_NOVEL_ID}/snapshots*`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(SNAPSHOTS_FIXTURE),
      });
    });

    // Suppress the first-visit feature tour overlay.
    await page.addInitScript(() => {
      localStorage.setItem("narrare:featureTourCompleted", "true");
    });
  });

  for (const theme of ["neutral", "narrare"] as const) {
    for (const mode of ["light", "dark"] as const) {
      test(`${theme} theme — ${mode} mode`, async ({ page }) => {
        await pinTheme(page, theme, mode);

        await page.goto("/dev/vrt/adaptive", {
          waitUntil: "domcontentloaded",
          timeout: 110000,
        });

        // Wait for the adaptive-context response so the dashboard is fully
        // populated (not its loading skeleton).
        await page.waitForResponse((resp) =>
          resp.url().includes(`/adaptive/${VRT_NOVEL_ID}/context`),
        );

        const dashboard = page.locator("#adaptive-dashboard");
        await expect(dashboard).toBeVisible();

        // Ensure the source summary rendered (query settled) before snapshot.
        await expect(dashboard.getByText("Active Sources")).toBeVisible();

        // Systemic guard: no /api/v1/** request may go unmocked (see beforeEach).
        // Polled (not a one-shot assertion) so a request that fires slightly
        // later is still captured; the failure diff lists the offending URLs.
        // Placed BEFORE the content guards so an unmocked call fails with this
        // diagnostic instead of a masked "Recent Activity not visible" timeout.
        await expect
          .poll(() => unmockedApiCalls, {
            message: "Every /api/v1/** request must be explicitly mocked (see beforeEach)",
            timeout: 10_000,
          })
          .toEqual([]);

        // Guard: the activity timeline rendered its 3 rows — not the degraded
        // empty state. Proves the /snapshots mock was consumed, so a baseline
        // can never silently capture "No recent activity yet." again.
        await expect(dashboard.getByText("Recent Activity")).toBeVisible();
        await expect(dashboard.getByTestId("snapshot-intent")).toHaveCount(3);

        await expect(dashboard).toHaveScreenshot(`adaptive-dashboard-${theme}-${mode}.png`);
      });
    }
  }
});
