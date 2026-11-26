// @vitest-environment jsdom
/**
 * The workspace page (W4 Task 11) — the read-only scene-centric surface
 * under the real root route and the capability's own route table: the
 * setup gate, the three columns on the rows' own data, the last-edited
 * active scene, scene/chapter selection, the empty faces, the loading
 * skeleton, the error retry and the 404 degrade to the shelf. Only the
 * API client is mocked at its module boundary; the chrome stays real and
 * its book face reads the route param (Task 11's chrome seam).
 *
 * Task 13's CRUD legs: the create flow (empty book → chapter → empty
 * chapter face → scene → editor, D16's canonical path), the delete flows
 * (last scene → empty chapter; active scene → the neighbour; chapter →
 * the cascade and the next chapter), rename/metadata round-trips through
 * the dialogs, and the reorder contract (optimistic order, the 409's
 * stored-ids revert, the refusal's restore, the honest notice + retry).
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// The full-suite run spawns one worker per file (46 on this repo) on a
// four-core box: the default 1 s findBy budget is tighter than the loaded
// jsdom render of the whole chrome + TipTap + router needs. The budget is
// a load allowance, not a lenience — a heading that never renders still
// fails the assertion (the solo runs and the E2E prove the render).
configure({ asyncUtilTimeout: 5000 });

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import { client, type Activity, type Chapter, type Novel, type Scene, type Storyboard } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { capabilityRoutes } from "@shell/lib/generated/routes";
import { applyLocale } from "@shell/lib/locale";
import { queryClient, takeNovelDeletedElsewhere } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";

import { requestDeskFocus } from "./workspace";

const de = catalogs.de;
const NOVEL_ID = "11111111-1111-1111-1111-111111111111";

// jsdom lays out nothing: Element geometry reports zeros, but Range geometry
// is simply missing — and ProseMirror reads Range rects whenever it scrolls
// a selection into view (after typing, after focus). Hand it the same zeros
// the elements already claim, so „nothing to scroll" is the only answer
// (the pre-rebuild ChapterEditor test's own polyfill).
const zeroRect = { top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0, x: 0, y: 0 } as DOMRect;
Range.prototype.getClientRects = function (): DOMRectList {
  return [zeroRect] as unknown as DOMRectList;
};
Range.prototype.getBoundingClientRect = () => zeroRect;

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
  target_words: null,
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
  target_words: null,
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

// Task 13's write doors — each test scripts the answers it asserts on.
let postChapterAnswer: () => Promise<{ data?: unknown; response: Response }>;
let postSceneAnswer: (chapterId: string) => Promise<{ data?: unknown; response: Response }>;
let putChapterAnswer: (chapterId: string, body: unknown) => Promise<{ data?: unknown; response: Response }>;
let putSceneAnswer: (sceneId: string, body: unknown) => Promise<{ data?: unknown; response: Response }>;
let chapterOrderAnswer: (body: { chapter_ids: string[] }) => Promise<{ data?: unknown; error?: unknown; response: Response }>;
let sceneOrderAnswer: (chapterId: string, body: { ids: string[] }) => Promise<{ data?: unknown; error?: unknown; response: Response }>;
let deleteChapterAnswer: (chapterId: string) => Promise<{ data?: unknown; response: Response }>;
let deleteSceneAnswer: (sceneId: string) => Promise<{ data?: unknown; response: Response }>;

const CH3: Chapter = { ...CH2, id: "c3", position: 2, title: "Drittes Kapitel", scene_count: 0, word_count: 0 };
const NEW_CHAPTER: Chapter = { ...CH1, id: "c-new", position: 0, title: "", scene_count: 0, word_count: 0 };
const NEW_SCENE: Scene = { ...S11, id: "s-new", chapter_id: "c-new", position: 1, title: "", body: "", word_count: 0 };

function noContent(): Response {
  return new Response(null, { status: 204 });
}

function scriptApi() {
  api.GET.mockImplementation(async (path: string, init?: { params?: { path?: Record<string, string> } }) => {
    if (path === "/api/settings") {
      return { data: { locale: "de", theme: null, author_name: null, daily_goal_words: 500, email: null }, response: ok() };
    }
    if (path === "/api/writing/series") return { data: [], response: ok() };
    if (path === "/api/setup/status") return { data: { complete: setupComplete }, response: ok() };
    if (path === "/api/writing/novels") return { data: [NOVEL], response: ok() };
    if (path === "/api/writing/novels/{novel_id}") return novelAnswer();
    if (path === "/api/writing/novels/{novel_id}/chapters") return chaptersAnswer();
    if (path === "/api/writing/chapters/{chapter_id}/scenes") {
      return scenesAnswer(init?.params?.path?.chapter_id ?? "");
    }
    if (path === "/api/writing/activity") return activityAnswer();
    if (path === "/api/planning/novels/{novel_id}/storyboard") return storyboardAnswer();
    // The dock header badge's findings read (W5 Task 2) — the shell's
    // seam, answered quiet so the workspace pins stay about the workspace.
    if (path === "/api/knowledge/novels/{novel_id}/findings") return { data: [], response: ok() };
    throw new Error(`unexpected request: ${path}`);
  });
  api.POST.mockImplementation(async (path: string, init?: { params?: { path?: Record<string, string> } }) => {
    if (path === "/api/writing/novels/{novel_id}/chapters") return postChapterAnswer();
    if (path === "/api/writing/chapters/{chapter_id}/scenes") {
      return postSceneAnswer(init?.params?.path?.chapter_id ?? "");
    }
    throw new Error(`unexpected POST: ${path}`);
  });
  api.PUT.mockImplementation(
    async (path: string, init?: { params?: { path?: Record<string, string> }; body?: Record<string, unknown> }) => {
      const params = init?.params?.path ?? {};
      const body = init?.body ?? {};
      if (path === "/api/writing/scenes/{scene_id}") return putSceneAnswer(params.scene_id ?? "", body);
      if (path === "/api/writing/chapters/{chapter_id}") return putChapterAnswer(params.chapter_id ?? "", body);
      if (path === "/api/writing/novels/{novel_id}/chapter-order") {
        return chapterOrderAnswer(body as { chapter_ids: string[] });
      }
      if (path === "/api/writing/chapters/{chapter_id}/scene-order") {
        return sceneOrderAnswer(params.chapter_id ?? "", body as { ids: string[] });
      }
      throw new Error(`unexpected PUT: ${path}`);
    },
  );
  api.DELETE.mockImplementation(async (path: string, init?: { params?: { path?: Record<string, string> } }) => {
    const params = init?.params?.path ?? {};
    if (path === "/api/writing/chapters/{chapter_id}") return deleteChapterAnswer(params.chapter_id ?? "");
    if (path === "/api/writing/scenes/{scene_id}") return deleteSceneAnswer(params.scene_id ?? "");
    throw new Error(`unexpected DELETE: ${path}`);
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
  // TipTap's platform detection reads userAgent — the stub must carry it.
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"], userAgent: "jsdom" });
  setupComplete = true;
  novelAnswer = async () => ({ data: NOVEL, response: ok() });
  chaptersAnswer = async () => ({ data: [CH1, CH2], response: ok() });
  scenesAnswer = async (chapterId) => ({
    data: chapterId === "c1" ? [S11, S12] : chapterId === "c2" ? [S21] : [],
    response: ok(),
  });
  activityAnswer = async () => ({ data: ACTIVITY, response: ok() });
  storyboardAnswer = async () => ({ data: STORYBOARD, response: ok() });
  postChapterAnswer = async () => ({ data: NEW_CHAPTER, response: ok() });
  postSceneAnswer = async () => ({ data: NEW_SCENE, response: ok() });
  putChapterAnswer = async (chapterId, body) => ({
    data: { ...CH1, id: chapterId, ...(body as { title?: string }) },
    response: ok(),
  });
  putSceneAnswer = async (sceneId, body) => ({
    data: { ...S12, id: sceneId, ...(body as Partial<Scene>) },
    response: ok(),
  });
  chapterOrderAnswer = async () => ({ data: undefined, response: noContent() });
  sceneOrderAnswer = async () => ({ data: undefined, response: noContent() });
  deleteChapterAnswer = async () => ({ data: undefined, response: noContent() });
  deleteSceneAnswer = async () => ({ data: undefined, response: noContent() });
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
    // The editor body is TipTap's async render — it lands a tick after the
    // heading (the scene title is cache-immediate). Wait for it, don't race it.
    expect(await screen.findByText("Unter der Station lag der Schacht.")).toBeTruthy();
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
  it("the empty book invites the first chapter — the door live (Task 13)", async () => {
    chaptersAnswer = async () => ({ data: [], response: ok() });
    await renderWorkspace();
    expect(
      await screen.findByRole("heading", { level: 1, name: de["writing.workspace.emptyBook.editorTitle"] }),
    ).toBeTruthy();
    expect(screen.getByText(de["writing.workspace.emptyBook.title"])).toBeTruthy();
    const first = screen.getByRole("button", { name: de["writing.workspace.emptyBook.action"] });
    expect(first.hasAttribute("disabled")).toBe(false);
    // The identity card and the dock stand — the book is real, only empty.
    expect(screen.getByTestId("explorer-identity")).toBeTruthy();
    expect(screen.getByTestId("dock-cover")).toBeTruthy();
  });

  it("the empty chapter explains the scene — D16's real state, the door live", async () => {
    chaptersAnswer = async () => ({ data: [{ ...CH1, scene_count: 0, word_count: 0 }], response: ok() });
    scenesAnswer = async () => ({ data: [], response: ok() });
    await renderWorkspace();
    expect(
      await screen.findByRole("heading", { level: 1, name: de["writing.workspace.emptyChapter.title"] }),
    ).toBeTruthy();
    expect(screen.getByText(de["writing.workspace.tree.emptyChapter"])).toBeTruthy();
    const create = screen.getByRole("button", { name: de["writing.workspace.emptyChapter.action"] });
    expect(create.hasAttribute("disabled")).toBe(false);
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
    // The round-2 corrected tile's copy, VERBATIM (d8e51c9d, PR #889 —
    // #887's ruling): the library's timeout named, the autosave reassurance
    // the coordinator ruled ships ahead of Task 12's engine (PR 3, this
    // wave), the retry alone.
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Die Bibliothek antwortet im Moment nicht rechtzeitig.",
      }),
    ).toBeTruthy();
    expect(
      screen.getByText("Deine Änderungen bleiben im Editor, bis sie gesichert sind."),
    ).toBeTruthy();
    expect(screen.getByText(de["writing.workspace.error.body"])).toBeTruthy();
    // The catalog's sentence rides the card — never the seam's own English.
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain(de["errors.server"]);
    expect(alert.textContent).not.toContain("novel unavailable");
    // The offline door is gone — the retry stands alone.
    expect(screen.queryByText(/Offline/)).toBeNull();
    expect(within(alert).getAllByRole("button")).toHaveLength(1);
    fireEvent.click(within(alert).getByRole("button", { name: "Erneut versuchen" }));
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

describe("the leave guard (Kachel 10) — flush first, ask only on a failed write", () => {
  /** Focus the live editor and type — the real TipTap path. The leave action
   *  under test flushes (clearing the debounce), so no timer wait is owed:
   *  the unsaved pill stands the instant a keystroke lands. */
  async function typeIntoScene(text: string) {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    const prose = de["writing.workspace.editor.proseLabel"];
    await screen.findByRole("textbox", { name: prose });
    await waitFor(() => expect(screen.getByRole("textbox", { name: prose }).textContent).not.toBe(""));
    screen.getByRole("textbox", { name: prose }).focus();
    await user.keyboard(text);
    expect(await screen.findByText(de["writing.workspace.ribbon.unsaved"])).toBeTruthy();
  }

  it("a healthy pending body flushes on a scene switch — no dialog", async () => {
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    await typeIntoScene(" Ein neuer Satz.");
    fireEvent.click(screen.getByRole("button", { name: /Szene 1 · Sub-Basement/ }));
    await waitFor(() => expect(api.PUT).toHaveBeenCalled());
    expect(api.PUT.mock.calls[0][1].body.body).toContain("Ein neuer Satz.");
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(await screen.findByRole("heading", { level: 1, name: "Sub-Basement" })).toBeTruthy();
  });

  it("a failed save raises the guard on a switch — Bleiben stays, Verwerfen goes", async () => {
    api.PUT.mockResolvedValue({ data: undefined, response: new Response(null, { status: 500 }) });
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    await typeIntoScene(" Ungesichert.");

    fireEvent.click(screen.getByRole("button", { name: /Szene 1 · Sub-Basement/ }));
    expect(await screen.findByRole("alertdialog")).toBeTruthy();
    expect(screen.getByText(de["writing.workspace.guard.title"])).toBeTruthy();
    expect(screen.getByText(de["writing.workspace.foot.failed"])).toBeTruthy();

    // Bleiben stays on the same scene, the failed body intact.
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.guard.stay"] }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(screen.getByRole("heading", { level: 1, name: "Das Signal im Permafrost" })).toBeTruthy();
    expect(screen.getByText(de["writing.workspace.foot.failed"])).toBeTruthy();

    // Verwerfen und verlassen drops the draft and switches.
    fireEvent.click(screen.getByRole("button", { name: /Szene 1 · Sub-Basement/ }));
    expect(await screen.findByRole("alertdialog")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.guard.discard"] }));
    expect(await screen.findByRole("heading", { level: 1, name: "Sub-Basement" })).toBeTruthy();
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });

  it("a failed save blocks a route leave — the resolver holds navigation until the answer", async () => {
    api.PUT.mockResolvedValue({ data: undefined, response: new Response(null, { status: 500 }) });
    const router = await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    await typeIntoScene(" Ungesichert.");

    // A route leave (the topbar's Manuscripts link path) flushes, fails, blocks.
    // The blocker holds the navigate promise until the dialog is answered, so
    // it is fired, not awaited — the resolver raises the guard meanwhile.
    void router.navigate({ to: "/" });
    expect(await screen.findByRole("alertdialog")).toBeTruthy();
    expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}`);

    // Bleiben resets the leave — still on the workspace.
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.guard.stay"] }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}`);

    // Verwerfen discards and proceeds to the shelf.
    void router.navigate({ to: "/" });
    expect(await screen.findByRole("alertdialog")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.guard.discard"] }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
  });

  it("a clean workspace leaves without a dialog", async () => {
    const router = await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    await router.navigate({ to: "/" });
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(api.PUT).not.toHaveBeenCalled();
  });
});

