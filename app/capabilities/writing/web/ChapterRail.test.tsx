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
 * The drafted chapter rows (spec §5.2): grip chrome revealed on hover, the
 * zero-padded "Kapitel 0N" eyebrow, the right-aligned tabular count, the
 * title in `text-emph` truncating with the whole string in the accessible
 * name, the interim status line, and the full-width add-chapter button on
 * the existing create path. The row machinery — walk, select, reorder,
 * filter — is pinned by NovelPage.test and stays untouched.
 *
 * The rail renders under the one router its planning link reads (a link is
 * a destination, not a button) — the WorkspaceToolbar.test harness pattern.
 */
import { act, cleanup, render, screen, within } from "@testing-library/react";
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
import { formatWordCount } from "@shell/lib/words";

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

/**
 * A row's accessible name: the card spelled in its DOM order — title,
 * eyebrow, figure, status — the one sequence both the axe label-content
 * rule and the E2E locators (which anchor on the leading title) read.
 */
function rowName(chapter: (typeof CHAPTERS)[number], words: number): string {
  const title = chapter.title || t("chapters.defaultTitle", { n: chapter.position + 1 });
  const eyebrow = t("chapters.defaultTitle", {
    n: String(chapter.position + 1).padStart(2, "0"),
  });
  return `${title} ${eyebrow} ${formatWordCount(words)} ${t("chapters.statusFirstDraft")}`;
}

/** The overrides a case names; everything else takes the loaded rail. */
type RailOverrides = {
  bookTitle?: string | undefined;
  chapterCounts?: Map<string, number>;
  visibleChapters?: Chapter[];
  chapterCount?: number;
  active?: string | null;
  activeVisibleIndex?: number;
};

let props: Record<string, unknown>;

function railProps(overrides: RailOverrides = {}): Record<string, unknown> {
  return {
    visibleChapters: overrides.visibleChapters ?? CHAPTERS,
    chapterCounts: overrides.chapterCounts ?? new Map([
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
    chapterCount: overrides.chapterCount ?? 3,
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
    // The serif rides as the family utility; the metrics stay the title
    // step's own — the draft's rail head draws the name near 21/28, not
    // the chapter headline's 26/34.
    expect(title.className).toContain("font-garamond");
    expect(title.className).toContain("text-title");
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
      "// interim: no version field — #816",
    );
    expect(source).toContain(
      "// interim: no scenes view — #819",
    );
  });
});

describe("the drafted rows", () => {
  it("composes the draft's four parts: grip, eyebrow, count, title, status", async () => {
    await renderRail();
    const row = screen.getByRole("button", { name: rowName(CHAPTERS[0]!, 765) });
    // The eyebrow: the position, zero-padded to two places ("Kapitel 01") —
    // the rail stays digits; only the editor's eyebrow is written out.
    expect(
      within(row).getByText(t("chapters.defaultTitle", { n: "01" })),
    ).toBeTruthy();
    // The count: the localized figure alone, in tabular figures.
    const count = within(row).getByText(formatWordCount(765));
    expect(count.className).toContain("tabular-nums");
    // The title: `text-emph`, truncating — the full string rides in the name.
    const title = within(row).getByText("Ghost in the Machine");
    expect(title.className).toContain("text-emph");
    expect(title.className).toContain("truncate");
    // The status: the interim line, on every row.
    expect(within(row).getByText(t("chapters.statusFirstDraft"))).toBeTruthy();
    expect(screen.getAllByText(t("chapters.statusFirstDraft"))).toHaveLength(3);
  });

  it("pads the eyebrow's digits past nine chapters too", async () => {
    const eleventh: Chapter = { ...CHAPTERS[2]!, id: "c11", position: 10, title: "Breites Wasser" };
    props = railProps({ visibleChapters: [...CHAPTERS, eleventh], chapterCount: 11 });
    await renderRail();
    const row = screen.getByRole("button", { name: rowName(eleventh, 0) });
    expect(within(row).getByText(t("chapters.defaultTitle", { n: "11" }))).toBeTruthy();
  });

  it("paints the active row with the drafted wash, not the shared row's", async () => {
    await renderRail();
    const active = screen.getByRole("button", { name: rowName(CHAPTERS[0]!, 765) });
    // The draft's `secondary-container` treatment — and none of the shared
    // Row's `--soft` wash or start edge: this rail composes its own frame.
    expect(active.className).toContain("bg-secondary-container");
    expect(active.className).not.toContain("bg-soft");
    expect(active.className).not.toContain("border-b");
    expect(active.getAttribute("aria-current")).toBe("true");
    const rest = screen.getByRole("button", { name: rowName(CHAPTERS[1]!, 1062) });
    expect(rest.className).not.toContain("bg-secondary-container");
    expect(rest.getAttribute("aria-current")).toBeNull();
    // The rest state hovers into the drafted container step.
    expect(rest.className).toContain("hover:bg-surface-container");
  });

  it("carries the whole title in the accessible name though the paint truncates", async () => {
    const long = "Die Nacht, in der der Nebel über die Deiche kroch und dort blieb";
    const chapter: Chapter = { ...CHAPTERS[0]!, title: long };
    props = railProps({
      visibleChapters: [chapter, CHAPTERS[1]!],
      chapterCounts: new Map([["c1", 765], ["c2", 1062]]),
    });
    await renderRail();
    const row = screen.getByRole("button", { name: rowName(chapter, 765) });
    // The name opens with the full, untruncated title — the E2E locators
    // anchor on it, and truncation may never hide it from a reader.
    expect(row.getAttribute("aria-label")!.startsWith(`${long} `)).toBe(true);
    // The DOM text stays whole too; only the paint clips.
    expect(within(row).getByText(long)).toBeTruthy();
  });

  it("keeps the grip chrome hidden from the reader and revealed on hover", async () => {
    await renderRail();
    const active = screen.getByRole("button", { name: rowName(CHAPTERS[0]!, 765) });
    const rest = screen.getByRole("button", { name: rowName(CHAPTERS[1]!, 1062) });
    for (const row of [active, rest]) {
      const grip = row.querySelector('span[aria-hidden="true"]');
      expect(grip?.querySelector("svg")).toBeTruthy();
      expect(grip?.className).toContain("group-hover:opacity-100");
    }
    // The draft's pair: the active row's grip stands at 60 %, a resting
    // row's stays hidden until hover or focus brings it out.
    expect(active.querySelector('span[aria-hidden="true"]')!.className).toContain("opacity-60");
    expect(rest.querySelector('span[aria-hidden="true"]')!.className).toContain("opacity-0");
  });

  it("spells the card in DOM order: title, eyebrow, figure, status", async () => {
    await renderRail();
    const row = screen.getByRole("button", { name: rowName(CHAPTERS[0]!, 765) });
    // The name is the card's visible sequence, word for word: axe's
    // label-content rule reads the DOM order (hidden chrome included),
    // so the name must carry every visible word, in order, unbroken.
    expect(row.getAttribute("aria-label")).toBe(rowName(CHAPTERS[0]!, 765));
    // The name still opens with the title — the E2E locators anchor on it.
    expect(row.getAttribute("aria-label")!.startsWith("Ghost in the Machine ")).toBe(true);
  });

  it("carries the status interim with its shared follow-up anchor", () => {
    const source = readFileSync("../app/capabilities/writing/web/novel/ChapterRail.tsx", "utf8");
    expect(source).toContain(
      "// interim: no chapter status field — shares shelf follow-up #784",
    );
  });

  it("offers the create path as the drafted full-width add-button", async () => {
    await renderRail();
    const add = screen.getByRole("button", { name: t("chapters.new") });
    expect(add.className).toContain("w-full");
    // The drafted chip paint (the owner's fix round): container-high ground,
    // the secondary container on the hover, primary ink, the chip's shadow —
    // the local composition the matrix has no voice for.
    expect(add.className).toContain("bg-surface-container-high");
    expect(add.className).toContain("hover:bg-secondary-container");
    expect(add.className).toContain("text-primary");
    expect(add.className).toContain("shadow-sm");
    // The drafted glyph rides beside the label.
    expect(add.querySelector("svg")).toBeTruthy();
    const user = userEvent.setup();
    await user.click(add);
    expect((props.onCreateChapter as ReturnType<typeof vi.fn>).mock.calls.length).toBeGreaterThan(
      0,
    );
  });
});

