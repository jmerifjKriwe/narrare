// @vitest-environment jsdom
/**
 * The explorer column (W4 Tasks 11/13): the scene-centric draft's 280px
 * left column — the identity card (real cover chip, title, genre), the
 * REAL daily ring (the activity aggregate's goal fields, the shelf
 * banner's own source), the tension card (real stage label from the
 * storyboard, placeholder curve #879, real scene codes), the scene tree
 * (position order, tabular word counts, the last-edited active marker,
 * neutral status dots #873) and the shelf mini-card. The empty-book
 * invitation answers per Kachel 3.
 *
 * Task 13 went live: the create doors (chapter, scene, the invitation),
 * the row menus (the shelf quick menu's discipline — edit/rename, delete),
 * the draft's drag grips at BOTH levels (scene rows as drawn; the chapter
 * header carries the same grip one level up) with the keyboard's one-step
 * move on the focused grip, and the honest notice under the tree (create
 * refusal, reorder refusal, the 409 conflict). The tree itself still
 * writes nothing — every action asks the page through a callback.
 */
import { cleanup, createEvent, fireEvent, render, screen, within } from "@testing-library/react";
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

/** The props' callbacks are vi.fn()s — the harness types them as the
 *  component's function props; the mock surface reads through the cast. */
function mock(fn: unknown): ReturnType<typeof vi.fn> {
  return fn as ReturnType<typeof vi.fn>;
}

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
    onCreateChapter: vi.fn(),
    onCreateScene: vi.fn(),
    onEditChapter: vi.fn(),
    onEditScene: vi.fn(),
    onDeleteChapter: vi.fn(),
    onDeleteScene: vi.fn(),
    onReorderChapters: vi.fn(),
    onReorderScenes: vi.fn(),
    reorderBusy: false,
    createBusy: false,
    notice: null,
    onNoticeRetry: vi.fn(),
    onNoticeDismiss: vi.fn(),
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

  it("many chapters scroll — every chapter stands, the count presentation holds (Kachel 6)", async () => {
    // Twelve chapters, three scenes each — the state tile's dense scale.
    const chapters = Array.from({ length: 12 }, (_, at) => ({
      ...CH1,
      id: `c${at + 1}`,
      position: at,
      title: `Kapitel ${at + 1} Titel`,
      scene_count: 3,
      word_count: 100,
    }));
    const scenesByChapter = new Map(
      chapters.map((chapter) => [
        chapter.id,
        Array.from({ length: 3 }, (_, at) => ({
          ...S11,
          id: `${chapter.id}-s${at + 1}`,
          chapter_id: chapter.id,
          position: at + 1,
          word_count: 33,
          title: `Titel ${chapter.id}-s${at + 1}`,
        })),
      ]),
    );
    await renderExplorer({
      novel: novelRow({ chapter_count: 12, word_count: 1200 }),
      chapters,
      sceneResults: chapters.map((chapter) => queryOf(scenesByChapter.get(chapter.id) ?? [])),
      entries: orderedSceneEntries(chapters, scenesByChapter),
      activeSceneId: "c9-s2",
      activeChapterId: "c9",
    });
    // The explorer body is the scroll container — the tree grows inside it.
    const body = screen.getByTestId("explorer-body");
    expect(body.className).toContain("overflow-y-auto");
    // Every chapter and every scene stands; the total is the rows' own Σ.
    expect(screen.getAllByText(/^Kapitel \d+ — Kapitel \d+ Titel$/)).toHaveLength(12);
    expect(screen.getAllByText(/^Szene \d · /)).toHaveLength(36);
    expect(screen.getByText("Gesamt: 1.200 W.")).toBeTruthy();
    // The active marker survives the density — chapter 9's second scene.
    expect(
      screen.getByRole("button", { name: /Szene 2 · Titel c9-s2/ }).getAttribute("aria-current"),
    ).toBe("true");
  });

  it("the create doors are live — the chapter door asks the page, the scene door names the active chapter", async () => {
    const props = await renderExplorer();
    const chapterDoor = screen.getByRole("button", { name: de["writing.workspace.tree.newChapter"] });
    expect(chapterDoor.hasAttribute("disabled")).toBe(false);
    fireEvent.click(chapterDoor);
    expect(props.onCreateChapter).toHaveBeenCalledTimes(1);
    const sceneDoor = screen.getByRole("button", { name: de["writing.workspace.tree.newScene"] });
    expect(sceneDoor.hasAttribute("disabled")).toBe(false);
    fireEvent.click(sceneDoor);
    // The active chapter is c1 (the active scene's own).
    expect(props.onCreateScene).toHaveBeenCalledWith("c1");
  });

  it("a busy create holds both doors — no double chapter from a double click", async () => {
    await renderExplorer({ createBusy: true });
    for (const name of [de["writing.workspace.tree.newChapter"], de["writing.workspace.tree.newScene"]]) {
      expect(screen.getByRole("button", { name }).hasAttribute("disabled")).toBe(true);
    }
  });
});

