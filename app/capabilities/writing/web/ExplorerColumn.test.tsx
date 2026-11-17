// @vitest-environment jsdom
/**
 * The explorer column (W4 Task 11, read-only): the scene-centric draft's
 * 280px left column — the identity card (real cover chip, title, genre),
 * the REAL daily ring (the activity aggregate's goal fields, the shelf
 * banner's own source), the tension card (real stage label from the
 * storyboard, placeholder curve #879, real scene codes), the scene tree
 * (position order, tabular word counts, the last-edited active marker,
 * neutral status dots #873, disabled create doors until Task 13) and the
 * shelf mini-card. The empty-book invitation answers per Kachel 3.
 */
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import type { UseQueryResult } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import type { Activity, Chapter, Novel, Scene, Storyboard } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";

import { ExplorerColumn } from "./ExplorerColumn";
import { orderedSceneEntries } from "./workspace";

const de = catalogs.de;

function novelRow(overrides: Partial<Novel> = {}): Novel {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    title: "Dead Signal",
    genre: "Hard Sci-Fi / Mystery",
    blurb: null,
    author: "H. Calder",
    language: null,
    chapter_count: 2,
    word_count: 1855,
    created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-14T10:00:00Z",
    last_exported_at: null,
    status: "draft",
    series_title: null,
    series_volume: null,
    archived_at: null,
    target_words: 85000,
    ...overrides,
  };
}

const CH1: Chapter = {
  id: "c1",
  novel_id: "11111111-1111-1111-1111-111111111111",
  title: "Ghost in the Machine",
  position: 0,
  scene_count: 2,
  word_count: 765,
  created_at: "2026-11-01T10:00:00Z",
  updated_at: "2026-11-12T10:00:00Z",
};
const CH2: Chapter = {
  id: "c2",
  novel_id: "11111111-1111-1111-1111-111111111111",
  title: "Nevada Echoes",
  position: 1,
  scene_count: 1,
  word_count: 1090,
  created_at: "2026-11-01T10:00:00Z",
  updated_at: "2026-11-11T10:00:00Z",
};
const S11: Scene = {
  id: "s11",
  chapter_id: "c1",
  title: "An Bord der Vanguard",
  body: "Prosa eins",
  setting: null,
  story_time: null,
  position: 1,
  word_count: 342,
  created_at: "2026-11-01T10:00:00Z",
  updated_at: "2026-11-11T08:00:00Z",
};
const S12: Scene = {
  id: "s12",
  chapter_id: "c1",
  title: "Das Signal im Permafrost",
  body: "Prosa zwei",
  setting: null,
  story_time: null,
  position: 2,
  word_count: 423,
  created_at: "2026-11-01T10:00:00Z",
  updated_at: "2026-11-14T09:30:00Z",
};
const S21: Scene = {
  id: "s21",
  chapter_id: "c2",
  title: "Sub-Basement",
  body: "Prosa drei",
  setting: null,
  story_time: null,
  position: 1,
  word_count: 1090,
  created_at: "2026-11-01T10:00:00Z",
  updated_at: "2026-11-12T07:00:00Z",
};

const CHAPTERS = [CH1, CH2];
const SCENES = new Map<string, Scene[]>([
  ["c1", [S11, S12]],
  ["c2", [S21]],
]);
const ENTRIES = orderedSceneEntries(CHAPTERS, SCENES);

function activityRow(overrides: Partial<Activity> = {}): Activity {
  return {
    points: [],
    streak_days: 0,
    weekly_average: 0,
    today_words: 412,
    daily_goal_words: 500,
    goal_met: false,
    goal_remaining: 88,
    ...overrides,
  };
}

const STORYBOARD: Storyboard = {
  novel_id: "11111111-1111-1111-1111-111111111111",
  structure_id: "three-act",
  stages: [
    {
      key: "setup",
      title_key: "storyboard.stage.setup",
      from: 0,
      to: 0.25,
      chapters: [
        {
          chapter_id: "c1",
          title: "Ghost in the Machine",
          position: 0,
          stage_key: "setup",
          assignment_source: "suggested",
          sync_status: "planned",
          word_count: 765,
        },
      ],
    },
    { key: "confrontation", title_key: "storyboard.stage.confrontation", from: 0.25, to: 0.75, chapters: [] },
    { key: "resolution", title_key: "storyboard.stage.resolution", from: 0.75, to: 1, chapters: [] },
  ],
};

