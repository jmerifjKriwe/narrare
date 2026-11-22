// @vitest-environment jsdom
/**
 * The setup capability's inverse gate after the W3 handover and the wizard's
 * addressable steps, driven through a real router over the real root route
 * with the generated capability table (the app's own composition), so a
 * post-setup redirect lands on writing's real `/` shelf, not a harness stub.
 * A fresh entry is the browser-refresh shape: the gate must answer from the
 * status it asks, never from a remembered variant. The welcome is mocked at
 * its module boundary so the door's choice stays observable here (the welcome
 * is tested in its own right); the wizard steps render the real ported
 * components, and the shelf the redirect lands on renders for real (its own
 * contract lives in writing's ShelfPage.test). The API client is mocked at
 * its module boundary — the request's truth is the backend's and the E2E's.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, configure, render, screen } from "@testing-library/react";

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

// The door's pre-setup face, mocked so the choice itself is what this file
// pins — the welcome's own contract lives in its own test file.
vi.mock("./WelcomePage", () => ({ WelcomePage: () => <p>welcome placeholder</p> }));

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
 *  on it); the gate's status read answers what the case scripts. The shelf
 *  the redirect lands on reads the novels list — an empty one here, so the
 *  gate's choice stays the fact under test, not the shelf's own content. */
function scriptStatus(answer: () => Promise<StatusAnswer>) {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") {
      return { data: { locale: null, theme: null }, response: ok() };
    }
    if (path === "/api/setup/status") return answer();
    if (path === "/api/writing/novels") return { data: [], response: ok() };
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

describe("the /setup door — the inverse gate", () => {
  it("renders the welcome while setup is incomplete", async () => {
    scriptStatus(async () => ({ data: { complete: false }, response: ok() }));
    const router = renderTree("/setup");

    expect(await screen.findByText("welcome placeholder")).toBeTruthy();
    expect(router.state.location.pathname).toBe("/setup");
    expect(screen.queryByRole("heading", { level: 1, name: t("writing.shelf.title") })).toBeNull();
    expect(api.GET).toHaveBeenCalledWith("/api/setup/status");
  });

  it("redirects to the shelf once setup is complete — a fresh load of /setup", async () => {
    scriptStatus(async () => ({ data: { complete: true }, response: ok() }));
    const router = renderTree("/setup");

    // An installed instance has no wizard: the door hands it to writing's
    // shelf, and the real shelf answers there.
    expect(
      await screen.findByRole("heading", { level: 1, name: t("writing.shelf.title") }),
    ).toBeTruthy();
    expect(router.state.location.pathname).toBe("/");
    expect(screen.queryByText("welcome placeholder")).toBeNull();
  });
});

describe("the wizard's steps — the inverse gate", () => {
  it("a post-setup deep link to any step redirects to the shelf", async () => {
    scriptStatus(async () => ({ data: { complete: true }, response: ok() }));
    for (const path of ["/setup/basis", "/setup/structure", "/setup/ai-rules", "/setup/provisioning"]) {
      const router = renderTree(path);
      expect(
        await screen.findByRole("heading", { level: 1, name: t("writing.shelf.title") }),
      ).toBeTruthy();
      expect(router.state.location.pathname).toBe("/");
      // A fresh load per step: the next deep link asks the status anew.
      cleanup();
      queryClient.clear();
    }
  });

  it("a pre-setup deep link renders the step — the wizard keeps working mid-setup", async () => {
    scriptStatus(async () => ({ data: { complete: false }, response: ok() }));
    const router = renderTree("/setup/basis");

    expect(
      await screen.findByRole("heading", { name: t("setup.basis.heroTitle") }),
    ).toBeTruthy();
    expect(router.state.location.pathname).toBe("/setup/basis");
  });
});

describe("the wizard's steps — the address is the memory", () => {
  it("an empty /setup/provisioning falls back to the basis without posting", async () => {
    scriptStatus(async () => ({ data: { complete: false }, response: ok() }));
    const router = renderTree("/setup/provisioning");

    // The real provisioning step mounts, finds no basis in the address, and
    // answers with step one — no POST on an empty deep link.
    await screen.findByRole("heading", { name: t("setup.basis.heroTitle") });
    expect(router.state.location.pathname).toBe("/setup/basis");
    expect(api.POST).not.toHaveBeenCalled();
  });
});
