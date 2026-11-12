// @vitest-environment jsdom
/**
 * The rail's drafted meta header and tabs (spec §5.2): the header card with
 * the area-writing eyebrow, the neutral draft badge, the book's name in the
 * serif and the two real counts — chapters, and the Σ of the rail's own
 * per-chapter words. Below it the "Chapters / Scenes & plot" pair: pure
 * client state, keyboard-operable ARIA tabs, the chapters' list on the first,
 * an honest empty state pointing at the novel's planning surface on the
 * second. What the draft shows that no field backs stays out and is named
 * for the follow-up where it hides (spec §6).
 *
 * The rail renders under the one router its planning link reads (a link is
 * a destination, not a button) — the WorkspaceToolbar.test harness pattern.
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

import type { Chapter } from "@shell/lib/api/client";
import { t } from "@shell/lib/i18n";

import { ChapterRail } from "./novel/ChapterRail";

const NOVEL_ID = "6f1c2a52-9d3e-4f6e-8df5-7db9df0f4a52";

/** Three drafted rows; the counts map is the draft's own numbers. */
const CHAPTERS: Chapter[] = [
  {
    id: "c1",
    novel_id: NOVEL_ID,
    title: "Ghost in the Machine",
    body: "",
    position: 0,
    created_at: "2026-11-12T09:00:00Z",
    updated_at: "2026-11-12T09:00:00Z",
  },
  {
    id: "c2",
    novel_id: NOVEL_ID,
    title: "The Door Between Worlds",
    body: "",
    position: 1,
    created_at: "2026-11-12T09:01:00Z",
    updated_at: "2026-11-12T09:01:00Z",
  },
  {
    id: "c3",
    novel_id: NOVEL_ID,
    title: "Signal Lost",
    body: "",
    position: 2,
    created_at: "2026-11-12T09:02:00Z",
    updated_at: "2026-11-12T09:02:00Z",
  },
];

/** A row's accessible name: the title, then its count in words (the rail's composition). */
function rowName(chapter: (typeof CHAPTERS)[number], words: number): string {
  return `${chapter.title} ${t("chapters.wordCount", { count: words })}`;
}

/** The overrides a case names; everything else takes the loaded rail. */
type RailOverrides = {
  bookTitle?: string | undefined;
  chapterCounts?: Map<string, number>;
};

let props: Record<string, unknown>;

function railProps(overrides: RailOverrides = {}): Record<string, unknown> {
  return {
    visibleChapters: CHAPTERS,
    chapterCounts: new Map([
      ["c1", 765],
      ["c2", 1062],
      ["c3", 1557],
    ]),
    active: "c1",
    activeVisibleIndex: 0,
    walkedIndex: null,
    railListRef: { current: null },
    dragId: { current: null },
    dropIndex: null,
    railFilter: null,
    orderFailed: false,
    createFailed: false,
    chapterCount: 3,
    novelId: NOVEL_ID,
    bookTitle: "Dead Signal" as string | undefined,
    move: vi.fn(),
    moveTo: vi.fn(),
    setWalkedIndex: vi.fn(),
    setDropIndex: vi.fn(),
    select: vi.fn(),
    walkRail: vi.fn(),
    onCreateChapter: vi.fn(),
    ...overrides,
  };
}
props = railProps();

/** The rail under the one router its planning link reads. */
function Harness() {
  return <ChapterRail {...(props as ComponentProps<typeof ChapterRail>)} />;
}

const rootRoute = createRootRoute({ component: Harness });
const novelRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/novels/$id",
  component: () => null,
});
const planningRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/planning",
  component: () => null,
});

async function renderRail(): Promise<void> {
  const router = createRouter({
    routeTree: rootRoute.addChildren([novelRoute, planningRoute]),
    history: createMemoryHistory({ initialEntries: [`/novels/${NOVEL_ID}`] }),
  });
  render(<RouterProvider router={router} />);
  // The router paints nothing on its first tick (TanStack mounts empty
  // once, then settles) — flush it so the assertions below read DOM.
  await act(async () => {});
}

afterEach(async () => {
  cleanup();
  props = railProps();
});

describe("the meta header", () => {
  it("wears the drafted eyebrow and a neutral draft badge", async () => {
    await renderRail();
    expect(screen.getByText(t("workspace.railOutline"))).toBeTruthy();
    const badge = screen.getByText(t("workspace.railDraft"));
    // Neutral paint — the draft badge is chrome, never an area hue.
    expect(badge.className).toContain("bg-surface");
    expect(badge.className).not.toContain("area-writing");
  });

  it("never invents the drafted version number", async () => {
    await renderRail();
    // The draft reads "Entwurf v2.4"; the app has no version field, so the
    // badge says "Entwurf" and nothing else — no digits, no "v2".
    expect(screen.getByText(t("workspace.railDraft")).textContent).toBe(
      t("workspace.railDraft"),
    );
  });

  it("shows the book in the serif, as text — never a second book-title heading", async () => {
    await renderRail();
    const title = screen.getByText("Dead Signal");
    expect(title.className).toContain("text-primary");
    expect(title.className).toContain("[font-family:");
    // The workspace's one book-title heading is the page's h1: eight E2E
    // files pin `get_by_role("heading", name=title)` to resolve to exactly
    // it, so the rail's drafted title must stay a styled paragraph.
    expect(screen.queryByRole("heading", { name: "Dead Signal" })).toBeNull();
  });

  it("waits for the book's row instead of naming an empty title", async () => {
    props = railProps({ bookTitle: undefined });
    await renderRail();
    expect(screen.queryByText("Dead Signal")).toBeNull();
  });

  it("derives both counts from the data the rail holds", async () => {
    await renderRail();
    expect(screen.getByText(t("shelf.card.chapters", { count: 3 }))).toBeTruthy();
    // 765 + 1062 + 1557: the map's Σ, in tabular figures.
    const words = screen.getByText(t("chapters.wordCount", { count: 3384 }));
    expect(words.className).toContain("tabular-nums");
  });

  it("re-derives the Σ when the counts change", async () => {
    props = railProps({ chapterCounts: new Map([["c1", 1], ["c2", 2]]) });
    await renderRail();
    // A derivation would print 3384 forever; a sum prints the map's truth.
    expect(screen.getByText(t("chapters.wordCount", { count: 3 }))).toBeTruthy();
    expect(screen.queryByText(t("chapters.wordCount", { count: 3384 }))).toBeNull();
  });

  it("carries the two interim comments with their follow-up anchors", () => {
    const source = readFileSync(
      "../app/capabilities/writing/web/novel/RailHeader.tsx",
      "utf8",
    );
    expect(source).toContain(
      "// interim: no version field — follow-up filed in W3's index",
    );
    expect(source).toContain(
      "// interim: no scenes view — follow-up filed in W3's index",
    );
  });
});

