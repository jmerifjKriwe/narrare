// @vitest-environment jsdom
/**
 * The rail's drafted chrome, pinned where it can only be seen rendered: the
 * four blocks the workspace draft carries on the icon rail (spec §5.0) —
 * the book-switcher with the active book's cover chip and the novel menu,
 * the sync dot the autosave state drives, the theme cycle on the settings
 * row's own write contract, and the user block with its fallback label —
 * beside the older pins: the area hues, the flat Tier 1 panel and the
 * eyebrow groups.
 *
 * React Aria owns the menu's keyboard contract; the rail's cases pin what
 * the rail hands it (the items, the trigger's name) and the whole keyboard
 * path — the arrows walking the items in their focus paint, Escape handing
 * focus back — the same legs Menu.test runs at the primitive. The axe leg
 * runs the same floor the E2E suites run (`app/kernel/testing/a11y.py`):
 * axe-core, WCAG 2 A/AA, over the rendered rail with the menu open.
 */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import { QueryClientProvider } from "@tanstack/react-query";
import axe from "axe-core";
import { readFileSync } from "node:fs";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AREA_ICON } from "@shell/lib/area";
import { nav } from "@shell/lib/generated/capabilities";

import { client } from "../lib/api/client";
import { t } from "../lib/i18n";
import { queryClient } from "../lib/query";
import { IconRail, areaStyle, RAIL_GROUPS, type RailSync } from "./IconRail";

vi.mock("../lib/api/client", () => ({
  client: { GET: vi.fn(), PATCH: vi.fn() },
}));

const get = client.GET as unknown as ReturnType<typeof vi.fn>;
const patch = client.PATCH as unknown as ReturnType<typeof vi.fn>;

// The jsdom environment hands import.meta.url an http scheme, so the source
// pins read through the runner's root (vitest runs with web/ as its working
// directory) instead of a file URL.
const railSource = readFileSync("components/IconRail.tsx", "utf8");

/** Two books: one with the author named on its row, one without. */
const NOVELS = [
  { id: "n1", title: "Ein sehr langer Buchtitel der nicht abreisst", author: "H. Calder" },
  { id: "n2", title: "Zweitwerk", author: null },
];

/** The settings row the theme cycle writes; the tests set it per case. */
let storedTheme: string | null = null;

function ok(): Response {
  return new Response(null, { status: 200 });
}

/** The answers the rail reads: the settings row and the library list. */
function mockApi(): void {
  get.mockImplementation(async (path: string) => {
    switch (path) {
      case "/api/settings":
        return { data: { locale: null, theme: storedTheme }, response: ok() };
      case "/api/writing/novels":
        return { data: NOVELS, response: ok() };
      default:
        throw new Error(`unexpected GET ${path}`);
    }
  });
  // The theme write lands: the row takes the body's value, as the endpoint
  // would, so the refetch the invalidation asks proves the cache honest.
  patch.mockImplementation(
    async (_path: string, init: { body: { theme: string | null } }) => {
      storedTheme = init.body.theme;
      return { response: ok() };
    },
  );
}

/** The sync state the shell hands the rail; each test sets it before rendering. */
let sync: RailSync = "saved";

/**
 * The rail under the one router it reads (matches, params, navigation): the
 * router is the context, not the subject — NovelPage.test's own pattern.
 */
function Harness() {
  return (
    <div>
      <IconRail sync={sync} />
      <Outlet />
    </div>
  );
}

const rootRoute = createRootRoute({ component: Harness });
const workspaceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/novels/$id",
  component: () => null,
});
const homeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: () => null,
});
const chatRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/chat",
  component: () => null,
});
const knowledgeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/knowledge",
  component: () => null,
});
const planningRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/planning",
  component: () => null,
});
const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: () => null,
});

