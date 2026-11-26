// @vitest-environment jsdom
/**
 * The causality strip page (W6 Task 5) — the planning capability's third
 * web surface, ported from the owner-approved harmonized `causality-strip`
 * draft onto the shell's tokens, driven through the real API seam (the
 * client mocked at its module boundary, the house pattern). The strip
 * chains the novel's real scenes chapter-grouped left-to-right: per scene
 * the title, the Konflikt, the Auflösung and the status badge — nothing
 * else. Missing conflict/resolution answers render the honest „—“, beats
 * are deliberately not shown, and the page invents no word count, no
 * phase label, no lock state (no field carries them). The empty novel
 * doors to the storyboard; the no-chapters and outage states stay honest
 * (no zero-chain); the subbar with its sibling doors stands in EVERY
 * state — pending, outage, empty, populated (W5 #923's rule). The face
 * speaks du-tone in all three catalogs.
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

import { client, type Chapter } from "@shell/lib/api/client";
import { applyLocale } from "@shell/lib/locale";
import { t, type MessageKey } from "@shell/lib/i18n";
import { queryClient } from "@shell/lib/query";
import { de } from "@shell/lib/test/catalogs";

import { CausalityPage } from "./CausalityPage";

const api = client as unknown as Record<"GET" | "POST" | "PUT" | "DELETE", ReturnType<typeof vi.fn>>;

/** The catalog's own formatter — a plural key formats through the active
 *  locale (de in this suite), it never string-replaces. */
function format(key: MessageKey, params: Record<string, string | number> = {}): string {
  return t(key, params);
}

configure({ asyncUtilTimeout: 5000 });

const NOVEL_ID = "11111111-1111-1111-1111-111111111111";
const TIMELINE_PATH = "/novels/$novelId/planning/timeline";
const STORYBOARD_PATH = "/novels/$novelId/planning/storyboard";
const CAUSALITY_PATH = "/novels/$novelId/planning/causality";
const WORKSPACE_PATH = "/novels/$novelId";

function ok(status = 200): Response {
  return new Response(null, { status });
}

function chapterRow(overrides: Partial<Chapter> & { id: string }): Chapter {
  return {
    novel_id: NOVEL_ID,
    title: "Nevada-Rückblende",
    position: 2,
    word_count: 0,
    created_at: "2026-11-18T10:00:00Z",
    updated_at: "2026-11-18T10:00:00Z",
    scene_count: 0,
    target_words: null,
    ...overrides,
  };
}

const CH1 = chapterRow({ id: "c1", title: "Ankunft", position: 0 });
const CH2 = chapterRow({ id: "c2", title: "Notfall-Code", position: 1 });
const CHAPTERS = [CH1, CH2];

function sceneRow(chapterId: string, overrides: { id: string; position: number } & Partial<{
  title: string;
  purpose: string;
  conflict: string;
  resolution: string;
  beats: string[];
  status: string;
}>) {
  return {
    chapter_id: chapterId,
    title: "",
    purpose: "",
    conflict: "",
    resolution: "",
    beats: [],
    status: "planned",
    created_at: "2026-11-18T10:00:00Z",
    updated_at: "2026-11-18T10:00:00Z",
    ...overrides,
  };
}

/** Chapter 1: two chained scenes with real answers; chapter 2: one scene
 *  whose conflict and resolution are both missing (the honest „—“). */
const S11 = sceneRow("c1", {
  id: "s11",
  position: 1,
  title: "Kalibrierung der Messsonde",
  conflict: "Die Sensoren empfangen Rauschmuster ohne Entsprechung in den Tabellen.",
  resolution: "Maya schaltet die Filter manuell aus, um das Direktsignal zu isolieren.",
  status: "complete",
});
const S12 = sceneRow("c1", {
  id: "s12",
  position: 2,
  title: "Das Artefakt im Schacht",
  conflict: "Der Schacht ist durch Vereisung blockiert; das Direktsignal überhitzt die Relais.",
  resolution: "Maya bricht das Siegel der Notdruckkammer auf.",
  status: "in_progress",
  beats: ["Erster Auftritt des Artefakts"],
});
const S21 = sceneRow("c2", {
  id: "s21",
  position: 1,
  title: "Unbenanntes Fragment",
  status: "planned",
});