describe("the outline tabs", () => {
  it("opens on Kapitel with the drafted pair and the list below", async () => {
    await renderRail();
    const tablist = screen.getByRole("tablist", { name: t("workspace.railViews") });
    expect(tablist).toBeTruthy();
    const chapters = screen.getByRole("tab", { name: t("workspace.railTabChapters") });
    const scenes = screen.getByRole("tab", { name: t("workspace.railTabScenes") });
    expect(chapters.getAttribute("aria-selected")).toBe("true");
    expect(scenes.getAttribute("aria-selected")).toBe("false");
    // Kapitel is the active tab: the chapters' list stands, the Szenen
    // panel does not.
    expect(
      screen.getByRole("button", { name: rowName(CHAPTERS[0]!, 765) }),
    ).toBeTruthy();
    expect(screen.queryByText(t("workspace.railScenesEmpty"))).toBeNull();
  });

  it("renders the Szenen empty state with the novel's planning link", async () => {
    await renderRail();
    const user = userEvent.setup();
    await user.click(screen.getByRole("tab", { name: t("workspace.railTabScenes") }));
    expect(screen.getByText(t("workspace.railScenesEmpty"))).toBeTruthy();
    const door = screen.getByRole("link", { name: t("workspace.railScenesOpen") });
    // The active novel's id rides the planning surface's `?novel=` param.
    expect(door.getAttribute("href")).toBe(`/planning?novel=${NOVEL_ID}`);
    // And back: the chapters' list returns, the empty state leaves.
    await user.click(screen.getByRole("tab", { name: t("workspace.railTabChapters") }));
    expect(
      screen.getByRole("button", { name: rowName(CHAPTERS[0]!, 765) }),
    ).toBeTruthy();
    expect(screen.queryByText(t("workspace.railScenesEmpty"))).toBeNull();
  });

  it("keeps the walk's tab stop on the Kapitel list alone", async () => {
    await renderRail();
    const first = screen.getByRole("button", { name: rowName(CHAPTERS[0]!, 765) });
    expect(first.getAttribute("tabindex")).toBe("0");
    // The keyboard walk belongs to the chapters' list: on the Szenen tab no
    // row renders, so no walk can reach or strand on a gone list.
    const user = userEvent.setup();
    await user.click(screen.getByRole("tab", { name: t("workspace.railTabScenes") }));
    expect(
      screen.queryByRole("button", { name: rowName(CHAPTERS[0]!, 765) }),
    ).toBeNull();
    expect(screen.queryByRole("button", { name: rowName(CHAPTERS[2]!, 1557) })).toBeNull();
  });

  it("names the rail for the reader the way the viewport E2Es find it", async () => {
    await renderRail();
    // `aside[aria-label="Kapitel"]` is two E2E files' RAIL selector; the
    // drafted header must not move the region's name.
    const aside = screen.getByRole("complementary", { name: t("chapters.heading") });
    expect(aside).toBeTruthy();
  });
});

describe("the tabs' keyboard", () => {
  it("moves selection and focus together, and comes back", async () => {
    await renderRail();
    const chapters = screen.getByRole("tab", { name: t("workspace.railTabChapters") });
    const scenes = screen.getByRole("tab", { name: t("workspace.railTabScenes") });
    chapters.focus();
    // APG automatic activation: the arrow moves the selection, the focus
    // rides with it, and the roving tabindex follows.
    await userEvent.keyboard("{ArrowRight}");
    expect(scenes.getAttribute("aria-selected")).toBe("true");
    expect(chapters.getAttribute("aria-selected")).toBe("false");
    expect(document.activeElement).toBe(scenes);
    await userEvent.keyboard("{ArrowLeft}");
    expect(chapters.getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(chapters);
  });

  it("jumps Home and End", async () => {
    await renderRail();
    const chapters = screen.getByRole("tab", { name: t("workspace.railTabChapters") });
    const scenes = screen.getByRole("tab", { name: t("workspace.railTabScenes") });
    chapters.focus();
    await userEvent.keyboard("{End}");
    expect(scenes.getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(scenes);
    await userEvent.keyboard("{Home}");
    expect(chapters.getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(chapters);
  });

  it("keeps the arrow walk off the tab row while the chapters' list walks", async () => {
    // The rail's own walk (ArrowUp/Down on rows) must not be eaten by the
    // tab row's handler: the tabs answer Left/Right/Home/End only.
    await renderRail();
    const chapters = screen.getByRole("tab", { name: t("workspace.railTabChapters") });
    chapters.focus();
    await userEvent.keyboard("{ArrowDown}");
    expect(chapters.getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(chapters);
  });
});
