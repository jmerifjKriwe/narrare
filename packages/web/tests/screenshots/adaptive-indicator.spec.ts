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

test.describe("AdaptiveStatusIndicator VRT", () => {
  // First on-demand dev-server compile of the `/dev/vrt/adaptive` route can
  // exceed the default 30s test timeout; 120s gives the cold compile room — only
  // the first test pays it, subsequent tests reuse the compiled route.
  test.describe.configure({ timeout: 120000 });

  test.beforeEach(async ({ page }) => {
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

        await expect(indicator).toHaveScreenshot(`adaptive-indicator-${state}-${mode}.png`);
      });
    }
  }
});
