// @vitest-environment jsdom
/**
 * The workspace page (W4 Task 11) — the read-only scene-centric surface
 * under the real root route and the capability's own route table: the
 * setup gate, the three columns on the rows' own data, the last-edited
 * active scene, scene/chapter selection, the empty faces, the loading
 * skeleton, the error retry and the 404 degrade to the shelf. Only the
 * API client is mocked at its module boundary; the chrome stays real and
 * its book face reads the route param (Task 11's chrome seam).
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import { client, type Activity, type Chapter, type Novel, type Scene, type Storyboard } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { capabilityRoutes } from "@shell/lib/generated/routes";
import { applyLocale } from "@shell/lib/locale";
import { queryClient, takeNovelDeletedElsewhere } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";

const de = catalogs.de;
const NOVEL_ID = "11111111-1111-1111-1111-111111111111";

const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

function ok(): Response {
  return new Response(null, { status: 200 });
}

const NOVEL: Novel = {
  id: NOVEL_ID,
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
};

const CH1: Chapter = {
  id: "c1",
  novel_id: NOVEL_ID,
  title: "Ghost in the Machine",
  position: 0,
  scene_count: 2,
  word_count: 765,
  created_at: "2026-11-01T10:00:00Z",
  updated_at: "2026-11-12T10:00:00Z",
};
const CH2: Chapter = {
  id: "c2",
  novel_id: NOVEL_ID,
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
  body: "Die Vanguard glitt durch den Permafrost.",
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
  body: "Ich kalibrierte die Sensoren.\n\n»Quelle triangulieren«, befahl ich.",
  setting: "Forschungsstation 7",
  story_time: "27. Oktober 2094, 03:14 UTC",
  position: 2,
  word_count: 423,
  created_at: "2026-11-01T10:00:00Z",
  updated_at: "2026-11-14T09:30:00Z",
};
const S21: Scene = {
  id: "s21",
  chapter_id: "c2",
  title: "Sub-Basement",
  body: "Unter der Station lag der Schacht.",
  setting: null,
  story_time: null,
  position: 1,
  word_count: 1090,
  created_at: "2026-11-01T10:00:00Z",
  updated_at: "2026-11-12T07:00:00Z",
};

const ACTIVITY: Activity = {
  points: [],
  streak_days: 0,
  weekly_average: 0,
  today_words: 412,
  daily_goal_words: 500,
  goal_met: false,
  goal_remaining: 88,
};

const STORYBOARD: Storyboard = {
  novel_id: NOVEL_ID,
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

/** What each read answers; a test scripts failures or other populations. */
let novelAnswer: () => Promise<{ data?: unknown; response: Response }>;
let chaptersAnswer: () => Promise<{ data?: unknown; response: Response }>;
let scenesAnswer: (chapterId: string) => Promise<{ data?: unknown; response: Response }>;
let activityAnswer: () => Promise<{ data?: unknown; response: Response }>;
let storyboardAnswer: () => Promise<{ data?: unknown; response: Response }>;
let setupComplete: boolean;

function scriptApi() {
  api.GET.mockImplementation(async (path: string, init?: { params?: { path?: Record<string, string> } }) => {
    if (path === "/api/settings") {
      return { data: { locale: "de", theme: null, author_name: null, email: null }, response: ok() };
    }
    if (path === "/api/setup/status") return { data: { complete: setupComplete }, response: ok() };
    if (path === "/api/writing/novels") return { data: [NOVEL], response: ok() };
    if (path === "/api/writing/novels/{novel_id}") return novelAnswer();
    if (path === "/api/writing/novels/{novel_id}/chapters") return chaptersAnswer();
    if (path === "/api/writing/chapters/{chapter_id}/scenes") {
      return scenesAnswer(init?.params?.path?.chapter_id ?? "");
    }
    if (path === "/api/writing/activity") return activityAnswer();
    if (path === "/api/planning/novels/{novel_id}/storyboard") return storyboardAnswer();
    throw new Error(`unexpected request: ${path}`);
  });
}

