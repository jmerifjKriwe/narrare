// @vitest-environment jsdom
/**
 * The palette's command table, pinned where it cannot drift quietly:
 * parametrized over the generated aggregation — ids unique, every title
 * present in all three catalogs (walking the generated map, never a hand
 * list), `enabled` answering an expectation table at both novelId states,
 * and each `run`'s observable effect — a navigation through a real router,
 * a POST that feeds one, or a route that stays put. The expectation tables
 * are bidirectional: they and the aggregation name exactly each other, so
 * a new command cannot land uncovered — it must join both tables. The
 * matcher's search reads every catalog regardless of the active language —
 * pinned with the German word an English UI must still find, with the
 * trimmed query, and with a query no rendering carries.
 */
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "./api/client";
import { type Command, type CommandContext, matchesAllLocales } from "./commands";
import { catalogs, locales } from "./generated/catalogs";
import { commands } from "./generated/commands";
import { applyLocale } from "./locale";

// The client's methods as plain mocks: the rows here navigate, and the
// new-chapter row POSTs — the request's answer is the mock's, the
// navigation's landing is what the test reads.
vi.mock("./api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

const api = client as unknown as Record<"POST", ReturnType<typeof vi.fn>>;
const POSTED_CHAPTER = { id: "71bfa163-2c8f-4a6f-9e07-6f5f2c8d1b63" };
// A chapter the workspace already held when the dock command ran — not the
// POST's fresh row, so the pin cannot pass by coincidence.
const HELD_CHAPTER = "3f1d5c47-8a2b-4e60-9c15-6d8b0a7f2e31";

// The aggregation's literal tuple, read through the contract — the same
// view the palette renders. `enabled` is optional per row; the union of
// literal shapes hides it on the rows that have none, Command carries it.
const rows: ReadonlyArray<Command> = commands;

// One router per case: plain leaf routes at the three destinations, a home
// to start from, no queries in the tree — the commands navigate, nothing
// renders data. The entry defaults to the shelf; a case that needs the
// workspace's address names it.
function makeRouter(initialEntry = "/") {
  const root = createRootRoute({});
  const tree = [
    createRoute({ getParentRoute: () => root, path: "/", component: () => <p>home</p> }),
    createRoute({
      getParentRoute: () => root,
      path: "/settings",
      component: () => <p>settings</p>,
    }),
    createRoute({
      getParentRoute: () => root,
      path: "/settings/prompts",
      component: () => <p>prompts</p>,
    }),
    createRoute({
      getParentRoute: () => root,
      path: "/novels/$id/wissen",
      component: () => <p>wissen</p>,
    }),
  ];
  return createRouter({
    routeTree: root.addChildren(tree),
    history: createMemoryHistory({ initialEntries: [initialEntry] }),
  });
}

// The context the shell would hand a row: the router's own navigate (it is
// typed `NavigateFn`, the same shape the contract carries), the novel under
// test, and a modal slot the navigation rows never touch.
function contextFor(router: ReturnType<typeof makeRouter>, novelId: string | null): CommandContext {
  return { navigate: router.navigate, novelId, openModal: () => {} };
}

// A context for the `enabled` table, which reads only the novel: the other
// slots are stubs a reading never calls.
function enabledContext(novelId: string | null): CommandContext {
  return { navigate: async () => {}, novelId, openModal: () => {} };
}

afterEach(cleanup);

describe("the generated commands", () => {
  it("keep ids unique across the aggregation", () => {
    expect(rows.length).toBeGreaterThan(0);
    expect(new Set(rows.map((command) => command.id)).size).toBe(rows.length);
  });

  it("have a title in every catalog, not only the source one", () => {
    for (const command of rows) {
      for (const [locale, catalog] of Object.entries(catalogs)) {
        expect(
          catalog[command.titleKey].trim(),
          `${command.id} in ${locale}`,
        ).not.toBe("");
      }
    }
  });

  // The expectation table — a command lands only together with its row,
  // and the rows only together with their table entries: the key sets are
  // equal both ways (the test below). Rows without their own `enabled` are
  // always on; the Wissen dock and the writing commands live at a novel,
  // so without one they are off.
  const enabledAt: Record<string, { novel: boolean; bare: boolean }> = {
    "new-chapter": { novel: true, bare: false },
    "export-novel": { novel: true, bare: false },
    "open-settings": { novel: true, bare: true },
    "open-prompts": { novel: true, bare: true },
    "open-wissen-dock": { novel: true, bare: false },
  };

  it("are enabled exactly where the table says, at both novelId states", () => {
    for (const command of rows) {
      const expected = enabledAt[command.id];
      expect(expected, `no table entry for ${command.id}`).toBeDefined();
      expect(command.enabled?.(enabledContext("7")) ?? true, `${command.id} with a novel`).toBe(
        expected.novel,
      );
      expect(command.enabled?.(enabledContext(null)) ?? true, `${command.id} without`).toBe(
        expected.bare,
      );
    }
  });

  it("and the tables name exactly the aggregation — both ways, no orphans either side", () => {
    const rowIds = rows.map((command) => command.id).sort();
    expect(Object.keys(enabledAt).sort()).toEqual(rowIds);
    expect(Object.keys(destinations).sort()).toEqual(rowIds);
  });

  // Where each run must land, and the novel the context carries — extend
  // with the command. A row that navigates nowhere names its start: the
  // settled location is the assertion (the export row hands the modal slot
  // its dialog and moves no route).
  const destinations: Record<string, { novelId: string | null; path: string }> = {
    "new-chapter": { novelId: "7", path: "/novels/7" },
    "export-novel": { novelId: "7", path: "/" },
    "open-settings": { novelId: null, path: "/settings" },
    "open-prompts": { novelId: null, path: "/settings/prompts" },
    "open-wissen-dock": { novelId: "7", path: "/novels/7/wissen" },
  };

  it("navigate to their destination through a real router", async () => {
    api.POST.mockResolvedValue({
      data: POSTED_CHAPTER,
      response: new Response(null, { status: 200 }),
    });
    for (const command of rows) {
      const expected = destinations[command.id];
      expect(expected, `no table entry for ${command.id}`).toBeDefined();
      const router = makeRouter();
      render(<RouterProvider router={router} />);
      command.run(contextFor(router, expected.novelId));
      await waitFor(() => expect(router.state.location.pathname).toBe(expected.path));
      cleanup();
    }
  });

  it("open-wissen-dock keeps the workspace's address — ?chapter= and a collapsed rail ride along", async () => {
    // The dock opens where the workbench stood: the chapter address is what
    // a reload or a share reads back, and the panel state lives in the same
    // URL. The router reads an absent `search` as the empty record, so a
    // writer that forgets it wipes the workspace's address — this pin is
    // where that failure lands, not in a screenshot.
    const router = makeRouter(`/novels/7?chapter=${HELD_CHAPTER}&rail=false`);
    render(<RouterProvider router={router} />);
    const dock = rows.find((command) => command.id === "open-wissen-dock");
    if (!dock) throw new Error("open-wissen-dock missing from the aggregation");
    dock.run(contextFor(router, "7"));
    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/novels/7/wissen"),
    );
    expect(router.state.location.search).toMatchObject({
      chapter: HELD_CHAPTER,
      rail: false,
    });
  });

  it("leave the Wissen dock unmoved without a novel", async () => {
    // A disabled row never runs; the guard in `run` is the behavior, not a
    // crash — a stale context must not navigate the dock to a novel-less
    // path. The assertion is the settled state, not a timer: the navigate
    // the context carries is spied, so a leaked navigation would be visible
    // in the calls, not only in a location that raced the wait.
    const dock = rows.find((command) => command.id === "open-wissen-dock");
    if (!dock) throw new Error("open-wissen-dock missing from the aggregation");
    const router = makeRouter();
    const navigate = vi.spyOn(router, "navigate").mockResolvedValue(undefined as never);
    render(<RouterProvider router={router} />);
    dock.run(contextFor(router, null));
    await Promise.resolve();
    expect(navigate).not.toHaveBeenCalled();
    expect(router.state.location.pathname).toBe("/");
    navigate.mockRestore();
  });
});

