// @vitest-environment jsdom
/**
 * The chronology page (W6 Task 3) — the planning capability's first web
 * surface, ported from the owner-approved harmonized `chronology-timeline-2`
 * draft onto the shell's tokens, driven through the real API seam (the
 * client mocked at its module boundary, the house pattern). The page
 * renders the novel's real TimelineEventRead rows in the server's manual
 * order — positioned rows in the ordered section, null positions last in
 * the unordered one — with only real fields on the cards: the free-text
 * date, the title, the description excerpt, the free-text name chips and
 * the chapter door-chip (no dead links: a chapter that no longer resolves
 * is no door at all). The name-chip filter composes with the quick
 * filters; the scene-status counters derive from the per-chapter fan-out;
 * the subbar with its sibling doors stands in EVERY state — pending,
 * outage, empty, populated (W5 #923's rule). CRUD round-trips through the
 * page: create from the header door and the undated placeholder, edit
 * from a card, delete through the confirm. The face speaks du-tone in all
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

import { client, type Chapter, type TimelineEvent } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";

import { TimelinePage } from "./TimelinePage";

const de = catalogs.de;
const api = client as unknown as Record<"GET" | "POST" | "PUT" | "DELETE", ReturnType<typeof vi.fn>>;

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

function eventRow(overrides: Partial<TimelineEvent> & { id: string }): TimelineEvent {
  return {
    novel_id: NOVEL_ID,
    chapter_id: null,
    title: "Der Große Bruch",
    description: "Nevada-Tiefraumarray verliert 41% der Verbindung.",
    position: 1,
    date_label: "2278",
    character_names: [],
    created_at: "2026-11-18T10:00:00Z",
    updated_at: "2026-11-18T10:00:00Z",
    ...overrides,
  };
}

const BRUCH = eventRow({ id: "ev1", position: 1, date_label: "2278" });
const UNGLUECK = eventRow({
  id: "ev2",
  position: 2,
  title: "Unglück auf Station 7",
  description: "Verdampfung des Hauptlabors. Lins Signal verstummt.",
  date_label: "14. Nov 2284",
  character_names: ["Maya Chen", "Lin Chen"],
  chapter_id: "c2",
  created_at: "2026-11-18T10:01:00Z",
});
const SEKTOR = eventRow({
  id: "ev3",
  position: null,
  title: "Öffnung von Sektor D-4",
  description: "Maya umgeht Sicherheitsgrenzen.",
  date_label: "",
  character_names: ["Maya Chen"],
  created_at: "2026-11-18T10:02:00Z",
});

function sceneAggregate(chapterId: string, statuses: string[]) {
  return {
    chapter_id: chapterId,
    version_updated_at: "2026-11-18T10:00:00Z",
    scenes: statuses.map((status, at) => ({
      id: `s-${chapterId}-${at}`,
      chapter_id: chapterId,
      position: at + 1,
      title: `Szene ${at + 1}`,
      purpose: "",
      conflict: "",
      resolution: "",
      beats: [],
      status,
      created_at: "2026-11-18T10:00:00Z",
      updated_at: "2026-11-18T10:00:00Z",
    })),
  };
}

const AGGREGATES = new Map([
  ["c1", sceneAggregate("c1", ["complete", "complete", "in_progress"])],
  ["c2", sceneAggregate("c2", ["planned"])],
]);

let events: TimelineEvent[];
let eventsFail: boolean;
let chaptersFail: boolean;
let scenesFail: boolean;

function baseGet(
  path: string,
  init?: { params?: { path?: { chapter_id?: string } } },
): Promise<{ data: unknown; response: Response }> {
  if (eventsFail && path === "/api/planning/novels/{novel_id}/timeline-events") {
    return Promise.resolve({ data: undefined, response: ok(503) });
  }
  if (path === "/api/planning/novels/{novel_id}/timeline-events") {
    return Promise.resolve({ data: events, response: ok() });
  }
  if (chaptersFail && path === "/api/writing/novels/{novel_id}/chapters") {
    return Promise.resolve({ data: undefined, response: ok(503) });
  }
  if (path === "/api/writing/novels/{novel_id}/chapters") {
    return Promise.resolve({ data: CHAPTERS, response: ok() });
  }
  if (path === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes") {
    if (scenesFail) return Promise.resolve({ data: undefined, response: ok(503) });
    const chapterId = init?.params?.path?.chapter_id ?? "";
    return Promise.resolve({ data: AGGREGATES.get(chapterId), response: ok() });
  }
  throw new Error(`unexpected GET: ${path}`);
}

/** The page on a harness route whose id is the real timeline path, beside
 *  stubs the sibling doors and the workspace door navigate to. */
