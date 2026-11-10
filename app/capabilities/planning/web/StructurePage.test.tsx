// @vitest-environment jsdom
import { QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@shell/lib/api/client";
import { queryClient } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";
import { bandPercents, readStructure, StructurePage, summarizeBoard } from "./StructurePage";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

const api = client as unknown as {
  GET: ReturnType<typeof vi.fn>;
};

const NOVEL_ID = "novel-1";

function chapterEntry(
  id: string,
  title: string,
  overrides: {
    position?: number;
    word_count?: number;
    sync_status?: string;
    assignment_source?: string;
    stage_key?: string;
  } = {},
) {
  return {
    chapter_id: id,
    title,
    position: overrides.position ?? 0,
    word_count: overrides.word_count ?? 0,
    sync_status: overrides.sync_status ?? "empty",
    assignment_source: overrides.assignment_source ?? "suggested",
    stage_key: overrides.stage_key ?? "setup",
  };
}

function stage(key: string, titleKey: string, from: number, to: number, chapters: ReturnType<typeof chapterEntry>[]) {
  return { key, title_key: titleKey, from, to, chapters };
}

function novel(id: string, title: string) {
  return {
    id,
    title,
    genre: "",
    blurb: "",
    author: "",
    language: "",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  };
}

/** Three acts: 25 / 50 / 25 of the story. */
function makeBoard() {
  return {
    novel_id: NOVEL_ID,
    structure_id: "three-act",
    stages: [
      stage("setup", "storyboard.stage.setup", 0, 0.25, [
        chapterEntry("chapter-b", "Abreise", { position: 1, stage_key: "setup" }),
        chapterEntry("chapter-a", "Ankunft", {
          position: 0,
          word_count: 12,
          sync_status: "planned",
          stage_key: "setup",
        }),
      ]),
      stage("confrontation", "storyboard.stage.confrontation", 0.25, 0.75, [
        chapterEntry("chapter-c", "Heimkehr", {
          position: 2,
          word_count: 30,
          sync_status: "deviated",
          assignment_source: "assigned",
          stage_key: "confrontation",
        }),
      ]),
      stage("resolution", "storyboard.stage.resolution", 0.75, 1.0, []),
    ],
  };
}
let liveBoard = makeBoard();
const liveNovels = [novel(NOVEL_ID, "Die geplante Bucht")];

function mockApi() {
  api.GET.mockImplementation(async (path: string) => {
    if (typeof path === "string" && path.includes("/storyboard")) {
      return { data: liveBoard, response: { ok: true } };
    }
    return { data: liveNovels, response: { ok: true } };
  });
}

function renderPage(entry: string) {
  const structure = createRoute({
    getParentRoute: () => rootRoute,
    path: "planning/structure",
    component: StructurePage,
    validateSearch: (search: { novel?: unknown }): { novel?: string } => ({
      ...(typeof search.novel === "string" && search.novel !== "" ? { novel: search.novel } : {}),
    }),
  });
  const router = createRouter({
    routeTree: rootRoute.addChildren([structure]),
    history: createMemoryHistory({ initialEntries: [entry] }),
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  queryClient.clear();
  liveBoard = makeBoard();
});

describe("readStructure", () => {
  it("passes the aggregate through, and never mistakes an outage for an empty canvas", () => {
    expect(readStructure({ data: liveBoard, response: { ok: true } })).toEqual({
      kind: "ok",
      board: liveBoard,
    });
    expect(readStructure({ data: undefined, response: { ok: true } })).toEqual({
      kind: "failed",
    });
    expect(readStructure({ data: liveBoard, response: { ok: false } })).toEqual({
      kind: "failed",
    });
  });
});

describe("bandPercents", () => {
  it("sizes each band by its share of the tiled span", () => {
    expect(
      bandPercents([
        { from: 0, to: 0.25 },
        { from: 0.25, to: 0.75 },
        { from: 0.75, to: 1.0 },
      ]),
    ).toEqual([25, 50, 25]);
  });

  it("splits evenly instead of dividing by zero when no stage spans anything", () => {
    const shares = bandPercents([
      { from: 0.5, to: 0.5 },
      { from: 0.5, to: 0.5 },
    ]);
    expect(shares).toEqual([50, 50]);
    for (const share of shares) {
      expect(Number.isFinite(share)).toBe(true);
    }
  });
});

describe("summarizeBoard", () => {
  it("counts chapters, words and deviations", () => {
    expect(summarizeBoard(liveBoard)).toEqual({ chapters: 3, words: 42, deviations: 1 });
  });
});

describe("StructurePage bands", () => {
  it("renders one band per stage, sized by its share of the story", async () => {
    mockApi();
    renderPage(`/planning/structure?novel=${NOVEL_ID}`);

    expect(await screen.findByRole("heading", { name: "Structure" })).toBeTruthy();
    const setup = await screen.findByRole("region", { name: "Setup" });
    const confrontation = screen.getByRole("region", { name: "Confrontation" });
    const resolution = screen.getByRole("region", { name: "Resolution" });
    expect(setup.getAttribute("style")).toContain("25%");
    expect(confrontation.getAttribute("style")).toContain("50%");
    expect(resolution.getAttribute("style")).toContain("25%");
  });

  it("orders the chapters inside their band by position", async () => {
    mockApi();
    renderPage(`/planning/structure?novel=${NOVEL_ID}`);

    const setup = await screen.findByRole("region", { name: "Setup" });
    const links = within(setup).getAllByRole("link");
    expect(links.map((link) => link.textContent)).toEqual(["Ankunft", "Abreise"]);
  });

  it("marks the deviated chapter in words, not colour alone", async () => {
    mockApi();
    renderPage(`/planning/structure?novel=${NOVEL_ID}`);

    const confrontation = await screen.findByRole("region", { name: "Confrontation" });
    expect(within(confrontation).getByText("Deviated")).toBeTruthy();
  });

  it("summarizes chapters, words and deviations", async () => {
    mockApi();
    renderPage(`/planning/structure?novel=${NOVEL_ID}`);

    expect(await screen.findByText("3 chapters · 42 words · 1 deviation")).toBeTruthy();
  });

  it("links each chapter to the workspace", async () => {
    mockApi();
    renderPage(`/planning/structure?novel=${NOVEL_ID}`);

    const setup = await screen.findByRole("region", { name: "Setup" });
    const link = within(setup).getByRole("link", { name: "Ankunft" });
    expect(link.getAttribute("href")).toContain(`/novels/${NOVEL_ID}`);
    expect(link.getAttribute("href")).toContain("chapter=chapter-a");
  });

  it("renders a single-chapter novel without dividing by zero", async () => {
    liveBoard = {
      novel_id: NOVEL_ID,
      structure_id: "three-act",
      stages: [
        stage("setup", "storyboard.stage.setup", 0, 0.25, [
          chapterEntry("chapter-a", "Ankunft", { position: 0, word_count: 5, stage_key: "setup" }),
        ]),
        stage("confrontation", "storyboard.stage.confrontation", 0.25, 0.75, []),
        stage("resolution", "storyboard.stage.resolution", 0.75, 1.0, []),
      ],
    };
    mockApi();
    renderPage(`/planning/structure?novel=${NOVEL_ID}`);

    expect(await screen.findByText("1 chapter · 5 words · 0 deviations")).toBeTruthy();
    expect(screen.getByRole("region", { name: "Setup" }).getAttribute("style")).toContain("25%");
    liveBoard = makeBoard();
  });

  it("names the next step when the novel holds no chapters", async () => {
    liveBoard = {
      novel_id: NOVEL_ID,
      structure_id: "three-act",
      stages: [
        stage("setup", "storyboard.stage.setup", 0, 0.25, []),
        stage("confrontation", "storyboard.stage.confrontation", 0.25, 0.75, []),
        stage("resolution", "storyboard.stage.resolution", 0.75, 1.0, []),
      ],
    };
    mockApi();
    renderPage(`/planning/structure?novel=${NOVEL_ID}`);

    expect(await screen.findByText(/Write the first one in the workspace/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Open storyboard" })).toBeTruthy();
    liveBoard = makeBoard();
  });
});