const AGGREGATES = new Map([
  ["c1", { chapter_id: "c1", version_updated_at: "2026-11-18T10:00:00Z", scenes: [S11, S12] }],
  ["c2", { chapter_id: "c2", version_updated_at: "2026-11-18T10:00:00Z", scenes: [S21] }],
]);

let chapters: Chapter[];
let chaptersFail: boolean;
let scenesFail: boolean;

function baseGet(
  path: string,
  init?: { params?: { path?: { chapter_id?: string } } },
): Promise<{ data: unknown; response: Response }> {
  if (chaptersFail && path === "/api/writing/novels/{novel_id}/chapters") {
    return Promise.resolve({ data: undefined, response: ok(503) });
  }
  if (path === "/api/writing/novels/{novel_id}/chapters") {
    return Promise.resolve({ data: chapters, response: ok() });
  }
  if (path === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes") {
    if (scenesFail) return Promise.resolve({ data: undefined, response: ok(503) });
    const chapterId = init?.params?.path?.chapter_id ?? "";
    return Promise.resolve({ data: AGGREGATES.get(chapterId), response: ok() });
  }
  throw new Error(`unexpected GET: ${path}`);
}

/** The page on a harness route whose id is the real causality path, beside
 *  stubs the sibling doors, the verketten door and the manuscript door
 *  walk to. */
const harnessRoot = createRootRoute({ component: () => <Outlet /> });

