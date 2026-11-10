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
import { PlanningPage, readEvents } from "./PlanningPage";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

const api = client as unknown as {
  GET: ReturnType<typeof vi.fn>;
  POST: ReturnType<typeof vi.fn>;
  PUT: ReturnType<typeof vi.fn>;
  DELETE: ReturnType<typeof vi.fn>;
};

const NOVEL_ID = "novel-1";
const CHAPTER_A = "chapter-a";
const CHAPTER_B = "chapter-b";

function event(
  id: string,
  title: string,
  overrides: {
    chapter_id?: string | null;
    position?: number | null;
    date_label?: string;
    description?: string;
    character_names?: string[];
    created_at?: string;
  } = {},
) {
  return {
    id,
    novel_id: NOVEL_ID,
    chapter_id: overrides.chapter_id ?? null,
    title,
    description: overrides.description ?? "",
    position: overrides.position ?? null,
    date_label: overrides.date_label ?? "",
    character_names: overrides.character_names ?? [],
    created_at: overrides.created_at ?? "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

function chapter(id: string, title: string, position: number) {
  return {
    id,
    novel_id: NOVEL_ID,
    title,
    body: "",
    position,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  };
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
let liveEvents: ReturnType<typeof event>[] = [];
let liveNovels: ReturnType<typeof novel>[] = [novel(NOVEL_ID, "Die geplante Bucht")];
let liveChapters: ReturnType<typeof chapter>[] = [
  chapter(CHAPTER_A, "Ankunft", 0),
  chapter(CHAPTER_B, "Abreise", 1),
];

function orderServer(rows: ReturnType<typeof event>[]): ReturnType<typeof event>[] {
  return [...rows].sort((left, right) => {
    if (left.position === null && right.position === null)
      return left.created_at < right.created_at ? -1 : 1;
    if (left.position === null) return 1;
    if (right.position === null) return -1;
    return left.position - right.position;
  });
}

function mockApi() {
  api.GET.mockImplementation(async (path: string) => {
    if (typeof path === "string" && path.includes("/timeline-events")) {
      return { data: orderServer(liveEvents), response: { ok: true } };
    }
    if (typeof path === "string" && path.includes("/chapters")) {
      return { data: liveChapters, response: { ok: true } };
    }
    return { data: liveNovels, response: { ok: true } };
  });
  api.POST.mockImplementation(async (path: string, options: { body: Record<string, unknown> }) => {
    const row = event(`event-${liveEvents.length + 1}`, options.body.title as string, {
      chapter_id: (options.body.chapter_id as string | null) ?? null,
      position: (options.body.position as number | null) ?? null,
      date_label: (options.body.date_label as string) ?? "",
      description: (options.body.description as string) ?? "",
      character_names: (options.body.character_names as string[]) ?? [],
      created_at: `2026-01-0${liveEvents.length + 1}T00:00:00Z`,
    });
    liveEvents = [...liveEvents, row];
    return { data: row, response: { ok: true, status: 201 } };
  });
  api.PUT.mockImplementation(
    async (
      _path: string,
      options: { body: Record<string, unknown>; params: { path: { event_id: string } } },
    ) => {
      // The mocked client receives the path template, not the built URL:
      // the ids ride options.params, like the real openapi-fetch call.
      const id = options.params.path.event_id;
      liveEvents = liveEvents.map((row) =>
      row.id === id ? { ...row, ...(options.body as object) } : row,
    );
      const row = liveEvents.find((candidate) => candidate.id === id);
      return { data: row, response: { ok: true } };
    },
  );
  api.DELETE.mockImplementation(
    async (_path: string, options: { params: { path: { event_id: string } } }) => {
      const id = options.params.path.event_id;
      liveEvents = liveEvents.filter((row) => row.id !== id);
      return { data: undefined, response: { ok: true, status: 204 } };
    },
  );
}

function renderPage(entry: string) {
  const planning = createRoute({
    getParentRoute: () => rootRoute,
    path: "planning",
    component: PlanningPage,
    validateSearch: (search: { novel?: unknown }): { novel?: string } => ({
      ...(typeof search.novel === "string" && search.novel !== "" ? { novel: search.novel } : {}),
    }),
  });
  const router = createRouter({
    routeTree: rootRoute.addChildren([planning]),
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
  liveEvents = [];
  liveNovels = [novel(NOVEL_ID, "Die geplante Bucht")];
  liveChapters = [chapter(CHAPTER_A, "Ankunft", 0), chapter(CHAPTER_B, "Abreise", 1)];
});

describe("readEvents", () => {
  it("passes the rows through, and never mistakes an outage for an empty canvas", () => {
    const rows = [event("e1", "Anfang")];
    expect(readEvents({ data: rows, response: { ok: true } })).toEqual({ kind: "ok", events: rows });
    expect(readEvents({ data: undefined, response: { ok: true } })).toEqual({
      kind: "ok",
      events: [],
    });
    expect(readEvents({ data: rows, response: { ok: false } })).toEqual({ kind: "failed" });
  });
});

describe("PlanningPage empty novel", () => {
  it("names the next step when the novel holds no events", async () => {
    mockApi();
    renderPage(`/planning?novel=${NOVEL_ID}`);

    expect(await screen.findByText("No events yet. Add the first one below.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Add event" })).toBeTruthy();
  });
});

describe("PlanningPage chronological view", () => {
  it("renders seeded events in server order, undated rows without a date", async () => {
    liveEvents = [
      event("e2", "Mitte", { position: 2, date_label: "Im Frühling" }),
      event("e1", "Anfang", { position: 1 }),
      event("e3", "Ausklang", { position: null, created_at: "2026-01-03T00:00:00Z" }),
    ];
    mockApi();
    renderPage(`/planning?novel=${NOVEL_ID}`);

    await screen.findByRole("group", { name: "Anfang" });
    const names = screen
      .getAllByRole("group", { name: /Anfang|Mitte|Ausklang/ })
      .map((group) => group.getAttribute("aria-label"));
    // Server order, not alphabetical: Anfang (1), Mitte (2), Ausklang last.
    expect(names).toEqual(["Anfang", "Mitte", "Ausklang"]);
    // The dated row carries its garnish; the undated rows carry none.
    expect(screen.getByText("Im Frühling")).toBeTruthy();
    expect(screen.getByText("#1")).toBeTruthy();
    expect(screen.getByText("#2")).toBeTruthy();
    expect(screen.getAllByText("Unordered")).toHaveLength(1);
  });
});

describe("PlanningPage by-chapter view", () => {
  it("groups the same events under their chapters", async () => {
    liveEvents = [
      event("e1", "Anfang", { position: 1, chapter_id: CHAPTER_A }),
      event("e2", "Mitte", { position: 2, chapter_id: CHAPTER_B }),
      event("e3", "Ausklang", { position: 3, chapter_id: null }),
    ];
    mockApi();
    renderPage(`/planning?novel=${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    await screen.findByRole("group", { name: "Anfang" });
    await user.click(screen.getByRole("button", { name: "By chapter" }));

    const ankunft = await screen.findByRole("region", { name: "Ankunft" });
    expect(within(ankunft).getByRole("group", { name: "Anfang" })).toBeTruthy();
    const abreise = screen.getByRole("region", { name: "Abreise" });
    expect(within(abreise).getByRole("group", { name: "Mitte" })).toBeTruthy();
    const loose = screen.getByRole("region", { name: "No chapter" });
    expect(within(loose).getByRole("group", { name: "Ausklang" })).toBeTruthy();
  });
});

describe("PlanningPage write flow", () => {
  it("adds an event through the dialog and shows it", async () => {
    mockApi();
    renderPage(`/planning?novel=${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    await screen.findByRole("button", { name: "Add event" });
    await user.click(screen.getByRole("button", { name: "Add event" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Title"), "Sturm");
    await user.type(within(dialog).getByLabelText("Date (optional)"), "Im Frühling");
    await user.click(within(dialog).getByRole("button", { name: "Add event" }));

    await waitFor(() => expect(api.POST).toHaveBeenCalledTimes(1));
    const [, options] = api.POST.mock.calls[0] as [string, { body: Record<string, unknown> }];
    expect(options.body.title).toBe("Sturm");
    expect(options.body.date_label).toBe("Im Frühling");
    expect(await screen.findByRole("group", { name: "Sturm" })).toBeTruthy();
  });

  it("edits an event's title through the mocked PUT", async () => {
    liveEvents = [event("e1", "Anfang", { position: 1 })];
    mockApi();
    renderPage(`/planning?novel=${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    const row = await screen.findByRole("group", { name: "Anfang" });
    await user.click(within(row).getByRole("button", { name: "Edit Anfang" }));
    const dialog = await screen.findByRole("dialog");
    await user.clear(within(dialog).getByLabelText("Title"));
    await user.type(within(dialog).getByLabelText("Title"), "Ankunft!");
    await user.click(within(dialog).getByRole("button", { name: "Save event" }));

    await waitFor(() => expect(api.PUT).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole("group", { name: "Ankunft!" })).toBeTruthy();
  });

  it("deletes an event after confirmation", async () => {
    liveEvents = [event("e1", "Anfang", { position: 1 })];
    mockApi();
    renderPage(`/planning?novel=${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    const row = await screen.findByRole("group", { name: "Anfang" });
    await user.click(within(row).getByRole("button", { name: "Delete Anfang" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(api.DELETE).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(screen.queryByRole("group", { name: "Anfang" })).toBeNull(),
    );
  });

  it("names a refused write and retries it", async () => {
    mockApi();
    api.POST.mockResolvedValueOnce({
      data: undefined,
      error: { detail: "chapter link the novel does not hold" },
      response: { ok: false, status: 422 },
    });
    renderPage(`/planning?novel=${NOVEL_ID}`);
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    await screen.findByRole("button", { name: "Add event" });
    await user.click(screen.getByRole("button", { name: "Add event" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Title"), "Sturm");
    await user.click(within(dialog).getByRole("button", { name: "Add event" }));

    const alert = await within(dialog).findByRole("alert");
    expect(alert.textContent).toContain("Saving failed: chapter link the novel does not hold");
    await user.click(within(alert).getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(api.POST).toHaveBeenCalledTimes(2));
    // The retry heals: the dialog closes and the event stands in the list.
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(await screen.findByRole("group", { name: "Sturm" })).toBeTruthy();
  });
});

describe("PlanningPage event cap", () => {
  it("renders at most 200 rows and says how many it holds", async () => {
    liveEvents = Array.from({ length: 201 }, (_, index) =>
      event(`e${index + 1}`, `Ereignis ${index + 1}`, {
        position: index + 1,
        created_at: `2026-01-${String((index % 28) + 1).padStart(2, "0")}T00:00:00Z`,
      }),
    );
    mockApi();
    renderPage(`/planning?novel=${NOVEL_ID}`);

    await screen.findByRole("group", { name: "Ereignis 1" });
    expect(screen.getAllByRole("group").length).toBe(200);
    expect(screen.getByText("Showing 200 of 201 events.")).toBeTruthy();
  });
});

describe("PlanningPage novel picker", () => {
  it("lists the novels as destinations when none is named", async () => {
    mockApi();
    renderPage("/planning");

    expect(await screen.findByRole("link", { name: "Die geplante Bucht" })).toHaveProperty(
      "href",
      expect.stringContaining("/planning?novel=novel-1"),
    );
  });

  it("says how to get a novel when the library is empty", async () => {
    liveNovels = [];
    mockApi();
    renderPage("/planning");

    expect(await screen.findByText("No novels yet. Create one under All novels first.")).toBeTruthy();
  });
});