const harnessRoot = createRootRoute({ component: () => <Outlet /> });

async function renderTimeline(entry = `/novels/${NOVEL_ID}/planning/timeline`) {
  const timeline = createRoute({
    getParentRoute: () => harnessRoot,
    path: TIMELINE_PATH,
    component: TimelinePage,
  });
  const storyboard = createRoute({
    getParentRoute: () => harnessRoot,
    path: STORYBOARD_PATH,
    component: () => <p>storyboard face</p>,
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
    routeTree: harnessRoot.addChildren([timeline, storyboard, causality, workspace]),
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
  const storyboardDoor = screen.getByTestId("timeline-storyboard-door");
  expect(within(storyboardDoor).getByText(de["planning.sub.storyboard"])).toBeTruthy();
  const causalityDoor = screen.getByTestId("timeline-causality-door");
  expect(within(causalityDoor).getByText(de["planning.sub.causality"])).toBeTruthy();
  expect(screen.getByText(de["planning.timeline.title"])).toBeTruthy();
}

beforeEach(() => {
  applyLocale("de");
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
  events = [BRUCH, UNGLUECK, SEKTOR];
  eventsFail = false;
  chaptersFail = false;
  scenesFail = false;
  api.GET.mockImplementation(baseGet);
  api.POST.mockResolvedValue({ data: BRUCH, response: ok(201) });
  api.PUT.mockResolvedValue({ data: BRUCH, response: ok() });
  api.DELETE.mockResolvedValue({ data: undefined, response: ok(204) });
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
  applyLocale(null);
});

describe("the board renders the novel's real events", () => {
  it("groups positioned rows first, null positions last, in the server's order", async () => {
    await renderTimeline();
    const ordered = await screen.findByTestId("timeline-ordered");
    const cards = within(ordered).getAllByTestId("timeline-card");
    expect(cards).toHaveLength(2);
    expect(within(cards[0]).getByText("Der Große Bruch")).toBeTruthy();
    expect(within(cards[1]).getByText("Unglück auf Station 7")).toBeTruthy();
    expect(within(ordered).getByText(/eingeordnete Ereignisse/)).toBeTruthy();
    expect(ordered.textContent).toMatch(/2\b/);

    const unordered = screen.getByTestId("timeline-unordered");
    const drafts = within(unordered).getAllByTestId("timeline-card");
    expect(drafts).toHaveLength(1);
    expect(within(drafts[0]).getByText("Öffnung von Sektor D-4")).toBeTruthy();
    // The reads carry the novel.
    expect(api.GET.mock.calls.some(([p]) => p === "/api/planning/novels/{novel_id}/timeline-events")).toBe(true);
  });

  it("the cards show only real fields — no invented relative dates, no draft badge", async () => {
    await renderTimeline();
    const cards = [...(await screen.findAllByTestId("timeline-card"))];
    for (const card of cards) {
      expect(within(card).queryByText(/Vor \d+ J\./)).toBeNull();
      expect(within(card).queryByText("Entwurf")).toBeNull();
      expect(within(card).queryByText("Ausgewählt")).toBeNull();
    }
    const bruch = cards.find((card) => within(card).queryByText("Der Große Bruch") !== null) as HTMLElement;
    expect(within(bruch).getByText("2278")).toBeTruthy();
    // The chapter link resolves: the door-chip carries the chapter position.
    const unglueck = cards.find((card) => within(card).queryByText("Unglück auf Station 7") !== null) as HTMLElement;
    expect(within(unglueck).getByText("Kapitel 2")).toBeTruthy();
    expect(within(unglueck).getByText("Maya Chen")).toBeTruthy();
    // The unlinked event says so honestly.
    expect(within(bruch).getByText(de["planning.timeline.noChapter"])).toBeTruthy();
    // A null position carries the honest no-date mark, not an invented one.
    const sek = cards.find((card) => within(card).queryByText("Öffnung von Sektor D-4") !== null) as HTMLElement;
    expect(within(sek).getByText(de["planning.timeline.noDate"])).toBeTruthy();
  });

  it("the chapter chip is a door to the book's workspace; a chapter that no longer resolves is no door", async () => {
    events = [
      eventRow({ id: "ev-dead", position: 1, chapter_id: "c-gone", title: "Verwaistes Ereignis" }),
    ];
    await renderTimeline();
    const card = (await screen.findAllByTestId("timeline-card"))[0];
    const door = within(card).queryByRole("link");
    expect(door).toBeNull();
    expect(within(card).getByText(de["planning.timeline.noChapter"])).toBeTruthy();

    // The cached first answer must not out-live the scenario: the second
    // face asks again with the linked row standing.
    cleanup();
    queryClient.clear();
    events = [UNGLUECK];
    await renderTimeline();
    const chip = await screen.findByRole("link", { name: "Kapitel 2" });
    expect(chip.getAttribute("href")).toBe(`/novels/${NOVEL_ID}`);
  });
});

describe("the filters", () => {
  it("the name chips narrow to the events carrying the name", async () => {
    await renderTimeline();
    await screen.findAllByTestId("timeline-card");
    fireEvent.click(screen.getByRole("button", { name: "Maya Chen" }));

    const visible = screen.getAllByTestId("timeline-card").map((card) => card.textContent);
    expect(visible.some((text) => text?.includes("Unglück auf Station 7"))).toBe(true);
    expect(visible.some((text) => text?.includes("Öffnung von Sektor D-4"))).toBe(true);
    expect(visible.some((text) => text?.includes("Der Große Bruch"))).toBe(false);
  });

  it("the quick filters compose with the names — no hit clears honestly", async () => {
    await renderTimeline();
    await screen.findAllByTestId("timeline-card");
    // Ohne Datum: the dated events leave, the undated stay.
    fireEvent.click(screen.getByRole("button", { name: de["planning.timeline.withoutDate"] }));
    let visible = screen.getAllByTestId("timeline-card").map((card) => card.textContent);
    expect(visible.some((text) => text?.includes("Öffnung von Sektor D-4"))).toBe(true);
    expect(visible.some((text) => text?.includes("Der Große Bruch"))).toBe(false);

    // A name composes with the quick filter: Lin Chen stands only on the
    // dated accident, so within „Ohne Datum" the intersection is empty —
    // the honest no-results face stands with the clear door.
    fireEvent.click(screen.getByRole("button", { name: "Lin Chen" }));
    expect(screen.getByTestId("timeline-no-results")).toBeTruthy();
    expect(screen.getByText(de["planning.timeline.noResults"])).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: de["planning.timeline.clearFilters"] }));
    await waitFor(() => expect(screen.getAllByTestId("timeline-card")).toHaveLength(3));

    // Mit Kapitel keeps the linked rows alone; Alle returns everything.
    fireEvent.click(screen.getByRole("button", { name: de["planning.timeline.withChapter"] }));
    expect(screen.getAllByTestId("timeline-card")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: de["planning.timeline.all"] }));
    expect(screen.getAllByTestId("timeline-card")).toHaveLength(3);
  });
});

