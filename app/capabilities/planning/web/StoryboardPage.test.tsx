// @vitest-environment jsdom
/**
 * The storyboard page (W6 Task 4) — the planning capability's second web
 * surface, ported from the owner-approved harmonized
 * `three-act-storyboard-2` draft onto the shell's tokens, driven through
 * the real API seam (the client mocked at its module boundary, the house
 * pattern). The novel's real StoryboardRead stages the chapters: the
 * structure switcher over the five real ids (three-act the default every
 * unremapped novel reads), the chapter cards carrying only real fields
 * (word count, sync status, the fan's scene count), the stage assignment
 * PUT, the remap preview/confirm round-trip with the unknown-id refusal
 * face, and the honest empty state with the switcher and the sibling
 * doors standing (W5 #923's rule). The scene drill-in lives beside the
 * board and is driven through the page: its aggregate save and the
 * stale-version conflict face are pinned here too, because they are the
 * page's own writes (Review Focus 1). The face speaks du-tone in all
 * three catalogs.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import { client, type Chapter, type Novel, type Storyboard } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { structures } from "@shell/lib/generated/structures";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";

import { StoryboardPage } from "./StoryboardPage";

const de = catalogs.de;
const api = client as unknown as Record<"GET" | "POST" | "PUT" | "DELETE", ReturnType<typeof vi.fn>>;

/** A literal string as a regex — the structure labels carry parentheses a
 *  plain `new RegExp` would read as groups. */
