// @vitest-environment jsdom
import { QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@shell/lib/api/client";
import { queryClient } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";
import { CHAPTER_LIMIT, StoryboardPage, readStoryboard } from "./StoryboardPage";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

const api = client as unknown as {
  GET: ReturnType<typeof vi.fn>;
  POST: ReturnType<typeof vi.fn>;
  PUT: ReturnType<typeof vi.fn>;
};

const NOVEL_ID = "novel-1";
const CHAPTER_A = "chapter-a";
const CHAPTER_B = "chapter-b";

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

function stage(key: string, titleKey: string, chapters: ReturnType<typeof chapterEntry>[]) {
  return { key, title_key: titleKey, from: 0, to: 0.25, chapters };
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

/** The live store the mocks read: the tests mutate it the way the server would. */
let liveBoard = {
  novel_id: NOVEL_ID,
  structure_id: "three-act",
  stages: [
    stage("setup", "storyboard.stage.setup", [
      chapterEntry(CHAPTER_A, "Ankunft", {
        position: 0,
        word_count: 12,
        sync_status: "planned",
        stage_key: "setup",
      }),
    ]),
    stage("confrontation", "storyboard.stage.confrontation", [
      chapterEntry(CHAPTER_B, "Abreise", {
        position: 1,
        word_count: 0,
        sync_status: "empty",
        stage_key: "confrontation",
      }),
    ]),
    stage("resolution", "storyboard.stage.resolution", []),
  ],
};
let liveNovels: ReturnType<typeof novel>[] = [novel(NOVEL_ID, "Die geplante Bucht")];

function resetBoard() {
  liveBoard = {
    novel_id: NOVEL_ID,
    structure_id: "three-act",
    stages: [
      stage("setup", "storyboard.stage.setup", [
        chapterEntry(CHAPTER_A, "Ankunft", {
          position: 0,
          word_count: 12,
          sync_status: "planned",
          stage_key: "setup",
        }),
      ]),
      stage("confrontation", "storyboard.stage.confrontation", [
        chapterEntry(CHAPTER_B, "Abreise", {
          position: 1,
          word_count: 0,
          sync_status: "empty",
          stage_key: "confrontation",
        }),
      ]),
      stage("resolution", "storyboard.stage.resolution", []),
    ],
  };
}

function findEntry(id: string) {
  for (const column of liveBoard.stages) {
    const found = (column.chapters ?? []).find((entry) => entry.chapter_id === id);
    if (found !== undefined) return { column, found };
  }
  return null;
}

function mockApi() {
  api.GET.mockImplementation(async (path: string) => {
    if (typeof path === "string" && path.includes("/storyboard")) {
      return { data: liveBoard, response: { ok: true } };
    }
    return { data: liveNovels, response: { ok: true } };
  });
  api.PUT.mockImplementation(
    async (_path: string, options: { body: { stage_key: string }; params: { path: { chapter_id: string } } }) => {
      // The mocked client receives the path template, not the built URL:
      // the ids ride options.params, like the real openapi-fetch call.
      const id = options.params.path.chapter_id;
      const hit = findEntry(id);
      if (hit === null) {
        return {
          data: undefined,
          error: { detail: "chapter the novel does not hold" },
          response: { ok: false, status: 422 },
        };
      }
      const moved = { ...hit.found, stage_key: options.body.stage_key, assignment_source: "assigned" };
      for (const column of liveBoard.stages) {
        column.chapters = (column.chapters ?? []).filter((entry) => entry.chapter_id !== id);
      }
      const target = liveBoard.stages.find((column) => column.key === options.body.stage_key);
      target?.chapters?.push(moved);
      return { data: moved, response: { ok: true } };
    },
  );
  api.POST.mockImplementation(
    async (_path: string, options: { body: { structure_id: string; confirm: boolean } }) => {
      const mapping = (liveBoard.stages.flatMap((column) => column.chapters ?? []) as ReturnType<
        typeof chapterEntry
      >[]).map((entry) => ({
        chapter_id: entry.chapter_id,
        from_stage: entry.stage_key,
        to_stage: "ordinary-world",
      }));
      if (options.body.confirm) {
        liveBoard = {
          novel_id: NOVEL_ID,
          structure_id: options.body.structure_id,
          stages: [
            {
              key: "ordinary-world",
              title_key: "storyboard.stage.ordinary-world",
              from: 0,
              to: 1 / 12,
              chapters: (liveBoard.stages.flatMap((column) => column.chapters ?? []) as ReturnType<
                typeof chapterEntry
              >[]).map((entry) => ({
                ...entry,
                stage_key: "ordinary-world",
                assignment_source: "assigned",
              })),
            },
          ],
        };
        return {
          data: { novel_id: NOVEL_ID, structure_id: options.body.structure_id, confirmed: true, mapping },
          response: { ok: true },
        };
      }
      return {
        data: { novel_id: NOVEL_ID, structure_id: options.body.structure_id, confirmed: false, mapping },
        response: { ok: true },
      };
    },
  );
}

function renderPage(entry: string) {
  const storyboard = createRoute({
    getParentRoute: () => rootRoute,
    path: "planning/storyboard",
    component: StoryboardPage,
    validateSearch: (search: { novel?: unknown }): { novel?: string } => ({
      ...(typeof search.novel === "string" && search.novel !== "" ? { novel: search.novel } : {}),
    }),
  });
  const router = createRouter({
    routeTree: rootRoute.addChildren([storyboard]),
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
  resetBoard();
  liveNovels = [novel(NOVEL_ID, "Die geplante Bucht")];
});

describe("readStoryboard", () => {
  it("passes the aggregate through, and never mistakes an outage for an empty canvas", () => {
    expect(readStoryboard({ data: liveBoard, response: { ok: true } })).toEqual({
      kind: "ok",
      board: liveBoard,
    });
    expect(readStoryboard({ data: undefined, response: { ok: true } })).toEqual({
      kind: "failed",
    });
    expect(readStoryboard({ data: liveBoard, response: { ok: false } })).toEqual({
      kind: "failed",
    });
  });
});

describe("StoryboardPage columns", () => {
  it("renders one column per stage from the aggregate", async () => {
    mockApi();
    renderPage(`/planning/storyboard?novel=${NOVEL_ID}`);

    expect(await screen.findByRole("heading", { name: "Setup" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Confrontation" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Resolution" })).toBeTruthy();
  });

  it("shows the chapter's title, word count and sync badge", async () => {
    mockApi();
    renderPage(`/planning/storyboard?novel=${NOVEL_ID}`);

    const card = await screen.findByRole("group", { name: "Ankunft" });
    expect(within(card).getByText("12 words")).toBeTruthy();
    expect(within(card).getByText("Planned")).toBeTruthy();
  });

  it("links the card to the chapter in the workspace", async () => {
    mockApi();
    renderPage(`/planning/storyboard?novel=${NOVEL_ID}`);

    const card = await screen.findByRole("group", { name: "Ankunft" });
    const link = within(card).getByRole("link", { name: "Ankunft" });
    expect(link.getAttribute("href")).toContain(`/novels/${NOVEL_ID}`);
    expect(link.getAttribute("href")).toContain(`chapter=${CHAPTER_A}`);
  });
});

describe("StoryboardPage move", () => {
  it("moves the card to the chosen stage through the mocked PUT", async () => {
    mockApi();
    renderPage(`/planning/storyboard?novel=${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    const card = await screen.findByRole("group", { name: "Ankunft" });
    await user.click(within(card).getByRole("button", { name: "Move Ankunft to another stage" }));
    await user.click(screen.getByRole("menuitem", { name: "Confrontation" }));

    await waitFor(() => expect(api.PUT).toHaveBeenCalledTimes(1));
    const [, options] = api.PUT.mock.calls[0] as [
      string,
      { body: { stage_key: string }; params: { path: { chapter_id: string } } },
    ];
    expect(options.body.stage_key).toBe("confrontation");
    // The card stands in its new column after the refetch.
    const column = await screen.findByRole("region", { name: "Confrontation" });
    expect(within(column).getByRole("group", { name: "Ankunft" })).toBeTruthy();
  });

  it("snaps the card back and names the retry when the PUT is refused", async () => {
    mockApi();
    api.PUT.mockResolvedValueOnce({
      data: undefined,
      error: { detail: "chapter the novel does not hold" },
      response: { ok: false, status: 422 },
    });
    renderPage(`/planning/storyboard?novel=${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    const card = await screen.findByRole("group", { name: "Ankunft" });
    await user.click(within(card).getByRole("button", { name: "Move Ankunft to another stage" }));
    await user.click(screen.getByRole("menuitem", { name: "Confrontation" }));

    // The refusal names itself where the retry sits, and the card snaps
    // back to the column the server still holds it in.
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Saving failed: chapter the novel does not hold");
    await waitFor(() => expect(api.PUT).toHaveBeenCalledTimes(1));
    const column = await screen.findByRole("region", { name: "Setup" });
    expect(within(column).getByRole("group", { name: "Ankunft" })).toBeTruthy();

    await user.click(within(alert).getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(api.PUT).toHaveBeenCalledTimes(2));
    const moved = await screen.findByRole("region", { name: "Confrontation" });
    expect(within(moved).getByRole("group", { name: "Ankunft" })).toBeTruthy();
  });
});

describe("StoryboardPage remap", () => {
  it("previews the mapping before applying it", async () => {
    mockApi();
    renderPage(`/planning/storyboard?novel=${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    await screen.findByRole("group", { name: "Ankunft" });
    await user.click(screen.getByRole("button", { name: "Preview structure change" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Hero's journey" }));

    // The preview names every move's before and after; nothing is written yet.
    expect(await within(dialog).findByText(/Setup → Ordinary world/)).toBeTruthy();
    expect(api.POST).toHaveBeenCalledTimes(1);
    const [, preview] = api.POST.mock.calls[0] as [
      string,
      { body: { structure_id: string; confirm: boolean } },
    ];
    expect(preview.body).toEqual({ structure_id: "heros-journey", confirm: false });

    await user.click(within(dialog).getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(api.POST).toHaveBeenCalledTimes(2));
    const [, applied] = api.POST.mock.calls[1] as [
      string,
      { body: { structure_id: string; confirm: boolean } },
    ];
    expect(applied.body).toEqual({ structure_id: "heros-journey", confirm: true });
    // The canvas re-reads onto the new structure's columns.
    expect(await screen.findByRole("heading", { name: "Ordinary world" })).toBeTruthy();
  });
});

describe("StoryboardPage chapter cap", () => {
  it("renders at most 200 cards and says how many it holds", async () => {
    const entries = Array.from({ length: 201 }, (_, index) =>
      chapterEntry(`chapter-${index + 1}`, `Kapitel ${index + 1}`, {
        position: index,
        stage_key: "setup",
      }),
    );
    liveBoard = {
      novel_id: NOVEL_ID,
      structure_id: "three-act",
      stages: [stage("setup", "storyboard.stage.setup", entries)],
    };
    mockApi();
    renderPage(`/planning/storyboard?novel=${NOVEL_ID}`);

    await screen.findByRole("group", { name: "Kapitel 1" });
    expect(screen.getAllByRole("group").length).toBe(200);
    expect(screen.getByText("Showing 200 of 201 chapters.")).toBeTruthy();
  });
});

describe("StoryboardPage novel picker", () => {
  it("lists the novels as destinations when none is named", async () => {
    mockApi();
    renderPage("/planning/storyboard");

    expect(await screen.findByRole("link", { name: "Die geplante Bucht" })).toHaveProperty(
      "href",
      expect.stringContaining("/planning/storyboard?novel=novel-1"),
    );
  });

  it("says how to get a novel when the library is empty", async () => {
    liveNovels = [];
    mockApi();
    renderPage("/planning/storyboard");

    expect(await screen.findByText("No novels yet. Create one under All novels first.")).toBeTruthy();
  });
});

describe("StoryboardPage chapter limit constant", () => {
  it("caps the canvas at two hundred cards", () => {
    expect(CHAPTER_LIMIT).toBe(200);
  });
});
