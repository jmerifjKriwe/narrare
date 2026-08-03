/**
 * VRT Screenshot Tests: AdaptiveStatusIndicator (ADR-059, ADR-069 D14)
 *
 * Captures the always-visible indicator across its 3 derived states
 * (active / paused / no-data) in both light and dark color modes.
 *
 * 3 states × 2 color modes = 6 baselines.
 *
 * The indicator's state is pure derived state from the canonical adaptive
 * context query (ADR-069 D15). Each test mocks `GET /adaptive/{id}/context`
 * with a deterministic fixture, navigates to the dev VRT fixture page
 * (`/dev/vrt/adaptive` — same precedent as `/dev/design-tokens`), and scopes
 * the screenshot to the `#adaptive-indicator` section. The real `/novel/[id]`
 * editor route is deliberately avoided: its on-demand dev-server compile is too
 * slow/flaky for repeatable VRT (see phase5-task-13-report.md).
 *
 * @see packages/web/components/studio/editor-view/AdaptiveStatusIndicator.tsx
 * @see packages/web/app/(studio)/dev/vrt/adaptive/page.tsx
 */

import { expect, test } from "@playwright/test";

const VRT_NOVEL_ID = "vrt-novel";

/** Deterministic adaptive-context fixtures — one per indicator state. */
const CONTEXT_FIXTURES = {
  /** enabled + has_any_signal → "active" (brand violet, gently pulsing). */
  active: {
    project_id: VRT_NOVEL_ID,
    enabled: true,
    weights: { preference: 0.8, voice_fidelity: 0.6, style_constraints: 0.5, avoidance: 0.4 },
    sources: {
      preference_text: "Prefers concise prose with vivid sensory detail.",
      voice_profiles_text: "Elena: contemplative; Marcus: terse and sardonic.",
      style_constraints_text: "Avoid adverb stacks; limit dialogue tags.",
      avoidance_patterns_text: "Clichés: 'silent as the grave'.",
    },
    has_any_signal: true,
  },
  /** disabled + has_any_signal → "paused" (muted). */
  paused: {
    project_id: VRT_NOVEL_ID,
    enabled: false,
    weights: { preference: 0.8, voice_fidelity: 0.6, style_constraints: 0.5, avoidance: 0.4 },
    sources: {
      preference_text: "Prefers concise prose with vivid sensory detail.",
      voice_profiles_text: "Elena: contemplative; Marcus: terse and sardonic.",
      style_constraints_text: "Avoid adverb stacks; limit dialogue tags.",
      avoidance_patterns_text: "Clichés: 'silent as the grave'.",
    },
    has_any_signal: true,
  },
  /** no signal → "no-data" (dashed/outline). */
  "no-data": {
    project_id: VRT_NOVEL_ID,
    enabled: false,
    weights: { preference: 0.5, voice_fidelity: 0.5, style_constraints: 0.5, avoidance: 0.5 },
    sources: {
      preference_text: "",
      voice_profiles_text: "",
      style_constraints_text: "",
      avoidance_patterns_text: "",
    },
    has_any_signal: false,
  },
} as const;

/** The label text the indicator renders per state (i18n: adaptive.indicator.*). */
const STATE_LABEL: Record<keyof typeof CONTEXT_FIXTURES, string> = {
  active: "Active",
  paused: "Paused",
  "no-data": "No data",
};

/**
 * Deterministic adaptive-snapshots fixture (ADR-070).
 *
 * Deliberately EMPTY: `AdaptiveStatusIndicator` derives its state purely from
 * the `/context` query (see component) — it never reads snapshot rows. The
 * `/snapshots` request fires from the co-mounted `AdaptiveDashboard` on this
 * shared `/dev/vrt/adaptive` VRT page (both sections render together), and
 * that dashboard's timeline lives OUTSIDE the `#adaptive-indicator` screenshot
 * scope. So an empty-but-valid envelope satisfies the ADR-059 systemic guard
 * (no unmocked call) without coupling THIS indicator baseline to dashboard
 * timeline content that is out of scope and owned by `adaptive.spec.ts`.
 * Empty = maximal determinism: no timestamps, no per-row variation.
 *
 * RULE-17: shape mirrors `AdaptiveSnapshotsResponse` (types/adaptive.ts) — the
 * wrapper `{ project_id, items }`, never a bare array.
 */