describe("the row menus — the shelf quick menu's discipline on the tree", () => {
  it("every chapter and scene carries its options trigger", async () => {
    await renderExplorer();
    expect(screen.getAllByRole("button", { name: de["writing.workspace.tree.chapterOptions"] })).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: de["writing.workspace.tree.sceneOptions"] })).toHaveLength(3);
  });

  it("the chapter menu hands the row to the page's rename and delete dialogs", async () => {
    const props = await renderExplorer();
    fireEvent.click(screen.getAllByRole("button", { name: de["writing.workspace.tree.chapterOptions"] })[1]);
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.tree.rename"] }));
    expect(props.onEditChapter).toHaveBeenCalledTimes(1);
    expect(mock(props.onEditChapter).mock.calls[0][0]).toMatchObject({ id: "c2" });
    expect(typeof mock(props.onEditChapter).mock.calls[0][1]).toBe("string");
    fireEvent.click(screen.getAllByRole("button", { name: de["writing.workspace.tree.chapterOptions"] })[1]);
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.tree.delete"] }));
    expect(props.onDeleteChapter).toHaveBeenCalledTimes(1);
    expect(mock(props.onDeleteChapter).mock.calls[0][0]).toMatchObject({ id: "c2" });
  });

  it("the scene menu hands the entry to the page's edit and delete dialogs", async () => {
    const props = await renderExplorer();
    fireEvent.click(screen.getAllByRole("button", { name: de["writing.workspace.tree.sceneOptions"] })[0]);
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.tree.editScene"] }));
    expect(props.onEditScene).toHaveBeenCalledTimes(1);
    expect(mock(props.onEditScene).mock.calls[0][0]).toMatchObject({ scene: { id: "s11" }, chapter: { id: "c1" } });
    fireEvent.click(screen.getAllByRole("button", { name: de["writing.workspace.tree.sceneOptions"] })[0]);
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.tree.delete"] }));
    expect(props.onDeleteScene).toHaveBeenCalledTimes(1);
    expect(mock(props.onDeleteScene).mock.calls[0][0]).toMatchObject({ scene: { id: "s11" } });
  });
});

