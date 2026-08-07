# Visual Regression Tests (VRT)

This directory holds Playwright `toHaveScreenshot()` specs that pin the visual
appearance of key UI surfaces across all theme variants (light/dark ×
neutral/narrare). The strategy, scope, and the **binding Mock Contract** are
defined in
[ADR-059](../../../docs/architecture/decisions/ADR-059-vrt-and-design-system-strategy.md).
See also the VRT section in
[testing-standards.md](../../../docs/development/testing-standards.md).

## Running

Always use the `just` recipes — they wrap browser/port dependency checks so you
do not need to memorize raw Playwright flags:

```bash
just vrt          # standard run (run before every UI PR)
just vrt-update   # regenerate baselines (--update-snapshots) AFTER visual review
```

If Chromium or other browser binaries are missing, `just vrt` prints a copyable
install command rather than failing with a cryptic error.

> **Warning:** Never update snapshots blindly. `just vrt-update` overwrites the
> baselines — run it only after you have visually verified the diff is the
> intended change. A careless update locks a visual regression in as the new
> truth.

## Snapshot folder convention

Playwright writes baselines next to each spec as
`<spec>.spec.ts-snapshots/<name>-<project>-linux.png`, where `<project>` is the
Playwright project name (`vrt`) and the suffix matches the CI OS (`linux`).
Baselines must be generated on the CI rendering environment (Ubuntu + CI
Chromium) to avoid cross-OS font-rendering drift; `maxDiffPixelRatio: 0.02`
tolerates minor pixel noise but not dimension changes. See ADR-059 §"Regenerating
baselines from CI artifacts" for the artifact-download workflow.

## Mock Contract (BINDING — ADR-059)

**Every `/api/v1/**` request the screened component makes MUST be explicitly
mocked.** Two mechanisms enforce this:

1. A **Catch-all route** `page.route("**/api/v1/**", …)` registered **first**
   (Playwright matches routes in reverse registration order, so specific mocks
   always win) that records any unmocked call into an array.
2. An **`expect.poll(() => unmockedApiCalls).toEqual([])`** guard **before** the
   screenshot (polled, not one-shot, so late-firing requests are still caught).

`requestfailed` cannot replace the guard: the Next.js dev rewrite turns an
unreachable upstream (`ECONNREFUSED` — the VRT job runs no API) into an HTTP 500,
so no `requestfailed` event fires. See ADR-059 for the full rationale and the
CI-Run 30758014183 incident.

### Minimal boilerplate

```typescript
import { expect, type Page, test } from "@playwright/test";

const unmockedApiCalls: string[] = [];

test.describe("MyComponent VRT", () => {
  // Pin the timezone if the component renders dates via Intl.DateTimeFormat —
  // CI runners are UTC; without this, baselines drift by local time.
  test.use({ timezoneId: "UTC" });

  test.beforeEach(async ({ page }) => {
    // 1. Catch-all FIRST — records any unmocked /api/v1/** call.
    unmockedApiCalls.length = 0;
    await page.route("**/api/v1/**", async (route) => {
      unmockedApiCalls.push(`${route.request().method()} ${route.request().url()}`);
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Unmocked API request in VRT" }),
      });
    });

    // 2. Auth mocks (dev pages only need /auth/me + /auth/refresh).
    await page.route("**/api/v1/auth/me", async (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: "{}" }),
    );
    await page.route("**/api/v1/auth/refresh", async (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: "{}" }),
    );

    // 3. Mock EVERY endpoint the screened component calls — no exceptions.
    //    Add one page.route() per real call.
    await page.route("**/api/v1/<your-endpoint>", async (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: "…" }),
    );
  });

  for (const theme of ["neutral", "narrare"] as const) {
    for (const mode of ["light", "dark"] as const) {
      test(`${theme} theme — ${mode} mode`, async ({ page }) => {
        await page.goto("/dev/vrt/<fixture>", { waitUntil: "domcontentloaded" });

        // Systemic guard BEFORE the screenshot — proves every call was mocked.
        await expect.poll(() => unmockedApiCalls, { timeout: 10_000 }).toEqual([]);

        await expect(page.locator("#<scope>")).toHaveScreenshot(
          `name-${theme}-${mode}.png`,
        );
      });
    }
  }
});
```

For a full worked example (auth + two query mocks + theme pinning + content
guards), see `adaptive.spec.ts`.