// --- Task 13: the tree's CRUD goes live ------------------------------------

describe("the create flow — D16's canonical new chapter", () => {
  it("empty book → first chapter → the empty-chapter face → first scene → the editor", async () => {
    // The world the refetch reads after each write — switched before the
    // click, so the invalidation's ask lands on the post-write truth.
    let chapterCreated = false;
    let sceneCreated = false;
    chaptersAnswer = async () => ({ data: chapterCreated ? [NEW_CHAPTER] : [], response: ok() });
    scenesAnswer = async () => ({ data: sceneCreated ? [NEW_SCENE] : [], response: ok() });
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: de["writing.workspace.emptyBook.editorTitle"] });

    // The invitation door creates the chapter — zero scenes, the honest
    // empty title — and the page selects it: the empty-chapter face.
    chapterCreated = true;
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.emptyBook.action"] }));
    await waitFor(() => expect(api.POST).toHaveBeenCalled());
    expect(api.POST.mock.calls[0][0]).toBe("/api/writing/novels/{novel_id}/chapters");
    expect(api.POST.mock.calls[0][1].body).toEqual({ title: "" });
    expect(
      await screen.findByRole("heading", { level: 1, name: de["writing.workspace.emptyChapter.title"] }),
    ).toBeTruthy();
    expect(screen.getByText(de["writing.workspace.tree.emptyChapter"])).toBeTruthy();

    // Kachel 4's door creates the scene under the empty chapter and opens
    // the editor on it — born empty, ready for the first word.
    sceneCreated = true;
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.emptyChapter.action"] }));
    await waitFor(() => expect(api.POST).toHaveBeenCalledTimes(2));
    expect(api.POST.mock.calls[1][0]).toBe("/api/writing/chapters/{chapter_id}/scenes");
    expect(api.POST.mock.calls[1][1].params.path.chapter_id).toBe("c-new");
    expect(api.POST.mock.calls[1][1].body).toEqual({ title: "", body: "" });
    expect(await screen.findByRole("textbox", { name: de["writing.workspace.editor.proseLabel"] })).toBeTruthy();
    expect(
      screen.getByRole("heading", { level: 1, name: de["writing.workspace.untitledScene"] }),
    ).toBeTruthy();
  });

  it("the tree's scene door creates under the active chapter and selects the new scene", async () => {
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    // A collapsed chapter opens for its new scene — the active row stands
    // visible (the select-a-chapter rule's discipline).
    fireEvent.click(screen.getByRole("button", { name: "Kapitel 1 einklappen" }));
    expect(screen.queryByText("Szene 1 · An Bord der Vanguard")).toBeNull();
    scenesAnswer = async (chapterId) => ({
      data: chapterId === "c1" ? [S11, S12, { ...NEW_SCENE, id: "s-new", chapter_id: "c1" }] : [S21],
      response: ok(),
    });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.tree.newScene"] }));
    await waitFor(() => expect(api.POST).toHaveBeenCalled());
    expect(api.POST.mock.calls[0][1].params.path.chapter_id).toBe("c1");
    expect(
      await screen.findByRole("heading", { level: 1, name: de["writing.workspace.untitledScene"] }),
    ).toBeTruthy();
    expect(screen.getByText("Szene 1 · An Bord der Vanguard")).toBeTruthy();
  });

  it("a refused create names the loss-free notice under the tree — the retry re-runs it", async () => {
    postChapterAnswer = async () => ({ data: undefined, response: new Response(null, { status: 503 }) });
    chaptersAnswer = async () => ({ data: [], response: ok() });
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: de["writing.workspace.emptyBook.editorTitle"] });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.emptyBook.action"] }));
    const notice = await screen.findByTestId("explorer-notice");
    expect(within(notice).getByText(de["writing.workspace.crud.createChapterError"])).toBeTruthy();
    // The retry re-runs the very create; the landed chapter opens its face.
    postChapterAnswer = async () => ({ data: NEW_CHAPTER, response: ok() });
    chaptersAnswer = async () => ({ data: [NEW_CHAPTER], response: ok() });
    scenesAnswer = async () => ({ data: [], response: ok() });
    fireEvent.click(within(notice).getByRole("button", { name: de["writing.shelf.error.retry"] }));
    // (the answers above were switched before the retry click — the
    // invalidation's refetch reads the post-create world)
    expect(
      await screen.findByRole("heading", { level: 1, name: de["writing.workspace.emptyChapter.title"] }),
    ).toBeTruthy();
    expect(screen.queryByTestId("explorer-notice")).toBeNull();
  });
});