function literal(text: string): RegExp {
  return new RegExp(text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
}

configure({ asyncUtilTimeout: 5000 });

const NOVEL_ID = "11111111-1111-1111-1111-111111111111";
const STORYBOARD_PATH = "/novels/$novelId/planning/storyboard";
const TIMELINE_PATH = "/novels/$novelId/planning/timeline";
const CAUSALITY_PATH = "/novels/$novelId/planning/causality";
const WORKSPACE_PATH = "/novels/$novelId";

function ok(status = 200): Response {
  return new Response(null, { status });
}

// The generated registry is the only list: the test derives its ids from
// the same import the switcher reads (#929), so a structure added or
// retired server-side moves every copy at once.
type StructureId = (typeof structures)[number]["id"];
const STRUCTURE_IDS: StructureId[] = structures.map((structure) => structure.id);

/** The registry's stage keys per structure — the column order the server
 *  answers, mirrored for building fixtures. */
const STAGE_KEYS: Record<StructureId, string[]> = {
  "three-act": ["setup", "confrontation", "resolution"],
  "heros-journey": [
    "ordinary-world", "call-to-adventure", "refusal", "mentor", "threshold",
    "tests-allies-enemies", "approach", "ordeal", "reward", "road-back",
    "resurrection", "return",
  ],
  "save-the-cat": [
    "opening-image", "theme-stated", "set-up", "catalyst", "debate",
    "break-into-two", "b-story", "fun-and-games", "midpoint",
    "bad-guys-close-in", "all-is-lost", "dark-night-of-the-soul",
    "break-into-three", "finale", "final-image",
  ],
  "five-act": ["exposition", "rising-action", "climax", "falling-action", "resolution"],
  "seven-point": ["hook", "plot-turn-1", "pinch-point-1", "midpoint", "pinch-point-2", "plot-turn-2", "resolution"],
};

function chapterRow(overrides: Partial<Chapter> & { id: string }): Chapter {
  return {
    novel_id: NOVEL_ID,
    title: "Ankunft",
    position: 0,
    word_count: 0,
    created_at: "2026-11-19T10:00:00Z",
    updated_at: "2026-11-19T10:00:00Z",
    scene_count: 0,
    target_words: null,
    ...overrides,
  };
}

const CH1 = chapterRow({ id: "c1", title: "Ankunft auf Horizon Station", position: 0, word_count: 5840 });
const CH2 = chapterRow({ id: "c2", title: "Das Signal im Permafrost", position: 1, word_count: 6120 });
const CH3 = chapterRow({ id: "c3", title: "Konfrontation am Relais", position: 2, word_count: 6300 });
const CHAPTERS = [CH1, CH2, CH3];

const NOVEL: Novel = {
  id: NOVEL_ID,
  title: "Dead Signal",
  author: null,
  blurb: null,
  genre: null,
  language: null,
  created_at: "2026-11-19T09:00:00Z",
  updated_at: "2026-11-19T10:00:00Z",
  word_count: 18260,
  target_words: 65000,
} as unknown as Novel;

type BoardChapter = NonNullable<Storyboard["stages"][number]["chapters"]>[number];

function boardChapter(overrides: Partial<BoardChapter> & { chapter_id: string }): BoardChapter {
  return {
    title: "Ankunft auf Horizon Station",
    position: 0,
    word_count: 5840,
    sync_status: "on_track",
    assignment_source: "suggested",
    stage_key: "setup",
    ...overrides,
  };
}

/** The board's chapter rows — rebuilt before every test: the stage-PUT
 *  mock writes its answer into them, and one test's write must not move
 *  the next test's fixture. */
function freshBoardChapters(): Record<string, BoardChapter> {
  return {
    c1: boardChapter({ chapter_id: "c1", position: 0, word_count: 5840, stage_key: "setup", sync_status: "on_track" }),
    c2: boardChapter({
      chapter_id: "c2",
      title: "Das Signal im Permafrost",
      position: 1,
      word_count: 6120,
      stage_key: "confrontation",
      sync_status: "deviated",
      assignment_source: "assigned",
    }),
    c3: boardChapter({
      chapter_id: "c3",
      title: "Konfrontation am Relais",
      position: 2,
      word_count: 6300,
      stage_key: "resolution",
      sync_status: "planned",
    }),
  };
}

let BOARD_CHAPTERS: Record<string, BoardChapter> = freshBoardChapters();

/** The real interval tiles per structure — three-act is the registry's own
 *  hand-set 25/50/25 split, the rest tile evenly (the backend's own rule). */
const STAGE_RATIOS: Record<StructureId, Array<[number, number]>> = {
  "three-act": [
    [0.0, 0.25],
    [0.25, 0.75],
    [0.75, 1.0],
  ],
  "heros-journey": Array.from({ length: 12 }, (_, index) => [index / 12, (index + 1) / 12] as [number, number]),
  "save-the-cat": Array.from({ length: 15 }, (_, index) => [index / 15, (index + 1) / 15] as [number, number]),
  "five-act": Array.from({ length: 5 }, (_, index) => [index / 5, (index + 1) / 5] as [number, number]),
  "seven-point": Array.from({ length: 7 }, (_, index) => [index / 7, (index + 1) / 7] as [number, number]),
};

/** The storyboard answer under one structure: every chapter standing in
 *  the column its stage_key names, the stage defs tiling [0,1]. */
function storyboardRow(structureId: StructureId, overrides: Partial<Storyboard> = {}): Storyboard {
  const keys = STAGE_KEYS[structureId];
  const ratios = STAGE_RATIOS[structureId];
  const chapters = Object.values(BOARD_CHAPTERS);
  return {
    novel_id: NOVEL_ID,
    structure_id: structureId,
    stages: keys.map((key, index) => ({
      key,
      title_key: `storyboard.stage.${key}`,
      from: ratios[index][0],
      to: ratios[index][1],
      chapters: chapters.filter((chapter) => chapter.stage_key === key),
    })),
    ...overrides,
  } as Storyboard;
}

function sceneAggregate(chapterId: string, version = "2026-11-19T10:00:00Z") {
  return {
    chapter_id: chapterId,
    version_updated_at: version,
    scenes:
      chapterId === "c2"
        ? [
            {
              id: "s-2-1",
              chapter_id: chapterId,
              position: 1,
              title: "Kalibrierung der Messsonde",
              purpose: "Mayas Arbeitsroutine etablieren.",
              conflict: "Die Sensoren empfangen unbekannte Rauschmuster.",
              resolution: "Maya schaltet die Filter manuell aus.",
              beats: ["Sonde schlägt bei 14.2 Hz aus", "Erste manuelle Filterumgehung"],
              status: "complete",
              created_at: "2026-11-19T10:00:00Z",
              updated_at: "2026-11-19T10:00:00Z",
            },
            {
              id: "s-2-2",
              chapter_id: chapterId,
              position: 2,
              title: "ARIA meldet Modulation",
              purpose: "Das Signal als Botschaft offenbaren.",
              conflict: "Die Bord-KI verlangt die Sperrung der Frequenz.",
              resolution: "Maya überschreibt ARIA.",
              beats: ["Warnmeldung der KI"],
              status: "in_progress",
              created_at: "2026-11-19T10:00:00Z",
              updated_at: "2026-11-19T10:00:00Z",
            },
          ]
        : [
            {
              id: `s-${chapterId}-1`,
              chapter_id: chapterId,
              position: 1,
              title: "Erste Szene",
              purpose: "",
              conflict: "",
              resolution: "",
              beats: [],
              status: "planned",
              created_at: "2026-11-19T10:00:00Z",
              updated_at: "2026-11-19T10:00:00Z",
            },
          ],
  };
}

const AGGREGATES = new Map([
  ["c1", sceneAggregate("c1")],
  ["c2", sceneAggregate("c2")],
  ["c3", sceneAggregate("c3")],
]);

// The mutable scenario: the standing structure the storyboard answers
// with, the remap answers, and the outage toggles.
let structure: StructureId;
let storyboardFail: boolean;
let chaptersFail: boolean;
let scenesFail: boolean;
let novelFail: boolean;
let sceneVersion: string;
let remapStatus: number;
let remapDetail: unknown;
let remapForeignEntry: boolean;
let scenesPutFail: boolean;
let scenesPutHang: boolean;
/** The next scenes GET answers; every one after it hangs forever — the
 *  pin for "the fan entry holds the rows without a refetch": whatever
 *  the dock shows after the hung refetch began can only come from the
 *  cache itself. */
let scenesHangAfterNext: boolean;
let scenesHangServed: boolean;

function baseGet(path: string, init?: { params?: { path?: { chapter_id?: string } } }): Promise<{ data: unknown; response: Response }> {
  if (storyboardFail && path === "/api/planning/novels/{novel_id}/storyboard") {
    return Promise.resolve({ data: undefined, response: ok(503) });
  }
  if (path === "/api/planning/novels/{novel_id}/storyboard") {
    return Promise.resolve({ data: storyboardRow(structure), response: ok() });
  }
  if (path === "/api/writing/novels/{novel_id}") {
    if (novelFail) return Promise.resolve({ data: undefined, response: ok(503) });
    return Promise.resolve({ data: NOVEL, response: ok() });
  }
  if (chaptersFail && path === "/api/writing/novels/{novel_id}/chapters") {
    return Promise.resolve({ data: undefined, response: ok(503) });
  }
  if (path === "/api/writing/novels/{novel_id}/chapters") {
    return Promise.resolve({ data: CHAPTERS, response: ok() });
  }
  if (path === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes") {
    if (scenesFail) return Promise.resolve({ data: undefined, response: ok(503) });
    if (scenesHangAfterNext) {
      if (scenesHangServed) return new Promise(() => {});
      scenesHangServed = true;
    }
    const chapterId = init?.params?.path?.chapter_id ?? "";
    const aggregate = AGGREGATES.get(chapterId);
    if (aggregate === undefined) return Promise.resolve({ data: undefined, response: ok(404) });
    return Promise.resolve({
      data: { ...aggregate, version_updated_at: sceneVersion },
      response: ok(),
    });
  }
  throw new Error(`unexpected GET: ${path}`);
}

/** The remap answer: every chapter moving from its current effective stage
 *  to the target structure's even suggestion (the fixtures' positions are
 *  0, 1, 2 of a three-chapter novel, so the ratio thirds decide). */
function remapAnswer(target: string, confirm: boolean) {
  const keys = STAGE_KEYS[target as StructureId];
  const chapters = Object.values(BOARD_CHAPTERS);
  const mapping = chapters.map((chapter) => ({
    chapter_id: chapter.chapter_id,
    from_stage: chapter.stage_key,
    to_stage: keys[Math.min(keys.length - 1, Math.floor((chapter.position / 2) * keys.length))],
  }));
  if (remapForeignEntry) {
    // A row whose chapter no board list resolves — the dialog must omit
    // its number, never invent one.
    mapping.push({ chapter_id: "c-gone", from_stage: "setup", to_stage: "finale" });
  }
  return {
    novel_id: NOVEL_ID,
    structure_id: target,
    confirmed: confirm,
    mapping,
  };
}

/** The page on a harness route whose id is the real storyboard path, beside
 *  stubs the sibling doors and the workspace door navigate to. */
const harnessRoot = createRootRoute({ component: () => <Outlet /> });

async function renderStoryboard(entry = `/novels/${NOVEL_ID}/planning/storyboard`) {
  const storyboard = createRoute({
    getParentRoute: () => harnessRoot,
    path: STORYBOARD_PATH,
    component: StoryboardPage,
  });
  const timeline = createRoute({
    getParentRoute: () => harnessRoot,
    path: TIMELINE_PATH,
    component: () => <p>timeline face</p>,
  });
  const causality = createRoute({
    getParentRoute: () => harnessRoot,
    path: CAUSALITY_PATH,
    component: () => <p>causality face</p>,
  });
  const workspace = createRoute({
    getParentRoute: () => harnessRoot,
    path: WORKSPACE_PATH,
    component: () => <p>workspace face</p>,
  });
  const router = createRouter({
    routeTree: harnessRoot.addChildren([storyboard, timeline, causality, workspace]),
    history: createMemoryHistory({ initialEntries: [entry] }),
  });
  await router.load();
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

/** The sibling doors — they must stand in every state (W5 #923). */
function expectSiblingDoors() {
  const timelineDoor = screen.getByTestId("storyboard-timeline-door");
  expect(within(timelineDoor).getByText(de["planning.timeline.title"])).toBeTruthy();
  const causalityDoor = screen.getByTestId("storyboard-causality-door");
  expect(within(causalityDoor).getByText(de["planning.sub.causality"])).toBeTruthy();
  expect(screen.getByText(de["planning.storyboard.title"])).toBeTruthy();
}

beforeEach(() => {
  applyLocale("de");
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
  structure = "three-act";
  storyboardFail = false;
  chaptersFail = false;
  scenesFail = false;
  novelFail = false;
  sceneVersion = "2026-11-19T10:00:00Z";
  remapStatus = 0;
  remapDetail = undefined;
  remapForeignEntry = false;
  scenesPutFail = false;
  scenesPutHang = false;
  scenesHangAfterNext = false;
  scenesHangServed = false;
  BOARD_CHAPTERS = freshBoardChapters();
  // Chapter 2's aggregate, fresh before every test: the conflict pins
  // move its rows and its stamp, and one test's move must not leak into
  // the next test's fixture.
  AGGREGATES.set("c2", sceneAggregate("c2"));
  api.GET.mockImplementation(baseGet);
  api.POST.mockImplementation((_path: string, init?: { body?: { structure_id?: string; confirm?: boolean } }) => {
    if (_path === "/api/planning/novels/{novel_id}/remap") {
      if (remapStatus !== 0) {
        return Promise.resolve({ data: { detail: remapDetail }, response: ok(remapStatus) });
      }
      const target = init?.body?.structure_id ?? "three-act";
      const confirm = init?.body?.confirm ?? false;
      if (confirm) structure = target as StructureId;
      return Promise.resolve({ data: remapAnswer(target, confirm), response: ok() });
    }
    throw new Error(`unexpected POST: ${_path}`);
  });
  api.PUT.mockImplementation((_path: string, init?: { params?: { path?: { chapter_id?: string } }; body?: { stage_key?: string } }) => {
    if (_path === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/stage") {
      const chapterId = init?.params?.path?.chapter_id ?? "c1";
      const stageKey = init?.body?.stage_key ?? "resolution";
      BOARD_CHAPTERS[chapterId] = { ...BOARD_CHAPTERS[chapterId], stage_key: stageKey, assignment_source: "assigned" };
      return Promise.resolve({ data: BOARD_CHAPTERS[chapterId], response: ok() });
    }
    if (_path === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes") {
      if (scenesPutHang) return new Promise(() => {});
      if (scenesPutFail) return Promise.resolve({ data: { detail: "outage" }, response: ok(503) });
      sceneVersion = "2026-11-19T11:00:00Z";
      const chapterId = init?.params?.path?.chapter_id ?? "";
      const body = init?.body as { scenes: { id: string; title: string; purpose: string; conflict: string; resolution: string; beats: string[]; status: string }[] };
      return Promise.resolve({
        data: {
          chapter_id: chapterId,
          version_updated_at: sceneVersion,
          scenes: body.scenes.map((scene, at) => ({
            ...scene,
            chapter_id: chapterId,
            position: at + 1,
            created_at: "2026-11-19T10:00:00Z",
            updated_at: sceneVersion,
          })),
        },
        response: ok(),
      });
    }
    throw new Error(`unexpected PUT: ${_path}`);
  });
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
  applyLocale(null);
});

describe("the board stages the novel's real chapters", () => {
  it("three columns for an unremapped novel — three-act is the default", async () => {
    await renderStoryboard();
    const stages = await screen.findAllByTestId("storyboard-stage");
    expect(stages).toHaveLength(3);
    expect(stages[0].getAttribute("aria-label")).toBe(de["storyboard.stage.setup"]);
    expect(stages[1].getAttribute("aria-label")).toBe(de["storyboard.stage.confrontation"]);
    expect(stages[2].getAttribute("aria-label")).toBe(de["storyboard.stage.resolution"]);
    // The chapters stand where their stage_key names.
    expect(within(stages[0]).getByText("Ankunft auf Horizon Station")).toBeTruthy();
    expect(within(stages[1]).getByText("Das Signal im Permafrost")).toBeTruthy();
    expect(within(stages[2]).getByText("Konfrontation am Relais")).toBeTruthy();
    // The reads carry the novel.
    expect(api.GET.mock.calls.some(([p]) => p === "/api/planning/novels/{novel_id}/storyboard")).toBe(true);
  });

  it("a remapped novel reads its own structure — five columns under five-act", async () => {
    structure = "five-act";
    await renderStoryboard();
    const stages = await screen.findAllByTestId("storyboard-stage");
    expect(stages).toHaveLength(5);
    expect(stages[0].getAttribute("aria-label")).toBe(de["storyboard.stage.exposition"]);
    expect(stages[4].getAttribute("aria-label")).toBe(de["storyboard.stage.resolution"]);
    // The switcher marks the standing structure active.
    const active = screen.getByRole("button", { name: literal(de["storyboard.structure.five-act"]) });
    expect(active.getAttribute("aria-pressed")).toBe("true");
  });

  it("the chapter cards carry only real fields — words, sync, the fan's scene count", async () => {
    await renderStoryboard();
    const cards = await screen.findAllByTestId("storyboard-card");
    expect(cards).toHaveLength(3);
    const signal = cards.find((card) => within(card).queryByText("Das Signal im Permafrost") !== null) as HTMLElement;
    // The real word count, German thousands separator and all.
    expect(within(signal).getByText("6.120 Wörter")).toBeTruthy();
    // The real sync label for a hand-set stage off the suggestion.
    expect(within(signal).getByText(/Abgewichen/)).toBeTruthy();
    expect(within(signal).getByText(/Von Hand/)).toBeTruthy();
    // The scene count from the per-chapter fan.
    expect(within(signal).getByText("2 Szenen")).toBeTruthy();
    // No invented prose excerpt — no field carries it.
    expect(within(signal).queryByText(/Subraum-Array/)).toBeNull();
    // The suggested chapter names its source honestly.
    const ankunft = cards.find((card) => within(card).queryByText("Ankunft auf Horizon Station") !== null) as HTMLElement;
    expect(within(ankunft).getByText(/Vorschlag/)).toBeTruthy();
    expect(within(ankunft).getByText(/Im Plan/)).toBeTruthy();
  });

  it("the stage share chip carries the real ratio and the stage's summed words", async () => {
    await renderStoryboard();
    const stages = await screen.findAllByTestId("storyboard-stage");
    // Akt II: 50 % of the unit interval, c2's 6.120 words standing in it.
    expect(within(stages[1]).getByText("ca. 50 % · 6.120 W.")).toBeTruthy();
  });

  it("the word-total chip reads the novel's real target and totals", async () => {
    await renderStoryboard();
    const chip = await screen.findByText(/18\.260/);
    expect(chip.closest('[data-testid="storyboard-progress"]')).toBeTruthy();
    const progress = screen.getByTestId("storyboard-progress");
    expect(await within(progress).findByText(/65\.000/)).toBeTruthy();
    expect(await within(progress).findByText("28 % erreicht")).toBeTruthy();
    expect(await within(progress).findByText("3 Kapitel")).toBeTruthy();
    expect(await within(progress).findByText("4 Szenen gesamt")).toBeTruthy();
    // The dot beside standing totals is the green „in sync" mark.
    expect((progress.firstElementChild as HTMLElement).className).toContain("bg-success");
  });

  it("a novel without a target names no invented one", async () => {
    cleanup();
    queryClient.clear();
    const NOVEL_NO_TARGET = { ...NOVEL, target_words: null } as Novel;
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/writing/novels/{novel_id}") {
        return Promise.resolve({ data: NOVEL_NO_TARGET, response: ok() });
      }
      return baseGet(path);
    });
    await renderStoryboard();
    const chip = screen.getByTestId("storyboard-progress");
    expect(await within(chip).findByText(/18\.260/)).toBeTruthy();
    await waitFor(() => expect(within(chip).getByText(/Wörter/)).toBeTruthy());
    expect(within(chip).queryByText(/erreicht/)).toBeNull();
    expect(within(chip).queryByText(/65\.000/)).toBeNull();
  });

  it("the scene counts degrade honestly when the fan fails", async () => {
    scenesFail = true;
    await renderStoryboard();
    const cards = await screen.findAllByTestId("storyboard-card");
    for (const card of cards) {
      expect(within(card).getByText(de["planning.storyboard.scenesUnavailable"])).toBeTruthy();
    }
  });
});

