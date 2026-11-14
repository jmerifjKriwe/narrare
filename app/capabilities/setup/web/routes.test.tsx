// @vitest-environment jsdom
/**
 * The `/` gate and the wizard's addressable steps, driven through a real
 * router over the real root route with a memory history — a fresh entry is
 * the browser-refresh shape, so the gate must answer from the status it
 * asks, never from a remembered variant. The gate's two choices are mocked
 * at their module boundary so the choice itself is observable while both
 * pages are still placeholders (the port tasks fill them and test them in
 * their own right); step one renders the real basis step, the other three
 * steps the interim placeholder. The API client is mocked at its module
 * boundary — the request's truth is the backend's and the E2E's.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
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

// The gate's two branches, distinguishable while both are placeholders.
vi.mock("./WelcomePage", () => ({ WelcomePage: () => <p>welcome placeholder</p> }));
vi.mock("./LandingPage", () => ({ LandingPage: () => <p>landing placeholder</p> }));

import { client } from "@shell/lib/api/client";
import { t } from "@shell/lib/i18n";
import { queryClient } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";

import { routes } from "./routes";

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
    routeTree: rootRoute.addChildren([...routes]),
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

describe("the / gate", () => {
  it("shows the welcome while setup is incomplete", async () => {
    scriptStatus(async () => ({ data: { complete: false }, response: ok() }));
    renderTree("/");

    expect(await screen.findByText("welcome placeholder")).toBeTruthy();
    expect(screen.queryByText("landing placeholder")).toBeNull();
    expect(api.GET).toHaveBeenCalledWith("/api/setup/status");
  });

  it("shows the landing once setup is complete — a fresh load of /", async () => {
    scriptStatus(async () => ({ data: { complete: true }, response: ok() }));
    renderTree("/");

    expect(await screen.findByText("landing placeholder")).toBeTruthy();
    expect(screen.queryByText("welcome placeholder")).toBeNull();
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

    // The shell is open (the status ask only goes out once the gate mounts),
    // and neither variant is on screen while the one fact is outstanding.
    await waitFor(() => expect(api.GET).toHaveBeenCalledWith("/api/setup/status"));
    expect(screen.queryByText("welcome placeholder")).toBeNull();
    expect(screen.queryByText("landing placeholder")).toBeNull();

    resolveStatus({ data: { complete: true }, response: ok() });
    expect(await screen.findByText("landing placeholder")).toBeTruthy();
  });

  it("names an unreachable status endpoint instead of guessing a variant", async () => {
    scriptStatus(async () => ({ data: undefined, response: new Response(null, { status: 503 }) }));
    renderTree("/");

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("503");
    expect(screen.queryByText("welcome placeholder")).toBeNull();
    expect(screen.queryByText("landing placeholder")).toBeNull();
  });
});

describe("the wizard's steps", () => {
  it("redirects /setup to the first step, keeping the search", async () => {
    scriptStatus(async () => ({ data: { complete: false }, response: ok() }));
    const router = renderTree("/setup?demo=dead-signal");

    // The door answers with the real basis step, and the search it kept is
    // the demo the step preselects — the binding is visible at once.
    await screen.findByRole("heading", { name: t("setup.basis.heroTitle") });
    expect(router.state.location.pathname).toBe("/setup/basis");
    expect(router.state.location.search).toEqual({ demo: "dead-signal" });
    expect(
      (screen.getByRole("textbox", { name: t("setup.basis.boundTitle") }) as HTMLInputElement).value,
    ).toBe("Dead Signal");
  });

  it.each(["/setup/structure", "/setup/ai-rules", "/setup/provisioning"])(
    "answers %s with the interim placeholder",
    async (path) => {
      scriptStatus(async () => ({ data: { complete: false }, response: ok() }));
      renderTree(path);

      expect(await screen.findByRole("heading", { name: t("setup.interimTitle") })).toBeTruthy();
    },
  );
});
