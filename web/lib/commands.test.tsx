// @vitest-environment jsdom
/**
 * The palette's command table, pinned where it cannot drift quietly:
 * parametrized over the generated aggregation — ids unique, every title
 * present in all three catalogs (walking the generated map, never a hand
 * list), `enabled` answering an expectation table at both novelId states,
 * and every `run` navigating through a real router. A new command cannot
 * land uncovered: it must join the two expectation tables below. The
 * matcher's search reads every catalog regardless of the active language —
 * pinned with the German word an English UI must still find, and with a
 * query no rendering carries.
 */
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { type Command, type CommandContext, matchesAllLocales } from "./commands";
import { catalogs, locales } from "./generated/catalogs";
import { commands } from "./generated/commands";
import { applyLocale } from "./locale";

// The aggregation's literal tuple, read through the contract — the same
// view the palette renders. `enabled` is optional per row; the union of
// literal shapes hides it on the rows that have none, Command carries it.
const rows: ReadonlyArray<Command> = commands;

// One router per case: plain leaf routes at the three destinations, a home
// to start from, no queries in the tree — the commands navigate, nothing
// renders data.
function makeRouter() {
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
    history: createMemoryHistory({ initialEntries: ["/"] }),
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

  // The expectation table — a command lands only together with its row.
  // Rows without their own `enabled` are always on; the Wissen dock lives
  // at a novel, so without one it is off.
  const enabledAt: Record<string, { novel: boolean; bare: boolean }> = {
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

  // Where each run must land, and the novel the context carries — extend
  // with the command.
  const destinations: Record<string, { novelId: string | null; path: string }> = {
    "open-settings": { novelId: null, path: "/settings" },
    "open-prompts": { novelId: null, path: "/settings/prompts" },
    "open-wissen-dock": { novelId: "7", path: "/novels/7/wissen" },
  };

  it("navigate to their destination through a real router", async () => {
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

  it("leave the Wissen dock unmoved without a novel", async () => {
    // A disabled row never runs; the guard in `run` is the behavior, not a
    // crash — a stale context must not navigate the dock to a novel-less
    // path.
    const dock = rows.find((command) => command.id === "open-wissen-dock");
    if (!dock) throw new Error("open-wissen-dock missing from the aggregation");
    const router = makeRouter();
    render(<RouterProvider router={router} />);
    dock.run(contextFor(router, null));
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(router.state.location.pathname).toBe("/");
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
    // "export" belongs to the export-novel row (Task 9); nothing that
    // openPrompts renders contains it, in any language — a matcher that
    // degraded to always-true would surface here first.
    for (const locale of locales) {
      applyLocale(locale);
      expect(matchesAllLocales("commands.openPrompts", "export"), locale).toBe(false);
    }
  });
});