describe("the delete flows — always allowed, the cascade honest", () => {
  async function openSceneMenu(sceneLabel: RegExp) {
    const row = screen.getByRole("button", { name: sceneLabel }).closest("[data-testid^='tree-scene-']");
    const trigger = within(row as HTMLElement).getByRole("button", {
      name: de["writing.workspace.tree.sceneOptions"],
    });
    fireEvent.click(trigger);
  }

  it("the last scene goes — the chapter stands empty (D16), the counts read zero", async () => {
    chaptersAnswer = async () => ({ data: [{ ...CH1, scene_count: 1, word_count: 342 }], response: ok() });
    scenesAnswer = async () => ({ data: [S11], response: ok() });
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "An Bord der Vanguard" });

    await openSceneMenu(/Szene 1 · An Bord der Vanguard/);
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.tree.delete"] }));
    const dialog = await screen.findByRole("alertdialog");
    expect(
      within(dialog).getByText("«An Bord der Vanguard» wird endgültig gelöscht. Das Kapitel bleibt bestehen."),
    ).toBeTruthy();
    chaptersAnswer = async () => ({ data: [{ ...CH1, scene_count: 0, word_count: 0 }], response: ok() });
    scenesAnswer = async () => ({ data: [], response: ok() });
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.workspace.crud.deleteConfirm"] }));
    await waitFor(() => expect(api.DELETE).toHaveBeenCalled());
    expect(api.DELETE.mock.calls[0][0]).toBe("/api/writing/scenes/{scene_id}");
    expect(
      await screen.findByRole("heading", { level: 1, name: de["writing.workspace.emptyChapter.title"] }),
    ).toBeTruthy();
    expect(screen.getByText(de["writing.workspace.tree.emptyChapter"])).toBeTruthy();
    expect(screen.getByText("Kapitel 1 — Ghost in the Machine")).toBeTruthy();
  });

  it("deleting the active scene selects its neighbour — and drops the dead scene's draft", async () => {
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    // A pending body on the active scene — the delete must discard it,
    // never flush it into a row that no longer exists.
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    screen.getByRole("textbox", { name: de["writing.workspace.editor.proseLabel"] }).focus();
    await user.keyboard(" Ungesichert.");
    expect(await screen.findByText(de["writing.workspace.ribbon.unsaved"])).toBeTruthy();

    await openSceneMenu(/Szene 2 · Das Signal im Permafrost/);
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.tree.delete"] }));
    chaptersAnswer = async () => ({ data: [{ ...CH1, scene_count: 1, word_count: 342 }, CH2], response: ok() });
    scenesAnswer = async (chapterId) => ({ data: chapterId === "c1" ? [S11] : [S21], response: ok() });
    fireEvent.click(
      await screen.findByRole("button", { name: de["writing.workspace.crud.deleteConfirm"] }),
    );
    await waitFor(() => expect(api.DELETE).toHaveBeenCalled());
    // The neighbour (the previous scene — the deleted one was the last).
    expect(await screen.findByRole("heading", { level: 1, name: "An Bord der Vanguard" })).toBeTruthy();
    // The discarded draft never reached the wire: no PUT to the dead scene.
    const deadPuts = api.PUT.mock.calls.filter(
      (call) => call[0] === "/api/writing/scenes/{scene_id}" && call[1].params.path.scene_id === "s12",
    );
    expect(deadPuts).toEqual([]);
  });

  it("deleting a chapter cascades its scenes and opens the neighbour — the last chapter leaves the empty book", async () => {
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    const trigger = screen.getAllByRole("button", { name: de["writing.workspace.tree.chapterOptions"] })[0];
    fireEvent.click(trigger);
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.tree.delete"] }));
    const dialog = await screen.findByRole("alertdialog");
    expect(
      within(dialog).getByText("«Ghost in the Machine» wird mit 2 Szenen endgültig gelöscht."),
    ).toBeTruthy();
    chaptersAnswer = async () => ({ data: [{ ...CH2, position: 0 }], response: ok() });
    scenesAnswer = async () => ({ data: [S21], response: ok() });
    fireEvent.click(within(dialog).getByRole("button", { name: de["writing.workspace.crud.deleteConfirm"] }));
    await waitFor(() => expect(api.DELETE).toHaveBeenCalled());
    expect(api.DELETE.mock.calls[0][0]).toBe("/api/writing/chapters/{chapter_id}");
    // The neighbour chapter's first scene opens; the dead chapter's scene
    // list is retired from the cache.
    expect(await screen.findByRole("heading", { level: 1, name: "Sub-Basement" })).toBeTruthy();
    expect(screen.queryByText("Kapitel 1 — Ghost in the Machine")).toBeNull();
    expect(queryClient.getQueryData(["scenes", "c1"])).toBeUndefined();

    // The last chapter goes — the empty book's invitation stands.
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.tree.chapterOptions"] }));
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.tree.delete"] }));
    chaptersAnswer = async () => ({ data: [], response: ok() });
    scenesAnswer = async () => ({ data: [], response: ok() });
    fireEvent.click(
      await screen.findByRole("button", { name: de["writing.workspace.crud.deleteConfirm"] }),
    );
    expect(
      await screen.findByRole("heading", { level: 1, name: de["writing.workspace.emptyBook.editorTitle"] }),
    ).toBeTruthy();
  });

  it("Abbrechen keeps the chapter — no write, the tree stands", async () => {
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    fireEvent.click(screen.getAllByRole("button", { name: de["writing.workspace.tree.chapterOptions"] })[0]);
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.tree.delete"] }));
    fireEvent.click(await screen.findByRole("button", { name: de["writing.workspace.crud.cancel"] }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(api.DELETE).not.toHaveBeenCalled();
    expect(screen.getByText("Kapitel 1 — Ghost in the Machine")).toBeTruthy();
  });
});

