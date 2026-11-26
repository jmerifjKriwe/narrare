// @vitest-environment jsdom
/**
 * The shell's two fallbacks, spoken by the catalog (#843): an unknown URL and
 * a route that throws must not paint TanStack's English defaults inside the
 * localized shell — every user-visible string lives in the catalog, and the
 * not-found and error screens are user-visible. Driven through a real router
 * over the real root route with a memory history. The not-found face renders
 * inside the Shell, so the pre-paint settings gate opens for it the same way
 * it opens for any page: the client is mocked at its module boundary and the
 * row carries the locale under test, modeling the real boot. The loop also
 * applies the locale directly for a deterministic first paint, so the pin
 * proves the faces speak the catalog — not that boot adoption alone delivers
 * the language. Every locale the app carries is walked, and the way home must
 * be the shelf gate (`/`), which redirects to the welcome pre-setup and shows
 * the shelf once the instance is set up.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRoute, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, configure, render, screen } from "@testing-library/react";

// Full-suite load: renders RouterProvider; see WorkspacePage.test.tsx.
configure({ asyncUtilTimeout: 5000 });
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/api/client", () => ({
  client: {
    GET: vi.fn(),
    POST: vi.fn(),
    PATCH: vi.fn(),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

import { client } from "../lib/api/client";
import { ApiError } from "../lib/api/errors";
import { catalogs, locales } from "../lib/generated/catalogs";
import { applyLocale } from "../lib/locale";
import { queryClient } from "../lib/query";
import { rootRoute } from "./__root";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

/** The shell root's settings read answers the row the case scripts. */
function scriptSettings(locale: string): void {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") {
      return { data: { locale, theme: null }, response: new Response(null, { status: 200 }) };
    }
    throw new Error(`unexpected request: ${path}`);
  });
}

// A home route so the tree has somewhere real to go; the cases live on
// paths it does not carry.
const home = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: () => <p>home</p>,
});

function renderTree(routes: Parameters<typeof rootRoute.addChildren>[0], path: string) {
  const router = createRouter({
    routeTree: rootRoute.addChildren(routes),
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  applyLocale("en");
});

describe("the shell's fallbacks", () => {
  it("names an unknown URL in every catalog's language", async () => {
    for (const candidate of locales) {
      // A fresh cache per locale: the settings row is the record, and a
      // cached answer from the previous iteration would adopt the wrong one.
      queryClient.clear();
      scriptSettings(candidate);
      applyLocale(candidate);
      renderTree([home], "/nowhere");

      const heading = await screen.findByRole("heading", {
        name: catalogs[candidate]["shell.notFound"],
      });
      expect(heading).toBeTruthy();
      // The body is the catalog's truthful interim copy (#850), and the way
      // home is the shelf gate — not TanStack's English default.
      expect(screen.getByText(catalogs[candidate]["shell.notFoundBody"])).toBeTruthy();
      const back = screen.getByRole("link", { name: catalogs[candidate]["nav.back"] });
      expect(back.getAttribute("href")).toBe("/");
      expect(document.body.textContent).not.toContain("Not Found");
      cleanup();
    }
  });

  it("names a route that throws, in every catalog's language", async () => {
    const boom = createRoute({
      getParentRoute: () => rootRoute,
      path: "/boom",
      component: () => {
        throw new Error("die Route ist explodiert");
      },
    });
    for (const candidate of locales) {
      queryClient.clear();
      scriptSettings(candidate);
      applyLocale(candidate);
      renderTree([home, boom], "/boom");

      const heading = await screen.findByRole("heading", {
        name: catalogs[candidate]["shell.error"],
      });
      expect(heading).toBeTruthy();
      // The catalog names the failure — the thrown sentence never reaches
      // the face, and the router's English default stays out.
      const alert = screen.getByRole("alert");
      expect(alert.textContent).toContain(catalogs[candidate]["errors.unexpected"]);
      expect(alert.textContent).not.toContain("die Route ist explodiert");
      const back = screen.getByRole("link", { name: catalogs[candidate]["nav.back"] });
      expect(back.getAttribute("href")).toBe("/");
      expect(document.body.textContent).not.toContain("Something went wrong");
      cleanup();
    }
  });

  it("names a thrown failure with a status by its family", async () => {
    const boom = createRoute({
      getParentRoute: () => rootRoute,
      path: "/boom",
      component: () => {
        throw new ApiError("x", { status: 503 });
      },
    });
    for (const candidate of locales) {
      queryClient.clear();
      scriptSettings(candidate);
      applyLocale(candidate);
      renderTree([home, boom], "/boom");

      const heading = await screen.findByRole("heading", {
        name: catalogs[candidate]["shell.error"],
      });
      expect(heading).toBeTruthy();
      const alert = screen.getByRole("alert");
      expect(alert.textContent).toContain(catalogs[candidate]["errors.server"]);
      expect(alert.textContent).not.toContain("x: 503");
      cleanup();
    }
  });
});
