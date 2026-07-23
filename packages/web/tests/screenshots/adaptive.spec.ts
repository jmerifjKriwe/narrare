/**
 * VRT Screenshot Tests: AdaptiveDashboard (ADR-059, ADR-069 §25 / D12)
 *
 * Captures the LEARN-002 settings dashboard (toggle + 4 weight sliders + source
 * summary) across 4 theme variants: light/dark × neutral/narrare.
 *
 * The dashboard is mounted on the dev VRT fixture page (`/dev/vrt/adaptive` —
 * same precedent as `/dev/design-tokens`). Each test mocks the canonical
 * adaptive-context query with a deterministic fixture and scopes the screenshot
 * to the `#adaptive-dashboard` section. The real `/novel/[id]/settings` route
 * is deliberately avoided: its on-demand dev-server compile is too slow/flaky
 * for repeatable VRT (see phase5-task-13-report.md).
 *
 * Theme selection: the theme store (`narrare-theme` localStorage, zustand
 * persist) drives both axes — `theme` (neutral|narrare) and `colorMode`
 * (light|dark). We pin both via addInitScript before first paint, and also
 * emulateMedia so native form controls render in the matching scheme.
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

type ThemeAxis = "neutral" | "narrare";
type ColorAxis = "light" | "dark";

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

  test.beforeEach(async ({ page }) => {
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

        await expect(dashboard).toHaveScreenshot(`adaptive-dashboard-${theme}-${mode}.png`);
      });
    }
  }
});