describe("matchesAllLocales", () => {
  it("finds a row through another locale's word, whatever is active", () => {
    // The German rendering ("Einstellungen öffnen") supplies the match after
    // normalization; neither the English nor the French one carries "offnen".
    // The matcher reads every catalog, so the answer cannot depend on the
    // active language — the loop pins exactly that.
    for (const locale of locales) {
      applyLocale(locale);
      expect(matchesAllLocales("commands.openSettings", "offnen"), locale).toBe(true);
    }
  });

  it("does not match a query no rendering carries", () => {
    // "export" belongs to the export-novel row; nothing that
    // openPrompts renders contains it, in any language — a matcher that
    // degraded to always-true would surface here first.
    for (const locale of locales) {
      applyLocale(locale);
      expect(matchesAllLocales("commands.openPrompts", "export"), locale).toBe(false);
    }
  });

  it("finds the export row through its English word in every active locale", () => {
    // The ruled carry-over: "export" must find commands.exportNovel —
    // "Export novel", "Roman exportieren", "Exporter le roman" all carry
    // it — whatever the UI speaks.
    for (const locale of locales) {
      applyLocale(locale);
      expect(matchesAllLocales("commands.exportNovel", "export"), locale).toBe(true);
    }
  });

  it("trims the query before matching", () => {
    // The field's value is handed through whole; the matcher, not the
    // caller, keeps whitespace out of the needle.
    for (const locale of locales) {
      applyLocale(locale);
      expect(matchesAllLocales("commands.openSettings", "  einstell  "), locale).toBe(true);
    }
  });
});