function renderAt(path: string) {
  const router = createRouter({
    routeTree: rootRoute.addChildren([
      homeRoute,
      workspaceRoute,
      chatRoute,
      knowledgeRoute,
      planningRoute,
      settingsRoute,
    ]),
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

function user() {
  return userEvent.setup({ pointerEventsCheck: 0 });
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  queryClient.clear();
  localStorage.clear();
  delete document.documentElement.dataset.theme;
  delete document.body.dataset.sync;
  storedTheme = null;
  sync = "saved";
});

describe("the book-switcher at the rail's head", () => {
  it("names the active book on the trigger and offers every novel in the menu", async () => {
    mockApi();
    const router = renderAt("/novels/n1");
    const trigger = await screen.findByRole("button", {
      name: `${t("shell.railBookMenu")}: ${NOVELS[0].title}`,
    });

    // The full title rides the accessible name; the visible line is the one
    // that truncates. The name is never allowed to be the truncation.
    expect(trigger.getAttribute("aria-label")).toBe(
      `${t("shell.railBookMenu")}: ${NOVELS[0].title}`,
    );
    const label = trigger.querySelector("span.truncate");
    expect(label?.textContent).toBe(NOVELS[0].title);

    // The cover chip is the collapsed rail's face for the book: decorative,
    // tone-keyed, present without the label.
    expect(trigger.querySelector("[data-rail-cover]")).not.toBeNull();

    const chooser = user();
    await chooser.click(trigger);
    expect(screen.getByRole("menu")).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: NOVELS[0].title })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: NOVELS[1].title })).toBeTruthy();

    // Choosing a novel is a navigation — the switcher's whole effect.
    await chooser.click(screen.getByRole("menuitem", { name: NOVELS[1].title }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/novels/n2"));
  });

  it("hands focus back to the trigger when Escape closes the menu", async () => {
    mockApi();
    renderAt("/novels/n1");
    const trigger = await screen.findByRole("button", {
      name: `${t("shell.railBookMenu")}: ${NOVELS[0].title}`,
    });
    const chooser = user();
    await chooser.click(trigger);
    expect(screen.getByRole("menu")).toBeTruthy();

    await chooser.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(trigger));
  });

  it("walks the novels with the arrow keys, the focused item painting its state", async () => {
    mockApi();
    renderAt("/novels/n1");
    const trigger = await screen.findByRole("button", {
      name: `${t("shell.railBookMenu")}: ${NOVELS[0].title}`,
    });
    const chooser = user();
    await chooser.click(trigger);

    // The walk: focus is the walk's own state, moving down the list in DOM
    // order — the same legs the primitive's test runs, driven here through
    // the rail's own menu.
    await chooser.keyboard("{ArrowDown}");
    const first = screen.getByRole("menuitem", { name: NOVELS[0].title });
    expect(document.activeElement).toBe(first);
    // The focused item paints the state it carries: React-Aria's
    // data-focused="true" against the soft-wash utility the class promises.
    expect(first.getAttribute("data-focused")).toBe("true");
    expect(first.className).toContain("data-[focused]:bg-soft");

    await chooser.keyboard("{ArrowDown}");
    const second = screen.getByRole("menuitem", { name: NOVELS[1].title });
    expect(document.activeElement).toBe(second);
    expect(second.getAttribute("data-focused")).toBe("true");
    // The state is exclusive: the item the walk left carries no focused
    // state at all — React-Aria drops the attribute, not a "false".
    expect(first.getAttribute("data-focused")).toBeNull();

    await chooser.keyboard("{ArrowUp}");
    expect(document.activeElement).toBe(first);
  });

  it("passes the axe floor with the menu open", async () => {
    mockApi();
    renderAt("/novels/n1");
    const trigger = await screen.findByRole("button", {
      name: `${t("shell.railBookMenu")}: ${NOVELS[0].title}`,
    });
    await user().click(trigger);
    expect(screen.getByRole("menu")).toBeTruthy();

    // The E2E floor's own scope (app/kernel/testing/a11y.py): axe-core on
    // the whole document — the menu's popover portals to the body, so the
    // open menu is inside the scan — over the WCAG 2 A/AA rule tags, failing
    // on any violation with the targets a fix needs. The same "cannot pass
    // without having checked" discipline: a verdict that is not a result
    // with a violations list is a failure, never a pass.
    const report = await axe.run(document.body, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
    });
    expect(Array.isArray(report.violations)).toBe(true);
    const found = report.violations
      .map((violation) => {
        const targets = violation.nodes
          .slice(0, 5)
          .map((node) => node.target.join(" "))
          .join("; ");
        return `[${violation.impact}] ${violation.id}: ${violation.help} — ${targets}`;
      })
      .join("\n");
    expect(found, `axe found WCAG A/AA violations:\n${found}`).toBe("");
  });

  it("offers the novels without an active one off the workspace", async () => {
    mockApi();
    renderAt("/");
    const trigger = await screen.findByRole("button", { name: t("shell.railBookMenu") });
    const chooser = user();
    await chooser.click(trigger);
    expect(screen.getByRole("menuitem", { name: NOVELS[0].title })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: NOVELS[1].title })).toBeTruthy();
  });

  it("waits for a book when the shelf is empty — no switcher of nothing", async () => {
    mockApi();
    get.mockImplementation(async (path: string) => {
      if (path === "/api/settings") {
        return { data: { locale: null, theme: null }, response: ok() };
      }
      if (path === "/api/writing/novels") return { data: [], response: ok() };
      throw new Error(`unexpected GET ${path}`);
    });
    renderAt("/");
    // The nav renders while the list is in flight; the assertion below is
    // about the settled state, so wait for the library ask to have happened.
    await screen.findByText(t("shell.navHome"));
    expect(
      screen.queryByRole("button", { name: t("shell.railBookMenu") }),
    ).toBeNull();
  });
});