describe("rename and metadata — the dialog round-trips", () => {
  it("a chapter rename lands the title and the tree speaks it", async () => {
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    fireEvent.click(screen.getAllByRole("button", { name: de["writing.workspace.tree.chapterOptions"] })[0]);
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.tree.rename"] }));
    const input = await screen.findByRole("textbox", { name: de["writing.workspace.crud.titleLabel"] });
    fireEvent.change(input, { target: { value: "Der neue Name" } });
    chaptersAnswer = async () => ({ data: [{ ...CH1, title: "Der neue Name" }, CH2], response: ok() });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    await waitFor(() => expect(api.PUT).toHaveBeenCalled());
    expect(api.PUT.mock.calls[0][0]).toBe("/api/writing/chapters/{chapter_id}");
    expect(api.PUT.mock.calls[0][1].body).toEqual({ title: "Der neue Name" });
    expect(await screen.findByText("Kapitel 1 — Der neue Name")).toBeTruthy();
  });

  it("a scene edit carries the labels — the overline appears, a clear removes it", async () => {
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    // S12 carries both labels; clear them — the overline goes (null carried).
    const row = screen
      .getByRole("button", { name: /Szene 2 · Das Signal im Permafrost/ })
      .closest("[data-testid^='tree-scene-']") as HTMLElement;
    fireEvent.click(within(row).getByRole("button", { name: de["writing.workspace.tree.sceneOptions"] }));
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.tree.editScene"] }));
    const setting = await screen.findByRole("textbox", { name: de["writing.workspace.crud.settingLabel"] });
    const storyTime = screen.getByRole("textbox", { name: de["writing.workspace.crud.storyTimeLabel"] });
    fireEvent.change(setting, { target: { value: "" } });
    fireEvent.change(storyTime, { target: { value: "" } });
    scenesAnswer = async (chapterId) => ({
      data: chapterId === "c1" ? [S11, { ...S12, setting: null, story_time: null }] : [S21],
      response: ok(),
    });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    await waitFor(() => expect(api.PUT).toHaveBeenCalled());
    expect(api.PUT.mock.calls[0][1].body).toEqual({
      title: "Das Signal im Permafrost",
      setting: null,
      story_time: null,
    });
    await waitFor(() => expect(screen.queryByTestId("workspace-overline")).toBeNull());

    // And back: a carried label rides trimmed, the overline returns.
    fireEvent.click(within(row).getByRole("button", { name: de["writing.workspace.tree.sceneOptions"] }));
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.tree.editScene"] }));
    fireEvent.change(
      await screen.findByRole("textbox", { name: de["writing.workspace.crud.settingLabel"] }),
      { target: { value: "  Hafen bei Nacht  " } },
    );
    scenesAnswer = async (chapterId) => ({
      data: chapterId === "c1" ? [S11, { ...S12, setting: "Hafen bei Nacht", story_time: null }] : [S21],
      response: ok(),
    });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    await waitFor(() => expect(api.PUT).toHaveBeenCalledTimes(2));
    expect(api.PUT.mock.calls[1][1].body.setting).toBe("Hafen bei Nacht");
    expect(await screen.findByTestId("workspace-overline")).toBeTruthy();
    expect(screen.getByText("Hafen bei Nacht")).toBeTruthy();
  });
});

describe("the reorder contract — optimistic, the 409 honest, the retry real", () => {
  function chapterOrderOnScreen(): string[] {
    return screen
      .getAllByText(/^Kapitel \d+ — /)
      .map((node) => (node.textContent ?? "").replace(/^Kapitel \d+ — /, ""));
  }

  it("a keyboard step PUTs the whole rail — the tree flips before the answer", async () => {
    let release: (() => void) | undefined;
    chapterOrderAnswer = async () => {
      await new Promise<void>((resolve) => {
        release = resolve;
      });
      return { data: undefined, response: noContent() };
    };
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    fireEvent.keyDown(screen.getByRole("button", { name: "Kapitel 1 verschieben" }), { key: "ArrowDown" });
    // The optimistic order stands while the PUT is on the wire — the
    // positions renumbered (Nevada Echoes leads as Kapitel 1). The cache
    // notification lands a microtask later; the gated PUT has not answered.
    await waitFor(() =>
      expect(chapterOrderOnScreen()).toEqual(["Nevada Echoes", "Ghost in the Machine"]),
    );
    await waitFor(() => expect(api.PUT).toHaveBeenCalled());
    expect(api.PUT.mock.calls[0][0]).toBe("/api/writing/novels/{novel_id}/chapter-order");
    expect(api.PUT.mock.calls[0][1].body).toEqual({ chapter_ids: ["c2", "c1"] });
    release?.();
    await waitFor(() => expect(screen.queryByTestId("explorer-notice")).toBeNull());
  });

  it("a scene step PUTs the whole chapter under its own door", async () => {
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    fireEvent.keyDown(screen.getByRole("button", { name: "Szene 1 in Kapitel 1 verschieben" }), {
      key: "ArrowDown",
    });
    await waitFor(() => expect(api.PUT).toHaveBeenCalled());
    expect(api.PUT.mock.calls[0][0]).toBe("/api/writing/chapters/{chapter_id}/scene-order");
    expect(api.PUT.mock.calls[0][1].params.path.chapter_id).toBe("c1");
    expect(api.PUT.mock.calls[0][1].body).toEqual({ ids: ["s12", "s11"] });
  });

  it("a 409 whose stored ids the cache holds reverts to them — no refetch, the notice stands", async () => {
    chapterOrderAnswer = async () => ({
      data: undefined,
      error: { detail: { code: "order_mismatch", chapter_ids: ["c1", "c2"] } },
      response: new Response(null, { status: 409 }),
    });
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    const getsBefore = api.GET.mock.calls.filter(
      (call) => call[0] === "/api/writing/novels/{novel_id}/chapters",
    ).length;
    fireEvent.keyDown(screen.getByRole("button", { name: "Kapitel 1 verschieben" }), { key: "ArrowDown" });
    const notice = await screen.findByTestId("explorer-notice");
    expect(within(notice).getByText(de["writing.workspace.crud.reorderConflict"])).toBeTruthy();
    // The stored order is back — the arrangement the server named.
    expect(chapterOrderOnScreen()).toEqual(["Ghost in the Machine", "Nevada Echoes"]);
    const getsAfter = api.GET.mock.calls.filter(
      (call) => call[0] === "/api/writing/novels/{novel_id}/chapters",
    ).length;
    expect(getsAfter).toBe(getsBefore);
  });

  it("a 409 naming a row the cache lacks refetches the truth — the second tab's chapter appears", async () => {
    chapterOrderAnswer = async () => ({
      data: undefined,
      error: { detail: { code: "order_mismatch", chapter_ids: ["c1", "c2", "c3"] } },
      response: new Response(null, { status: 409 }),
    });
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    chaptersAnswer = async () => ({ data: [CH1, CH2, CH3], response: ok() });
    scenesAnswer = async (chapterId) => ({
      data: chapterId === "c1" ? [S11, S12] : chapterId === "c2" ? [S21] : [],
      response: ok(),
    });
    fireEvent.keyDown(screen.getByRole("button", { name: "Kapitel 1 verschieben" }), { key: "ArrowDown" });
    expect(await screen.findByText("Kapitel 3 — Drittes Kapitel")).toBeTruthy();
    expect(screen.getByTestId("explorer-notice")).toBeTruthy();
    // The conflict's retry asks the truth again — a refetch, never the
    // stale arrangement re-sent.
    const putsBefore = api.PUT.mock.calls.length;
    fireEvent.click(
      within(screen.getByTestId("explorer-notice")).getByRole("button", {
        name: de["writing.shelf.error.retry"],
      }),
    );
    await waitFor(() =>
      expect(
        api.GET.mock.calls.filter((call) => call[0] === "/api/writing/novels/{novel_id}/chapters").length,
      ).toBeGreaterThan(1),
    );
    expect(api.PUT.mock.calls.length).toBe(putsBefore);
    expect(screen.queryByTestId("explorer-notice")).toBeNull();
  });

  it("a refused reorder restores the order and the retry re-sends the very arrangement", async () => {
    let failures = 1;
    chapterOrderAnswer = async () => {
      if (failures > 0) {
        failures -= 1;
        return { data: undefined, response: new Response(null, { status: 503 }) };
      }
      return { data: undefined, response: noContent() };
    };
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    fireEvent.keyDown(screen.getByRole("button", { name: "Kapitel 1 verschieben" }), { key: "ArrowDown" });
    const notice = await screen.findByTestId("explorer-notice");
    expect(within(notice).getByText(de["writing.workspace.crud.reorderError"])).toBeTruthy();
    // The pre-drag order stands again — nothing lost.
    expect(chapterOrderOnScreen()).toEqual(["Ghost in the Machine", "Nevada Echoes"]);
    fireEvent.click(within(notice).getByRole("button", { name: de["writing.shelf.error.retry"] }));
    await waitFor(() => expect(api.PUT).toHaveBeenCalledTimes(2));
    expect(api.PUT.mock.calls[1][1].body).toEqual({ chapter_ids: ["c2", "c1"] });
    await waitFor(() => expect(screen.queryByTestId("explorer-notice")).toBeNull());
    expect(chapterOrderOnScreen()).toEqual(["Nevada Echoes", "Ghost in the Machine"]);
  });

  it("the notice dismisses — the tree stands as it is", async () => {
    chapterOrderAnswer = async () => ({ data: undefined, response: new Response(null, { status: 503 }) });
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    fireEvent.keyDown(screen.getByRole("button", { name: "Kapitel 1 verschieben" }), { key: "ArrowDown" });
    const notice = await screen.findByTestId("explorer-notice");
    fireEvent.click(
      within(notice).getByRole("button", { name: de["writing.workspace.crud.noticeClose"] }),
    );
    expect(screen.queryByTestId("explorer-notice")).toBeNull();
  });
});

