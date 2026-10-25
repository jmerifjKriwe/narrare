// @vitest-environment jsdom
/**
 * The shell's two fallbacks, spoken by the catalog: an unknown URL and a
 * route that throws must not paint TanStack's English defaults inside the
 * localized shell — every user-visible string lives in the catalog, and the
 * not-found and error screens are user-visible. Driven through a real
 * router over the real root route with a memory history; the shell's
 * pre-paint gate (the settings query) has to open for the fallbacks the
 * same way it opens for any page.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRoute, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { t } from "../lib/i18n";
import { queryClient } from "../lib/query";
import { rootRoute } from "./__root";

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
});

describe("the shell's fallbacks", () => {
  it("names an unknown URL in the catalog's language", async () => {
    renderTree([home], "/nowhere");

    const heading = await screen.findByRole("heading", { name: t("shell.notFound") });
    expect(heading).toBeTruthy();
    // The way home is the shell's own copy, and the router's English
    // default ("Not Found") is nowhere on the page.
    expect(screen.getByRole("link", { name: t("nav.back") })).toBeTruthy();
    expect(document.body.textContent).not.toContain("Not Found");
  });

  it("names a route that throws, in the catalog's language", async () => {
    const boom = createRoute({
      getParentRoute: () => rootRoute,
      path: "/boom",
      component: () => {
        throw new Error("die Route ist explodiert");
      },
    });
    renderTree([home, boom], "/boom");

    const heading = await screen.findByRole("heading", { name: t("shell.error") });
    expect(heading).toBeTruthy();
    // The thrown message rides along — a local-first app shows its own
    // errors — and the router's English default stays out.
    expect(screen.getByRole("alert").textContent).toContain("die Route ist explodiert");
    expect(document.body.textContent).not.toContain("Something went wrong");
  });
});