describe("the reorder grips — the draft's handles, real at both levels", () => {
  function dataTransfer() {
    return { setData: vi.fn(), getData: vi.fn(), effectAllowed: "", dropEffect: "" };
  }

  // jsdom has no DragEvent constructor — the fallback Event drops clientY,
  // so the midpoint's coordinate is defined on the event explicitly.
  function dragOverAt(target: HTMLElement, clientY: number) {
    const event = createEvent.dragOver(target, { dataTransfer: dataTransfer() });
    Object.defineProperty(event, "clientY", { value: clientY });
    fireEvent(target, event);
  }

  it("scene rows carry the draft's grip, chapter headers the same one level up", async () => {
    await renderExplorer();
    const sceneGrip = screen.getByRole("button", { name: "Szene 1 in Kapitel 1 verschieben" });
    expect(sceneGrip.getAttribute("draggable")).toBe("true");
    expect(sceneGrip.getAttribute("title")).toBe(de["writing.workspace.tree.moveHint"]);
    expect(screen.getByRole("button", { name: "Szene 2 in Kapitel 1 verschieben" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Kapitel 1 verschieben" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Kapitel 2 verschieben" })).toBeTruthy();
  });

  it("a scene drag asks the whole chapter order — the permutation, nothing less", async () => {
    const props = await renderExplorer();
    const grip = screen.getByRole("button", { name: "Szene 1 in Kapitel 1 verschieben" });
    const target = screen.getByTestId("tree-scene-s12");
    fireEvent.dragStart(grip, { dataTransfer: dataTransfer() });
    dragOverAt(target, 1);
    fireEvent.drop(target, { dataTransfer: dataTransfer() });
    expect(props.onReorderScenes).toHaveBeenCalledWith("c1", ["s12", "s11"]);
    expect(props.onReorderChapters).not.toHaveBeenCalled();
  });

  it("a drop above the target's midpoint inserts before it", async () => {
    // Three scenes: drag the third onto the first's top half — it leads.
    const scenes = [S11, S12, { ...S11, id: "s13", position: 3, title: "Dritte" }];
    const props = await renderExplorer({
      sceneResults: [queryOf(scenes), queryOf([S21])],
      entries: orderedSceneEntries(CHAPTERS, new Map([["c1", scenes], ["c2", [S21]]])),
    });
    const grip = screen.getByRole("button", { name: "Szene 3 in Kapitel 1 verschieben" });
    const target = screen.getByTestId("tree-scene-s11");
    fireEvent.dragStart(grip, { dataTransfer: dataTransfer() });
    dragOverAt(target, -1);
    fireEvent.drop(target, { dataTransfer: dataTransfer() });
    expect(props.onReorderScenes).toHaveBeenCalledWith("c1", ["s13", "s11", "s12"]);
  });

  it("a chapter drag asks the whole rail order", async () => {
    const props = await renderExplorer();
    const grip = screen.getByRole("button", { name: "Kapitel 1 verschieben" });
    const target = screen.getByTestId("tree-chapter-c2");
    fireEvent.dragStart(grip, { dataTransfer: dataTransfer() });
    dragOverAt(target, 1);
    fireEvent.drop(target, { dataTransfer: dataTransfer() });
    expect(props.onReorderChapters).toHaveBeenCalledWith(["c2", "c1"]);
  });

  it("a scene never crosses its chapter — the move is within-chapter (spec §12)", async () => {
    const props = await renderExplorer();
    const grip = screen.getByRole("button", { name: "Szene 1 in Kapitel 1 verschieben" });
    const foreign = screen.getByTestId("tree-scene-s21");
    fireEvent.dragStart(grip, { dataTransfer: dataTransfer() });
    dragOverAt(foreign, 1);
    fireEvent.drop(foreign, { dataTransfer: dataTransfer() });
    expect(props.onReorderScenes).not.toHaveBeenCalled();
  });

  it("a drop on the dragged row itself asks nothing", async () => {
    const props = await renderExplorer();
    const grip = screen.getByRole("button", { name: "Szene 1 in Kapitel 1 verschieben" });
    const self = screen.getByTestId("tree-scene-s11");
    fireEvent.dragStart(grip, { dataTransfer: dataTransfer() });
    dragOverAt(self, 1);
    fireEvent.drop(self, { dataTransfer: dataTransfer() });
    expect(props.onReorderScenes).not.toHaveBeenCalled();
  });

  it("the focused grip moves one step with the arrow keys — the keyboard's own drag", async () => {
    const props = await renderExplorer();
    fireEvent.keyDown(screen.getByRole("button", { name: "Szene 1 in Kapitel 1 verschieben" }), { key: "ArrowDown" });
    expect(props.onReorderScenes).toHaveBeenCalledWith("c1", ["s12", "s11"]);
    fireEvent.keyDown(screen.getByRole("button", { name: "Kapitel 2 verschieben" }), { key: "ArrowUp" });
    expect(props.onReorderChapters).toHaveBeenCalledWith(["c2", "c1"]);
  });

  it("the ends hold — no step beyond the first or last row", async () => {
    const props = await renderExplorer();
    fireEvent.keyDown(screen.getByRole("button", { name: "Szene 1 in Kapitel 1 verschieben" }), { key: "ArrowUp" });
    fireEvent.keyDown(screen.getByRole("button", { name: "Kapitel 1 verschieben" }), { key: "ArrowUp" });
    expect(props.onReorderScenes).not.toHaveBeenCalled();
    expect(props.onReorderChapters).not.toHaveBeenCalled();
  });

  it("a busy reorder holds the grips — one arrangement on the wire at a time", async () => {
    const props = await renderExplorer({ reorderBusy: true });
    fireEvent.keyDown(screen.getByRole("button", { name: "Szene 1 in Kapitel 1 verschieben" }), { key: "ArrowDown" });
    expect(props.onReorderScenes).not.toHaveBeenCalled();
    const grip = screen.getByRole("button", { name: "Szene 1 in Kapitel 1 verschieben" });
    const target = screen.getByTestId("tree-scene-s12");
    fireEvent.dragStart(grip, { dataTransfer: dataTransfer() });
    dragOverAt(target, 1);
    fireEvent.drop(target, { dataTransfer: dataTransfer() });
    expect(props.onReorderScenes).not.toHaveBeenCalled();
  });
});