describe("the scene-status counters", () => {
  it("derive from the per-chapter fan-out, every real status counted", async () => {
    await renderTimeline();
    await screen.findAllByTestId("timeline-card");
    const counters = await screen.findByTestId("timeline-counters");
    // c1 (complete×2, in_progress×1) + c2 (planned×1) — the fan-out asked
    // each chapter once.
    const asks = api.GET.mock.calls.filter(
      ([path]) => path === "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes",
    );
    expect(asks).toHaveLength(2);
    expect(within(counters).getByText("2 verfasste Szenen")).toBeTruthy();
    expect(within(counters).getByText("1 Szene in Arbeit")).toBeTruthy();
    expect(within(counters).getByText("1 geplante Szene")).toBeTruthy();
    // The events' own honest count: one carries no free-text date.
    expect(within(counters).getByText("1 Ereignis ohne Datum")).toBeTruthy();
  });

  it("a failed fan-out invents no numbers — the counters wait without them", async () => {
    scenesFail = true;
    await renderTimeline();
    await screen.findAllByTestId("timeline-card");
    expect(screen.queryByTestId("timeline-counters")).toBeNull();
  });
});

describe("the honest states keep the doors", () => {
  it("pending: the subbar stands, the body waits", async () => {
    let resolveEvents!: (answer: { data: unknown; response: Response }) => void;
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/planning/novels/{novel_id}/timeline-events") {
        return new Promise<{ data: unknown; response: Response }>((resolve) => {
          resolveEvents = resolve;
        });
      }
      return baseGet(path);
    });
    const router = await renderTimeline();
    expect(screen.getByRole("status")).toBeTruthy();
    expectSiblingDoors();

    resolveEvents({ data: events, response: ok() });
    await waitFor(() => expect(screen.getAllByTestId("timeline-card")).toHaveLength(3));
    expect(router.state.location.pathname).toContain("/planning/timeline");
  });

  it("outage: the failure face with its retry, the doors still standing", async () => {
    eventsFail = true;
    await renderTimeline();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["planning.timeline.loadFailed"])).toBeTruthy();
    expectSiblingDoors();

    eventsFail = false;
    fireEvent.click(screen.getByRole("button", { name: de["planning.timeline.retry"] }));
    await waitFor(() => expect(screen.getAllByTestId("timeline-card")).toHaveLength(3));
  });

  it("empty: the honest empty face with the create door in reach", async () => {
    events = [];
    await renderTimeline();
    expect(await screen.findByTestId("timeline-empty")).toBeTruthy();
    expect(screen.getByText(de["planning.timeline.empty"])).toBeTruthy();
    expectSiblingDoors();
    expect(screen.getByRole("button", { name: de["planning.timeline.newEvent"] })).toBeTruthy();
  });
});