async function renderWorkspace(novelId: string = NOVEL_ID) {
  const router = createRouter({
    routeTree: rootRoute.addChildren([...capabilityRoutes]),
    history: createMemoryHistory({ initialEntries: [`/novels/${novelId}`] }),
  });
  await router.load();
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

beforeEach(() => {
  applyLocale("de");
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
  setupComplete = true;
  novelAnswer = async () => ({ data: NOVEL, response: ok() });
  chaptersAnswer = async () => ({ data: [CH1, CH2], response: ok() });
  scenesAnswer = async (chapterId) => ({
    data: chapterId === "c1" ? [S11, S12] : chapterId === "c2" ? [S21] : [],
    response: ok(),
  });
  activityAnswer = async () => ({ data: ACTIVITY, response: ok() });
  storyboardAnswer = async () => ({ data: STORYBOARD, response: ok() });
  scriptApi();
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("the populated workspace", () => {
  it("renders the three columns on the rows' own data — the last-edited scene active", async () => {
    await renderWorkspace();
    // The editor opens on the last-edited scene (S12, updated_at leads).
    expect(
      await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" }),
    ).toBeTruthy();
    expect(screen.getByText("Ich kalibrierte die Sensoren.")).toBeTruthy();
    expect(screen.getByText("Forschungsstation 7 · 27. Oktober 2094, 03:14 UTC")).toBeTruthy();
    expect(screen.getByTestId("workspace-running-head").textContent).toBe("Dead Signal — H. Calder");
    // The tree carries the chapters, scenes and the active marker.
    expect(screen.getByText("Kapitel 1 — Ghost in the Machine")).toBeTruthy();
    expect(screen.getByText("Szene 1 · An Bord der Vanguard")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: /Szene 2 · Das Signal im Permafrost/ }).getAttribute("aria-current"),
    ).toBe("true");
    // The ring and the tension label read their real sources — independent
    // asks, so the assertions wait for them (the scene heading only proves
    // the novel/chapters/scenes reads).
    expect(await screen.findByText("412")).toBeTruthy();
    expect(await screen.findByText("/ 500 W.")).toBeTruthy();
    expect(await screen.findByText("Exposition")).toBeTruthy();
    // The dock's cover miniature is real.
    expect(await screen.findByText("2 % Gesamt")).toBeTruthy();
    // The chrome's book face: the breadcrumb names the route's book, the
    // word chip the book's own count (the param seam, not a pathname parse).
    // The chrome's novels list is its own ask — wait for the chip.
    const topbar = screen.getByRole("banner");
    expect(within(topbar).getByText("Dead Signal")).toBeTruthy();
    expect(await within(topbar).findByText("1.855 Wörter")).toBeTruthy();
    // The tab names the book.
    expect(document.title).toBe("Dead Signal — Narrare");
  });

  it("selecting another scene moves the editor and the marker", async () => {
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    fireEvent.click(screen.getByRole("button", { name: /Szene 1 · Sub-Basement/ }));
    expect(await screen.findByRole("heading", { level: 1, name: "Sub-Basement" })).toBeTruthy();
    expect(screen.getByText("Unter der Station lag der Schacht.")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: /Szene 1 · Sub-Basement/ }).getAttribute("aria-current"),
    ).toBe("true");
    expect(
      screen.getByRole("button", { name: /Szene 2 · Das Signal im Permafrost/ }).getAttribute("aria-current"),
    ).toBeNull();
  });

  it("selecting a chapter opens its first scene", async () => {
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    fireEvent.click(screen.getByRole("button", { name: "Kapitel 2 — Nevada Echoes" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Sub-Basement" })).toBeTruthy();
  });

  it("the chevron collapses a chapter without touching the selection", async () => {
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    fireEvent.click(screen.getByRole("button", { name: "Kapitel 1 einklappen" }));
    expect(screen.queryByText("Szene 1 · An Bord der Vanguard")).toBeNull();
    // The editor keeps its scene — collapsing is a tree affordance only.
    expect(screen.getByRole("heading", { level: 1, name: "Das Signal im Permafrost" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Kapitel 1 ausklappen" }));
    expect(screen.getByText("Szene 1 · An Bord der Vanguard")).toBeTruthy();
  });
});

describe("the empty faces", () => {
  it("the empty book invites the first chapter — both create doors disabled", async () => {
    chaptersAnswer = async () => ({ data: [], response: ok() });
    await renderWorkspace();
    expect(
      await screen.findByRole("heading", { level: 1, name: de["writing.workspace.emptyBook.editorTitle"] }),
    ).toBeTruthy();
    expect(screen.getByText(de["writing.workspace.emptyBook.title"])).toBeTruthy();
    const first = screen.getByRole("button", { name: de["writing.workspace.emptyBook.action"] });
    expect(first.hasAttribute("disabled")).toBe(true);
    // The identity card and the dock stand — the book is real, only empty.
    expect(screen.getByTestId("explorer-identity")).toBeTruthy();
    expect(screen.getByTestId("dock-cover")).toBeTruthy();
  });

  it("the empty chapter explains the scene — D16's real state", async () => {
    chaptersAnswer = async () => ({ data: [{ ...CH1, scene_count: 0, word_count: 0 }], response: ok() });
    scenesAnswer = async () => ({ data: [], response: ok() });
    await renderWorkspace();
    expect(
      await screen.findByRole("heading", { level: 1, name: de["writing.workspace.emptyChapter.title"] }),
    ).toBeTruthy();
    expect(screen.getByText(de["writing.workspace.tree.emptyChapter"])).toBeTruthy();
    const create = screen.getByRole("button", { name: de["writing.workspace.emptyChapter.action"] });
    expect(create.hasAttribute("disabled")).toBe(true);
  });

  it("an empty chapter beside a populated one opens on the last-edited scene, and selects empty on click", async () => {
    chaptersAnswer = async () => ({ data: [CH1, { ...CH2, scene_count: 0, word_count: 0 }], response: ok() });
    scenesAnswer = async (chapterId) => ({
      data: chapterId === "c1" ? [S11, S12] : [],
      response: ok(),
    });
    await renderWorkspace();
    expect(
      await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" }),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Kapitel 2 — Nevada Echoes" }));
    expect(
      await screen.findByRole("heading", { level: 1, name: de["writing.workspace.emptyChapter.title"] }),
    ).toBeTruthy();
  });
});

describe("loading, error and the 404 degrade", () => {
  it("the loading skeleton stands while the reads are in flight — no invented content", async () => {
    let release: (() => void) | undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    novelAnswer = async () => {
      await gate;
      return { data: NOVEL, response: ok() };
    };
    await renderWorkspace();
    expect(await screen.findByRole("status")).toBeTruthy();
    expect(screen.queryByRole("heading", { level: 1, name: "Das Signal im Permafrost" })).toBeNull();
    release?.();
    expect(
      await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" }),
    ).toBeTruthy();
  });

  it("the error face retries into the populated workspace", async () => {
    let failures = 1;
    novelAnswer = async () => {
      if (failures > 0) {
        failures -= 1;
        return { data: undefined, response: new Response(null, { status: 503 }) };
      }
      return { data: NOVEL, response: ok() };
    };
    await renderWorkspace();
    expect(
      await screen.findByRole("heading", { level: 1, name: de["writing.workspace.error.title"] }),
    ).toBeTruthy();
    // The honest body — no browser-cache claim (#887), no offline door.
    expect(screen.getByText(de["writing.workspace.error.body"])).toBeTruthy();
    expect(screen.queryByText(/Offline/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: de["writing.shelf.error.retry"] }));
    expect(
      await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" }),
    ).toBeTruthy();
  });

  it("a 404 degrades to the shelf with the deleted-elsewhere note", async () => {
    novelAnswer = async () => ({ data: undefined, response: new Response(null, { status: 404 }) });
    const router = await renderWorkspace();
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
    // The shelf itself renders (its own reads answer from the script) and
    // carries the note the workspace's degrade recorded — taken once, in
    // the shelf's mount effect (the text waits for that effect's render).
    expect(
      await screen.findByRole("heading", { level: 1, name: de["writing.shelf.title"] }),
    ).toBeTruthy();
    expect(await screen.findByText(de["writing.shelf.deletedElsewhere"])).toBeTruthy();
    expect(takeNovelDeletedElsewhere()).toBe(false);
  });
});

describe("the setup gate", () => {
  it("an unconfigured instance is handed to the welcome before the workspace mounts", async () => {
    setupComplete = false;
    const router = await renderWorkspace();
    await waitFor(() => expect(router.state.location.pathname).toBe("/setup"));
  });
});