describe("the rail's foot", () => {
  it("mounts the arc and the session card with the open chapter's number", async () => {
    await renderRail();
    expect(screen.getByText(t("workspace.railArcLabel"))).toBeTruthy();
    // The open chapter is the book's first: the caption names chapter 1,
    // the marker rides at 1/3, and the meta keeps its plot placeholder.
    expect(screen.getByText(t("workspace.railArcChapter", { n: 1 }))).toBeTruthy();
    expect(screen.getByText(t("workspace.railArcNone"))).toBeTruthy();
    expect(screen.getByText(t("workspace.railSessionLabel"))).toBeTruthy();
    expect(screen.getByText(t("workspace.railSessionNone"))).toBeTruthy();
  });

  it("marks no place on the curve when no chapter is open", async () => {
    props = railProps({ active: null, activeVisibleIndex: -1 });
    await renderRail();
    expect(screen.queryByText(t("workspace.railArcChapter", { n: 1 }))).toBeNull();
  });

  it("stands on the rail's foot, both tabs — not the chapters panel's", async () => {
    await renderRail();
    const user = userEvent.setup();
    await user.click(screen.getByRole("tab", { name: t("workspace.railTabScenes") }));
    expect(screen.getByText(t("workspace.railArcLabel"))).toBeTruthy();
    expect(screen.getByText(t("workspace.railSessionLabel"))).toBeTruthy();
  });

  it("lays the drawer's panels out at natural flow — flex-1 is the desktop column's alone", () => {
    // Below 1024 the drawer is the scroll container: a flex-growing panel
    // under the drawer's height collapses and spills the list beneath the
    // foot widgets, which paint over it — the rows and the add button
    // become unclickable (the 360 sweep's drawer legs once proved it).
    // The panel may take the capped column's remainder only at ≥1024,
    // where the list scrolls inside itself.
    const source = readFileSync("../app/capabilities/writing/web/novel/ChapterRail.tsx", "utf8");
    expect(source).toContain('className="flex flex-col px-3 lg:min-h-0 lg:flex-1"');
    expect(source).toContain('className="flex flex-col lg:min-h-0 lg:flex-1"');
    // No bare flex-1 on a tabpanel — the spill is what the pins above prevent.
    expect(source).not.toMatch(/className="flex min-h-0 flex-1[^"]*"/);
  });

  it("reads the marker from the chapter's own place in the book, not the filter's slot", async () => {
    // A filter's slot is the visible list's order, not the book's; the
    // caption names the chapter's number, so it must survive the filter.
    const late: Chapter = { ...CHAPTERS[2]!, id: "c9", position: 8, title: "Spät" };
    props = railProps({
      visibleChapters: [CHAPTERS[0]!, late],
      active: "c9",
      chapterCount: 9,
    });
    await renderRail();
    expect(screen.getByText(t("workspace.railArcChapter", { n: 9 }))).toBeTruthy();
    expect(screen.queryByText(t("workspace.railArcChapter", { n: 2 }))).toBeNull();
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