const SNAPSHOTS_FIXTURE = {
  project_id: VRT_NOVEL_ID,
  items: [],
};

/** Unmocked /api/v1/** requests observed by the catch-all route (reset per test). */
const unmockedApiCalls: string[] = [];

test.describe("AdaptiveStatusIndicator VRT", () => {
  // First on-demand dev-server compile of the `/dev/vrt/adaptive` route can
  // exceed the default 30s test timeout; 120s gives the cold compile room — only
  // the first test pays it, subsequent tests reuse the compiled route.
  test.describe.configure({ timeout: 120000 });

  // Pin the timezone so baselines are identical on CI (UTC) and local machines
  // (ADR-059 Mock Contract BINDING — timezoneId is required for every VRT spec).
  test.use({ timezoneId: "UTC" });

  test.beforeEach(async ({ page }) => {
    // Systemic guard: every /api/v1/** request must be explicitly mocked below.
    // Registered FIRST — Playwright tries routes in reverse registration order,
    // so the specific mocks are always checked before this catch-all. Unmocked
    // calls are recorded and asserted empty before the screenshot (ADR-059).
    unmockedApiCalls.length = 0;
    await page.route("**/api/v1/**", async (route) => {
      unmockedApiCalls.push(`${route.request().method()} ${route.request().url()}`);
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Unmocked API request in VRT" }),
      });
    });

    // `/dev/*` is NOT protected by proxy.ts (only /dashboard, /wizard, /novel
    // are), so no server-side JWT cookie is needed — only the client-side
    // AuthGate `/auth/me` mock. Mirrors the design-tokens VRT setup.
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

    // Canonical adaptive-snapshots query (ADR-070). The indicator itself does
    // not consume snapshots, but the co-mounted AdaptiveDashboard on this VRT
    // page fires the request — registering an empty-but-valid envelope here
    // keeps it off the catch-all / unmocked list (ADR-059). Registered AFTER
    // the catch-all so Playwright's reverse-order matching checks it first.
    await page.route(`**/api/v1/adaptive/${VRT_NOVEL_ID}/snapshots*`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(SNAPSHOTS_FIXTURE),
      });
    });

    // Suppress the first-visit feature tour overlay (blocks pointer events).
    await page.addInitScript(() => {
      localStorage.setItem("narrare:featureTourCompleted", "true");
    });
  });

  for (const state of ["active", "paused", "no-data"] as const) {
    for (const mode of ["light", "dark"] as const) {
      test(`${state} — ${mode} mode`, async ({ page }) => {
        // Deterministic color mode (theme store defaults to "system").
        await page.emulateMedia({ colorScheme: mode });

        // Mock the canonical adaptive-context query with the state fixture.
        await page.route(`**/api/v1/adaptive/${VRT_NOVEL_ID}/context`, async (route) => {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(CONTEXT_FIXTURES[state]),
          });
        });

        await page.goto("/dev/vrt/adaptive", {
          waitUntil: "domcontentloaded",
          timeout: 110000,
        });

        // Wait for the adaptive-context response so the indicator reflects the
        // mocked state (not the transient loading/no-data default).
        await page.waitForResponse((resp) =>
          resp.url().includes(`/adaptive/${VRT_NOVEL_ID}/context`),
        );

        const indicator = page.locator("#adaptive-indicator");
        await expect(indicator).toBeVisible();

        // Guard: the resolved label matches the expected state, so we never
        // snapshot a stale loading frame.
        await expect(indicator).toContainText(STATE_LABEL[state]);

        // Systemic guard: no /api/v1/** request may go unmocked (see
        // beforeEach). Polled so a late-firing request is still caught.
        await expect.poll(() => unmockedApiCalls).toEqual([]);

        await expect(indicator).toHaveScreenshot(`adaptive-indicator-${state}-${mode}.png`);
      });
    }
  }
});