function queryOf<T>(data: T | undefined, state: "success" | "pending" | "error" = "success"): UseQueryResult<T> {
  return {
    data,
    isPending: state === "pending",
    isError: state === "error",
    isSuccess: state === "success",
  } as UseQueryResult<T>;
}

function sceneResults(): UseQueryResult<Scene[]>[] {
  return [queryOf([S11, S12]), queryOf([S21])];
}

/** The column under a bare router root — the mini-card's Link needs the
 *  router context; the chrome's own contract lives in its own tests. */
const harnessRoot = createRootRoute({ component: () => <Outlet /> });

type ExplorerProps = Parameters<typeof ExplorerColumn>[0];

function explorerProps(overrides: Partial<ExplorerProps> = {}): ExplorerProps {
  return {
    novel: novelRow(),
    chapters: CHAPTERS,
    sceneResults: sceneResults(),
    entries: ENTRIES,
    activeSceneId: "s12",
    activeChapterId: "c1",
    collapsed: new Set<string>(),
    onToggleChapter: vi.fn(),
    onSelectChapter: vi.fn(),
    onSelectScene: vi.fn(),
    activity: queryOf(activityRow()),
    storyboard: queryOf(STORYBOARD),
    ...overrides,
  };
}

async function renderExplorer(overrides: Partial<ExplorerProps> = {}) {
  const props = explorerProps(overrides);
  const harnessRoute = createRoute({
    getParentRoute: () => harnessRoot,
    path: "/explorer-test",
    component: () => <ExplorerColumn {...props} />,
  });
  const router = createRouter({
    routeTree: harnessRoot.addChildren([harnessRoute]),
    history: createMemoryHistory({ initialEntries: ["/explorer-test"] }),
  });
  await router.load();
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return props;
}

beforeEach(() => {
  applyLocale("de");
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.unstubAllGlobals();
});

describe("the identity card", () => {
  it("carries the real cover chip, the title, the author and the genre", async () => {
    await renderExplorer();
    const card = screen.getByTestId("explorer-identity");
    expect(within(card).getByText("Dead Signal")).toBeTruthy();
    expect(within(card).getByText("H. Calder")).toBeTruthy();
    expect(within(card).getByText("Hard Sci-Fi / Mystery")).toBeTruthy();
    expect(within(card).getByText("DS")).toBeTruthy();
  });

  it("a missing author or genre keeps the card honest — no invented line", async () => {
    await renderExplorer({ novel: novelRow({ author: null, genre: null }) });
    const card = screen.getByTestId("explorer-identity");
    expect(within(card).queryByText("H. Calder")).toBeNull();
    expect(within(card).queryByText("Hard Sci-Fi / Mystery")).toBeNull();
  });
});

describe("the daily ring — the aggregate's own goal fields", () => {
  it("renders the real progress: today over goal, the remainder, the floored percent", async () => {
    await renderExplorer();
    const card = screen.getByTestId("explorer-ring");
    expect(within(card).getByText("412")).toBeTruthy();
    expect(within(card).getByText("/ 500 W.")).toBeTruthy();
    expect(within(card).getByText("82 %")).toBeTruthy();
    expect(within(card).getByText("Noch 88 Wörter bis zum Etappenziel")).toBeTruthy();
    const ring = card.querySelector("svg path[data-ring-progress]");
    expect(ring?.getAttribute("stroke-dasharray")).toBe("82, 100");
  });

  it("no goal keeps the honest neutral — today alone, no percent, the setter waits", async () => {
    await renderExplorer({ activity: queryOf(activityRow({ daily_goal_words: null, goal_remaining: 0 })) });
    const card = screen.getByTestId("explorer-ring");
    expect(within(card).getByText("412")).toBeTruthy();
    expect(within(card).getByText("W.", { exact: false })).toBeTruthy();
    expect(within(card).getByText(de["writing.workspace.ring.noGoal"])).toBeTruthy();
    expect(within(card).queryByText(/%/)).toBeNull();
    const edit = within(card).getByRole("button", { name: de["writing.workspace.ring.edit"] });
    expect(edit.hasAttribute("disabled")).toBe(true);
  });

  it("a reached day speaks the done copy at 100 percent", async () => {
    await renderExplorer({
      activity: queryOf(activityRow({ today_words: 500, goal_met: true, goal_remaining: 0 })),
    });
    const card = screen.getByTestId("explorer-ring");
    expect(within(card).getByText("100 %")).toBeTruthy();
    expect(within(card).getByText(de["writing.workspace.ring.met"])).toBeTruthy();
  });

  it("a negative day is unfloored — the aggregate's own math, never a zero", async () => {
    await renderExplorer({
      activity: queryOf(activityRow({ today_words: -40, goal_remaining: 540 })),
    });
    const card = screen.getByTestId("explorer-ring");
    expect(within(card).getByText("-40")).toBeTruthy();
    expect(within(card).getByText("/ 500 W.")).toBeTruthy();
    expect(within(card).getByText("0 %")).toBeTruthy();
  });

  it("pending placeholders and the error neutral — never an invented zero", async () => {
    await renderExplorer({ activity: queryOf<Activity>(undefined, "pending") });
    expect(screen.getByTestId("explorer-ring").querySelector("[aria-hidden='true']")).not.toBeNull();
    expect(screen.queryByText("0 W.")).toBeNull();
    cleanup();
    await renderExplorer({ activity: queryOf<Activity>(undefined, "error") });
    expect(screen.getByTestId("explorer-ring").textContent).toContain("—");
  });
});

