// @vitest-environment jsdom
/**
 * The language state's floor: a language is spoken only once its catalog is
 * here. Before any adoption the app speaks the source catalog — the only one
 * the store holds at module init, whatever the browser asks for — and a route
 * that fails ahead of the boot's ready gate wears the source's words under the
 * source's `lang`, never another language's tag over source text.
 *
 * The module registry is reset per case: the invariant is the module's own
 * starting point, which the statically imported bed would already have moved.
 */
import { act, cleanup, configure, render, screen } from "@testing-library/react";

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

beforeEach(() => {
  vi.resetModules();
  // The German visitor: init must ignore the browser while its catalog is
  // not in the store.
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.resetModules();
  localStorage.clear();
});

it("starts at the source, whatever the browser asks for", async () => {
  const { activeLocale } = await import("../lib/locale");
  const { isLoaded } = await import("../lib/catalog");

  expect(activeLocale()).toBe("en");
  expect(isLoaded(activeLocale())).toBe(true);
  expect(document.documentElement.lang).toBe("en");
});

it("a route that fails before the boot settles paints nothing, then the source's face", async () => {
  // A browser the catalogue knows nothing about: the boot's target is the
  // source, the one language the store holds before any adoption.
  vi.stubGlobal("navigator", { language: "ja-JP", languages: ["ja-JP"] });
  const { QueryClientProvider } = await import("@tanstack/react-query");
  const { createMemoryHistory, createRoute, createRouter, RouterProvider } = await import(
    "@tanstack/react-router"
  );
  const { client } = await import("../lib/api/client");
  const { queryClient } = await import("../lib/query");
  const { en, de } = await import("../lib/test/catalogs");
  const { rootRoute } = await import("./__root");

  const api = client as unknown as Record<"GET", ReturnType<typeof vi.fn>>;
  let answer!: (value: { data: { locale: string | null; theme: string | null }; response: Response }) => void;
  api.GET.mockImplementation(
    () =>
      new Promise((resolve) => {
        answer = resolve;
      }),
  );

  const boom = createRoute({
    getParentRoute: () => rootRoute,
    path: "/boom",
    component: () => {
      throw new Error("die Route ist explodiert");
    },
  });
  const router = createRouter({
    routeTree: rootRoute.addChildren([boom]),
    history: createMemoryHistory({ initialEntries: ["/boom"] }),
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );

  // The settings read is out, so the boot has not settled and the shell's
  // gate is closed: no face paints at all — there is no English error under
  // a `de` tag for a reader to see while the boot is still reading.
  await act(async () => {});
  expect(document.body.textContent).toBe("");

  answer({ data: { locale: null, theme: null }, response: new Response(null, { status: 200 }) });

  expect(await screen.findByRole("heading", { name: en["shell.error"] })).toBeTruthy();
  const alert = screen.getByRole("alert");
  expect(alert.textContent).toContain(en["errors.unexpected"]);
  expect(alert.textContent).not.toContain(de["errors.unexpected"]);
  expect(alert.textContent).not.toContain("die Route ist explodiert");
  expect(document.documentElement.lang).toBe("en");
});
