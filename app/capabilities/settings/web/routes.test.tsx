// @vitest-environment jsdom
/**
 * The settings capability's `/settings` gate (W7 Task 3): an unconfigured
 * instance is handed to the welcome at `/setup` before the page mounts, and
 * a configured one reaches the Allgemein surface. Driven through a real
 * router over the real root route with the generated capability table (the
 * app's own composition), so the redirect lands on setup's real `/setup`
 * door. The page itself is mocked at its module boundary — its contract
 * lives in SettingsPage.test; the request's truth is the backend's and the
 * E2E's.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

// The face mocked so the gate's choice is observable here; the page's
// contract lives in SettingsPage.test and the E2E pins it on the real stack.
vi.mock("./SettingsPage", () => ({ SettingsPage: () => <p>settings placeholder</p> }));

import { client } from "@shell/lib/api/client";
import { capabilityRoutes } from "@shell/lib/generated/routes";
import { t } from "@shell/lib/i18n";
import { queryClient } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<"GET" | "PATCH", ReturnType<typeof vi.fn>>;

function ok(): Response {
  return new Response(null, { status: 200 });
}

/** The shell root's settings read always answers (the pre-paint gate opens
 *  on it); the gate's status read answers what the case scripts. */
function scriptStatus(complete: boolean) {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") {
      return { data: { locale: null, theme: null }, response: ok() };
    }
    if (path === "/api/setup/status") return { data: { complete }, response: ok() };
    throw new Error(`unexpected request: ${path}`);
  });
}

function renderTree(path: string) {
  const router = createRouter({
    routeTree: rootRoute.addChildren([...capabilityRoutes]),
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
});

describe("the /settings gate", () => {
  it("redirects an unconfigured instance to the welcome at /setup", async () => {
    scriptStatus(false);
    const router = renderTree("/settings");
    // The gate hands the unconfigured instance to setup's door, and the real
    // welcome answers there — not a not-found, not the settings surface.
    expect(
      await screen.findByRole("heading", { level: 1, name: t("setup.welcome.heroTitle") }),
    ).toBeTruthy();
    expect(router.state.location.pathname).toBe("/setup");
    expect(screen.queryByText("settings placeholder")).toBeNull();
    expect(api.GET).toHaveBeenCalledWith("/api/setup/status");
  });

  it("a configured instance reaches the Allgemein surface", async () => {
    scriptStatus(true);
    const router = renderTree("/settings");
    await waitFor(() => expect(screen.getByText("settings placeholder")).toBeTruthy());
    expect(router.state.location.pathname).toBe("/settings");
  });
});
