// @vitest-environment jsdom
/**
 * The boot's catalog gate: the first paint waits for the row's catalog and
 * speaks it, and a catalog that cannot be fetched opens the page in the
 * source language instead of a half-translated shell. Driven through the
 * real root route over a memory history, with the client mocked at its
 * module boundary (the settings row is the only wire answer) — the same
 * scaffolding as `__root.test.tsx`.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRoute, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, configure, render, screen } from "@testing-library/react";

// Full-suite load: renders RouterProvider; see WorkspacePage.test.tsx.
configure({ asyncUtilTimeout: 5000 });
import { afterEach, beforeEach, expect, it, vi } from "vitest";

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
import { isLoaded, resetCatalogs } from "../lib/catalog";
import { catalogLoaders } from "../lib/generated/catalogs";
import { activeLocale } from "../lib/locale";
import { queryClient } from "../lib/query";
import { merged, preloadCatalogs } from "../lib/test/catalogs";
import { rootRoute } from "./__root";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

const realLoaders = { ...catalogLoaders };

/** The shell root's settings read answers the row the case scripts. */
function scriptSettings(locale: string): void {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") {
      return { data: { locale, theme: null }, response: new Response(null, { status: 200 }) };
    }
    throw new Error(`unexpected request: ${path}`);
  });
}

// A home route so the tree has somewhere real to go; the cases live on a
// path it does not carry.
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

beforeEach(() => {
  localStorage.clear();
  queryClient.clear();
  preloadCatalogs();
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  vi.restoreAllMocks();
  Object.assign(catalogLoaders, realLoaders);
  resetCatalogs();
  preloadCatalogs();
  localStorage.clear();
});

it("the first paint waits for the catalog and speaks the row's language", async () => {
  resetCatalogs();
  scriptSettings("fr");
  renderTree([home], "/nowhere");

  const heading = await screen.findByRole("heading", { name: merged.fr["shell.notFound"] });
  expect(heading).toBeTruthy();
  expect(activeLocale()).toBe("fr");
  expect(isLoaded("fr")).toBe(true);
});

it("a catalog that cannot be fetched opens the page in the source language", async () => {
  resetCatalogs();
  catalogLoaders.fr = () => Promise.reject(new Error("chunk"));
  // The fallback is expected to be loud; the assertion below reads the spy.
  vi.spyOn(console, "error").mockImplementation(() => {});
  scriptSettings("fr");
  renderTree([home], "/nowhere");

  const heading = await screen.findByRole("heading", { name: merged.en["shell.notFound"] });
  expect(heading).toBeTruthy();
  expect(activeLocale()).toBe("en");
  expect(isLoaded("fr")).toBe(false);
  expect(console.error).toHaveBeenCalled();
});