describe("the stage assignment PUT", () => {
  it("moves a chapter through the card's stage select and refetches the board", async () => {
    await renderStoryboard();
    const cards = await screen.findAllByTestId("storyboard-card");
    const ankunft = cards.find((card) => within(card).queryByText("Ankunft auf Horizon Station") !== null) as HTMLElement;
    const select = within(ankunft).getByLabelText(de["planning.storyboard.moveLabel"]);
    fireEvent.change(select, { target: { value: "resolution" } });
    await waitFor(() =>
      expect(api.PUT).toHaveBeenCalledWith(
        "/api/planning/novels/{novel_id}/chapters/{chapter_id}/stage",
        { params: { path: { novel_id: NOVEL_ID, chapter_id: "c1" } }, body: { stage_key: "resolution" } },
      ),
    );
    // The board refetches: the card stands in its new column.
    const stages = await screen.findAllByTestId("storyboard-stage");
    await waitFor(() =>
      expect(within(stages[2]).getByText("Ankunft auf Horizon Station")).toBeTruthy(),
    );
  });
});

describe("the structure switcher and the remap", () => {
  it("offers the five real structures with the draft's wording", async () => {
    await renderStoryboard();
    await screen.findAllByTestId("storyboard-card");
    const switcher = screen.getByTestId("storyboard-structure-switcher");
    for (const id of STRUCTURE_IDS) {
      expect(within(switcher).getByText(de[`storyboard.structure.${id}`])).toBeTruthy();
    }
    // Three-act is active; the others are not.
    expect(
      within(switcher).getByRole("button", { name: literal(de["storyboard.structure.three-act"]) }).getAttribute("aria-pressed"),
    ).toBe("true");
    expect(
      within(switcher).getByRole("button", { name: literal(de["storyboard.structure.heros-journey"]) }).getAttribute("aria-pressed"),
    ).toBe("false");
  });

  it("selecting a structure stands the notice; abort clears it without a write", async () => {
    await renderStoryboard();
    await screen.findAllByTestId("storyboard-card");
    fireEvent.click(screen.getByRole("button", { name: literal(de["storyboard.structure.heros-journey"]) }));
    const notice = screen.getByTestId("storyboard-remap-notice");
    expect(within(notice).getByText(/Struktur wechseln & Kapitel remappen/)).toBeTruthy();
    expect(api.POST).not.toHaveBeenCalled();
    fireEvent.click(within(notice).getByRole("button", { name: de["planning.crud.cancel"] }));
    expect(screen.queryByTestId("storyboard-remap-notice")).toBeNull();
  });

  it("the remap previews, then confirms exactly the previewed mapping", async () => {
    await renderStoryboard();
    await screen.findAllByTestId("storyboard-card");
    fireEvent.click(screen.getByRole("button", { name: literal(de["storyboard.structure.five-act"]) }));
    fireEvent.click(within(screen.getByTestId("storyboard-remap-notice")).getByRole("button", { name: de["planning.storyboard.remapApply"] }));

    const dialog = await screen.findByRole("dialog");
    // The preview asked with confirm: false and named the moves (the
    // fixtures' position thirds put chapter 2 on the five-act climax).
    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/planning/novels/{novel_id}/remap",
        { params: { path: { novel_id: NOVEL_ID } }, body: { structure_id: "five-act", confirm: false } },
      ),
    );
    expect(within(dialog).getByText(/Exposition/)).toBeTruthy();
    expect(within(dialog).getByText(/Höhepunkt/)).toBeTruthy();

    fireEvent.click(within(dialog).getByRole("button", { name: de["planning.storyboard.remapConfirm"] }));
    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/planning/novels/{novel_id}/remap",
        { params: { path: { novel_id: NOVEL_ID } }, body: { structure_id: "five-act", confirm: true } },
      ),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    // The board reads the remapped structure, the switcher follows.
    const stages = await screen.findAllByTestId("storyboard-stage");
    expect(stages).toHaveLength(5);
    expect(
      screen.getByRole("button", { name: literal(de["storyboard.structure.five-act"]) }).getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("cancelling after the preview writes nothing — the board stands", async () => {
    await renderStoryboard();
    await screen.findAllByTestId("storyboard-card");
    fireEvent.click(screen.getByRole("button", { name: literal(de["storyboard.structure.five-act"]) }));
    fireEvent.click(within(screen.getByTestId("storyboard-remap-notice")).getByRole("button", { name: de["planning.storyboard.remapApply"] }));
    const dialog = await screen.findByRole("dialog");
    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/planning/novels/{novel_id}/remap",
        { params: { path: { novel_id: NOVEL_ID } }, body: { structure_id: "five-act", confirm: false } },
      ),
    );
    fireEvent.click(within(dialog).getByRole("button", { name: de["planning.crud.cancel"] }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    // No confirm was ever sent; the board reads its own structure still.
    expect(api.POST.mock.calls.some(([, init]) => (init?.body as { confirm?: boolean } | undefined)?.confirm === true)).toBe(false);
    expect(screen.getAllByTestId("storyboard-stage")).toHaveLength(3);
    expect(
      screen.getByRole("button", { name: literal(de["storyboard.structure.three-act"]) }).getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("a mapping row the board cannot name omits the number — never a wrong one", async () => {
    remapForeignEntry = true;
    await renderStoryboard();
    await screen.findAllByTestId("storyboard-card");
    fireEvent.click(screen.getByRole("button", { name: literal(de["storyboard.structure.save-the-cat"]) }));
    fireEvent.click(within(screen.getByTestId("storyboard-remap-notice")).getByRole("button", { name: de["planning.storyboard.remapApply"] }));
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findAllByRole("listitem");
    const rows = within(dialog).getAllByRole("listitem");
    // The foreign chapter's move carries the stages without a number.
    expect(rows.some((row) => !/Kapitel \d/.test(row.textContent ?? ""))).toBe(true);
    // The board's own chapters keep their numbered moves.
    expect(rows.some((row) => /Kapitel 1:/.test(row.textContent ?? ""))).toBe(true);
  });

  it("an unknown structure id surfaces the API's refusal — the switcher never bricks", async () => {
    remapStatus = 422;
    remapDetail = "unknown structure: heros-journey";
    await renderStoryboard();
    await screen.findAllByTestId("storyboard-card");
    fireEvent.click(screen.getByRole("button", { name: literal(de["storyboard.structure.heros-journey"]) }));
    fireEvent.click(within(screen.getByTestId("storyboard-remap-notice")).getByRole("button", { name: de["planning.storyboard.remapApply"] }));

    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText(de["planning.storyboard.remapUnknownStructure"])).toBeTruthy();
    // The switcher still stands with all five doors.
    const switcher = screen.getByTestId("storyboard-structure-switcher");
    for (const id of STRUCTURE_IDS) {
      expect(within(switcher).getByText(de[`storyboard.structure.${id}`])).toBeTruthy();
    }
    fireEvent.click(within(dialog).getByRole("button", { name: de["planning.crud.close"] }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("the honest states", () => {
  it("pending stands the bar and the doors", async () => {
    await renderStoryboard();
    expectSiblingDoors();
    expect(screen.getByText(de["planning.storyboard.loading"])).toBeTruthy();
  });

  it("the outage names itself and retries", async () => {
    storyboardFail = true;
    await renderStoryboard();
    expect(await screen.findByText(de["planning.storyboard.loadFailed"])).toBeTruthy();
    expectSiblingDoors();
    storyboardFail = false;
    fireEvent.click(screen.getByRole("button", { name: de["planning.storyboard.retry"] }));
    await screen.findAllByTestId("storyboard-card");
  });

  it("an empty novel keeps the switcher and the doors, and guides to the workspace", async () => {
    cleanup();
    queryClient.clear();
    const emptyBoard = storyboardRow("three-act");
    emptyBoard.stages = emptyBoard.stages.map((stage) => ({ ...stage, chapters: [] }));
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/planning/novels/{novel_id}/storyboard") {
        return Promise.resolve({ data: emptyBoard, response: ok() });
      }
      if (path === "/api/writing/novels/{novel_id}") {
        return Promise.resolve({ data: { ...NOVEL, word_count: 0, chapter_count: 0 }, response: ok() });
      }
      if (path === "/api/writing/novels/{novel_id}/chapters") {
        return Promise.resolve({ data: [], response: ok() });
      }
      throw new Error(`unexpected GET: ${path}`);
    });
    await renderStoryboard();
    expect(await screen.findByTestId("storyboard-empty")).toBeTruthy();
    expect(screen.getByText(de["planning.storyboard.empty"])).toBeTruthy();
    // The five structures still stand.
    const switcher = screen.getByTestId("storyboard-structure-switcher");
    for (const id of STRUCTURE_IDS) {
      expect(within(switcher).getByText(de[`storyboard.structure.${id}`])).toBeTruthy();
    }
    expectSiblingDoors();
    // The door walks to the workspace — chapter creation lives there.
    const door = screen.getByRole("link", { name: de["planning.storyboard.emptyDoor"] });
    expect(door.getAttribute("href")).toBe(`/novels/${NOVEL_ID}`);
  });
});

describe("the scene drill-in", () => {
  it("selecting a chapter opens the dock with its real scenes", async () => {
    await renderStoryboard();
    const cards = await screen.findAllByTestId("storyboard-card");
    fireEvent.click(within(cards[1]).getByText("Das Signal im Permafrost"));
    const dock = await screen.findByTestId("drill-in");
    expect(within(dock).getByText(de["planning.storyboard.drillInTitle"])).toBeTruthy();
    expect(within(dock).getByText("KAPITEL 2 · 2 SZENEN")).toBeTruthy();
    expect(within(dock).getByText("Das Signal im Permafrost")).toBeTruthy();
    expect(within(dock).getByText("Szene 2.1: Kalibrierung der Messsonde")).toBeTruthy();
    expect(within(dock).getByText(de["planning.sceneStatus.complete"])).toBeTruthy();
    expect(within(dock).getByText("Sonde schlägt bei 14.2 Hz aus")).toBeTruthy();
    // The workspace door stands.
    expect(
      within(dock).getByRole("link", { name: de["planning.storyboard.openWorkspace"] }).getAttribute("href"),
    ).toBe(`/novels/${NOVEL_ID}`);
  });

  it("the dock waits honestly when no chapter stands selected", async () => {
    await renderStoryboard();
    await screen.findAllByTestId("storyboard-card");
    expect(screen.getByText(de["planning.storyboard.drillInNone"])).toBeTruthy();
  });

  it("edits ride the aggregate PUT — fields, beats, status, order", async () => {
    await renderStoryboard();
    const cards = await screen.findAllByTestId("storyboard-card");
    fireEvent.click(within(cards[1]).getByText("Das Signal im Permafrost"));
    const dock = await screen.findByTestId("drill-in");
    const scenes = await within(dock).findAllByTestId("drill-in-scene");
    expect(scenes).toHaveLength(2);

    // Edit the first scene: purpose and a beat.
    fireEvent.click(within(scenes[0]).getByRole("button", { name: de["planning.storyboard.editScene"] }));
    let dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(de["planning.storyboard.purpose"]), {
      target: { value: "Die Isolation des Außenpostens zeigen." },
    });
    const beatsInput = within(dialog).getByLabelText(de["planning.storyboard.beats"]);
    fireEvent.change(beatsInput, { target: { value: "Dritter Beat" } });
    fireEvent.keyDown(beatsInput, { key: "Enter" });
    fireEvent.click(within(dialog).getByRole("button", { name: de["planning.crud.saveChanges"] }));

    // Move the second scene up — the draft reorders without a write.
    fireEvent.click(within(scenes[1]).getByRole("button", { name: de["planning.storyboard.moveUp"] }));
    expect(api.PUT).not.toHaveBeenCalled();

    // The save commits the whole aggregate in its new order.
    fireEvent.click(await within(dock).findByRole("button", { name: de["planning.storyboard.saveAggregate"] }));
    await waitFor(() =>
      expect(api.PUT).toHaveBeenCalledWith(
        "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes",
        expect.objectContaining({
          params: { path: { novel_id: NOVEL_ID, chapter_id: "c2" } },
        }),
      ),
    );
    const call = api.PUT.mock.calls.find(([, init]) => (init as { params?: { path?: { chapter_id?: string } } })?.params?.path?.chapter_id === "c2");
    const body = (call?.[1] as { body: { scenes: { id: string; purpose: string; beats: string[] }[] } }).body;
    expect(body.scenes.map((scene) => scene.id)).toEqual(["s-2-2", "s-2-1"]);
    expect(body.scenes[1].purpose).toBe("Die Isolation des Außenpostens zeigen.");
    expect(body.scenes[1].beats).toContain("Dritter Beat");
  });

  it("an added scene rides the PUT with a minted id; a removed one is absent", async () => {
    await renderStoryboard();
    const cards = await screen.findAllByTestId("storyboard-card");
    fireEvent.click(within(cards[1]).getByText("Das Signal im Permafrost"));
    const dock = await screen.findByTestId("drill-in");
    fireEvent.click(within(dock).getByRole("button", { name: /Szene zu Kapitel 2 hinzufügen/ }));
    let scenes = await within(dock).findAllByTestId("drill-in-scene");
    expect(scenes).toHaveLength(3);
    expect(within(scenes[2]).getByText(/Ohne Titel/)).toBeTruthy();

    // Remove the first scene through its confirm.
    fireEvent.click(within(scenes[0]).getByRole("button", { name: de["planning.storyboard.removeScene"] }));
    const confirm = await screen.findByRole("alertdialog");
    fireEvent.click(within(confirm).getByRole("button", { name: de["planning.storyboard.deleteSceneConfirm"] }));

    fireEvent.click(within(dock).getByRole("button", { name: de["planning.storyboard.saveAggregate"] }));
    await waitFor(() => expect(api.PUT).toHaveBeenCalled());
    const call = api.PUT.mock.calls.find(([, init]) => (init as { params?: { path?: { chapter_id?: string } } })?.params?.path?.chapter_id === "c2");
    const body = (call?.[1] as { body: { scenes: { id: string; title: string }[] } }).body;
    expect(body.scenes).toHaveLength(2);
    expect(body.scenes.map((scene) => scene.id)).not.toContain("s-2-1");
    const added = body.scenes.find((scene) => scene.id !== "s-2-2");
    expect(added).toBeDefined();
    expect(added?.title).toBe("");
  });

  it("the stale version surfaces the conflict face — no silent clobber (Review Focus 1)", async () => {
    await renderStoryboard();
    const cards = await screen.findAllByTestId("storyboard-card");
    fireEvent.click(within(cards[1]).getByText("Das Signal im Permafrost"));
    const dock = await screen.findByTestId("drill-in");
    const scenes = await within(dock).findAllByTestId("drill-in-scene");

    // Dirty the draft through the edit dialog.
    fireEvent.click(within(scenes[0]).getByRole("button", { name: de["planning.storyboard.editScene"] }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(de["planning.storyboard.conflict"]), {
      target: { value: "Ein anderer Konflikt." },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: de["planning.crud.saveChanges"] }));

    // The chapter's stamp moves elsewhere between the load and the save.
    sceneVersion = "2026-11-19T12:00:00Z";
    fireEvent.click(within(dock).getByRole("button", { name: de["planning.storyboard.saveAggregate"] }));

    // The conflict face stands and NO PUT crossed the wire.
    expect(await within(dock).findByTestId("drill-in-conflict")).toBeTruthy();
    expect(
      api.PUT.mock.calls.some(([p, init]) => p === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes"),
    ).toBe(false);

    // „Trotzdem speichern" names the API's last-writer-wins and PUTs.
    fireEvent.click(within(screen.getByTestId("drill-in-conflict")).getByRole("button", { name: de["planning.storyboard.conflictOverwrite"] }));
    await waitFor(() =>
      expect(
        api.PUT.mock.calls.some(([p]) => p === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes"),
      ).toBe(true),
    );
  });

  it("the conflict's fresh load adopts the server's copy and drops the draft", async () => {
    await renderStoryboard();
    const cards = await screen.findAllByTestId("storyboard-card");
    fireEvent.click(within(cards[1]).getByText("Das Signal im Permafrost"));
    const dock = await screen.findByTestId("drill-in");
    const scenes = await within(dock).findAllByTestId("drill-in-scene");
    fireEvent.click(within(scenes[0]).getByRole("button", { name: de["planning.storyboard.editScene"] }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(de["planning.storyboard.purpose"]), {
      target: { value: "Lokale Antwort, die der Server nie sah." },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: de["planning.crud.saveChanges"] }));

    sceneVersion = "2026-11-19T12:00:00Z";
    fireEvent.click(within(dock).getByRole("button", { name: de["planning.storyboard.saveAggregate"] }));
    const conflict = await screen.findByTestId("drill-in-conflict");
    fireEvent.click(within(conflict).getByRole("button", { name: de["planning.storyboard.conflictReload"] }));

    // The draft is gone — the server's copy stands, and no PUT was sent.
    await waitFor(() => expect(screen.queryByTestId("drill-in-conflict")).toBeNull());
    expect(
      api.PUT.mock.calls.some(([p]) => p === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes"),
    ).toBe(false);
    expect(screen.queryByText("Lokale Antwort, die der Server nie sah.")).toBeNull();
  });

  it("the save bar discards the draft without a write", async () => {
    await renderStoryboard();
    const cards = await screen.findAllByTestId("storyboard-card");
    fireEvent.click(within(cards[1]).getByText("Das Signal im Permafrost"));
    const dock = await screen.findByTestId("drill-in");
    const scenes = await within(dock).findAllByTestId("drill-in-scene");
    fireEvent.click(within(scenes[0]).getByRole("button", { name: de["planning.storyboard.editScene"] }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(de["planning.storyboard.purpose"]), {
      target: { value: "Weg damit." },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: de["planning.crud.saveChanges"] }));
    fireEvent.click(within(dock).getByRole("button", { name: de["planning.storyboard.discardAggregate"] }));
    expect(screen.queryByText("Weg damit.")).toBeNull();
    expect(api.PUT).not.toHaveBeenCalled();
  });
});

describe("the sub-nav doors", () => {
  it("walk to the chronology and the causality stub", async () => {
    const router = await renderStoryboard();
    await screen.findAllByTestId("storyboard-card");
    fireEvent.click(within(screen.getByTestId("storyboard-timeline-door")).getByText(de["planning.timeline.title"]));
    await waitFor(() => expect(router.state.location.pathname).toContain("/planning/timeline"));

    await renderStoryboard();
    fireEvent.click(within(screen.getByTestId("storyboard-causality-door")).getByText(de["planning.sub.causality"]));
  });
});

describe("the review fixes", () => {
  /** Chapter 2's copy, dirtied through the edit dialog — the shared
   *  preamble of the guard pins. */
  async function dirtySignalCopy() {
    const cards = await screen.findAllByTestId("storyboard-card");
    fireEvent.click(within(cards[1]).getByText("Das Signal im Permafrost"));
    const dock = await screen.findByTestId("drill-in");
    const scenes = await within(dock).findAllByTestId("drill-in-scene");
    fireEvent.click(within(scenes[0]).getByRole("button", { name: de["planning.storyboard.editScene"] }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(de["planning.storyboard.purpose"]), {
      target: { value: "Wähle mich." },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: de["planning.crud.saveChanges"] }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    return { cards, dock };
  }

  it("a dirty copy survives a guarded switch — cancel keeps it, confirm folds it", async () => {
    await renderStoryboard();
    const { dock } = await dirtySignalCopy();
    expect(within(dock).getByText(/Wähle mich\./)).toBeTruthy();

    // Switching while dirty asks first; the cancel keeps the copy.
    const ankunft = screen.getAllByTestId("storyboard-card").find((card) =>
      within(card).queryByText("Ankunft auf Horizon Station") !== null,
    ) as HTMLElement;
    fireEvent.click(within(ankunft).getByText("Ankunft auf Horizon Station"));
    const guard = await screen.findByRole("alertdialog");
    expect(within(guard).getByText(/Das Signal im Permafrost/)).toBeTruthy();
    fireEvent.click(within(guard).getByRole("button", { name: de["planning.crud.cancel"] }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(within(screen.getByTestId("drill-in")).getByText(/Wähle mich\./)).toBeTruthy();
    expect(within(screen.getByTestId("drill-in")).getByText(/KAPITEL 2/)).toBeTruthy();

    // The confirmed switch folds the copy — the new chapter stands clean.
    fireEvent.click(within(ankunft).getByText("Ankunft auf Horizon Station"));
    const second = await screen.findByRole("alertdialog");
    fireEvent.click(within(second).getByRole("button", { name: de["planning.storyboard.discardDraftConfirm"] }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    await waitFor(() =>
      expect(within(screen.getByTestId("drill-in")).getByText(/KAPITEL 1/)).toBeTruthy(),
    );
    expect(screen.queryByText(/Wähle mich\./)).toBeNull();
    expect(api.PUT.mock.calls.some(([p]) => p === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes")).toBe(false);
  });

  it("an immediate second save does not conflict — the PUT's answer seeds the stamp", async () => {
    await renderStoryboard();
    await dirtySignalCopy();
    const dock = screen.getByTestId("drill-in");
    fireEvent.click(within(dock).getByRole("button", { name: de["planning.storyboard.saveAggregate"] }));
    await waitFor(() =>
      expect(api.PUT.mock.calls.some(([p]) => p === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes")).toBe(true),
    );
    await waitFor(() => expect(screen.queryByText(/Wähle mich\./)).toBeNull());

    // The second edit rides the seeded stamp: no conflict face, a second PUT.
    const scenes = await within(dock).findAllByTestId("drill-in-scene");
    fireEvent.click(within(scenes[0]).getByRole("button", { name: de["planning.storyboard.editScene"] }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(de["planning.storyboard.purpose"]), {
      target: { value: "Zweite Antwort." },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: de["planning.crud.saveChanges"] }));
    fireEvent.click(within(dock).getByRole("button", { name: de["planning.storyboard.saveAggregate"] }));
    await waitFor(() =>
      expect(
        api.PUT.mock.calls.filter(([p]) => p === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes"),
      ).toHaveLength(2),
    );
    expect(screen.queryByTestId("drill-in-conflict")).toBeNull();
  });

  it("a failed overwrite retries as the overwrite — not back into the conflict face", async () => {
    await renderStoryboard();
    await dirtySignalCopy();
    const dock = screen.getByTestId("drill-in");

    // The stamp moves: the first save refuses as the conflict face.
    sceneVersion = "2026-11-19T12:00:00Z";
    fireEvent.click(within(dock).getByRole("button", { name: de["planning.storyboard.saveAggregate"] }));
    expect(await within(dock).findByTestId("drill-in-conflict")).toBeTruthy();

    // The overwrite leaves, and its PUT fails — the failed face stands and
    // the conflict face folds.
    scenesPutFail = true;
    fireEvent.click(within(screen.getByTestId("drill-in-conflict")).getByRole("button", { name: de["planning.storyboard.conflictOverwrite"] }));
    const failedText = await within(dock).findByText(de["planning.crud.error"]);
    const failedFace = failedText.closest('[role="alert"]') as HTMLElement;
    expect(screen.queryByTestId("drill-in-conflict")).toBeNull();

    // The retry re-sends the overwrite: no fresh version check, no bounce
    // back into the conflict face. The count pins the RE-SEND — two PUTs
    // cross in the test's whole life (the failed overwrite, then its
    // retry); asserting one would match only the first failure and let a
    // retry that never fired pass.
    scenesPutFail = false;
    fireEvent.click(within(failedFace).getByRole("button", { name: de["planning.storyboard.retry"] }));
    await waitFor(() =>
      expect(
        api.PUT.mock.calls.filter(([p]) => p === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes"),
      ).toHaveLength(2),
    );
    expect(screen.queryByTestId("drill-in-conflict")).toBeNull();
    await waitFor(() => expect(screen.queryByText(/Wähle mich\./)).toBeNull());
  });

  it("a chapter switch retires the stale failed face — no unversioned PUT can leave for the next chapter", async () => {
    await renderStoryboard();
    await dirtySignalCopy();
    const dock = screen.getByTestId("drill-in");

    // Chapter A refuses as a conflict; its overwrite leaves and fails.
    sceneVersion = "2026-11-19T12:00:00Z";
    fireEvent.click(within(dock).getByRole("button", { name: de["planning.storyboard.saveAggregate"] }));
    expect(await within(dock).findByTestId("drill-in-conflict")).toBeTruthy();
    scenesPutFail = true;
    fireEvent.click(within(screen.getByTestId("drill-in-conflict")).getByRole("button", { name: de["planning.storyboard.conflictOverwrite"] }));
    await within(dock).findByText(de["planning.crud.error"]);

    // The guarded switch folds chapter A's copy into chapter B (c1).
    const ankunft = screen.getAllByTestId("storyboard-card").find((card) =>
      within(card).queryByText("Ankunft auf Horizon Station") !== null,
    ) as HTMLElement;
    fireEvent.click(within(ankunft).getByText("Ankunft auf Horizon Station"));
    fireEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: de["planning.storyboard.discardDraftConfirm"] }));
    await waitFor(() => expect(within(screen.getByTestId("drill-in")).getByText(/KAPITEL 1/)).toBeTruthy());

    // Chapter B's own answers: once its copy stands, the stale failed face
    // (and the unversioned overwrite its retry would re-send) must have
    // retired with the chapter it belonged to.
    const scenes = await within(screen.getByTestId("drill-in")).findAllByTestId("drill-in-scene");
    fireEvent.click(within(scenes[0]).getByRole("button", { name: de["planning.storyboard.editScene"] }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(de["planning.storyboard.purpose"]), {
      target: { value: "Antwort des nächsten Kapitels." },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: de["planning.crud.saveChanges"] }));
    expect(within(screen.getByTestId("drill-in")).queryByText(de["planning.crud.error"])).toBeNull();

    // And chapter B's save is a CHECKED one: its stamp moved too, so the
    // honest answer is the conflict face — never an unversioned PUT.
    scenesPutFail = false;
    fireEvent.click(within(screen.getByTestId("drill-in")).getByRole("button", { name: de["planning.storyboard.saveAggregate"] }));
    expect(await within(screen.getByTestId("drill-in")).findByTestId("drill-in-conflict")).toBeTruthy();
    expect(
      api.PUT.mock.calls.some(([, init]) => (init as { params?: { path?: { chapter_id?: string } } })?.params?.path?.chapter_id === "c1"),
    ).toBe(false);
  });
});

describe("the review fixes, second round", () => {
  /** Chapter 2 selected with its dock standing — the shared preamble. */
  async function openSignalDock() {
    const cards = await screen.findAllByTestId("storyboard-card");
    fireEvent.click(within(cards[1]).getByText("Das Signal im Permafrost"));
    const dock = await screen.findByTestId("drill-in");
    await within(dock).findAllByTestId("drill-in-scene");
    return dock;
  }

  /** Dirty chapter 2's copy through the edit dialog — the marker the
   *  conflict pins must not survive the fresh load. */
  async function dirtySignalCopy(dock: HTMLElement, purpose: string) {
    const scenes = within(dock).getAllByTestId("drill-in-scene");
    fireEvent.click(within(scenes[0]).getByRole("button", { name: de["planning.storyboard.editScene"] }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(de["planning.storyboard.purpose"]), {
      target: { value: purpose },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: de["planning.crud.saveChanges"] }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  }

  it("the conflict seeds the fan's entry — the fresh load shows the server's rows without a refetch", async () => {
    await renderStoryboard();
    const dock = await openSignalDock();
    await dirtySignalCopy(dock, "Lokale Antwort, die der Server nie sah.");

    // The server moved on: a third scene stands and the stamp advanced —
    // a FRESH aggregate, so the cache's own entry (a shallow copy of the
    // old one) keeps its two rows and cannot alias the move.
    const moved = sceneAggregate("c2");
    moved.scenes.push({
      id: "s-2-3",
      chapter_id: "c2",
      position: 3,
      title: "Dritte Szene",
      purpose: "",
      conflict: "",
      resolution: "",
      beats: [],
      status: "planned",
      created_at: "2026-11-19T11:30:00Z",
      updated_at: "2026-11-19T11:30:00Z",
    });
    AGGREGATES.set("c2", moved);
    sceneVersion = "2026-11-19T12:00:00Z";
    // The pre-read answers (the next scenes GET); every GET after it —
    // the invalidation's refetch — hangs: whatever the dock shows after
    // the fresh load can only come from the conflict's own copy.
    scenesHangAfterNext = true;
    fireEvent.click(within(dock).getByRole("button", { name: de["planning.storyboard.saveAggregate"] }));
    expect(await within(dock).findByTestId("drill-in-conflict")).toBeTruthy();

    fireEvent.click(within(screen.getByTestId("drill-in-conflict")).getByRole("button", { name: de["planning.storyboard.conflictReload"] }));

    // The server's three rows stand — seeded, not refetched — the draft
    // is gone, and no PUT crossed.
    await waitFor(() => expect(within(dock).getAllByTestId("drill-in-scene")).toHaveLength(3));
    expect(within(dock).getByText(/Szene 2\.3: Dritte Szene/)).toBeTruthy();
    expect(screen.queryByText("Lokale Antwort, die der Server nie sah.")).toBeNull();
    expect(
      api.PUT.mock.calls.some(([p]) => p === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes"),
    ).toBe(false);
  });

  it("a failed version pre-read refuses the save — no PUT crosses", async () => {
    await renderStoryboard();
    const dock = await openSignalDock();
    await dirtySignalCopy(dock, "Antwort ohne Vorablesen.");

    // The pre-read itself breaks: the version compare cannot run, and the
    // save must refuse rather than fall through to an unchecked PUT.
    scenesFail = true;
    fireEvent.click(within(dock).getByRole("button", { name: de["planning.storyboard.saveAggregate"] }));
    const failedText = await within(dock).findByText(de["planning.crud.error"]);
    expect(
      api.PUT.mock.calls.some(([p]) => p === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes"),
    ).toBe(false);

    // The retry re-runs the CHECKED save: the pre-read answers again, the
    // stamp stands as the snapshot left it, and the PUT crosses.
    scenesFail = false;
    fireEvent.click(within(failedText.closest('[role="alert"]') as HTMLElement).getByRole("button", { name: de["planning.storyboard.retry"] }));
    await waitFor(() =>
      expect(
        api.PUT.mock.calls.some(([p]) => p === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes"),
      ).toBe(true),
    );
  });

  it("a scene is minted as a real UUID from crypto randomness when randomUUID is absent", async () => {
    // A runtime without randomUUID but with the universal getRandomValues:
    // bytes 0..15 make the minted id a predictable line — and the server's
    // SceneUpsert.id is a UUID, so the fallback must dress the bytes as
    // one (version 4, variant 8) or the whole add-scene flow 422s.
    vi.stubGlobal("crypto", {
      getRandomValues: (array: Uint8Array) => {
        for (let index = 0; index < array.length; index += 1) array[index] = index;
        return array;
      },
    });
    await renderStoryboard();
    const dock = await openSignalDock();
    fireEvent.click(within(dock).getByRole("button", { name: /Szene zu Kapitel 2 hinzufügen/ }));
    fireEvent.click(within(dock).getByRole("button", { name: de["planning.storyboard.saveAggregate"] }));
    await waitFor(() =>
      expect(
        api.PUT.mock.calls.some(([p]) => p === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes"),
      ).toBe(true),
    );
    const call = api.PUT.mock.calls.find(([, init]) => (init as { params?: { path?: { chapter_id?: string } } })?.params?.path?.chapter_id === "c2");
    const body = (call?.[1] as { body: { scenes: { id: string }[] } }).body;
    const added = body.scenes.find((scene) => scene.id !== "s-2-1" && scene.id !== "s-2-2");
    // Bytes 0..15 with the v4/variant bits set read as exactly this UUID.
    expect(added?.id).toBe("00010203-0405-4607-8809-0a0b0c0d0e0f");
  });

  it("the dialog panels keep to a short viewport — long content scrolls inside the frame", async () => {
    await renderStoryboard();
    const dock = await openSignalDock();
    const scenes = within(dock).getAllByTestId("drill-in-scene");

    // The scene edit's form panel.
    fireEvent.click(within(scenes[0]).getByRole("button", { name: de["planning.storyboard.editScene"] }));
    const edit = await screen.findByRole("dialog");
    expect(edit.className).toContain("max-h-[calc(100vh-2rem)]");
    expect(edit.className).toContain("overflow-y-auto");
    fireEvent.click(within(edit).getByRole("button", { name: de["planning.crud.cancel"] }));

    // The scene remove's confirm panel (the discard guard shares it).
    fireEvent.click(within(scenes[0]).getByRole("button", { name: de["planning.storyboard.removeScene"] }));
    const remove = await screen.findByRole("alertdialog");
    expect(remove.className).toContain("max-h-[calc(100vh-2rem)]");
    expect(remove.className).toContain("overflow-y-auto");
    fireEvent.click(within(remove).getByRole("button", { name: de["planning.crud.cancel"] }));

    // The remap's panel.
    fireEvent.click(screen.getByRole("button", { name: literal(de["storyboard.structure.heros-journey"]) }));
    fireEvent.click(within(screen.getByTestId("storyboard-remap-notice")).getByRole("button", { name: de["planning.storyboard.remapApply"] }));
    const remap = await screen.findByRole("dialog");
    expect(remap.className).toContain("max-h-[calc(100vh-2rem)]");
    expect(remap.className).toContain("overflow-y-auto");
  });

  it("while the save is in flight the dock holds its editing — no edit slips under the PUT", async () => {
    await renderStoryboard();
    const dock = await openSignalDock();
    await dirtySignalCopy(dock, "Wird gerade gesichert.");

    // The PUT never settles: the save stays busy.
    scenesPutHang = true;
    fireEvent.click(within(dock).getByRole("button", { name: de["planning.storyboard.saveAggregate"] }));
    await waitFor(() => {
      for (const scene of within(dock).getAllByTestId("drill-in-scene")) {
        expect((within(scene).getByRole("button", { name: de["planning.storyboard.editScene"] }) as HTMLButtonElement).disabled).toBe(true);
        expect((within(scene).getByRole("button", { name: de["planning.storyboard.moveUp"] }) as HTMLButtonElement).disabled).toBe(true);
        expect((within(scene).getByRole("button", { name: de["planning.storyboard.moveDown"] }) as HTMLButtonElement).disabled).toBe(true);
        expect((within(scene).getByRole("button", { name: de["planning.storyboard.removeScene"] }) as HTMLButtonElement).disabled).toBe(true);
      }
      expect(
        (within(dock).getByRole("button", { name: /Szene zu Kapitel 2 hinzufügen/ }) as HTMLButtonElement).disabled,
      ).toBe(true);
    });
  });

  it("a failed chapters read is its own face — no false empty, and the retry re-arms", async () => {
    chaptersFail = true;
    await renderStoryboard();
    const cards = await screen.findAllByTestId("storyboard-card");

    // The board stands on its own read; the chip names what broke instead
    // of painting the counts of a novel it never heard back from.
    const chip = screen.getByTestId("storyboard-progress");
    await waitFor(() => expect(within(chip).getByText(de["planning.storyboard.scenesUnavailable"])).toBeTruthy());
    expect(within(chip).queryByText(/0 Szenen gesamt/)).toBeNull();
    expect(within(chip).queryByText(/^0 Kapitel$/)).toBeNull();

    // The drill-in names the outage instead of loading forever — and its
    // retry re-fetches the chapters read the fan arms through.
    fireEvent.click(within(cards[1]).getByText("Das Signal im Permafrost"));
    const dock = await screen.findByTestId("drill-in");
    expect(await within(dock).findByText(de["planning.storyboard.scenesUnavailable"])).toBeTruthy();
    chaptersFail = false;
    fireEvent.click(within(dock).getByRole("button", { name: de["planning.storyboard.retry"] }));
    await waitFor(() => expect(within(dock).getAllByTestId("drill-in-scene")).toHaveLength(2));
    await waitFor(() => expect(within(chip).getByText("3 Kapitel")).toBeTruthy());
    expect(within(chip).getByText("4 Szenen gesamt")).toBeTruthy();
  });
});

describe("the Codacy re-analysis round", () => {
  /** Chapter 2 selected with its dock standing. */
  async function openSignalDock() {
    const cards = await screen.findAllByTestId("storyboard-card");
    fireEvent.click(within(cards[1]).getByText("Das Signal im Permafrost"));
    const dock = await screen.findByTestId("drill-in");
    await within(dock).findAllByTestId("drill-in-scene");
    return dock;
  }

  it("the dock keeps to a small screen — its own list scrolls instead of clipping", async () => {
    await renderStoryboard();
    const dock = await openSignalDock();
    // The mobile (sub-xl) dock carries its own height bound and scroll:
    // the page body clips at every breakpoint, so an unbounded list would
    // lose its tail — and the save bar — off-screen with no way to reach
    // them. The xl: variants keep the wide-viewport contract (the dock
    // fills the column and scrolls inside it).
    expect(dock.className).toContain("max-h-[70vh]");
    expect(dock.className).toContain("overflow-y-auto");
    expect(dock.className).toContain("xl:max-h-full");
  });

  it("the conflict's fresh load retires the face — a re-edit saves checked, not into a stale conflict", async () => {
    await renderStoryboard();
    const dock = await openSignalDock();
    const scenes = within(dock).getAllByTestId("drill-in-scene");
    fireEvent.click(within(scenes[0]).getByRole("button", { name: de["planning.storyboard.editScene"] }));
    let dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(de["planning.storyboard.purpose"]), {
      target: { value: "Erste Antwort." },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: de["planning.crud.saveChanges"] }));

    sceneVersion = "2026-11-19T12:00:00Z";
    fireEvent.click(within(dock).getByRole("button", { name: de["planning.storyboard.saveAggregate"] }));
    expect(await within(dock).findByTestId("drill-in-conflict")).toBeTruthy();
    fireEvent.click(within(screen.getByTestId("drill-in-conflict")).getByRole("button", { name: de["planning.storyboard.conflictReload"] }));
    await waitFor(() => expect(screen.queryByTestId("drill-in-conflict")).toBeNull());

    // The next edit is a NEW save on the reloaded rows: its bar must be
    // the honest save/discard one — the spent conflict may not stand
    // over it (its only doors are a reload of a clean copy and an
    // unversioned overwrite).
    const fresh = within(dock).getAllByTestId("drill-in-scene");
    fireEvent.click(within(fresh[0]).getByRole("button", { name: de["planning.storyboard.editScene"] }));
    dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(de["planning.storyboard.purpose"]), {
      target: { value: "Zweite Antwort nach dem Neu laden." },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: de["planning.crud.saveChanges"] }));
    expect(screen.queryByTestId("drill-in-conflict")).toBeNull();
    fireEvent.click(within(dock).getByRole("button", { name: de["planning.storyboard.saveAggregate"] }));

    // The save runs CHECKED against the reloaded stamp — it crosses, and
    // no conflict face returns.
    await waitFor(() =>
      expect(
        api.PUT.mock.calls.some(([p]) => p === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes"),
      ).toBe(true),
    );
    expect(screen.queryByTestId("drill-in-conflict")).toBeNull();
  });

  it("a failed remap confirm retries as the confirm — never back into the preview", async () => {
    await renderStoryboard();
    await screen.findAllByTestId("storyboard-card");
    fireEvent.click(screen.getByRole("button", { name: literal(de["storyboard.structure.five-act"]) }));
    fireEvent.click(within(screen.getByTestId("storyboard-remap-notice")).getByRole("button", { name: de["planning.storyboard.remapApply"] }));
    const dialog = await screen.findByRole("dialog");
    await waitFor(() =>
      expect(api.POST).toHaveBeenCalledWith(
        "/api/planning/novels/{novel_id}/remap",
        { params: { path: { novel_id: NOVEL_ID } }, body: { structure_id: "five-act", confirm: false } },
      ),
    );

    // The confirm leaves and fails: the retry must re-send CONFIRM, not
    // quietly fall back to a second preview.
    remapStatus = 503;
    fireEvent.click(within(dialog).getByRole("button", { name: de["planning.storyboard.remapConfirm"] }));
    const failedText = await within(dialog).findByText(de["planning.storyboard.remapError"]);
    remapStatus = 0;
    fireEvent.click(within(failedText.closest('[role="alert"]') as HTMLElement).getByRole("button", { name: de["planning.storyboard.retry"] }));

    await waitFor(() =>
      expect(
        api.POST.mock.calls.filter(([, init]) => (init as { body?: { confirm?: boolean } })?.body?.confirm === true),
      ).toHaveLength(2),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("a failed novel read names itself in the chip — the word totals never silently vanish", async () => {
    novelFail = true;
    await renderStoryboard();
    await screen.findAllByTestId("storyboard-card");
    const chip = screen.getByTestId("storyboard-progress");
    expect(await within(chip).findByText(de["planning.storyboard.wordsUnavailable"])).toBeTruthy();
    // The dot beside the face is the family's neutral tone — not the
    // green „in sync“ mark of a word total that never stood.
    const dot = chip.firstElementChild as HTMLElement;
    expect(dot.className).toContain("bg-outline");
    expect(dot.className).not.toContain("bg-success");
    expect(within(chip).queryByText(/18\.260/)).toBeNull();
    expect(within(chip).queryByText(/65\.000/)).toBeNull();
    // The counts the chapters read does own still stand.
    expect(within(chip).getByText("3 Kapitel")).toBeTruthy();
  });

  it("removing one of two equal beats keeps the other — the remove is by row, not by value", async () => {
    // The server's rows carry the same beat twice (nothing in the schema
    // forbids it — only the editor's own commit refuses new doubles) —
    // set BEFORE the render, so the fan reads it whenever it fires.
    const doubled = sceneAggregate("c2");
    doubled.scenes[0].beats.push(doubled.scenes[0].beats[0]);
    AGGREGATES.set("c2", doubled);
    await renderStoryboard();
    const dock = await openSignalDock();
    expect(within(dock).getAllByText("Sonde schlägt bei 14.2 Hz aus")).toHaveLength(2);

    const scenes = within(dock).getAllByTestId("drill-in-scene");
    fireEvent.click(within(scenes[0]).getByRole("button", { name: de["planning.storyboard.editScene"] }));
    const dialog = await screen.findByRole("dialog");
    const removes = within(dialog).getAllByRole("button", {
      name: de["planning.crud.removeName"].replace("{name}", "Sonde schlägt bei 14.2 Hz aus"),
    });
    fireEvent.click(removes[0]);
    fireEvent.click(within(dialog).getByRole("button", { name: de["planning.crud.saveChanges"] }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    // The twin keeps its row; only the clicked one left the copy.
    expect(within(dock).getAllByText("Sonde schlägt bei 14.2 Hz aus")).toHaveLength(1);
  });
});

describe("the catalogs", () => {
  it("carry the storyboard's keys in parity, sorted, in the du register", () => {
    const deKeys = Object.keys(de).filter((key) => key.startsWith("planning.storyboard") || key.startsWith("planning.sync") || key.startsWith("planning.sceneStatus") || key.startsWith("storyboard."));
    expect(deKeys.length).toBeGreaterThan(60);
    for (const locale of ["en", "fr"] as const) {
      for (const key of deKeys) {
        expect((catalogs[locale] as Record<string, string>)[key], `${locale}/${key}`).toBeTruthy();
      }
    }
    // The du register: the conflict's own words speak to the writer.
    expect(de["planning.storyboard.conflictBody"]).toMatch(/Deine\b/);
    expect(de["planning.storyboard.emptyNote"]).toMatch(/deine\b/);
    // The English stage chip carries its own unit — no German „W." leak.
    expect(catalogs.en["planning.storyboard.stageShare"]).toContain("words");
    expect(catalogs.en["planning.storyboard.stageShare"]).not.toContain("W.");
    expect(catalogs.fr["planning.storyboard.stageShare"]).toContain("mots");
  });
});

describe("the route-leave guard (#928)", () => {
  /** Chapter 2's copy, dirtied through the edit dialog — the shared
   *  preamble of the route-leave pins. */
  async function dirtySignalCopy() {
    const cards = await screen.findAllByTestId("storyboard-card");
    fireEvent.click(within(cards[1]).getByText("Das Signal im Permafrost"));
    const dock = await screen.findByTestId("drill-in");
    const scenes = await within(dock).findAllByTestId("drill-in-scene");
    fireEvent.click(within(scenes[0]).getByRole("button", { name: de["planning.storyboard.editScene"] }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(de["planning.storyboard.purpose"]), {
      target: { value: "Wähle mich." },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: de["planning.crud.saveChanges"] }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    return dock;
  }

  it("a dirty draft asks before any route leave — the same confirm the chapter switch speaks", async () => {
    const router = await renderStoryboard();
    const dock = await dirtySignalCopy();

    // The dock's workspace door (a Link) fires a route leave: the blocker
    // holds it and the confirm stands, naming the chapter the copy belongs
    // to — the page never folds the draft behind a silent navigation.
    fireEvent.click(within(dock).getByRole("link", { name: de["planning.storyboard.openWorkspace"] }));
    const guard = await screen.findByRole("alertdialog");
    expect(within(guard).getByText(/Das Signal im Permafrost/)).toBeTruthy();
    expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}/planning/storyboard`);

    // The safe answer keeps BOTH: the page and the copy.
    fireEvent.click(within(guard).getByRole("button", { name: de["planning.crud.cancel"] }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}/planning/storyboard`);
    expect(within(screen.getByTestId("drill-in")).getByText(/Wähle mich\./)).toBeTruthy();

    // The named loss proceeds — the route completes, the copy folds with
    // the page it belonged to.
    fireEvent.click(within(screen.getByTestId("drill-in")).getByRole("link", { name: de["planning.storyboard.openWorkspace"] }));
    const second = await screen.findByRole("alertdialog");
    fireEvent.click(within(second).getByRole("button", { name: de["planning.storyboard.discardDraftConfirm"] }));
    await waitFor(() => expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}`));
    expect(await screen.findByText("workspace face")).toBeTruthy();
  });

  it("a sub-nav sibling door asks too, and a clean draft leaves without a dialog", async () => {
    const router = await renderStoryboard();
    await dirtySignalCopy();

    // The subbar's timeline door is a route leave like any other.
    fireEvent.click(screen.getByTestId("storyboard-timeline-door"));
    expect(await screen.findByRole("alertdialog")).toBeTruthy();
    fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: de["planning.storyboard.discardDraftConfirm"] }));
    await waitFor(() => expect(router.state.location.pathname).toContain("/planning/timeline"));

    // A clean draft never asks: a fresh page walks straight out.
    await renderStoryboard();
    await screen.findAllByTestId("storyboard-card");
    fireEvent.click(screen.getByTestId("storyboard-timeline-door"));
    await waitFor(() => expect(router.state.location.pathname).toContain("/planning/timeline"));
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });

  it("a leave fired while the switch guard stands queues behind it — one dialog at a time", async () => {
    const router = await renderStoryboard();
    await dirtySignalCopy();

    // The chapter-switch guard's ask stands.
    const ankunft = screen.getAllByTestId("storyboard-card").find((card) =>
      within(card).queryByText("Ankunft auf Horizon Station") !== null,
    ) as HTMLElement;
    fireEvent.click(within(ankunft).getByText("Ankunft auf Horizon Station"));
    expect(await screen.findByRole("alertdialog")).toBeTruthy();

    // A programmatic route leave fires mid-dialog: the resolver holds it
    // exactly like a dock-door click, and the standing ask stays standing
    // — exactly ONE alertdialog, the switch confirm, no leave dialog
    // stacking a second question over the first.
    void router.navigate({ to: WORKSPACE_PATH, params: { novelId: NOVEL_ID } });
    await waitFor(() => expect(screen.getAllByRole("alertdialog")).toHaveLength(1));
    expect(within(screen.getByRole("alertdialog")).getByText(/Das Signal im Permafrost/)).toBeTruthy();
    expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}/planning/storyboard`);

    // The first ask answered (cancel: the copy keeps standing), the held
    // leave now asks its own — still exactly one at a time, the page
    // never moved.
    fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: de["planning.crud.cancel"] }));
    expect(await screen.findByRole("alertdialog")).toBeTruthy();
    expect(screen.getAllByRole("alertdialog")).toHaveLength(1);
    expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}/planning/storyboard`);

    // The leave's own safe answer stands everything down: page and copy.
    fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: de["planning.crud.cancel"] }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}/planning/storyboard`);
    expect(within(screen.getByTestId("drill-in")).getByText(/Wähle mich\./)).toBeTruthy();
    expect(within(screen.getByTestId("drill-in")).getByText(/KAPITEL 2/)).toBeTruthy();
  });

  it("a confirmed switch releases a held leave cleanly — no second ask over the folded copy", async () => {
    const router = await renderStoryboard();
    await dirtySignalCopy();

    // The switch ask stands, then a programmatic leave is held behind it.
    const ankunft = screen.getAllByTestId("storyboard-card").find((card) =>
      within(card).queryByText("Ankunft auf Horizon Station") !== null,
    ) as HTMLElement;
    fireEvent.click(within(ankunft).getByText("Ankunft auf Horizon Station"));
    expect(await screen.findByRole("alertdialog")).toBeTruthy();
    void router.navigate({ to: WORKSPACE_PATH, params: { novelId: NOVEL_ID } });
    await waitFor(() => expect(screen.getAllByRole("alertdialog")).toHaveLength(1));

    // The named loss is given to the switch ask: the copy folds into
    // chapter 1, and the held leave dies with it — the loss it waited to
    // name was already given, so its dialog never mounts, no spurious
    // ask stands over the now-clean chapter, and the page stays where
    // the confirmed switch put it.
    fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: de["planning.storyboard.discardDraftConfirm"] }));
    await waitFor(() => expect(within(screen.getByTestId("drill-in")).getByText(/KAPITEL 1/)).toBeTruthy());
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(screen.queryAllByRole("alertdialog")).toHaveLength(0);
    expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}/planning/storyboard`);
    // The fold took the copy with the switch — chapter 1's clean rows stand.
    expect(within(screen.getByTestId("drill-in")).queryByText(/Wähle mich\./)).toBeNull();
  });
});
