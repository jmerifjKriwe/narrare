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
import { act, cleanup, configure, fireEvent, render, screen, waitFor } from "@testing-library/react";

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
import { isLoaded, resetCatalogs, setCatalog } from "../lib/catalog";
import { catalogLoaders } from "../lib/generated/catalogs";
import { useTranslation } from "../lib/i18n";
import { LanguageSwitcher } from "../lib/language";
import { activeLocale, applyLocale } from "../lib/locale";
import { storePreSetupLocale } from "../lib/preSetupLocale";
import { queryClient } from "../lib/query";
import { de, en, fr, merged, preloadCatalogs } from "../lib/test/catalogs";
import { rootRoute } from "./__root";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

const realLoaders = { ...catalogLoaders };

function ok(): Response {
  return new Response(null, { status: 200 });
}

/** The shell root's settings read answers the row the case scripts. */
function scriptSettings(locale: string | null): void {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") {
      return { data: { locale, theme: null }, response: ok() };
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

/** A parameterized key, so a stale formatter cache would show: the sentence
 *  is built once per language and must never be served under another's key. */
function Counter() {
  const t = useTranslation();
  return <p data-testid="step">{t("setup.structure.stepOf", { step: 2, total: 4 })}</p>;
}

const counter = createRoute({
  getParentRoute: () => rootRoute,
  path: "/counter",
  component: Counter,
});

/** The switcher's own choose seam, mounted under the real boot. */
const switcher = createRoute({
  getParentRoute: () => rootRoute,
  path: "/switcher",
  component: () => <LanguageSwitcher variant="welcome" />,
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
  api.PATCH.mockReset();
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

it("the first paint stays closed until the row's catalog is here", async () => {
  resetCatalogs();
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const realFr = catalogLoaders.fr;
  catalogLoaders.fr = async () => {
    await gate;
    return realFr();
  };
  scriptSettings("fr");
  renderTree([home], "/nowhere");

  // A flush is all the boot gets while the chunk is out: the ready gate
  // paints neither the source nor a half-translated face.
  await act(async () => {});
  await act(async () => {});
  expect(screen.queryByRole("heading", { name: merged.en["shell.notFound"] })).toBeNull();
  expect(screen.queryByRole("heading", { name: merged.fr["shell.notFound"] })).toBeNull();

  release();
  expect(await screen.findByRole("heading", { name: merged.fr["shell.notFound"] })).toBeTruthy();
  expect(isLoaded("fr")).toBe(true);
});

it("a settings refetch to an uncached language holds the face it has until that catalog lands", async () => {
  resetCatalogs();
  setCatalog("fr", merged.fr);
  applyLocale("fr");
  let row: string | null = "fr";
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") {
      return { data: { locale: row, theme: null }, response: ok() };
    }
    throw new Error(`unexpected request: ${path}`);
  });

  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const realDe = catalogLoaders.de;
  catalogLoaders.de = async () => {
    await gate;
    return realDe();
  };

  renderTree([home, counter], "/counter");
  await screen.findByTestId("step");
  expect(document.documentElement.lang).toBe("fr");
  expect(screen.getByTestId("step").textContent).toBe(
    fr["setup.structure.stepOf"].replace("{step}", "2").replace("{total}", "4"),
  );

  // The row now names a language this session never loaded. The face keeps
  // the French it speaks — never the English source under a `de` tag, never
  // a formatter built from the English message under the `de` cache key.
  row = "de";
  await act(async () => {
    await queryClient.refetchQueries({ queryKey: ["settings"] });
  });
  await act(async () => {});
  expect(document.documentElement.lang).toBe("fr");
  expect(screen.getByTestId("step").textContent).toBe(
    fr["setup.structure.stepOf"].replace("{step}", "2").replace("{total}", "4"),
  );

  release();
  await waitFor(() => expect(document.documentElement.lang).toBe("de"));
  expect(screen.getByTestId("step").textContent).toBe(
    de["setup.structure.stepOf"].replace("{step}", "2").replace("{total}", "4"),
  );
  // A further, real render must read German too: no formatter was cached from
  // the English source under `de` while the row's catalog was on its way.
  // Switching away and back changes the snapshot `useTranslation` reads, so
  // the tree genuinely re-renders — `applyLocale("de")` on an already active
  // `de` would bail out and prove nothing.
  act(() => applyLocale("en"));
  await waitFor(() => expect(document.documentElement.lang).toBe("en"));
  expect(screen.getByTestId("step").textContent).toBe(
    en["setup.structure.stepOf"].replace("{step}", "2").replace("{total}", "4"),
  );
  act(() => applyLocale("de"));
  await waitFor(() => expect(document.documentElement.lang).toBe("de"));
  expect(screen.getByTestId("step").textContent).toBe(
    de["setup.structure.stepOf"].replace("{step}", "2").replace("{total}", "4"),
  );
});

