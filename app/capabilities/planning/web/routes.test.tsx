// @vitest-environment jsdom
/**
 * The planning capability's setup gate: a failed status read throws the
 * refusal with its status, so the root error face names the server family
 * rather than the generic fallback, and never the seam's own English.
 * Driven through a real router over the real root route with the generated
 * capability table (the app's own composition); the lazy page is mocked at
 * its boundary because this file pins the gate, not the surface.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, configure, render, screen } from "@testing-library/react";

// Full-suite load: renders RouterProvider; see WorkspacePage.test.tsx.
configure({ asyncUtilTimeout: 5000 });
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

// The face mocked so the gate's failure is what this file observes; the
// page's contract lives in its own test.
vi.mock("./TimelinePage", () => ({ TimelinePage: () => <p>timeline placeholder</p> }));

import { client } from "@shell/lib/api/client";
import { capabilityRoutes } from "@shell/lib/generated/routes";
import { t } from "@shell/lib/i18n";
import { queryClient } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";

const api = client as unknown as Record<"GET", ReturnType<typeof vi.fn>>;

function ok(): Response {
  return new Response(null, { status: 200 });
}

/** The shell root's settings read always answers; the gate's status read
 *  answers a server outage without a body. */
function scriptStatusFailure(): void {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") {
      return { data: { locale: null, theme: null }, response: ok() };
    }
    if (path === "/api/setup/status") {
      return { data: undefined, response: new Response(null, { status: 503 }) };
    }
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

describe("the planning gate", () => {
  it("names a failed status read by its server family", async () => {
    scriptStatusFailure();
    renderTree("/novels/11111111-1111-1111-1111-111111111111/planning/timeline");

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(t("errors.server"));
    expect(alert.textContent).not.toContain(t("errors.unexpected"));
    expect(alert.textContent).not.toContain("setup status unavailable");
    expect(screen.queryByText("timeline placeholder")).toBeNull();
    expect(api.GET).toHaveBeenCalledWith("/api/setup/status");
  });
});