describe("the CRUD round-trips through the page", () => {
  it("create from the header door POSTs the row and refetches the list", async () => {
    await renderTimeline();
    await screen.findAllByTestId("timeline-card");
    fireEvent.click(screen.getByRole("button", { name: de["planning.timeline.newEvent"] }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(de["planning.crud.titleLabel"]), {
      target: { value: "Verlegung Transmitter L2" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: de["planning.crud.save"] }));
    await waitFor(() => expect(api.POST).toHaveBeenCalledWith(
      "/api/planning/novels/{novel_id}/timeline-events",
      {
        params: { path: { novel_id: NOVEL_ID } },
        body: {
          title: "Verlegung Transmitter L2",
          description: "",
          date_label: "",
          character_names: [],
          chapter_id: null,
          position: null,
        },
      },
    ));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    // The settle invalidated the list key; the refetch went out.
    await waitFor(() =>
      expect(
        api.GET.mock.calls.filter(
          ([path]) => path === "/api/planning/novels/{novel_id}/timeline-events",
        ).length,
      ).toBeGreaterThan(1),
    );
  });

  it("the undated placeholder opens the same create door", async () => {
    events = [BRUCH];
    await renderTimeline();
    await screen.findAllByTestId("timeline-card");
    fireEvent.click(
      screen.getByRole("button", { name: new RegExp(de["planning.timeline.newUndated"]) }),
    );
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(de["planning.crud.createTitle"])).toBeTruthy();
  });

  it("a card opens the edit; the remove hands off to the confirm and DELETEs", async () => {
    await renderTimeline();
    const cards = await screen.findAllByTestId("timeline-card");
    fireEvent.click(within(cards[0]).getByText("Der Große Bruch"));
    const edit = await screen.findByRole("dialog");
    expect(within(edit).getByText(de["planning.crud.editTitle"])).toBeTruthy();

    fireEvent.click(within(edit).getByRole("button", { name: de["planning.crud.remove"] }));
    const confirm = await screen.findByRole("alertdialog");
    fireEvent.click(within(confirm).getByRole("button", { name: de["planning.crud.deleteConfirm"] }));
    await waitFor(() => expect(api.DELETE).toHaveBeenCalledWith(
      "/api/planning/novels/{novel_id}/timeline-events/{event_id}",
      { params: { path: { novel_id: NOVEL_ID, event_id: "ev1" } } },
    ));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("an edit saves the dirtied fields through the page's card", async () => {
    await renderTimeline();
    const cards = await screen.findAllByTestId("timeline-card");
    fireEvent.click(within(cards[0]).getByText("Der Große Bruch"));
    const edit = await screen.findByRole("dialog");
    fireEvent.change(within(edit).getByLabelText(de["planning.crud.dateLabel"]), {
      target: { value: "2279" },
    });
    fireEvent.click(within(edit).getByRole("button", { name: de["planning.crud.save"] }));
    await waitFor(() => expect(api.PUT).toHaveBeenCalledWith(
      "/api/planning/novels/{novel_id}/timeline-events/{event_id}",
      {
        params: { path: { novel_id: NOVEL_ID, event_id: "ev1" } },
        body: { date_label: "2279" },
      },
    ));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});

describe("the sub-nav doors", () => {
  it("walk to the storyboard and the causality stubs", async () => {
    const router = await renderTimeline();
    await screen.findAllByTestId("timeline-card");
    fireEvent.click(within(screen.getByTestId("timeline-storyboard-door")).getByText(de["planning.sub.storyboard"]));
    await waitFor(() => expect(router.state.location.pathname).toContain("/planning/storyboard"));

    await renderTimeline();
    fireEvent.click(within(screen.getByTestId("timeline-causality-door")).getByText(de["planning.sub.causality"]));
  });

  it("the chapter-sequence view waits honestly — no face was drawn for it", async () => {
    await renderTimeline();
    await screen.findAllByTestId("timeline-card");
    const gap = screen.getByTestId("timeline-sequence-gap");
    expect(gap.getAttribute("aria-disabled")).toBe("true");
    expect(within(gap).getByText(de["planning.timeline.chapterSequenceNote"])).toBeTruthy();
  });
});