describe("the notice under the tree — the honest refusal, the retry", () => {
  it("a create refusal names the loss-free error and retries the very create", async () => {
    const props = await renderExplorer({ notice: { kind: "createChapterFailed" } });
    const notice = screen.getByTestId("explorer-notice");
    expect(notice.getAttribute("role")).toBe("alert");
    expect(within(notice).getByText(de["writing.workspace.crud.createChapterError"])).toBeTruthy();
    fireEvent.click(within(notice).getByRole("button", { name: de["writing.shelf.error.retry"] }));
    expect(props.onNoticeRetry).toHaveBeenCalledTimes(1);
    fireEvent.click(within(notice).getByRole("button", { name: de["writing.workspace.crud.noticeClose"] }));
    expect(props.onNoticeDismiss).toHaveBeenCalledTimes(1);
  });

  it("the reorder conflict speaks the current truth, the refusal the loss-free line", async () => {
    await renderExplorer({ notice: { kind: "reorderConflict" } });
    expect(screen.getByText(de["writing.workspace.crud.reorderConflict"])).toBeTruthy();
    cleanup();
    await renderExplorer({
      notice: { kind: "reorderFailed", level: "scenes", chapterId: "c1", ids: ["s12", "s11"] },
    });
    expect(screen.getByText(de["writing.workspace.crud.reorderError"])).toBeTruthy();
  });
});

describe("the empty book (Kachel 3)", () => {
  it("the invitation replaces the tree — its create door live, the first chapter's door", async () => {
    const props = await renderExplorer({ chapters: [], sceneResults: [], entries: [], activeSceneId: null, activeChapterId: null });
    const invitation = screen.getByTestId("explorer-empty-book");
    expect(within(invitation).getByText(de["writing.workspace.emptyBook.eyebrow"])).toBeTruthy();
    expect(within(invitation).getByText(de["writing.workspace.emptyBook.title"])).toBeTruthy();
    expect(within(invitation).getByText(de["writing.workspace.emptyBook.body"])).toBeTruthy();
    const button = within(invitation).getByRole("button", { name: de["writing.workspace.emptyBook.action"] });
    expect(button.hasAttribute("disabled")).toBe(false);
    fireEvent.click(button);
    expect(props.onCreateChapter).toHaveBeenCalledTimes(1);
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
