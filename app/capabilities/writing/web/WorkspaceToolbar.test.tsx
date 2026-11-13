// @vitest-environment jsdom
/**
 * The workspace band's drafted ribbon (spec §5.1): the breadcrumb naming
 * the place and the book, the save chip speaking the one autosave status
 * the runhead's indicator reads, the book's live word count in tabular
 * figures, the language chip opening the settings page's own switcher, and
 * the drafted right cluster — focus, history (interim: disabled, with its
 * reason) and export. Every chip's content derives from the props the page
 * hands it; nothing on the band invents a value the app does not hold, and
 * the drafted target-progress pill stays an empty slot.
 *
 * The band renders under the one router its language chip reads (a link is
 * a destination, not a button) — the NovelPage.test harness pattern,
 * scoped to the band alone.
 */
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { readFileSync } from "node:fs";
import { afterEach, describe, expect, it, vi } from "vitest";

import { t } from "@shell/lib/i18n";
import type { SaveStatus } from "@shell/lib/save";

import { WorkspaceToolbar } from "./novel/WorkspaceToolbar";
import type { FocusStep } from "./routes";

/** A title long enough that the band must truncate it somewhere. */
const LONG_TITLE = "Ein sehr langer Buchtitel der beim Kürzen seinen Namen behält";

/** The overrides a case names; everything else takes the loaded workbench. */
type BandOverrides = {
  focus?: FocusStep;
  pending?: boolean;
  failed?: boolean;
  chapterCount?: number;
  bookTitle?: string | undefined;
  words?: number | undefined;
  status?: SaveStatus;
  localeChip?: string;
  onExport?: (() => void) | undefined;
};

function bandProps(overrides: BandOverrides = {}): Record<string, unknown> {
  return {
    focus: 0 as FocusStep,
    collapsed: false,
    showRail: true,
    pending: false,
    failed: false,
    chapterCount: 3,
    railFilter: null,
    activeDockPath: undefined,
    step: () => {},
    toggleRail: () => {},
    toggleDock: () => {},
    setWalkedIndex: () => {},
    setRailFilter: () => {},
    bookTitle: "Dead Signal" as string | undefined,
    words: 3384 as number | undefined,
    status: "saved" as SaveStatus,
    localeChip: "EN",
    onExport: vi.fn(),
    ...overrides,
  };
}

let props = bandProps();

/** The band under the one router its language link reads. */
function Harness() {
  return <WorkspaceToolbar {...(props as ComponentProps<typeof WorkspaceToolbar>)} />;
}

const rootRoute = createRootRoute({ component: Harness });
const novelRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/novels/$id",
  component: () => null,
});
const languageRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings/language",
  component: () => null,
});

async function renderBand(): Promise<void> {
  const router = createRouter({
    routeTree: rootRoute.addChildren([novelRoute, languageRoute]),
    history: createMemoryHistory({ initialEntries: ["/novels/n1"] }),
  });
  render(<RouterProvider router={router} />);
  // The router paints nothing on its first tick (TanStack mounts empty
  // once, then settles) — flush it so the sync queries below read DOM.
  await act(async () => {});
}

afterEach(async () => {
  cleanup();
  props = bandProps();
});

describe("the breadcrumb", () => {
  it("names the place and the book, the full title riding the truncating span", async () => {
    props = bandProps({ bookTitle: LONG_TITLE });
    await renderBand();
    expect(screen.getByText(t("workspace.breadcrumbRoot"))).toBeTruthy();
    const book = screen.getByText(LONG_TITLE);
    // The visible span truncates; its text — and with it the accessible
    // name — stays the whole title (Review focus 3).
    expect(book.className).toContain("truncate");
    expect(book.textContent).toBe(LONG_TITLE);
    expect(book.className).toContain("text-emph");
  });

  it("waits for the book's row: the place alone, no dangling separator", async () => {
    props = bandProps({ bookTitle: undefined });
    await renderBand();
    expect(screen.getByText(t("workspace.breadcrumbRoot"))).toBeTruthy();
    expect(screen.queryByText("Dead Signal")).toBeNull();
    expect(screen.queryByText("/")).toBeNull();
  });
});