describe("the sync dot", () => {
  const DOT_CLASS = {
    saved: "bg-success",
    pending: "bg-warning",
    failed: "bg-danger",
  } as const;
  const LABEL_KEY = {
    saved: "shell.syncSaved",
    pending: "shell.syncPending",
    failed: "shell.syncFailed",
  } as const;

  it.each(["saved", "pending", "failed"] as const)(
    "renders the state it is handed: %s",
    async (state) => {
      sync = state;
      renderAt("/");
      // The router's first paint is a tick away; the nav's own Home link is
      // the arrival marker.
      await screen.findByText(t("shell.navHome"));
      const line = document.querySelector(`[data-sync="${state}"]`);
      expect(line).not.toBeNull();
      expect(line?.textContent).toBe(t(LABEL_KEY[state]));
      const dot = line?.querySelector("span span");
      expect(dot?.className).toContain(DOT_CLASS[state]);
    },
  );
});

describe("the theme toggle", () => {
  function triggerName(state: "system" | "light" | "dark"): string {
    const key = {
      system: "settings.appearance.system",
      light: "settings.appearance.light",
      dark: "settings.appearance.dark",
    }[state] as "settings.appearance.system";
    return `${t("shell.railTheme")}: ${t(key)}`;
  }

  it("cycles system → light → dark on the settings row's write contract", async () => {
    mockApi();
    storedTheme = null;
    renderAt("/");
    const chooser = user();
    const trigger = await screen.findByRole("button", { name: triggerName("system") });

    // system → light: applied before the write, named as the AppearancePage
    // contract drives it.
    await chooser.click(trigger);
    expect(document.documentElement.dataset.theme).toBe("light");
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith("/api/settings/theme", {
        body: { theme: "light" },
      }),
    );
    await waitFor(() =>
      expect(trigger.getAttribute("aria-label")).toBe(triggerName("light")),
    );

    // light → dark: same contract, the row now holds light.
    await chooser.click(trigger);
    expect(document.documentElement.dataset.theme).toBe("dark");
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith("/api/settings/theme", {
        body: { theme: "dark" },
      }),
    );
    await waitFor(() =>
      expect(trigger.getAttribute("aria-label")).toBe(triggerName("dark")),
    );

    // dark → system: the choice is the row's null, the document's attribute gone.
    await chooser.click(trigger);
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith("/api/settings/theme", {
        body: { theme: null },
      }),
    );
    await waitFor(() => expect(document.documentElement.dataset.theme).toBeUndefined());
    await waitFor(() =>
      expect(trigger.getAttribute("aria-label")).toBe(triggerName("system")),
    );
  });

  it("restores the stored light when the write is refused", async () => {
    mockApi();
    storedTheme = "light";
    patch.mockRejectedValue(new Error("the service is down"));
    renderAt("/");
    const chooser = user();
    const trigger = await screen.findByRole("button", { name: triggerName("light") });

    await chooser.click(trigger);
    // The press walked the cycle — the write it attempted was the dark —
    // and the refusal rolled it back: document and control hold the stored
    // light again, the mirror included.
    expect(patch).toHaveBeenCalledWith("/api/settings/theme", {
      body: { theme: "dark" },
    });
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("light"));
    expect(trigger.getAttribute("aria-label")).toBe(triggerName("light"));
    expect(localStorage.getItem("narrare.theme")).toBe("light");
  });
});