it("a stale hydration does not land over a newer, already-held target", async () => {
  resetCatalogs();
  setCatalog("de", merged.de);
  let row: string | null = "fr";
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") {
      return { data: { locale: row, theme: null }, response: ok() };
    }
    throw new Error(`unexpected request: ${path}`);
  });

  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const realFr = catalogLoaders.fr;
  catalogLoaders.fr = async () => {
    await gate;
    return realFr();
  };

  renderTree([home], "/nowhere");
  await act(async () => {});

  // The row turns to a language the store already holds while the first
  // hydration is still out: that newer target is the face, and the older
  // chunk's late landing must not repaint it.
  row = "de";
  await act(async () => {
    await queryClient.refetchQueries({ queryKey: ["settings"] });
  });
  expect(await screen.findByRole("heading", { name: merged.de["shell.notFound"] })).toBeTruthy();

  release();
  await act(async () => {});
  expect(activeLocale()).toBe("de");
  expect(screen.getByRole("heading", { name: merged.de["shell.notFound"] })).toBeTruthy();
});

it("a settings change that changes nothing does not supersede a language choice in flight", async () => {
  resetCatalogs();
  setCatalog("de", merged.de);
  applyLocale("de");
  let storedLocale: string | null = "de";
  let theme: string | null = null;
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") {
      return { data: { locale: storedLocale, theme }, response: ok() };
    }
    throw new Error(`unexpected request: ${path}`);
  });
  api.PATCH.mockImplementation(
    async (path: string, init?: { body?: { locale?: string | null } }) => {
      if (path !== "/api/settings") throw new Error(`unexpected request: ${path}`);
      storedLocale = init?.body?.locale ?? null;
      return { data: { locale: storedLocale, theme }, response: ok() };
    },
  );

  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const realFr = catalogLoaders.fr;
  catalogLoaders.fr = async () => {
    await gate;
    return realFr();
  };

  renderTree([home, switcher], "/switcher");
  await screen.findByRole("radio", { name: "Français" });

  fireEvent.click(screen.getByRole("radio", { name: "Français" }));
  expect(activeLocale()).toBe("de"); // the chunk is the only thing missing

  // The row's data changes while nothing of its language does: the boot's
  // hydration of the active catalog takes no number, so the click stands.
  theme = "light";
  await act(async () => {
    await queryClient.refetchQueries({ queryKey: ["settings"] });
  });
  await act(async () => {});
  expect(activeLocale()).toBe("de");

  release();
  await waitFor(() => expect(activeLocale()).toBe("fr"));
  await waitFor(() =>
    expect(api.PATCH).toHaveBeenCalledWith("/api/settings", { body: { locale: "fr" } }),
  );
  expect(storedLocale).toBe("fr");
});

it("a stored row choice wins over a leftover pre-setup mirror", async () => {
  resetCatalogs();
  setCatalog("de", merged.de);
  storePreSetupLocale("fr");
  scriptSettings("de");
  renderTree([home], "/nowhere");

  // Let the boot's read and hydration settle; the row's German is the face,
  // never the mirror's French a refused carry-over left behind.
  await waitFor(() => expect(queryClient.getQueryState(["settings"])?.status).toBe("success"));
  await act(async () => {});
  expect(activeLocale()).toBe("de");
  expect(await screen.findByRole("heading", { name: merged.de["shell.notFound"] })).toBeTruthy();
});

it("the mirror is hydrated when the row holds no choice", async () => {
  resetCatalogs();
  storePreSetupLocale("fr");
  scriptSettings(null);
  renderTree([home], "/nowhere");

  const heading = await screen.findByRole("heading", { name: merged.fr["shell.notFound"] });
  expect(heading).toBeTruthy();
  expect(activeLocale()).toBe("fr");
});