describe("the save chip", () => {
  it.each([
    ["idle", "shell.syncSaved", "bg-success"],
    ["saved", "shell.syncSaved", "bg-success"],
    ["pending", "shell.syncPending", "bg-warning"],
    ["saving", "shell.syncPending", "bg-warning"],
    ["failed", "shell.syncFailed", "bg-danger"],
  ] as const)("speaks %s from the one status owner", async (status, key, dot) => {
    props = bandProps({ status });
    await renderBand();
    const chip = screen.getByText(t(key)).closest("span");
    expect(chip?.dataset.save).toBe(status);
    expect(chip?.querySelector("span")?.className).toContain(dot);
  });

  it("stands down while the chapters wait", async () => {
    props = bandProps({ pending: true });
    await renderBand();
    expect(screen.queryByText(t("shell.syncSaved"))).toBeNull();
    expect(screen.queryByText(t("shell.syncPending"))).toBeNull();
  });

  it("stands down on the outage page", async () => {
    props = bandProps({ failed: true });
    await renderBand();
    expect(screen.queryByText(t("shell.syncSaved"))).toBeNull();
  });

  it("stands down for an empty book — no save state, no document", async () => {
    props = bandProps({ chapterCount: 0 });
    await renderBand();
    expect(screen.queryByText(t("shell.syncSaved"))).toBeNull();
  });
});

describe("the word-count chip", () => {
  it("counts the book in tabular figures beside the edit glyph", async () => {
    await renderBand();
    const count = screen.getByText(t("chapters.wordCount", { count: 3384 }));
    expect(count.className).toContain("tabular-nums");
    // The glyph is decorative; the count's text is the chip's content.
    expect(count.parentElement?.querySelector("svg")).not.toBeNull();
  });

  it("waits for the chapters' answer instead of claiming zero", async () => {
    props = bandProps({ words: undefined });
    await renderBand();
    expect(document.querySelector(".tabular-nums")).toBeNull();
  });
});

describe("the language chip", () => {
  it("renders the active locale and opens the settings page's switcher", async () => {
    props = bandProps({ localeChip: "DE" });
    await renderBand();
    const chip = screen.getByRole("link", {
      name: t("workspace.languageChip", { code: "DE" }),
    });
    expect(chip.getAttribute("href")).toBe("/settings/language");
    // The visible code rides inside the accessible name — the name is
    // never less than what is on screen.
    expect(chip.textContent).toContain("DE");
  });
});

describe("the interim history control", () => {
  it("renders disabled and carries its reason as name and tooltip", async () => {
    await renderBand();
    const button = screen.getByRole("button", { name: t("workspace.historyPending") });
    expect(button.getAttribute("aria-disabled")).toBe("true");
    expect(button.getAttribute("title")).toBe(t("workspace.historyPending"));
  });
});

describe("the export control", () => {
  it("presses the page's export dialog open", async () => {
    const onExport = vi.fn();
    props = bandProps({ onExport });
    await renderBand();
    const chooser = userEvent.setup({ pointerEventsCheck: 0 });
    await chooser.click(screen.getByRole("button", { name: t("shelf.export") }));
    expect(onExport).toHaveBeenCalledTimes(1);
  });

  it("waits with the book: no press while the row has not arrived", async () => {
    props = bandProps({ onExport: undefined });
    await renderBand();
    expect(screen.queryByRole("button", { name: t("shelf.export") })).toBeNull();
  });
});

describe("the interim target pill", () => {
  it("keeps its slot empty — no bar, no invented number", async () => {
    await renderBand();
    expect(screen.queryByRole("progressbar")).toBeNull();
  });

  it("carries the two interim comments with their follow-up anchors", async () => {
    const source = readFileSync(
      "../app/capabilities/writing/web/novel/WorkspaceToolbar.tsx",
      "utf8",
    );
    expect(source).toContain(
      "// interim: no version-history capability yet — #823",
    );
    expect(source).toContain(
      "// interim: per-chapter target field missing, shares shelf follow-up #783",
    );
  });
});

describe("the frozen controls", () => {
  it("keeps focus, rail toggle and the dock tabs in the band", async () => {
    await renderBand();
    const focus = screen.getByRole("button", { name: t("workspace.focusToggle") });
    expect(focus.getAttribute("aria-pressed")).toBe("false");
    expect(screen.getByRole("button", { name: t("workspace.railToggle") })).toBeTruthy();
    const dockTabs = screen.getByRole("group", { name: t("workspace.dockToggle") });
    expect(dockTabs.querySelectorAll("button").length).toBe(3);
  });

  it("hides the rail toggle where the rail is suppressed", async () => {
    props = bandProps({ focus: 1 });
    await renderBand();
    expect(screen.queryByRole("button", { name: t("workspace.railToggle") })).toBeNull();
    expect(screen.getByRole("button", { name: t("workspace.focusToggle") })).toBeTruthy();
  });
});