describe("the tension card", () => {
  it("the stage label is the storyboard's own — the curve a marked placeholder (#879)", async () => {
    await renderExplorer();
    const card = screen.getByTestId("explorer-tension");
    expect(within(card).getByText("Exposition")).toBeTruthy();
    const curve = card.querySelector("svg");
    expect(curve?.getAttribute("aria-hidden")).toBe("true");
    // The real codes: first, active (marked), last.
    expect(within(card).getByText("K1-S1")).toBeTruthy();
    expect(within(card).getByText(/K1-S2/)).toBeTruthy();
    expect(within(card).getByText(de["writing.workspace.tension.activeMark"])).toBeTruthy();
    expect(within(card).getByText("K2-S1")).toBeTruthy();
  });

  it("no storyboard answer keeps the label neutral — the page stands", async () => {
    await renderExplorer({ storyboard: queryOf<Storyboard>(undefined, "error") });
    const card = screen.getByTestId("explorer-tension");
    expect(within(card).queryByText("Exposition")).toBeNull();
  });

  it("no scenes, no codes — the card keeps its geometry", async () => {
    await renderExplorer({ entries: [], activeSceneId: null, chapters: [], sceneResults: [] });
    const card = screen.getByTestId("explorer-tension");
    expect(within(card).queryByText(/K\d/)).toBeNull();
  });
});