describe("the continuation wiring (Task 16) — the page's own doors", () => {
  /** The SSE door stubbed at the global boundary — the frames are the
   *  kernel's own bytes, the typed client stays mocked for the reads. */
  function stubStream(chunks: readonly string[]) {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
        controller.close();
      },
    });
    const fetchMock = vi.fn(async () =>
      new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } }),
    );
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }

  const PROSE = de["writing.workspace.editor.proseLabel"];
  const PILL = /Vorschlag übernehmen/;

  /** Type into the live prose — the real TipTap path, the unsaved pill the
   *  proof the draft stands (the leave guard's own helper discipline). The
   *  ask under test flushes (clearing the debounce), so no timer wait is
   *  owed. */
  async function typeIntoScene(text: string) {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await screen.findByRole("textbox", { name: PROSE });
    await waitFor(() => expect(screen.getByRole("textbox", { name: PROSE }).textContent).not.toBe(""));
    screen.getByRole("textbox", { name: PROSE }).focus();
    await user.keyboard(text);
    expect(await screen.findByText(de["writing.workspace.ribbon.unsaved"])).toBeTruthy();
  }

  async function openWithPendingGhost() {
    stubStream(['data: {"delta": "Der Nebel hob sich."}\n\n', "event: done\ndata: {}\n\n"]);
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.promptBar.continue"] }));
    expect(await screen.findByRole("button", { name: PILL })).toBeTruthy();
  }

  it("typing dismisses the pending ghost — the writer's words win", async () => {
    await openWithPendingGhost();
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    screen.getByRole("textbox", { name: PROSE }).focus();
    await user.keyboard("X");
    await waitFor(() => expect(screen.queryByRole("button", { name: PILL })).toBeNull());
    expect(screen.queryByTestId("ghost-preview")).toBeNull();
    // The typed word stands in the prose — the dismissal dropped the
    // proposal, never the writer's own edit.
    expect(screen.getByRole("textbox", { name: PROSE }).textContent).toContain("X");
  });

  it("Esc dismisses the pending ghost — the ghost owns it first", async () => {
    await openWithPendingGhost();
    fireEvent.keyDown(screen.getByRole("textbox", { name: PROSE }), { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("button", { name: PILL })).toBeNull());
    expect(screen.queryByTestId("ghost-preview")).toBeNull();
  });

  it("a quick pill's label rides the prompt body — the round-trip", async () => {
    const fetchMock = stubStream([
      'data: {"delta": "Der Nebel hob sich."}\n\n',
      "event: done\ndata: {}\n\n",
    ]);
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    fireEvent.click(
      screen.getByRole("button", { name: de["writing.workspace.promptBar.pillTension"] }),
    );
    expect(await screen.findByRole("button", { name: PILL })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/writing/scenes/${S12.id}/continue`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ prompt: "Spannungsspitze einbauen" }),
      }),
    );
  });

  it("a running stream is not an unsaved edit — a route leave passes without the guard", async () => {
    // The streaming phase itself, held open deterministically: one delta,
    // then the wire keeps running (no done). The E2E's fake crosses localhost
    // too fast to hold mid-flight (#899's boundary) — the resting face rides
    // the real-stack legs; here the running face asks the guard's question.
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"delta": "Der Nebel hob sich."}\n\n'));
      },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } }),
      ),
    );
    const router = await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.promptBar.continue"] }));
    // The streaming face stands — the ARIA chip over the growing preview,
    // not the pending pill (the wire never reaches done).
    expect(await screen.findByTestId("ghost-preview")).toBeTruthy();
    expect(screen.getByText(de["writing.workspace.ghost.writing"])).toBeTruthy();
    expect(screen.queryByRole("button", { name: PILL })).toBeNull();

    // The leave: no draft, so the flush gate passes clean — no guard, no write.
    await router.navigate({ to: "/" });
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(api.PUT).not.toHaveBeenCalled();
  }, 10000);

  it("a pending body flushes before the ask — the PUT lands before /continue", async () => {
    // The order oracle: the save seam and the SSE door both record, and the
    // save must come first — the ghost continues the SAVED body, never the
    // stale row (the leave guard's flush-first rule, the ask's own door).
    const order: string[] = [];
    putSceneAnswer = async (sceneId, body) => {
      order.push("put");
      return { data: { ...S12, id: sceneId, ...(body as Partial<Scene>) }, response: ok() };
    };
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"delta": "Der Nebel hob sich."}\n\n'));
        controller.enqueue(encoder.encode("event: done\ndata: {}\n\n"));
        controller.close();
      },
    });
    const fetchMock = vi.fn(async () => {
      order.push("continue");
      return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
    });
    vi.stubGlobal("fetch", fetchMock);
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    await typeIntoScene(" Neue Worte.");

    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.promptBar.continue"] }));
    expect(await screen.findByRole("button", { name: PILL })).toBeTruthy();
    expect(order).toEqual(["put", "continue"]);
    expect(api.PUT).toHaveBeenCalledTimes(1);
    expect(api.PUT.mock.calls[0][1].body.body).toContain("Neue Worte.");
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/writing/scenes/${S12.id}/continue`,
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("a failed flush keeps the ask home — the autosave's failure face stands", async () => {
    const fetchMock = stubStream([
      'data: {"delta": "Der Nebel hob sich."}\n\n',
      "event: done\ndata: {}\n\n",
    ]);
    putSceneAnswer = async () => ({ data: undefined, response: new Response(null, { status: 500 }) });
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    await typeIntoScene(" Ungesichert.");

    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.promptBar.continue"] }));
    // The flush tried and failed — the writer saves first: the save's own
    // failure face answers, and no continue request ever leaves.
    expect(await screen.findByText(de["writing.workspace.foot.failed"])).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.queryByTestId("ghost-preview")).toBeNull();
    expect(screen.queryByTestId("ghost-error")).toBeNull();
    expect(screen.queryByRole("button", { name: PILL })).toBeNull();
  });

  it("a clean body asks as today — no save is owed before the wire", async () => {
    const fetchMock = stubStream([
      'data: {"delta": "Der Nebel hob sich."}\n\n',
      "event: done\ndata: {}\n\n",
    ]);
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.promptBar.continue"] }));
    expect(await screen.findByRole("button", { name: PILL })).toBeTruthy();
    // Today's behavior, byte for byte: the bare ask, no PUT owed.
    expect(api.PUT).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/writing/scenes/${S12.id}/continue`,
      expect.objectContaining({ method: "POST" }),
    );
  });
});

/** The world the refetch reads after a save — the typed body lands in the
 *  cache the remounting editor initializes from (the flush-first rule).
 *  Shared by the zen legs and the swap-window legs below. */
function liveBodyWorld() {
  let s12Body = S12.body;
  scenesAnswer = async (chapterId) => ({
    data: chapterId === "c1" ? [S11, { ...S12, body: s12Body }] : chapterId === "c2" ? [S21] : [],
    response: ok(),
  });
  putSceneAnswer = async (sceneId, body) => {
    const carried = (body as { body?: string }).body;
    if (sceneId === "s12" && typeof carried === "string") s12Body = carried;
    return { data: { ...S12, id: sceneId, ...(body as Partial<Scene>) }, response: ok() };
  };
}

async function typeIntoProse(text: string) {
  const user = userEvent.setup({ pointerEventsCheck: 0 });
  const box = await screen.findByRole("textbox", { name: de["writing.workspace.editor.proseLabel"] });
  await waitFor(() => expect(box.textContent).not.toBe(""));
  box.focus();
  await user.keyboard(text);
}

describe("zen mode (Task 18) — F9 clears the desk, Esc returns (D19)", () => {
  const EXIT = de["writing.workspace.zen.exit"];
  const PROSE = de["writing.workspace.editor.proseLabel"];

  function stubStream(chunks: readonly string[]) {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
        controller.close();
      },
    });
    const fetchMock = vi.fn(async () =>
      new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } }),
    );
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }

  async function enterZen() {
    fireEvent.keyDown(document, { key: "F9" });
    expect(await screen.findByRole("button", { name: EXIT })).toBeTruthy();
  }

  it("F9 opens zen over the workspace — the columns yield, the counters read the aggregate", async () => {
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    await enterZen();
    // The workspace chrome's room is gone — the zen surface owns the desk.
    expect(screen.queryByTestId("workspace-ribbon")).toBeNull();
    expect(screen.queryByTestId("workspace-running-head")).toBeNull();
    // The scene's own prose stands centered, the overline real. The editor
    // mounts asynchronously, so wait for its box instead of assuming it
    // landed in the same commit as the zen surface.
    const box = await screen.findByRole("textbox", { name: PROSE });
    await waitFor(() => expect(box.textContent).toContain("Ich kalibrierte die Sensoren."));
    expect(screen.getByText("Forschungsstation 7 · 27. Oktober 2094, 03:14 UTC")).toBeTruthy();
    // Today's words are the aggregate's own (412), the session starts at 0.
    expect(await screen.findByText(/Heute: \+412 W · Sitzung: 0 W/)).toBeTruthy();
    // The pomodoro starts full — session-only, nothing stored.
    expect(screen.getByText("25:00")).toBeTruthy();
  });

  it("F9 again returns the workspace — the chrome's room intact", async () => {
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    await enterZen();
    fireEvent.keyDown(document, { key: "F9" });
    expect(await screen.findByTestId("workspace-ribbon")).toBeTruthy();
    expect(screen.queryByRole("button", { name: EXIT })).toBeNull();
    expect(
      screen.getByRole("heading", { level: 1, name: "Das Signal im Permafrost" }),
    ).toBeTruthy();
  });

  it("Esc exits zen — D19's second door, the desk's focus returned", async () => {
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    await enterZen();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(await screen.findByTestId("workspace-ribbon")).toBeTruthy();
    await waitFor(() =>
      expect(document.activeElement).toBe(
        screen.getByRole("button", { name: de["writing.workspace.ribbon.focus"] }),
      ),
    );
  });

  it("the pending focus flag dies with the page — unmount, remount, no door focus absent a fresh exit", async () => {
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    await enterZen();
    // The hazard the unmount cleanup owns (Task 21's review): an exit that
    // navigates instead of remounting the columns leaves the flag pending
    // with no door to take it. Set it as such an exit would — the room
    // standing, the door gone — then leave the page without an exit.
    requestDeskFocus();
    cleanup();
    await renderWorkspace();
    const door = await screen.findByRole("button", { name: de["writing.workspace.ribbon.focus"] });
    // The fresh mount's door ref fired in-commit: had the flag survived the
    // unmount, the ref would have taken it and focused the door — unasked.
    expect(document.activeElement).not.toBe(door);
    // A fresh exit still returns the focus — the reset killed the stale
    // flag, not the mechanism.
    await enterZen();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(await screen.findByTestId("workspace-ribbon")).toBeTruthy();
    await waitFor(() =>
      expect(document.activeElement).toBe(
        screen.getByRole("button", { name: de["writing.workspace.ribbon.focus"] }),
      ),
    );
  });

  it("the ribbon's Fokus door opens zen — the interim ends (Task 18)", async () => {
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    const door = screen.getByRole("button", { name: de["writing.workspace.ribbon.focus"] });
    expect(door.hasAttribute("disabled")).toBe(false);
    fireEvent.click(door);
    expect(await screen.findByRole("button", { name: EXIT })).toBeTruthy();
  });

  it("F9 without a scene does nothing — the empty book keeps its face", async () => {
    chaptersAnswer = async () => ({ data: [], response: ok() });
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: de["writing.workspace.emptyBook.editorTitle"] });
    fireEvent.keyDown(document, { key: "F9" });
    expect(screen.queryByRole("button", { name: EXIT })).toBeNull();
    expect(
      screen.getByRole("heading", { level: 1, name: de["writing.workspace.emptyBook.editorTitle"] }),
    ).toBeTruthy();
  });

  it("the ghost owns Esc first inside zen — the room stays until the ghost is gone", async () => {
    stubStream(['data: {"delta": "Der Nebel hob sich."}\n\n', "event: done\ndata: {}\n\n"]);
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.promptBar.continue"] }));
    expect(await screen.findByTestId("ghost-preview")).toBeTruthy();
    await enterZen();
    // The proposal rode into the room — PR 4's seam is not stranded.
    expect(screen.getByTestId("ghost-preview").textContent).toContain("Der Nebel hob sich.");
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(screen.queryByTestId("ghost-preview")).toBeNull());
    // The first Esc belonged to the ghost — zen stands.
    expect(screen.getByRole("button", { name: EXIT })).toBeTruthy();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(await screen.findByTestId("workspace-ribbon")).toBeTruthy();
  });

  it("Tab accepts the ghost inside zen — the acceptance rides the one write path", async () => {
    liveBodyWorld();
    stubStream(['data: {"delta": "Der Nebel hob sich."}\n\n', "event: done\ndata: {}\n\n"]);
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.promptBar.continue"] }));
    expect(await screen.findByTestId("ghost-preview")).toBeTruthy();
    await enterZen();
    // The prose editor mounts asynchronously under the zen surface: wait for
    // its box instead of racing the commit that renders EXIT.
    const box = await screen.findByRole("textbox", { name: PROSE });
    fireEvent.keyDown(box, { key: "Tab" });
    await waitFor(() => expect(screen.queryByTestId("ghost-preview")).toBeNull());
    expect(box.textContent).toContain("Der Nebel hob sich.");
    // The acceptance is an edit: the autosave chain carries it to the PUT.
    await waitFor(() =>
      expect(api.PUT).toHaveBeenCalledWith(
        "/api/writing/scenes/{scene_id}",
        expect.objectContaining({
          params: { path: { scene_id: "s12" } },
          body: { body: expect.stringContaining("Der Nebel hob sich.") },
        }),
      ),
    );
  });

  it("entry flushes the draft — zen opens on the saved words, never a stale body", async () => {
    liveBodyWorld();
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    await typeIntoProse(" Mehr Text.");
    // F9 inside the debounce window: the flush lands the words first.
    await enterZen();
    expect(api.PUT).toHaveBeenCalledWith(
      "/api/writing/scenes/{scene_id}",
      expect.objectContaining({
        params: { path: { scene_id: "s12" } },
        body: { body: expect.stringContaining("Mehr Text.") },
      }),
    );
    // The prose editor mounts asynchronously under the zen surface: wait for
    // its box instead of racing the commit that rendered the room.
    const box = await screen.findByRole("textbox", { name: PROSE });
    await waitFor(() => expect(box.textContent).toContain("Mehr Text."));
  });

  it("exit flushes zen's draft — the workspace returns on the saved words", async () => {
    liveBodyWorld();
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    await enterZen();
    await typeIntoProse(" Noch ein Satz.");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(await screen.findByTestId("workspace-ribbon")).toBeTruthy();
    expect(api.PUT).toHaveBeenCalledWith(
      "/api/writing/scenes/{scene_id}",
      expect.objectContaining({
        params: { path: { scene_id: "s12" } },
        body: { body: expect.stringContaining("Noch ein Satz.") },
      }),
    );
    // The desk returns asynchronously after the exit: wait for the prose box
    // instead of racing the commit that renders the workspace.
    const box = await screen.findByRole("textbox", { name: PROSE });
    await waitFor(() => expect(box.textContent).toContain("Noch ein Satz."));
  });

  it("a failed exit flush raises the guard — Esc stays with it, Bleiben keeps zen, Verwerfen leaves", async () => {
    liveBodyWorld();
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    await enterZen();
    await typeIntoProse(" Words.");
    putSceneAnswer = async () => ({ data: undefined, response: new Response(null, { status: 503 }) });
    fireEvent.keyDown(document, { key: "Escape" });
    // The guard owns the room — the failed write asks before anything leaves.
    expect(await screen.findByRole("alertdialog")).toBeTruthy();
    // Esc belongs to the guard first (the page defers): stay, zen stands.
    // The guard's keyboard listener lands with its mount effect; wait for the
    // safe answer to take focus before sending the Escape that asks it.
    const stay = screen.getByRole("button", { name: de["writing.workspace.guard.stay"] });
    await waitFor(() => expect(document.activeElement).toBe(stay));
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(screen.getByRole("button", { name: EXIT })).toBeTruthy();
    // The failed flush lifted the swap window — the room's prose edits
    // again (the pin: a failed flush leaves editing ON). Wait for the
    // editable state to land instead of asserting it synchronously, so a
    // slow remount under load cannot false-fail the pin.
    const stayedBox = screen.getByRole("textbox", { name: PROSE });
    await waitFor(() => expect(stayedBox.getAttribute("contenteditable")).toBe("true"));
    await typeIntoProse(" Bleibt.");
    await waitFor(() => expect(stayedBox.textContent).toContain("Bleibt."));
    // The next exit ask fails again — the draft is still unsaved.
    fireEvent.keyDown(document, { key: "Escape" });
    expect(await screen.findByRole("alertdialog")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.guard.discard"] }));
    expect(await screen.findByTestId("workspace-ribbon")).toBeTruthy();
    // The discarded words never reached the wire — the cache's truth stands.
    // The desk's editor mounts asynchronously after the exit, so await it.
    const box = await screen.findByRole("textbox", { name: PROSE });
    await waitFor(() => expect(box.textContent).toContain("Ich kalibrierte die Sensoren."));
    expect(box.textContent).not.toContain("Words.");
    // The discard exit returns the desk's focus (the healthy exit's own
    // rule) — the guard's opener-restore no-ops on the detached zen node,
    // so the exit carries it. The door's ref takes the pending flag exactly
    // at remount (Task 21's deterministic return, no rAF race). Poll the
    // condition with an explicit ceiling: the remount lands in React's async
    // commit, which can run past the suite's implicit asyncUtilTimeout under
    // full-suite load.
    await waitFor(
      () =>
        expect(document.activeElement).toBe(
          screen.getByRole("button", { name: de["writing.workspace.ribbon.focus"] }),
        ),
      { timeout: 10000 },
    );
  }, 15000);

  it("the session is the zen spell — re-entry starts a fresh timer and counter", async () => {
    liveBodyWorld();
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    await enterZen();
    await typeIntoProse(" Eins zwei.");
    expect(await screen.findByText(/Sitzung: 2 W/)).toBeTruthy();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(await screen.findByTestId("workspace-ribbon")).toBeTruthy();
    await enterZen();
    expect(screen.getByText("25:00")).toBeTruthy();
    expect(await screen.findByText(/Sitzung: 0 W/)).toBeTruthy();
  });

  it("an unavailable aggregate keeps the neutral in the counter — never an invented today", async () => {
    activityAnswer = async () => ({ data: undefined, response: new Response(null, { status: 503 }) });
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    await enterZen();
    expect(await screen.findByText(/Heute: — · Sitzung: 0 W/)).toBeTruthy();
  });
});

describe("the zen swap window (the Codacy fix) — the transition locks the live editor", () => {
  const PROSE = de["writing.workspace.editor.proseLabel"];
  const FOCUS = de["writing.workspace.ribbon.focus"];
  const FOCUS_BUSY = de["writing.workspace.ribbon.focusBusy"];
  const EXIT = de["writing.workspace.zen.exit"];
  const EXIT_BUSY = de["writing.workspace.zen.exitBusy"];

  /** Hold the scene refetch the swap awaits — the window stands open until
   *  release. Armed AFTER the initial reads, so only the swap's own refetch
   *  (the flush's invalidation family) waits on the gate. */
  function refetchGate() {
    const base = scenesAnswer;
    let held = false;
    let release: (() => void) | undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    scenesAnswer = async (chapterId) => {
      if (held) await gate;
      return base(chapterId);
    };
    return {
      hold: () => {
        held = true;
      },
      release: () => release?.(),
    };
  }

  it("entry: the window locks the desk editor and busies the Fokus door — the swap lifts both", async () => {
    liveBodyWorld();
    const gate = refetchGate();
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    await typeIntoProse(" Mehr Text.");
    const box = screen.getByRole("textbox", { name: PROSE });
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    gate.hold();
    fireEvent.keyDown(document, { key: "F9" });
    // The flush lands; the refetch the swap awaits is held — the window stands.
    await waitFor(() => expect(api.PUT).toHaveBeenCalled());
    await waitFor(() => expect(box.getAttribute("contenteditable")).toBe("false"));
    const door = screen.getByRole("button", { name: FOCUS_BUSY });
    expect(door.hasAttribute("disabled")).toBe(true);
    // Keystrokes in the window are blocked — they would die with the unmount
    // (the refetched body predates them). No second write owes itself.
    await user.keyboard(" Fensterwort.");
    expect(box.textContent).not.toContain("Fensterwort.");
    expect(api.PUT).toHaveBeenCalledTimes(1);
    // A second F9 in the window is ignored — one swap, not a toggle race.
    fireEvent.keyDown(document, { key: "F9" });
    gate.release();
    // The swap lands: the room stands on the saved words, its editor live,
    // the pending flag lifted (the exit chip wears its resting face).
    expect(await screen.findByRole("button", { name: EXIT })).toBeTruthy();
    // The entry swap lands on a freshly mounted room: wait for its prose box
    // instead of racing the commit that rendered EXIT.
    const zenBox = await screen.findByRole("textbox", { name: PROSE });
    await waitFor(() => expect(zenBox.getAttribute("contenteditable")).toBe("true"));
    expect(zenBox.textContent).toContain("Mehr Text.");
    expect(zenBox.textContent).not.toContain("Fensterwort.");
    expect(screen.getByRole("button", { name: EXIT }).hasAttribute("disabled")).toBe(false);
  });

  it("exit: the window locks the room editor and busies the exit chip — the swap lifts both", async () => {
    liveBodyWorld();
    const gate = refetchGate();
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    fireEvent.keyDown(document, { key: "F9" });
    expect(await screen.findByRole("button", { name: EXIT })).toBeTruthy();
    await typeIntoProse(" Noch ein Satz.");
    const box = screen.getByRole("textbox", { name: PROSE });
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    gate.hold();
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(api.PUT).toHaveBeenCalled());
    await waitFor(() => expect(box.getAttribute("contenteditable")).toBe("false"));
    const chip = screen.getByRole("button", { name: EXIT_BUSY });
    expect(chip.hasAttribute("disabled")).toBe(true);
    await user.keyboard(" Fensterwort.");
    expect(box.textContent).not.toContain("Fensterwort.");
    expect(api.PUT).toHaveBeenCalledTimes(1);
    // A second Esc in the window is ignored — the guard owns no ask here.
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("alertdialog")).toBeNull();
    gate.release();
    // The desk returns on the saved words, its editor live, the door resting.
    expect(await screen.findByTestId("workspace-ribbon")).toBeTruthy();
    // The exit swap lands on a freshly mounted desk: wait for its prose box
    // instead of racing the commit that rendered the ribbon.
    const deskBox = await screen.findByRole("textbox", { name: PROSE });
    await waitFor(() => expect(deskBox.getAttribute("contenteditable")).toBe("true"));
    expect(deskBox.textContent).toContain("Noch ein Satz.");
    expect(deskBox.textContent).not.toContain("Fensterwort.");
    expect(screen.getByRole("button", { name: FOCUS }).hasAttribute("disabled")).toBe(false);
  });

  it("a failed entry flush keeps editing on — the window lifts, the room stays closed", async () => {
    liveBodyWorld();
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    await typeIntoProse(" Ungesichert.");
    putSceneAnswer = async () => ({ data: undefined, response: new Response(null, { status: 503 }) });
    fireEvent.keyDown(document, { key: "F9" });
    await waitFor(() => expect(api.PUT).toHaveBeenCalled());
    // The failed flush keeps the room closed (the writer saves first) and
    // lifts the window: the door rests, the prose edits again.
    expect(screen.queryByRole("button", { name: EXIT })).toBeNull();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: FOCUS }).hasAttribute("disabled")).toBe(false),
    );
    const box = screen.getByRole("textbox", { name: PROSE });
    expect(box.getAttribute("contenteditable")).toBe("true");
    box.focus();
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await user.keyboard(" Weiter.");
    expect(box.textContent).toContain("Weiter.");
  });
});

describe("book settings and the goal setters (Task 19) — the page's doors", () => {
  it("the identity card's door opens the book settings; Fertig returns the focus", async () => {
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    const door = screen.getByRole("button", { name: de["writing.workspace.identity.settings"] });
    fireEvent.click(door);
    // The form mounts once the reads settle — the title field is its face.
    const titleField = (await screen.findByLabelText(de["writing.settings.titleLabel"])) as HTMLInputElement;
    expect(screen.getByRole("heading", { name: de["writing.settings.title"] })).toBeTruthy();
    // The dialog reads the real novel — the title field opens on it.
    expect(titleField.value).toBe("Dead Signal");
    fireEvent.click(screen.getByRole("button", { name: `${de["writing.settings.close"]} (${de["writing.workspace.crud.close"]})` }));
    await waitFor(() => expect(screen.queryByRole("heading", { name: de["writing.settings.title"] })).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(door));
  }, 15000);

  it("a settings save rides the novel PATCH and the shelf family refetches", async () => {
    api.PATCH.mockImplementation(async (path: string, init?: { body?: Record<string, unknown> }) => {
      if (path === "/api/writing/novels/{novel_id}") {
        novelAnswer = async () => ({ data: { ...NOVEL, ...(init?.body ?? {}) }, response: ok() });
        return { data: { ...NOVEL, ...(init?.body ?? {}) }, response: ok() };
      }
      throw new Error(`unexpected PATCH: ${path}`);
    });
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.identity.settings"] }));
    const title = await screen.findByLabelText(de["writing.settings.titleLabel"]);
    fireEvent.change(title, { target: { value: "Dead Signal II" } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
    expect(api.PATCH.mock.calls[0][1].body).toEqual({ title: "Dead Signal II" });
    // The dialog closes; the refetched row speaks the new title.
    await waitFor(() => expect(screen.queryByRole("heading", { name: de["writing.settings.title"] })).toBeNull());
    expect((await screen.findAllByText("Dead Signal II")).length).toBeGreaterThan(0);
  }, 15000);

  it("the ring's setter opens the daily goal dialog — the save rides the settings PATCH", async () => {
    api.PATCH.mockResolvedValue({ data: {}, response: ok() });
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    const ring = screen.getByTestId("explorer-ring");
    fireEvent.click(within(ring).getByRole("button", { name: de["writing.workspace.ring.edit"] }));
    const field = await screen.findByLabelText(de["writing.workspace.goal.dailyLabel"]);
    expect((field as HTMLInputElement).value).toBe("500");
    await waitFor(() => expect((screen.getByRole("button", { name: de["writing.workspace.crud.save"] }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.change(field, { target: { value: "750" } });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(1));
    expect(api.PATCH.mock.calls[0][0]).toBe("/api/settings");
    expect(api.PATCH.mock.calls[0][1].body).toEqual({ locale: "de", daily_goal_words: 750 });
  }, 15000);

  it("the daily setter opens on the stored goal while the aggregate is pending", async () => {
    // The aggregate never answers — the ring keeps its skeleton, but the
    // setter's field reads the SETTINGS row (the save's own source).
    activityAnswer = () => new Promise(() => {});
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    const ring = screen.getByTestId("explorer-ring");
    fireEvent.click(within(ring).getByRole("button", { name: de["writing.workspace.ring.edit"] }));
    const field = await screen.findByLabelText(de["writing.workspace.goal.dailyLabel"]);
    expect((field as HTMLInputElement).value).toBe("500");
  }, 15000);

  it("the ribbon pill's setter opens the chapter goal dialog — the save rides the chapter PUT", async () => {
    await renderWorkspace();
    await screen.findByRole("heading", { level: 1, name: "Das Signal im Permafrost" });
    const ribbon = screen.getByTestId("workspace-ribbon");
    fireEvent.click(within(ribbon).getByRole("button", { name: de["writing.workspace.ribbon.targetEdit"] }));
    const field = await screen.findByLabelText(de["writing.workspace.goal.chapterLabel"]);
    fireEvent.change(field, { target: { value: "1000" } });
    putChapterAnswer = async (chapterId, body) => ({
      data: { ...(chapterId === "c1" ? CH1 : CH2), ...(body as { target_words?: number | null }) },
      response: ok(),
    });
    // The structure refetch reads the changed row — the goal stands.
    chaptersAnswer = async () => ({ data: [{ ...CH1, target_words: 1000 }, CH2], response: ok() });
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.crud.save"] }));
    await waitFor(() => expect(api.PUT).toHaveBeenCalled());
    const call = api.PUT.mock.calls.find((entry) => entry[0] === "/api/writing/chapters/{chapter_id}");
    expect(call?.[1].body).toEqual({ target_words: 1000 });
    // The pill reads the refetched row — the real pair stands.
    expect(
      await within(ribbon).findByText(
        de["writing.workspace.ribbon.targetValue"].replace("{count, number}", "765").replace("{target, number}", "1.000"),
      ),
    ).toBeTruthy();
  }, 15000);
});