describe("the user block", () => {
  it("names the writer the open book's row carries", async () => {
    mockApi();
    renderAt("/novels/n1");
    expect(await screen.findByText("H. Calder")).toBeTruthy();
    expect(screen.getByText(t("shell.railUserTier"))).toBeTruthy();
  });

  it("renders the fallback label when the author name is null", async () => {
    mockApi();
    renderAt("/novels/n2");
    expect(await screen.findByText(t("shell.railUserFallback"))).toBeTruthy();
    expect(screen.getByText(t("shell.railUserTier"))).toBeTruthy();
  });
});

describe("the rail's area hues", () => {
  it("maps the five areas to five distinct utilities", () => {
    expect(Object.keys(AREA_ICON).sort()).toEqual([
      "chat",
      "knowledge",
      "planning",
      "settings",
      "writing",
    ]);
    expect(new Set(Object.values(AREA_ICON)).size).toBe(5);
  });

  it("applies the hue to the icon's span", () => {
    // The constant alone would pass while the link stopped wearing it; the
    // four hues would collapse to the rail's muted ink unnoticed.
    expect(railSource).toMatch(/<span style=\{areaStyle\(area\)\}>/);
  });

  it("derives the colour from any capability id", () => {
    expect(areaStyle("future-area")).toEqual({
      color: "var(--area-future-area, var(--foreground))",
    });
  });

  it("keeps a token for each of the five existing areas", () => {
    const css = readFileSync("globals.css", "utf8");
    for (const area of ["writing", "knowledge", "chat", "planning", "settings"]) {
      expect(css).toContain(`--area-${area}:`);
    }
  });
});

describe("the rail's drafted chrome", () => {
  it("sits on the panel ground behind a hairline edge, flat (Tier 1)", () => {
    // The tier's discipline: a chrome rail is a flat panel bound by the
    // hairline — the open rail's overlay shadow the old shell wore is
    // gone, because elevation belongs to the tiers that earn it. The one
    // `shadow-overlay` in the file belongs to the book menu's popover, the
    // floating surface's own Tier 3 elevation (Menu.tsx's paint) — the
    // rail panel itself stays flat.
    expect(railSource).toMatch(/border-r border-border bg-panel/);
    expect(railSource).not.toMatch(/shadow-(?!overlay)/);
  });

  it("carries the eyebrow-tracked group labels the drafts group the rail by", () => {
    // The section label rides the eyebrow step and the same reveal the
    // destination names ride — one mechanism, so the labels can never
    // open on a different trigger than the names they sit above.
    expect(railSource).toMatch(/text-eyebrow uppercase/);
    expect(railSource).toMatch(/const REVEAL =/);
    expect(railSource.match(new RegExp("\\$\\{REVEAL\\}", "g"))?.length).toBeGreaterThanOrEqual(2);
  });
});

describe("the rail's groups", () => {
  it("place every generated destination exactly once, Home in exactly one", () => {
    // A capability that joins `nav` without being placed in a group
    // fails here: the grouping is a decision the drafts made, not a
    // default the generated file carries.
    const placed = RAIL_GROUPS.flatMap((group) => group.ids).sort();
    expect(placed).toEqual([...nav.map((entry) => entry.id)].sort());
    expect(new Set(placed).size).toBe(placed.length);
    expect(RAIL_GROUPS.filter((group) => group.home)).toHaveLength(1);
  });

  it("names each group through the catalogs, never a hard-coded string", () => {
    for (const group of RAIL_GROUPS) {
      expect(group.labelKey).toMatch(/^shell\.railGroup/);
    }
  });
});