describe("the scene tree", () => {
  it("chapters and scenes stand in position order with their tabular word counts", async () => {
    await renderExplorer();
    const tree = screen.getByTestId("explorer-tree");
    expect(within(tree).getByText("Kapitel 1 — Ghost in the Machine")).toBeTruthy();
    expect(within(tree).getByText("Kapitel 2 — Nevada Echoes")).toBeTruthy();
    expect(within(tree).getByText("Szene 1 · An Bord der Vanguard")).toBeTruthy();
    expect(within(tree).getByText("Szene 2 · Das Signal im Permafrost")).toBeTruthy();
    expect(within(tree).getByText("Szene 1 · Sub-Basement")).toBeTruthy();
    expect(within(tree).getByText("765 W.")).toBeTruthy();
    expect(within(tree).getByText("342 W.")).toBeTruthy();
    expect(within(tree).getByText("Gesamt: 1.855 W.")).toBeTruthy();
  });

  it("the active scene carries the marker — the last-edited one by default", async () => {
    await renderExplorer();
    const active = screen.getByRole("button", { name: /Szene 2 · Das Signal im Permafrost/ });
    expect(active.getAttribute("aria-current")).toBe("true");
    const inactive = screen.getByRole("button", { name: /Szene 1 · An Bord der Vanguard/ });
    expect(inactive.getAttribute("aria-current")).toBeNull();
  });

  it("selecting a scene or a chapter asks the page — the tree itself writes nothing", async () => {
    const props = await renderExplorer();
    fireEvent.click(screen.getByRole("button", { name: /Szene 1 · Sub-Basement/ }));
    expect(props.onSelectScene).toHaveBeenCalledWith("s21");
    fireEvent.click(screen.getByRole("button", { name: /Kapitel 2 — Nevada Echoes/ }));
    expect(props.onSelectChapter).toHaveBeenCalledWith("c2");
  });

  it("the chevron collapses and expands — the scenes hide, the header stays", async () => {
    const props = await renderExplorer();
    const chevron = screen.getByRole("button", { name: "Kapitel 1 einklappen" });
    fireEvent.click(chevron);
    expect(props.onToggleChapter).toHaveBeenCalledWith("c1");
    cleanup();
    await renderExplorer({ collapsed: new Set(["c1"]) });
    expect(screen.queryByText("Szene 1 · An Bord der Vanguard")).toBeNull();
    expect(screen.getByText("Kapitel 1 — Ghost in the Machine")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Kapitel 1 ausklappen" })).toBeTruthy();
  });

  it("untitled chapters and scenes read the localized placeholder", async () => {
    const chapters = [{ ...CH1, title: "" }];
    const scenes = [{ ...S11, title: "  " }];
    await renderExplorer({
      chapters,
      sceneResults: [queryOf(scenes)],
      entries: orderedSceneEntries(chapters, new Map([["c1", scenes]])),
    });
    const tree = screen.getByTestId("explorer-tree");
    expect(within(tree).getByText(/Unbenanntes Kapitel/)).toBeTruthy();
    expect(within(tree).getByText(/Unbenannte Szene/)).toBeTruthy();
  });

  it("an empty chapter says so — D16's real state, no invented scene", async () => {
    const chapters = [CH1, { ...CH2, scene_count: 0, word_count: 0 }];
    await renderExplorer({
      chapters,
      sceneResults: [queryOf([S11, S12]), queryOf([])],
      entries: orderedSceneEntries(chapters, new Map([["c1", [S11, S12]]])),
    });
    expect(screen.getByText(de["writing.workspace.tree.emptyChapter"])).toBeTruthy();
  });

  it("a chapter whose scenes are still loading placeholders them — no false empty", async () => {
    await renderExplorer({ sceneResults: [queryOf<Scene[]>(undefined, "pending"), queryOf([S21])] });
    expect(screen.queryByText(de["writing.workspace.tree.emptyChapter"])).toBeNull();
  });

  it("long titles truncate with the full title in the tooltip (Kachel 5)", async () => {
    const long = "Die unterirdischen Frequenz-Archive von Svalbard und der unvollendete Bericht";
    const chapters = [{ ...CH1, title: long }];
    await renderExplorer({
      chapters,
      sceneResults: [queryOf([S11])],
      entries: orderedSceneEntries(chapters, new Map([["c1", [S11]]])),
    });
    const header = screen.getByText(`Kapitel 1 — ${long}`);
    expect(header.className).toContain("truncate");
    expect(header.getAttribute("title")).toBe(`Kapitel 1 — ${long}`);
  });

  it("the create doors stay disabled until Task 13 wires the CRUD", async () => {
    await renderExplorer();
    for (const name of [de["writing.workspace.tree.newChapter"], de["writing.workspace.tree.newScene"]]) {
      const button = screen.getByRole("button", { name });
      expect(button.hasAttribute("disabled")).toBe(true);
      expect(button.getAttribute("title")).toBe(de["writing.workspace.crudNote"]);
    }
  });
});

describe("the empty book (Kachel 3)", () => {
  it("the invitation replaces the tree — the create door disabled until Task 13", async () => {
    await renderExplorer({ chapters: [], sceneResults: [], entries: [], activeSceneId: null, activeChapterId: null });
    const invitation = screen.getByTestId("explorer-empty-book");
    expect(within(invitation).getByText(de["writing.workspace.emptyBook.eyebrow"])).toBeTruthy();
    expect(within(invitation).getByText(de["writing.workspace.emptyBook.title"])).toBeTruthy();
    expect(within(invitation).getByText(de["writing.workspace.emptyBook.body"])).toBeTruthy();
    const button = within(invitation).getByRole("button", { name: de["writing.workspace.emptyBook.action"] });
    expect(button.hasAttribute("disabled")).toBe(true);
    expect(screen.queryByTestId("explorer-tree")).toBeNull();
  });
});

describe("the shelf mini-card", () => {
  it("links back to the shelf with the cover chip and the drafted lines", async () => {
    await renderExplorer();
    const link = screen.getByRole("link", { name: /Zurück zum Bücherregal/ });
    expect(link.getAttribute("href")).toBe("/");
    expect(screen.getByText(de["writing.workspace.mini.sub"])).toBeTruthy();
  });
});