async function renderCausality(entry = `/novels/${NOVEL_ID}/planning/causality`) {
  const causality = createRoute({
    getParentRoute: () => harnessRoot,
    path: CAUSALITY_PATH,
    component: CausalityPage,
  });
  const storyboard = createRoute({
    getParentRoute: () => harnessRoot,
    path: STORYBOARD_PATH,
    component: () => <p>storyboard face</p>,
  });
  const timeline = createRoute({
    getParentRoute: () => harnessRoot,
    path: TIMELINE_PATH,
    component: () => <p>timeline face</p>,
  });
  const workspace = createRoute({
    getParentRoute: () => harnessRoot,
    path: WORKSPACE_PATH,
    component: () => <p>workspace face</p>,
  });
  const router = createRouter({
    routeTree: harnessRoot.addChildren([causality, storyboard, timeline, workspace]),
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
  const timelineDoor = screen.getByTestId("causality-timeline-door");
  expect(within(timelineDoor).getByText(de["planning.timeline.title"])).toBeTruthy();
  const storyboardDoor = screen.getByTestId("causality-storyboard-door");
  expect(within(storyboardDoor).getByText(de["planning.sub.storyboard"])).toBeTruthy();
  expect(screen.getByText(de["planning.sub.causality"])).toBeTruthy();
}

beforeEach(() => {
  applyLocale("de");
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
  chapters = CHAPTERS;
  chaptersFail = false;
  scenesFail = false;
  api.GET.mockImplementation(baseGet);
  api.POST.mockResolvedValue({ data: undefined, response: ok(201) });
  api.PUT.mockResolvedValue({ data: undefined, response: ok() });
  api.DELETE.mockResolvedValue({ data: undefined, response: ok(204) });
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
  applyLocale(null);
});

describe("the chain renders the novel's real scenes", () => {
  it("groups the chapters in their order, each with its scene chain", async () => {
    await renderCausality();
    const track = await screen.findByTestId("causality-track");
    const groups = within(track).getAllByTestId("causality-chapter");
    expect(groups).toHaveLength(2);
    expect(within(groups[0]).getByText(de["planning.storyboard.chapterCard"].replace("{position}", "1"))).toBeTruthy();
    expect(within(groups[0]).getByText("Ankunft")).toBeTruthy();
    expect(within(groups[1]).getByText("Notfall-Code")).toBeTruthy();

    // The fan-out asked each chapter once.
    const asks = api.GET.mock.calls.filter(
      ([path]) => path === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes",
    );
    expect(asks).toHaveLength(2);

    // The scenes of chapter 1 in the server's own order — no client re-sort.
    const firstGroupScenes = within(groups[0]).getAllByTestId("causality-scene");
    expect(firstGroupScenes).toHaveLength(2);
    expect(firstGroupScenes[0].textContent).toContain("Kalibrierung der Messsonde");
    expect(firstGroupScenes[1].textContent).toContain("Das Artefakt im Schacht");
    const secondGroupScenes = within(groups[1]).getAllByTestId("causality-scene");
    expect(secondGroupScenes).toHaveLength(1);
  });

  it("the scene cards carry only the real fields — title, Konflikt, Auflösung, status", async () => {
    await renderCausality();
    const cards = await screen.findAllByTestId("causality-scene");
    const scene = cards[0];
    expect(within(scene).getByText(
      de["planning.storyboard.sceneLabel"]
        .replace("{chapter}", "1")
        .replace("{position}", "1")
        .replace("{title}", "Kalibrierung der Messsonde"),
    )).toBeTruthy();
    expect(within(scene).getByText(de["planning.storyboard.conflict"], { exact: false })).toBeTruthy();
    expect(within(scene).getByText("Die Sensoren empfangen Rauschmuster ohne Entsprechung in den Tabellen.")).toBeTruthy();
    expect(within(scene).getByText(de["planning.storyboard.resolutionField"], { exact: false })).toBeTruthy();
    expect(within(scene).getByText("Maya schaltet die Filter manuell aus, um das Direktsignal zu isolieren.")).toBeTruthy();
    expect(within(scene).getByText(de["planning.sceneStatus.complete"])).toBeTruthy();

    // No invented fields on any card: no word count, no lock state, no
    // phase label, no invented relative time.
    for (const card of cards) {
      expect(card.textContent).not.toMatch(/Wörter/);
      expect(card.textContent).not.toMatch(/Ausgangsphase|Eskalationsphase/);
      expect(within(card).queryByText(/vor \d+ Min\./)).toBeNull();
    }
  });

  it("missing conflict and resolution render the honest „—“, never invented content", async () => {
    await renderCausality();
    const groups = await screen.findAllByTestId("causality-chapter");
    const second = groups[1];
    const scene = within(second).getByTestId("causality-scene");
    const dashes = within(scene).getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(2);
    // The Konflikt and Auflösung labels still name the slots (each label
    // carries its colon in the same breath).
    expect(within(scene).getByText(de["planning.storyboard.conflict"], { exact: false })).toBeTruthy();
    expect(within(scene).getByText(de["planning.storyboard.resolutionField"], { exact: false })).toBeTruthy();
  });

  it("beats are deliberately not shown — the chain carries the chain, not the beat sheet", async () => {
    await renderCausality();
    const cards = await screen.findAllByTestId("causality-scene");
    for (const card of cards) {
      expect(within(card).queryByText("Erster Auftritt des Artefakts")).toBeNull();
      expect(within(card).queryByText(de["planning.storyboard.beats"])).toBeNull();
    }
    expect(screen.queryByText(de["planning.storyboard.beats"])).toBeNull();
  });

  it("an empty scene title says so honestly instead of inventing a name", async () => {
    chapters = [chapterRow({ id: "c3", title: "Leeres Kapitel", position: 0 })];
    api.GET.mockImplementation((path: string, init?: { params?: { path?: { chapter_id?: string } } }) => {
      if (path === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes") {
        return Promise.resolve({
          data: {
            chapter_id: "c3",
            version_updated_at: "2026-11-18T10:00:00Z",
            scenes: [sceneRow("c3", { id: "s31", position: 1, status: "planned" })],
          },
          response: ok(),
        });
      }
      return baseGet(path, init);
    });
    await renderCausality();
    const label = await screen.findByText(
      de["planning.storyboard.sceneLabel"]
        .replace("{chapter}", "1")
        .replace("{position}", "1")
        .replace("{title}", de["planning.storyboard.untitledScene"]),
    );
    expect(label).toBeTruthy();
  });

  it("an empty chapter between two scene-bearing ones breaks the chain — no arrow through the void", async () => {
    // A(empty) · B(empty scenes) · C(scenes): the transition needs the
    // immediately preceding rendered group to bear scenes — B's emptiness
    // is a break, and an arrow from B into C would claim a forcing B does
    // not carry.
    chapters = [
      chapterRow({ id: "c1", title: "Mit Szenen", position: 0 }),
      chapterRow({ id: "c2", title: "Leer dazwischen", position: 1 }),
      chapterRow({ id: "c3", title: "Wieder Szenen", position: 2 }),
    ];
    api.GET.mockImplementation((path: string, init?: { params?: { path?: { chapter_id?: string } } }) => {
      if (path === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes") {
        const id = init?.params?.path?.chapter_id ?? "";
        return Promise.resolve({
          data: {
            chapter_id: id,
            version_updated_at: "2026-11-18T10:00:00Z",
            scenes:
              id === "c2"
                ? []
                : [
                    sceneRow(id, {
                      id: `s-${id}`,
                      position: 1,
                      conflict: `Konflikt ${id}`,
                      resolution: `Auflösung ${id}`,
                      status: "complete",
                    }),
                  ],
          },
          response: ok(),
        });
      }
      return baseGet(path, init);
    });
    await renderCausality();
    const track = await screen.findByTestId("causality-track");
    expect(within(track).getAllByTestId("causality-chapter")).toHaveLength(3);
    // The broken chain names no transition anywhere — and no scene link
    // (each standing chapter carries one scene).
    expect(within(track).queryByTestId("causality-transition")).toBeNull();
    expect(within(track).queryByTestId("causality-link")).toBeNull();
    // The counts still speak the real fields: two scenes, no gaps (both
    // flanking chapters' scenes are answered — the empty chapter carries
    // no scene to gap) — so the chain chip reads the real closed zero.
    const counts = screen.getByTestId("causality-counts");
    expect(within(counts).getByText(format("planning.storyboard.scenesTotal", { count: 2 }))).toBeTruthy();
    const chain = screen.getByTestId("causality-chain");
    expect(within(chain).getByText(de["planning.causality.chainWhole"])).toBeTruthy();
    expect(within(chain).queryByText(format("planning.causality.chainGaps", { count: 0 }))).toBeNull();
  });

  it("an empty chapter FIRST stands alone — no arrow before the first scene-bearing group", async () => {
    chapters = [
      chapterRow({ id: "c1", title: "Leer vorne", position: 0 }),
      chapterRow({ id: "c2", title: "Danach Szenen", position: 1 }),
    ];
    api.GET.mockImplementation((path: string, init?: { params?: { path?: { chapter_id?: string } } }) => {
      if (path === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes") {
        const id = init?.params?.path?.chapter_id ?? "";
        return Promise.resolve({
          data: {
            chapter_id: id,
            version_updated_at: "2026-11-18T10:00:00Z",
            scenes:
              id === "c1"
                ? []
                : [
                    sceneRow(id, {
                      id: `s-${id}`,
                      position: 1,
                      conflict: `Konflikt ${id}`,
                      resolution: `Auflösung ${id}`,
                      status: "complete",
                    }),
                  ],
          },
          response: ok(),
        });
      }
      return baseGet(path, init);
    });
    await renderCausality();
    const track = await screen.findByTestId("causality-track");
    expect(within(track).getAllByTestId("causality-chapter")).toHaveLength(2);
    // The empty opener claims no transition: the first scene-bearing
    // group has no rendered predecessor that bears scenes.
    expect(within(track).queryByTestId("causality-transition")).toBeNull();
    expect(within(track).queryByTestId("causality-link")).toBeNull();
  });

  it("an empty chapter LAST stands alone — no trailing transition", async () => {
    chapters = [
      chapterRow({ id: "c1", title: "Szenen zuerst", position: 0 }),
      chapterRow({ id: "c2", title: "Leer hinten", position: 1 }),
    ];
    api.GET.mockImplementation((path: string, init?: { params?: { path?: { chapter_id?: string } } }) => {
      if (path === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes") {
        const id = init?.params?.path?.chapter_id ?? "";
        return Promise.resolve({
          data: {
            chapter_id: id,
            version_updated_at: "2026-11-18T10:00:00Z",
            scenes:
              id === "c2"
                ? []
                : [
                    sceneRow(id, {
                      id: `s-${id}`,
                      position: 1,
                      conflict: `Konflikt ${id}`,
                      resolution: `Auflösung ${id}`,
                      status: "complete",
                    }),
                  ],
          },
          response: ok(),
        });
      }
      return baseGet(path, init);
    });
    await renderCausality();
    const track = await screen.findByTestId("causality-track");
    expect(within(track).getAllByTestId("causality-chapter")).toHaveLength(2);
    // The scene-bearing group draws no arrow into the empty tail: the
    // transition needs the NEXT group to bear scenes too.
    expect(within(track).queryByTestId("causality-transition")).toBeNull();
    expect(within(track).queryByTestId("causality-link")).toBeNull();
    expect(within(track).getByText("Leer hinten")).toBeTruthy();
  });

  it("connectors chain the scenes — Erzwingt within a chapter, Kapitel-Übergang across", async () => {
    await renderCausality();
    const track = await screen.findByTestId("causality-track");
    // One scene-to-scene connector inside chapter 1 (two scenes), none in
    // chapter 2 (one scene).
    const links = within(track).getAllByTestId("causality-link");
    expect(links).toHaveLength(1);
    expect(within(links[0]).getByText(de["planning.causality.forces"])).toBeTruthy();

    // One chapter transition between the two scene-bearing groups, without
    // an invented summary sentence.
    const transitions = within(track).getAllByTestId("causality-transition");
    expect(transitions).toHaveLength(1);
    expect(within(transitions[0]).getByText(de["planning.causality.chapterTransition"])).toBeTruthy();

    // The connector labels are real content, not decor: they reach the
    // accessibility tree (only the glyphs stay hidden — a glyph is never
    // its own accessible name), and „Erzwingt" stands in reading order
    // between exactly the two scenes it holds together.
    expect(links[0].getAttribute("aria-hidden")).toBeNull();
    expect(transitions[0].getAttribute("aria-hidden")).toBeNull();
    const forces = within(links[0]).getByText(de["planning.causality.forces"]);
    expect(forces.closest('[aria-hidden="true"]')).toBeNull();
    const scenes = within(track).getAllByTestId("causality-scene");
    expect(scenes[0].compareDocumentPosition(forces) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(scenes[1].compareDocumentPosition(forces) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();
  });

  it("the header chips derive from real counts — chapters, scenes, gaps", async () => {
    await renderCausality();
    const counts = await screen.findByTestId("causality-counts");
    expect(within(counts).getByText(format("planning.storyboard.chaptersCount", { count: 2 }))).toBeTruthy();
    expect(within(counts).getByText(format("planning.storyboard.scenesTotal", { count: 3 }))).toBeTruthy();

    // Scene 2.1 misses both answers: one gap, named as a count, never
    // dressed as a closed chain.
    const chain = await screen.findByTestId("causality-chain");
    expect(within(chain).getByText(format("planning.causality.chainGaps", { count: 1 }))).toBeTruthy();
    expect(within(chain).queryByText(de["planning.causality.chainWhole"])).toBeNull();
    // The diagnostics box counts the same truth.
    const bento = screen.getByTestId("causality-bento");
    expect(within(bento).getByText(format("planning.causality.gapStatus", { count: 1 }))).toBeTruthy();
  });

  it("a gapless chain reads as closed — the real zero, not a wish", async () => {
    api.GET.mockImplementation((path: string, init?: { params?: { path?: { chapter_id?: string } } }) => {
      if (path === "/api/writing/novels/{novel_id}/chapters") {
        return Promise.resolve({
          data: [chapterRow({ id: "c9", title: "Nur Kette", position: 0 })],
          response: ok(),
        });
      }
      if (path === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes") {
        return Promise.resolve({
          data: {
            chapter_id: "c9",
            version_updated_at: "2026-11-18T10:00:00Z",
            scenes: [sceneRow("c9", { id: "s91", position: 1, conflict: "A", resolution: "B", status: "complete" })],
          },
          response: ok(),
        });
      }
      throw new Error(`unexpected GET: ${path}`);
    });
    await renderCausality();
    const chain = await screen.findByTestId("causality-chain");
    expect(within(chain).getByText(de["planning.causality.chainWhole"])).toBeTruthy();
  });

  it("the methodology row and the manuscript door stand on the populated face", async () => {
    const router = await renderCausality();
    await screen.findByTestId("causality-track");
    // All three boxes of the draft's bento, one mapped render.
    const bento = screen.getByTestId("causality-bento");
    expect(within(bento).getByText(de["planning.causality.bento1Title"])).toBeTruthy();
    expect(within(bento).getByText(de["planning.causality.bento1Rule"])).toBeTruthy();
    expect(within(bento).getByText(de["planning.causality.bento2Title"])).toBeTruthy();
    expect(within(bento).getByText(de["planning.causality.bento3Title"])).toBeTruthy();

    // The bottom disclaimer renders its one honest line — the draft's
    // retired sentence, reworded without its banned vocabulary (even
    // negated, the words stay out).
    const note = screen.getByTestId("causality-note");
    expect(within(note).getByText(de["planning.causality.laterNote"])).toBeTruthy();
    expect(note.textContent ?? "").not.toMatch(/Simulation|Verzweigung|Divergenz|Paradox|Twist|What-If/i);

    // The draft's Zum Manuskript door walks to the workspace.
    fireEvent.click(screen.getByTestId("causality-manuscript-door"));
    await waitFor(() => expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}`));
  });
});

describe("the empty novel doors to the storyboard", () => {
  it("a novel without chapters shows the honest banner, not a zero chain", async () => {
    chapters = [];
    const router = await renderCausality();
    const empty = await screen.findByTestId("causality-empty");
    expect(within(empty).getByText(de["planning.causality.empty"])).toBeTruthy();
    expect(screen.queryByTestId("causality-track")).toBeNull();
    expectSiblingDoors();

    fireEvent.click(within(empty).getByRole("button", { name: de["planning.causality.emptyDoor"] }));
    await waitFor(() => expect(router.state.location.pathname).toContain("/planning/storyboard"));
  });

  it("chapters without scenes are unbesetzt too — the banner, not empty groups", async () => {
    // The chapter's aggregate answers an empty scene list — a real
    // chapter whose scenes are all still to be planned.
    chapters = [chapterRow({ id: "c-empty", title: "Leeres Kapitel", position: 0 })];
    api.GET.mockImplementation((path: string, init?: { params?: { path?: { chapter_id?: string } } }) => {
      if (path === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes") {
        return Promise.resolve({
          data: { chapter_id: init?.params?.path?.chapter_id, version_updated_at: "2026-11-18T10:00:00Z", scenes: [] },
          response: ok(),
        });
      }
      return baseGet(path, init);
    });
    await renderCausality();
    const empty = await screen.findByTestId("causality-empty");
    expect(within(empty).getByText(de["planning.causality.emptyNote"])).toBeTruthy();
    expect(screen.queryByTestId("causality-track")).toBeNull();
    expectSiblingDoors();
  });
});

describe("the honest outage keeps the doors", () => {
  it("a chapters outage shows no zero-chain — the failure face with its retry", async () => {
    chaptersFail = true;
    await renderCausality();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["planning.causality.loadFailed"])).toBeTruthy();
    expect(screen.queryByTestId("causality-track")).toBeNull();
    expect(screen.queryByTestId("causality-empty")).toBeNull();
    expectSiblingDoors();

    // The in-place retry re-asks the chapters (and the fan that hangs
    // from them) without a remount.
    chaptersFail = false;
    const chapterAsks = () =>
      api.GET.mock.calls.filter(([path]) => path === "/api/writing/novels/{novel_id}/chapters").length;
    const before = chapterAsks();
    fireEvent.click(within(alert).getByRole("button", { name: de["planning.causality.retry"] }));
    await waitFor(() => expect(chapterAsks()).toBeGreaterThan(before));
    await waitFor(() => expect(screen.getByTestId("causality-track")).toBeTruthy());
  });

  it("a failed fan-out is an outage too — the chain never stands half-current", async () => {
    scenesFail = true;
    await renderCausality();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["planning.causality.loadFailed"])).toBeTruthy();
    expect(screen.queryByTestId("causality-track")).toBeNull();
    expectSiblingDoors();

    scenesFail = false;
    const sceneAsks = () =>
      api.GET.mock.calls.filter(
        ([path]) => path === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes",
      ).length;
    const before = sceneAsks();
    fireEvent.click(within(alert).getByRole("button", { name: de["planning.causality.retry"] }));
    await waitFor(() => expect(sceneAsks()).toBeGreaterThan(before));
    await waitFor(() => expect(screen.getByTestId("causality-track")).toBeTruthy());
  });

  it("pending: the subbar stands, the body waits — no zeros on a guess", async () => {
    let resolveChapters!: (answer: { data: unknown; response: Response }) => void;
    api.GET.mockImplementation((path: string, init?: { params?: { path?: { chapter_id?: string } } }) => {
      if (path === "/api/writing/novels/{novel_id}/chapters") {
        return new Promise<{ data: unknown; response: Response }>((resolve) => {
          resolveChapters = resolve;
        });
      }
      return baseGet(path, init);
    });
    await renderCausality();
    expect(screen.getByRole("status")).toBeTruthy();
    expect(screen.queryByTestId("causality-track")).toBeNull();
    expect(screen.queryByTestId("causality-empty")).toBeNull();
    expect(screen.queryByTestId("causality-counts")).toBeNull();
    expectSiblingDoors();

    resolveChapters({ data: CHAPTERS, response: ok() });
    await waitFor(() => expect(screen.getByTestId("causality-track")).toBeTruthy());
  });
});

describe("the sub-nav doors", () => {
  it("walk to the chronology and the storyboard from the populated face", async () => {
    const router = await renderCausality();
    await screen.findByTestId("causality-track");

    fireEvent.click(within(screen.getByTestId("causality-timeline-door")).getByText(de["planning.timeline.title"]));
    await waitFor(() => expect(router.state.location.pathname).toContain("/planning/timeline"));

    // The second face's own router answers its own navigation.
    const second = await renderCausality();
    await screen.findByTestId("causality-track");
    fireEvent.click(within(screen.getByTestId("causality-storyboard-door")).getByText(de["planning.sub.storyboard"]));
    await waitFor(() => expect(second.state.location.pathname).toContain("/planning/storyboard"));
  });

  it("the verketten door hands to the storyboard — where scenes are chained", async () => {
    const router = await renderCausality();
    await screen.findByTestId("causality-track");
    fireEvent.click(screen.getByTestId("causality-verketten-door"));
    await waitFor(() => expect(router.state.location.pathname).toContain("/planning/storyboard"));
  });
});
