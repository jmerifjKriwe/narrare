// @vitest-environment jsdom
/**
 * The writing capability's `/` gate — the shelf's door after the W3 handover.
 * Driven through a real router over the real root route with the generated
 * capability table (the app's own composition), so the gate's redirect lands
 * on setup's real `/setup` door, not a harness stub. A fresh entry is the
 * browser-refresh shape: the gate must answer from the status it asks, never
 * from a remembered variant. The shelf itself is mocked at its module boundary
 * so the gate's choice is what this file pins (the shelf's own contract lives
 * in ShelfPage.test); the welcome it redirects to renders for real. The API
 * client is mocked at its module boundary — the request's truth is the
 * backend's and the E2E's.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, configure, render, screen, waitFor } from "@testing-library/react";

// Full-suite load: renders RouterProvider; see WorkspacePage.test.tsx.
configure({ asyncUtilTimeout: 5000 });
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: {
    GET: vi.fn(),
    POST: vi.fn(),
    PATCH: vi.fn(),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

// The shelf's own face, mocked so the gate's choice is observable here; the
// shelf's contract lives in ShelfPage.test and the E2E pins it on the real stack.
vi.mock("./ShelfPage", () => ({ ShelfPage: () => <p>shelf placeholder</p> }));
// The workspace's face, mocked for the same reason (W4 Task 11): this file
// pins the gate, WorkspacePage.test pins the page.
vi.mock("./WorkspacePage", () => ({ WorkspacePage: () => <p>workspace placeholder</p> }));

import { client } from "@shell/lib/api/client";
import { capabilityRoutes } from "@shell/lib/generated/routes";
import { t } from "@shell/lib/i18n";
import { queryClient } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

function ok(): Response {
  return new Response(null, { status: 200 });
}

type StatusAnswer = { data?: { complete: boolean }; response: Response };

/** The shell root's settings read always answers (the pre-paint gate opens
 *  on it); the gate's status read answers what the case scripts. */
function scriptStatus(answer: () => Promise<StatusAnswer>) {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") {
      return { data: { locale: null, theme: null }, response: ok() };
    }
    if (path === "/api/setup/status") return answer();
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

describe("the / shelf gate", () => {
  it("redirects an unconfigured instance to the welcome at /setup", async () => {
    scriptStatus(async () => ({ data: { complete: false }, response: ok() }));
    const router = renderTree("/");

    // The gate hands the unconfigured instance to setup's door, and the real
    // welcome answers there — not a not-found, not a shelf.
    expect(
      await screen.findByRole("heading", { level: 1, name: t("setup.welcome.heroTitle") }),
    ).toBeTruthy();
    expect(router.state.location.pathname).toBe("/setup");
    expect(screen.queryByText("shelf placeholder")).toBeNull();
    expect(api.GET).toHaveBeenCalledWith("/api/setup/status");
  });

  it("shows the shelf once setup is complete — a fresh load of /", async () => {
    scriptStatus(async () => ({ data: { complete: true }, response: ok() }));
    const router = renderTree("/");

    expect(await screen.findByText("shelf placeholder")).toBeTruthy();
    expect(router.state.location.pathname).toBe("/");
    expect(screen.queryByText(t("setup.welcome.heroTitle"))).toBeNull();
  });

  it("suspends while the status is in flight — nothing invented", async () => {
    let resolveStatus!: (answer: StatusAnswer) => void;
    scriptStatus(
      () =>
        new Promise<StatusAnswer>((resolve) => {
          resolveStatus = resolve;
        }),
    );
    renderTree("/");

    // The status ask goes out as the route loads, and neither the shelf nor
    // a redirect is on screen while the one fact is outstanding.
    await waitFor(() => expect(api.GET).toHaveBeenCalledWith("/api/setup/status"));
    expect(screen.queryByText("shelf placeholder")).toBeNull();
    expect(screen.queryByText(t("setup.welcome.heroTitle"))).toBeNull();

    resolveStatus({ data: { complete: true }, response: ok() });
    expect(await screen.findByText("shelf placeholder")).toBeTruthy();
  });

  it("names an unreachable status endpoint instead of guessing a variant", async () => {
    scriptStatus(async () => ({ data: undefined, response: new Response(null, { status: 503 }) }));
    renderTree("/");

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("503");
    expect(screen.queryByText("shelf placeholder")).toBeNull();
    expect(screen.queryByText(t("setup.welcome.heroTitle"))).toBeNull();
  });
});

describe("the /novels/$novelId workspace gate (W4 Task 11)", () => {
  it("shows the workspace once setup is complete", async () => {
    scriptStatus(async () => ({ data: { complete: true }, response: ok() }));
    const router = renderTree("/novels/11111111-1111-1111-1111-111111111111");

    expect(await screen.findByText("workspace placeholder")).toBeTruthy();
    expect(router.state.location.pathname).toBe("/novels/11111111-1111-1111-1111-111111111111");
    expect(screen.queryByText("shelf placeholder")).toBeNull();
  });

  it("hands an unconfigured instance to the welcome — the same gate as the shelf", async () => {
    scriptStatus(async () => ({ data: { complete: false }, response: ok() }));
    const router = renderTree("/novels/11111111-1111-1111-1111-111111111111");

    expect(
      await screen.findByRole("heading", { level: 1, name: t("setup.welcome.heroTitle") }),
    ).toBeTruthy();
    expect(router.state.location.pathname).toBe("/setup");
    expect(screen.queryByText("workspace placeholder")).toBeNull();
  });
});
