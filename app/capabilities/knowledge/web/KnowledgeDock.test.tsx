// @vitest-environment jsdom
/**
 * The knowledge dock face (W5 Tasks 1/2) — the findings queue, the entity
 * chips and the extraction's suggestion review, all on the real API seam
 * (the shell's query hooks, the client mocked at its module boundary per
 * house pattern): the lists render the rows the server files, the review
 * decisions mutate with an honest pending face and name their refusal,
 * both triggers ride the 202 job lane with their honest busy until the
 * settle's refetch lands, and an empty queue reads as empty — never as an
 * outage. The entity chips are the novel's real rows, typed by the
 * contract's vocabulary; each is a door that opens the lore graph with the
 * row selected (Task 3 wired it). The #866/#867 interims are retired.
 *
 * The concurrency and lane pins (the PR #913 fixes): two review decisions
 * in flight keep BOTH cards' busy faces — the shared mutation observer
 * names only the last call, so the dock keeps its own per-row truth — and
 * a refusal names its own card alone. The job lanes live at module scope
 * keyed by novel: a dock closed mid-job resumes its busy face on reopen,
 * and a dead poll's click RESUMES the poll instead of enqueueing a second
 * job over work the server may still be running (a settled failure clears
 * the lane — only then is the next click a fresh enqueue — and so does a
 * poll that answered 404: the job row itself is gone, destroyed under the
 * session, and no resume can ever answer a dead id; 5xx and a dead wire
 * keep the resume, for the job may still live). Every test
 * that starts a job therefore settles its lane before ending, so the
 * module map hands the next test a clean novel.
 *
 * The face speaks du-tone in all three catalogs — each locale its own
 * copy, never a German fallback.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
  useSearch,
} from "@tanstack/react-router";
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import {
  client,
  type Accept,
  type Chapter,
  type Entity,
  type Finding,
  type Job,
  type Suggestion,
} from "@shell/lib/api/client";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";
import { de, en, fr, merged } from "@shell/lib/test/catalogs";

import { KnowledgeDock } from "./KnowledgeDock";

const api = client as unknown as Record<"GET" | "POST", ReturnType<typeof vi.fn>>;

// The full-suite run spawns one worker per file on a four-core box; the
// job poll's one-second beat needs a budget that survives the load (the
// workspace page test's own allowance).
configure({ asyncUtilTimeout: 5000 });

const NOVEL_ID = "11111111-1111-1111-1111-111111111111";

function ok(): Response {
  return new Response(null, { status: 200 });
}

function findingRow(overrides: Partial<Finding> = {}): Finding {
  return {
    id: "f1",
    novel_id: NOVEL_ID,
    summary: "Stationsbezeichnung uneinheitlich",
    detail: "Die Bezeichnung schwankt zwischen „Forschungsstation 7“ und „Station 9“.",
    status: "pending",
    created_at: "2026-11-18T10:00:00Z",
    ...overrides,
  };
}

const F2 = findingRow({
  id: "f2",
  summary: "Atemluft-Wert widerspricht sich",
  detail: null,
});

function entityRow(overrides: Partial<Entity> = {}): Entity {
  return {
    id: "e1",
    novel_id: NOVEL_ID,
    name: "ARIA",
    type: "character",
    aliases: [],
    tags: [],
    content: "",
    created_at: "2026-11-18T10:00:00Z",
    updated_at: "2026-11-18T10:00:00Z",
    ...overrides,
  };
}

const E2 = entityRow({ id: "e2", name: "Horizon Station", type: "location" });

function suggestionRow(overrides: Partial<Suggestion> = {}): Suggestion {
  return {
    id: "s1",
    novel_id: NOVEL_ID,
    chapter_id: "c2",
    name: "Dr. Maya Chen",
    type: "character",
    description: "Chefingenieurin der Tiefraum-Mission.",
    relations: [{ target_name: "Horizon Station", relation_type: "located_in" }],
    status: "pending",
    created_at: "2026-11-18T10:00:00Z",
    ...overrides,
  };
}

const S2 = suggestionRow({
  id: "s2",
  name: "Resonanz-Transmitter",
  type: "object",
  description: null,
  relations: [],
});

function chapterRow(overrides: Partial<Chapter> = {}): Chapter {
  return {
    id: "c1",
    novel_id: NOVEL_ID,
    position: 0,
    title: "Die Frequenz",
    scene_count: 1,
    word_count: 4120,
    target_words: null,
    created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-10T10:00:00Z",
    ...overrides,
  };
}

// The last-written chapter — the shell's dock fallback rule picks it.
const CH2 = chapterRow({
  id: "c2",
  position: 1,
  title: "Nevada Echoes",
  updated_at: "2026-11-18T10:00:00Z",
});

function jobRow(status: string, kind = "consistency"): Job {
  return { id: "j1", kind, status, progress: null, result: null, error: null };
}

/** The face under the workspace route's own param — the harness mirrors
 *  the generated table's composition: the dock is a child of the
 *  workspace route, and the face reads the novel from the parent. A graph
 *  route stub stands at the real graph path so the chip's door (Task 3)
 *  lands somewhere observable: it shows the `entity` param it was handed. */
const harnessRoot = createRootRoute({ component: () => <Outlet /> });

function GraphTarget() {
  const { entity } = useSearch({ from: "/novels/$novelId/knowledge/graph" });
  return <div data-testid="graph-target">{entity ?? "none"}</div>;
}

async function renderDock() {
  const workspace = createRoute({
    getParentRoute: () => harnessRoot,
    path: "/novels/$novelId",
    component: () => <Outlet />,
  });
  const dock = createRoute({
    getParentRoute: () => workspace,
    path: "knowledge",
    component: () => <KnowledgeDock />,
  });
  const graph = createRoute({
    getParentRoute: () => harnessRoot,
    path: "/novels/$novelId/knowledge/graph",
    validateSearch: (search: Record<string, unknown>): { entity?: string } =>
      typeof search.entity === "string" && search.entity !== "" ? { entity: search.entity } : {},
    component: GraphTarget,
  });
  const router = createRouter({
    routeTree: harnessRoot.addChildren([workspace.addChildren([dock]), graph]),
    history: createMemoryHistory({ initialEntries: [`/novels/${NOVEL_ID}/knowledge`] }),
  });
  await router.load();
  const face = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  // The unmount handle: the job-lane tests close the dock mid-job and
  // reopen it, pinning that the lane outlives the mount that started it.
  return face;
}

/** The answers the mock serves; the tests mutate them to model the
 *  server's rows after a review decision or a finished job. */
let queue: Finding[];
let entities: Entity[];
let suggestions: Suggestion[];
let chapters: Chapter[];
/** The job answer the mock serves; the tests advance it down the lane. */
let jobStatus: string;
let jobKind: string;

/** The base GET answer: every read the face makes, from the mutable
 *  state. A test driving one query by hand wraps this — the other faces
 *  keep their quiet answers, so one outage names itself alone. */
function baseGet(path: string): Promise<{ data: unknown; response: Response }> {
  if (path === "/api/knowledge/novels/{novel_id}/findings") {
    return Promise.resolve({ data: queue, response: ok() });
  }
  if (path === "/api/knowledge/novels/{novel_id}/entities") {
    return Promise.resolve({ data: entities, response: ok() });
  }
  if (path === "/api/knowledge/novels/{novel_id}/suggestions") {
    return Promise.resolve({ data: suggestions, response: ok() });
  }
  if (path === "/api/writing/novels/{novel_id}/chapters") {
    return Promise.resolve({ data: chapters, response: ok() });
  }
  if (path === "/api/jobs/{job_id}") {
    return Promise.resolve({ data: jobRow(jobStatus, jobKind), response: ok() });
  }
  throw new Error(`unexpected GET: ${path}`);
}

/** The job ids the mock hands out — one fresh id per enqueue, the
 *  server's own shape: a second job is a new row, never the settled one
 *  again (the client's query cache would serve the old answer and never
 *  ask). */
let jobSeq = 0;

function basePost(path: string): Promise<{ data: unknown; response: Response }> {
  if (path === "/api/knowledge/consistency/{novel_id}") {
    jobSeq += 1;
    return Promise.resolve({
      data: { job_id: `j${jobSeq}` },
      response: new Response(null, { status: 202 }),
    });
  }
  if (path === "/api/knowledge/extraction/{novel_id}") {
    jobSeq += 1;
    return Promise.resolve({
      data: { job_id: `j${jobSeq}` },
      response: new Response(null, { status: 202 }),
    });
  }
  if (path === "/api/knowledge/findings/{finding_id}/acknowledge") {
    return Promise.resolve({ data: findingRow({ status: "acknowledged" }), response: ok() });
  }
  if (path === "/api/knowledge/findings/{finding_id}/dismiss") {
    return Promise.resolve({ data: findingRow({ status: "dismissed" }), response: ok() });
  }
  if (path === "/api/knowledge/suggestions/{suggestion_id}/accept") {
    const accepted: Accept = { entity: entityRow({ id: "e-new" }), skipped_relations: [] };
    return Promise.resolve({ data: accepted, response: ok() });
  }
  if (path === "/api/knowledge/suggestions/{suggestion_id}/discard") {
    return Promise.resolve({ data: suggestionRow({ status: "discarded" }), response: ok() });
  }
  throw new Error(`unexpected POST: ${path}`);
}

beforeEach(() => {
  applyLocale("de");
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
  queue = [findingRow(), F2];
  entities = [entityRow(), E2];
  suggestions = [];
  chapters = [chapterRow(), CH2];
  jobStatus = "done";
  jobKind = "consistency";
  jobSeq = 0;
  api.GET.mockImplementation(baseGet);
  api.POST.mockImplementation(basePost);
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("the findings face reads the real queue", () => {
  it("renders the rows the server files — summary, detail, conflict badge, severity rail", async () => {
    await renderDock();
    const cards = await screen.findAllByTestId("knowledge-finding");
    expect(cards).toHaveLength(2);
    expect(within(cards[0]).getByText("Stationsbezeichnung uneinheitlich")).toBeTruthy();
    expect(
      within(cards[0]).getByText("Die Bezeichnung schwankt zwischen „Forschungsstation 7“ und „Station 9“."),
    ).toBeTruthy();
    expect(within(cards[0]).getByText(de["knowledge.dock.conflict"])).toBeTruthy();
    // The draft's severity shaping: the warning rail and the warning ink.
    // FindingRead carries no severity field — every finding is a
    // consistency conflict, so the draft's conflict tone stands for all.
    expect(cards[0].querySelector("[data-severity-rail]")?.className).toContain("bg-warning");
    // A null detail renders no paragraph — never an invented evidence.
    expect(within(cards[1]).getByText("Atemluft-Wert widerspricht sich")).toBeTruthy();
    expect(within(cards[1]).queryByText(/schwankt/)).toBeNull();
    // The ask carries the novel and the pending question.
    const call = api.GET.mock.calls.find(([path]) => path === "/api/knowledge/novels/{novel_id}/findings");
    expect(call?.[1]).toEqual({
      params: { path: { novel_id: NOVEL_ID }, query: { status: "pending" } },
    });
    // The diagnosis header counts the queue in the locale's own plural.
    expect(screen.getByText("2 offene Befunde")).toBeTruthy();
  });

  it("the singular count speaks the one form", async () => {
    queue = [findingRow()];
    await renderDock();
    expect(await screen.findByText("1 offener Befund")).toBeTruthy();
  });

  it("an empty queue reads as empty — the honest face, not an outage", async () => {
    queue = [];
    await renderDock();
    const empty = await screen.findByTestId("knowledge-empty");
    expect(within(empty).getByText(de["knowledge.dock.empty"])).toBeTruthy();
    expect(within(empty).getByText(de["knowledge.dock.emptyNote"])).toBeTruthy();
    expect(screen.queryByTestId("knowledge-finding")).toBeNull();
    expect(screen.getByText("0 offene Befunde")).toBeTruthy();
  });

  it("a pending ask shows the loading face, never an invented list", async () => {
    let resolveFindings: (value: { data: Finding[]; response: Response }) => void = () => {};
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/knowledge/novels/{novel_id}/findings") {
        return new Promise((resolve) => {
          resolveFindings = resolve;
        });
      }
      return baseGet(path);
    });
    await renderDock();
    expect(await screen.findByText(de["knowledge.dock.loading"])).toBeTruthy();
    expect(screen.queryByTestId("knowledge-finding")).toBeNull();
    resolveFindings({ data: [findingRow()], response: ok() });
    expect(await screen.findByTestId("knowledge-finding")).toBeTruthy();
  });

  it("an unavailable queue names itself and offers the retry", async () => {
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/knowledge/novels/{novel_id}/findings") {
        return Promise.resolve({ data: undefined, response: new Response(null, { status: 500 }) });
      }
      return baseGet(path);
    });
    await renderDock();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.dock.loadFailed"])).toBeTruthy();
    queue = [findingRow()];
    api.GET.mockImplementation(baseGet);
    fireEvent.click(within(alert).getByRole("button", { name: de["knowledge.dock.retry"] }));
    expect(await screen.findByTestId("knowledge-finding")).toBeTruthy();
  });
});

describe("the two review decisions are real mutations", () => {
  it("acknowledge posts the finding's own door and the queue refetches", async () => {
    await renderDock();
    const cards = await screen.findAllByTestId("knowledge-finding");
    // The server consumes the row at the moment the POST lands: the
    // queue the refetch reads already lacks it — no race between the
    // decision and the answer it moves.
    queue = [F2];
    fireEvent.click(within(cards[0]).getByRole("button", { name: de["knowledge.dock.acknowledge"] }));
    await waitFor(() => {
      const call = api.POST.mock.calls.find(
        ([path]) => path === "/api/knowledge/findings/{finding_id}/acknowledge",
      );
      expect(call?.[1]).toEqual({ params: { path: { finding_id: "f1" } } });
    });
    // The settled decision refetches the queue — the server's truth, not
    // an optimistic removal: the acknowledged row leaves when the answer
    // says it left.
    await waitFor(() => expect(screen.getAllByTestId("knowledge-finding")).toHaveLength(1));
    expect(screen.getByText("Atemluft-Wert widerspricht sich")).toBeTruthy();
  });

  it("dismiss posts the finding's own door and the queue refetches", async () => {
    await renderDock();
    const cards = await screen.findAllByTestId("knowledge-finding");
    queue = [findingRow()];
    fireEvent.click(within(cards[1]).getByRole("button", { name: de["knowledge.dock.dismiss"] }));
    await waitFor(() => {
      const call = api.POST.mock.calls.find(
        ([path]) => path === "/api/knowledge/findings/{finding_id}/dismiss",
      );
      expect(call?.[1]).toEqual({ params: { path: { finding_id: "f2" } } });
    });
    await waitFor(() => expect(screen.getAllByTestId("knowledge-finding")).toHaveLength(1));
    expect(screen.getByText("Stationsbezeichnung uneinheitlich")).toBeTruthy();
  });

  it("a pending decision wears the busy face — its own card alone", async () => {
    let resolveAck: (value: { data: Finding; response: Response }) => void = () => {};
    api.POST.mockImplementation(
      (path: string) =>
        new Promise((resolve) => {
          if (path === "/api/knowledge/findings/{finding_id}/acknowledge") resolveAck = resolve;
        }),
    );
    await renderDock();
    const cards = await screen.findAllByTestId("knowledge-finding");
    const ack = within(cards[0]).getByRole("button", { name: de["knowledge.dock.acknowledge"] });
    fireEvent.click(ack);
    await waitFor(() => expect((ack as HTMLButtonElement).disabled).toBe(true));
    expect(ack.getAttribute("aria-busy")).toBe("true");
    // The card's OTHER door locks with it — the server consumes the
    // finding once, so a sibling click would race the same row into a 409.
    const ownDismiss = within(cards[0]).getByRole("button", { name: de["knowledge.dock.dismiss"] });
    expect((ownDismiss as HTMLButtonElement).disabled).toBe(true);
    // The sibling card's decisions stay live — one pending ask locks one
    // card, never the whole queue.
    const sibling = within(cards[1]).getByRole("button", { name: de["knowledge.dock.acknowledge"] });
    expect((sibling as HTMLButtonElement).disabled).toBe(false);
    const siblingDismiss = within(cards[1]).getByRole("button", { name: de["knowledge.dock.dismiss"] });
    expect((siblingDismiss as HTMLButtonElement).disabled).toBe(false);
    queue = [F2];
    resolveAck({ data: findingRow({ status: "acknowledged" }), response: ok() });
    await waitFor(() => expect(screen.getAllByTestId("knowledge-finding")).toHaveLength(1));
  });

  it("a pending dismiss locks its card's acknowledge too — the guard is symmetric", async () => {
    let resolveDismiss: (value: { data: Finding; response: Response }) => void = () => {};
    api.POST.mockImplementation(
      (path: string) =>
        new Promise((resolve) => {
          if (path === "/api/knowledge/findings/{finding_id}/dismiss") resolveDismiss = resolve;
        }),
    );
    await renderDock();
    const cards = await screen.findAllByTestId("knowledge-finding");
    const dismiss = within(cards[1]).getByRole("button", { name: de["knowledge.dock.dismiss"] });
    fireEvent.click(dismiss);
    await waitFor(() => expect((dismiss as HTMLButtonElement).disabled).toBe(true));
    expect(dismiss.getAttribute("aria-busy")).toBe("true");
    const ownAck = within(cards[1]).getByRole("button", { name: de["knowledge.dock.acknowledge"] });
    expect((ownAck as HTMLButtonElement).disabled).toBe(true);
    // The busy ink stays on the door whose ask is in flight — the locked
    // sibling is disabled, not busy.
    expect(ownAck.getAttribute("aria-busy")).toBe("false");
    const otherAck = within(cards[0]).getByRole("button", { name: de["knowledge.dock.acknowledge"] });
    expect((otherAck as HTMLButtonElement).disabled).toBe(false);
    queue = [findingRow()];
    resolveDismiss({ data: findingRow({ id: "f2", status: "dismissed" }), response: ok() });
    await waitFor(() => expect(screen.getAllByTestId("knowledge-finding")).toHaveLength(1));
  });

  it("a refused decision names itself on its card and unlocks it again", async () => {
    api.POST.mockImplementation(async (path: string) => {
      if (path === "/api/knowledge/findings/{finding_id}/acknowledge") {
        return { data: undefined, response: new Response(null, { status: 409 }) };
      }
      throw new Error(`unexpected POST: ${path}`);
    });
    await renderDock();
    const cards = await screen.findAllByTestId("knowledge-finding");
    const ack = within(cards[0]).getByRole("button", { name: de["knowledge.dock.acknowledge"] });
    fireEvent.click(ack);
    const alert = await within(cards[0]).findByRole("alert");
    expect(within(alert).getByText(de["knowledge.dock.actionFailed"])).toBeTruthy();
    await waitFor(() => expect((ack as HTMLButtonElement).disabled).toBe(false));
    // The 409's refetch keeps the card standing — the queue is the truth.
    expect(screen.getAllByTestId("knowledge-finding")).toHaveLength(2);
  });

  it("two decisions in flight keep both cards busy — the observer's last call repaints neither idle", async () => {
    // Both acks hang, each on its own row: the shared mutation observer
    // holds only the LAST call's variables, so the second click is the
    // trap — the first card must stay busy on the dock's own per-row
    // truth, never on the observer's single slot.
    const answers = new Map<string, (value: { data: Finding | undefined; response: Response }) => void>();
    api.POST.mockImplementation((path: string, init: { params: { path: { finding_id: string } } }) =>
      new Promise((resolve) => {
        if (path === "/api/knowledge/findings/{finding_id}/acknowledge") {
          answers.set(init.params.path.finding_id, resolve);
        }
      }),
    );
    await renderDock();
    const cards = await screen.findAllByTestId("knowledge-finding");
    const first = within(cards[0]).getByRole("button", { name: de["knowledge.dock.acknowledge"] });
    const second = within(cards[1]).getByRole("button", { name: de["knowledge.dock.acknowledge"] });
    fireEvent.click(first);
    await waitFor(() => expect((first as HTMLButtonElement).disabled).toBe(true));
    fireEvent.click(second);
    await waitFor(() => expect((second as HTMLButtonElement).disabled).toBe(true));
    // BOTH busy faces stand under concurrency: a decision elsewhere never
    // repaints a card idle while its own ask still flies — an unlocked
    // door here would race the same row into a second POST.
    expect((first as HTMLButtonElement).disabled).toBe(true);
    expect(first.getAttribute("aria-busy")).toBe("true");
    expect(second.getAttribute("aria-busy")).toBe("true");
    // The first card's refusal names its own card alone: the sibling
    // keeps its busy face and wears no alert it did not earn.
    answers.get("f1")?.({ data: undefined, response: new Response(null, { status: 409 }) });
    const refusal = await within(cards[0]).findByRole("alert");
    expect(within(refusal).getByText(de["knowledge.dock.actionFailed"])).toBeTruthy();
    expect(within(cards[1]).queryByRole("alert")).toBeNull();
    expect((second as HTMLButtonElement).disabled).toBe(true);
    expect(second.getAttribute("aria-busy")).toBe("true");
    // The sibling's answer settles its own card; the queue refetches.
    queue = [findingRow()];
    answers.get("f2")?.({ data: findingRow({ id: "f2", status: "acknowledged" }), response: ok() });
    await waitFor(() => expect(screen.getAllByTestId("knowledge-finding")).toHaveLength(1));
    expect(screen.getByText("Stationsbezeichnung uneinheitlich")).toBeTruthy();
  });
});

describe("the consistency trigger rides the job lane honestly", () => {
  it("posts the check, stands busy until the findings refetch, then counts the result", async () => {
    queue = [];
    // The job's answer is the test's to give: the busy face stands while
    // the poll is outstanding, and settles exactly when the lane answers.
    let resolveJob: (value: { data: Job; response: Response }) => void = () => {};
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/jobs/{job_id}") {
        return new Promise((resolve) => {
          resolveJob = resolve;
        });
      }
      return baseGet(path);
    });
    await renderDock();
    expect(await screen.findByTestId("knowledge-empty")).toBeTruthy();
    const trigger = screen.getByRole("button", { name: de["knowledge.dock.check"] });
    // The check files its finding while the job runs: the queue the
    // settle's refetch reads already carries it (the race-free order —
    // the mutation lands before any awaited answer resolves).
    queue = [findingRow()];
    fireEvent.click(trigger);
    // The 202's job id opens the poll; the busy face stands in the
    // trigger's own place — no invented progress, no fake finding.
    await waitFor(() => {
      const call = api.POST.mock.calls.find(([path]) => path === "/api/knowledge/consistency/{novel_id}");
      expect(call?.[1]).toEqual({ params: { path: { novel_id: NOVEL_ID } } });
    });
    expect(await screen.findByText(de["knowledge.dock.checkBusy"])).toBeTruthy();
    expect((trigger as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByTestId("knowledge-finding")).toBeNull();
    // The settled job refetches the queue; the count reads the result.
    resolveJob({ data: jobRow("done"), response: ok() });
    await waitFor(() => expect(screen.queryByText(de["knowledge.dock.checkBusy"])).toBeNull());
    expect(await screen.findByTestId("knowledge-finding")).toBeTruthy();
    expect(screen.getByText("1 offener Befund")).toBeTruthy();
    expect((screen.getByRole("button", { name: de["knowledge.dock.check"] }) as HTMLButtonElement).disabled).toBe(false);
    // The poll asked the job's own door.
    expect(api.GET.mock.calls.some(([path]) => path === "/api/jobs/{job_id}")).toBe(true);
  });

  it("a running job keeps the busy face across the poll's beat", async () => {
    jobStatus = "running";
    await renderDock();
    const trigger = await screen.findByRole("button", { name: de["knowledge.dock.check"] });
    fireEvent.click(trigger);
    expect(await screen.findByText(de["knowledge.dock.checkBusy"])).toBeTruthy();
    // The first poll answers running — the busy face holds. The lane's
    // one-second beat asks again; the second answer settles the job.
    await waitFor(() =>
      expect(api.GET.mock.calls.filter(([path]) => path === "/api/jobs/{job_id}").length).toBeGreaterThanOrEqual(1),
    );
    expect(screen.getByText(de["knowledge.dock.checkBusy"])).toBeTruthy();
    jobStatus = "done";
    await waitFor(() => expect(screen.queryByText(de["knowledge.dock.checkBusy"])).toBeNull(), {
      timeout: 5000,
    });
  });

  it("a refused enqueue names itself and keeps the trigger live", async () => {
    api.POST.mockImplementation(async (path: string) => {
      if (path === "/api/knowledge/consistency/{novel_id}") {
        return { data: undefined, response: new Response(null, { status: 409 }) };
      }
      throw new Error(`unexpected POST: ${path}`);
    });
    await renderDock();
    const trigger = await screen.findByRole("button", { name: de["knowledge.dock.check"] });
    fireEvent.click(trigger);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.dock.checkFailed"])).toBeTruthy();
    expect((trigger as HTMLButtonElement).disabled).toBe(false);
    expect(screen.queryByText(de["knowledge.dock.checkBusy"])).toBeNull();
  });

  it("a failed job names itself after the settle — the queue still refetches", async () => {
    jobStatus = "failed";
    await renderDock();
    const trigger = await screen.findByRole("button", { name: de["knowledge.dock.check"] });
    fireEvent.click(trigger);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.dock.checkFailed"])).toBeTruthy();
    await waitFor(() => expect((trigger as HTMLButtonElement).disabled).toBe(false));
    expect(screen.queryByText(de["knowledge.dock.checkBusy"])).toBeNull();
    // The settled failure cleared the lane — the next click is a fresh
    // enqueue, the retry contract's other half (only a live lane resumes),
    // and the fresh job is a new row the poll asks for and settles.
    jobStatus = "done";
    const findingsReads = () =>
      api.GET.mock.calls.filter(([path]) => path === "/api/knowledge/novels/{novel_id}/findings")
        .length;
    const before = findingsReads();
    fireEvent.click(trigger);
    await waitFor(() =>
      expect(
        api.POST.mock.calls.filter(([path]) => path === "/api/knowledge/consistency/{novel_id}"),
      ).toHaveLength(2),
    );
    // The second job's settle lands: the findings read again (the settle
    // beat's own refetch) and the lane clears behind it.
    await waitFor(() => expect(findingsReads()).toBeGreaterThan(before), { timeout: 5000 });
  });

  it("a dead poll's click resumes the lane — never a second enqueue over work that may still run", async () => {
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/jobs/{job_id}") {
        return Promise.resolve({ data: undefined, response: new Response(null, { status: 500 }) });
      }
      return baseGet(path);
    });
    await renderDock();
    const trigger = await screen.findByRole("button", { name: de["knowledge.dock.check"] });
    fireEvent.click(trigger);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.dock.pollFailed"])).toBeTruthy();
    await waitFor(() => expect((trigger as HTMLButtonElement).disabled).toBe(false));
    // The lane still holds the job: the click must RESUME the poll, not
    // enqueue a second check the server may already be running (the API
    // guards nothing here — no endpoint refuses a concurrent job).
    api.GET.mockImplementation(baseGet);
    queue = [findingRow()];
    const polls = () =>
      api.GET.mock.calls.filter(([path]) => path === "/api/jobs/{job_id}").length;
    const before = polls();
    fireEvent.click(trigger);
    await waitFor(() => expect(polls()).toBeGreaterThan(before), { timeout: 5000 });
    // The resumed poll answers done: the settle lands, the queue refetches,
    // and the enqueue count never moved past one.
    await waitFor(() => expect(screen.queryByText(de["knowledge.dock.checkBusy"])).toBeNull(), {
      timeout: 5000,
    });
    expect(
      api.POST.mock.calls.filter(([path]) => path === "/api/knowledge/consistency/{novel_id}"),
    ).toHaveLength(1);
    expect(await screen.findByText("1 offener Befund")).toBeTruthy();
  });

  it("a poll that answers 404 clears the lane — the click enqueues fresh, never resumes a dead row", async () => {
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/jobs/{job_id}") {
        return Promise.resolve({ data: undefined, response: new Response(null, { status: 404 }) });
      }
      return baseGet(path);
    });
    await renderDock();
    const trigger = await screen.findByRole("button", { name: de["knowledge.dock.check"] });
    fireEvent.click(trigger);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.dock.pollFailed"])).toBeTruthy();
    await waitFor(() => expect((trigger as HTMLButtonElement).disabled).toBe(false));
    // The job row is gone — destroyed under the session, the server's
    // own answer for a dead id — so a resume would re-ask a door that
    // can never answer and only a reload could recover. The click must
    // enqueue FRESH over the cleared lane instead.
    api.GET.mockImplementation(baseGet);
    queue = [findingRow()];
    fireEvent.click(trigger);
    await waitFor(() =>
      expect(
        api.POST.mock.calls.filter(([path]) => path === "/api/knowledge/consistency/{novel_id}"),
      ).toHaveLength(2),
    );
    // The fresh job is a new row the poll asks for; the settle lands and
    // the lane clears behind it.
    await waitFor(() => expect(screen.queryByText(de["knowledge.dock.checkBusy"])).toBeNull(), {
      timeout: 5000,
    });
    expect(await screen.findByText("1 offener Befund")).toBeTruthy();
  });

  it("a network-dead poll keeps the resume contract — the job may still live server-side", async () => {
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/jobs/{job_id}") {
        return Promise.reject(new TypeError("Failed to fetch"));
      }
      return baseGet(path);
    });
    await renderDock();
    const trigger = await screen.findByRole("button", { name: de["knowledge.dock.check"] });
    fireEvent.click(trigger);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.dock.pollFailed"])).toBeTruthy();
    await waitFor(() => expect((trigger as HTMLButtonElement).disabled).toBe(false));
    // The wire died, not the row: a network failure carries no status,
    // and the click must still RESUME the poll — the job may still be
    // running server-side, and a fresh enqueue would pile onto it.
    api.GET.mockImplementation(baseGet);
    queue = [findingRow()];
    const polls = () =>
      api.GET.mock.calls.filter(([path]) => path === "/api/jobs/{job_id}").length;
    const before = polls();
    fireEvent.click(trigger);
    await waitFor(() => expect(polls()).toBeGreaterThan(before), { timeout: 5000 });
    await waitFor(() => expect(screen.queryByText(de["knowledge.dock.checkBusy"])).toBeNull(), {
      timeout: 5000,
    });
    expect(
      api.POST.mock.calls.filter(([path]) => path === "/api/knowledge/consistency/{novel_id}"),
    ).toHaveLength(1);
    expect(await screen.findByText("1 offener Befund")).toBeTruthy();
  });

  it("closing the dock mid-job does not lose the lane — a reopened dock resumes and lands the settle", async () => {
    jobStatus = "running";
    const first = await renderDock();
    const trigger = await screen.findByRole("button", { name: de["knowledge.dock.check"] });
    fireEvent.click(trigger);
    expect(await screen.findByText(de["knowledge.dock.checkBusy"])).toBeTruthy();
    // The dock closes while the job runs; the server finishes unwatched.
    first.unmount();
    jobStatus = "done";
    queue = [findingRow()];
    await renderDock();
    // The reopened dock resumes the busy face — the trigger never went
    // idle, so no second enqueue can pile onto work the server ran.
    expect(await screen.findByText(de["knowledge.dock.checkBusy"])).toBeTruthy();
    expect(
      api.POST.mock.calls.filter(([path]) => path === "/api/knowledge/consistency/{novel_id}"),
    ).toHaveLength(1);
    // The resumed poll answers done; the settle lands — the queue
    // refetches and the count reads the result.
    await waitFor(() => expect(screen.queryByText(de["knowledge.dock.checkBusy"])).toBeNull(), {
      timeout: 5000,
    });
    expect(await screen.findByText("1 offener Befund")).toBeTruthy();
  });
});

describe("the entity chips read the novel's real rows", () => {
  it("renders the entities the server files — name, type label, glyph, count", async () => {
    await renderDock();
    const chips = await screen.findAllByTestId("knowledge-entity-chip");
    expect(chips).toHaveLength(2);
    expect(within(chips[0]).getByText("ARIA")).toBeTruthy();
    expect(within(chips[0]).getByText(de["knowledge.type.character"])).toBeTruthy();
    expect(within(chips[1]).getByText("Horizon Station")).toBeTruthy();
    expect(within(chips[1]).getByText(de["knowledge.type.location"])).toBeTruthy();
    // The type's glyph rides the chip (the draft's entity-pill icon).
    expect(chips[0].querySelector("svg")).not.toBeNull();
    // The header counts the list in the locale's own plural.
    expect(screen.getByText("2 Entitäten")).toBeTruthy();
    // The ask carries the novel and no filter — the whole canon.
    const call = api.GET.mock.calls.find(([path]) => path === "/api/knowledge/novels/{novel_id}/entities");
    expect(call?.[1]).toEqual({
      params: { path: { novel_id: NOVEL_ID }, query: { type: undefined, tag: undefined, q: undefined } },
    });
  });

  it("the singular count speaks the one form", async () => {
    entities = [entityRow()];
    await renderDock();
    expect(await screen.findByText("1 Entität")).toBeTruthy();
  });

  it("a type outside the contract falls back to the generic label — never a crash", async () => {
    entities = [entityRow({ type: "contraption" })];
    await renderDock();
    const chip = await screen.findByTestId("knowledge-entity-chip");
    expect(within(chip).getByText(de["knowledge.type.generic"])).toBeTruthy();
  });

  it("the chip is a door — it opens the lore graph with the row selected (Task 3)", async () => {
    await renderDock();
    const chips = await screen.findAllByTestId("knowledge-entity-chip");
    // The inert interim retired: the chip is a button now, and its click
    // navigates to the graph with this row's id in the `entity` param.
    expect(chips[0].tagName).toBe("BUTTON");
    fireEvent.click(chips[0]);
    const target = await screen.findByTestId("graph-target");
    expect(target.textContent).toBe("e1");
  });

  it("an empty list reads as empty — the honest face, not an outage", async () => {
    entities = [];
    await renderDock();
    const empty = await screen.findByTestId("knowledge-entities-empty");
    expect(within(empty).getByText(de["knowledge.dock.entitiesEmpty"])).toBeTruthy();
    expect(within(empty).getByText(de["knowledge.dock.entitiesEmptyNote"])).toBeTruthy();
    expect(screen.queryByTestId("knowledge-entity-chip")).toBeNull();
    expect(screen.getByText("0 Entitäten")).toBeTruthy();
  });

  it("a pending ask shows the loading face, never an invented chip", async () => {
    let resolveEntities: (value: { data: Entity[]; response: Response }) => void = () => {};
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/knowledge/novels/{novel_id}/entities") {
        return new Promise((resolve) => {
          resolveEntities = resolve;
        });
      }
      return baseGet(path);
    });
    await renderDock();
    expect(await screen.findByText(de["knowledge.dock.entitiesLoading"])).toBeTruthy();
    expect(screen.queryByTestId("knowledge-entity-chip")).toBeNull();
    resolveEntities({ data: [entityRow()], response: ok() });
    expect(await screen.findByTestId("knowledge-entity-chip")).toBeTruthy();
  });

  it("an unavailable list names itself and offers the retry", async () => {
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/knowledge/novels/{novel_id}/entities") {
        return Promise.resolve({ data: undefined, response: new Response(null, { status: 500 }) });
      }
      return baseGet(path);
    });
    await renderDock();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.dock.entitiesFailed"])).toBeTruthy();
    api.GET.mockImplementation(baseGet);
    fireEvent.click(within(alert).getByRole("button", { name: de["knowledge.dock.retry"] }));
    // The refetched canon: both rows the base answer carries.
    expect(await screen.findAllByTestId("knowledge-entity-chip")).toHaveLength(2);
  });
});

describe("the extraction trigger rides the job lane honestly", () => {
  it("posts the last-written chapter, stands busy until the suggestions refetch", async () => {
    jobKind = "extraction";
    suggestions = [];
    let resolveJob: (value: { data: Job; response: Response }) => void = () => {};
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/jobs/{job_id}") {
        return new Promise((resolve) => {
          resolveJob = resolve;
        });
      }
      return baseGet(path);
    });
    await renderDock();
    const trigger = await screen.findByRole("button", { name: de["knowledge.dock.extract"] });
    // The target note names the chapter the extraction reads — the
    // shell's dock fallback: the last-written chapter, never a guess.
    expect(screen.getByText(de["knowledge.dock.extractTarget"].replace("{title}", "Nevada Echoes"))).toBeTruthy();
    // The job files its suggestion while it runs: the queue the settle's
    // refetch reads already carries it (the race-free order).
    suggestions = [suggestionRow()];
    fireEvent.click(trigger);
    await waitFor(() => {
      const call = api.POST.mock.calls.find(([path]) => path === "/api/knowledge/extraction/{novel_id}");
      expect(call?.[1]).toEqual({
        params: { path: { novel_id: NOVEL_ID } },
        body: { chapter_id: "c2" },
      });
    });
    expect(await screen.findByText(de["knowledge.dock.extractBusy"])).toBeTruthy();
    expect((trigger as HTMLButtonElement).disabled).toBe(true);
    expect(trigger.getAttribute("aria-busy")).toBe("true");
    expect(screen.queryByTestId("knowledge-suggestion")).toBeNull();
    // The settled job refetches the queue; the proposal stands for review.
    resolveJob({ data: jobRow("done", "extraction"), response: ok() });
    await waitFor(() => expect(screen.queryByText(de["knowledge.dock.extractBusy"])).toBeNull());
    expect(await screen.findByTestId("knowledge-suggestion")).toBeTruthy();
    expect(
      (screen.getByRole("button", { name: de["knowledge.dock.extract"] }) as HTMLButtonElement).disabled,
    ).toBe(false);
    expect(api.GET.mock.calls.some(([path]) => path === "/api/jobs/{job_id}")).toBe(true);
  });

  it("a running job keeps the busy face across the poll's beat", async () => {
    jobKind = "extraction";
    jobStatus = "running";
    await renderDock();
    const trigger = await screen.findByRole("button", { name: de["knowledge.dock.extract"] });
    fireEvent.click(trigger);
    expect(await screen.findByText(de["knowledge.dock.extractBusy"])).toBeTruthy();
    await waitFor(() =>
      expect(api.GET.mock.calls.filter(([path]) => path === "/api/jobs/{job_id}").length).toBeGreaterThanOrEqual(1),
    );
    expect(screen.getByText(de["knowledge.dock.extractBusy"])).toBeTruthy();
    jobStatus = "done";
    await waitFor(() => expect(screen.queryByText(de["knowledge.dock.extractBusy"])).toBeNull(), {
      timeout: 5000,
    });
  });

  it("a refused enqueue names itself and keeps the trigger live", async () => {
    api.POST.mockImplementation(async (path: string) => {
      if (path === "/api/knowledge/extraction/{novel_id}") {
        return { data: undefined, response: new Response(null, { status: 409 }) };
      }
      throw new Error(`unexpected POST: ${path}`);
    });
    await renderDock();
    const trigger = await screen.findByRole("button", { name: de["knowledge.dock.extract"] });
    fireEvent.click(trigger);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.dock.extractFailed"])).toBeTruthy();
    expect((trigger as HTMLButtonElement).disabled).toBe(false);
    expect(screen.queryByText(de["knowledge.dock.extractBusy"])).toBeNull();
  });

  it("a failed job names itself after the settle — the queue still refetches", async () => {
    jobKind = "extraction";
    jobStatus = "failed";
    await renderDock();
    const trigger = await screen.findByRole("button", { name: de["knowledge.dock.extract"] });
    fireEvent.click(trigger);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.dock.extractFailed"])).toBeTruthy();
    await waitFor(() => expect((trigger as HTMLButtonElement).disabled).toBe(false));
    expect(screen.queryByText(de["knowledge.dock.extractBusy"])).toBeNull();
    // The settled failure cleared the lane — the next click is a fresh
    // enqueue, the retry contract's other half (only a live lane
    // resumes), and the fresh job is a new row the poll asks for and
    // settles. The check lane's own pin's twin: the lanes share the
    // code shape, so they share the pin.
    jobStatus = "done";
    const suggestionsReads = () =>
      api.GET.mock.calls.filter(([path]) => path === "/api/knowledge/novels/{novel_id}/suggestions")
        .length;
    const before = suggestionsReads();
    fireEvent.click(trigger);
    await waitFor(() =>
      expect(
        api.POST.mock.calls.filter(([path]) => path === "/api/knowledge/extraction/{novel_id}"),
      ).toHaveLength(2),
    );
    // The second job's settle lands: the suggestions read again (the
    // settle beat's own refetch) and the lane clears behind it.
    await waitFor(() => expect(suggestionsReads()).toBeGreaterThan(before), { timeout: 5000 });
  });

  it("a dead poll unlocks the trigger and names itself apart — and the click resumes the lane", async () => {
    jobKind = "extraction";
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/jobs/{job_id}") {
        return Promise.resolve({ data: undefined, response: new Response(null, { status: 500 }) });
      }
      return baseGet(path);
    });
    await renderDock();
    const trigger = await screen.findByRole("button", { name: de["knowledge.dock.extract"] });
    fireEvent.click(trigger);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.dock.extractPollFailed"])).toBeTruthy();
    await waitFor(() => expect((trigger as HTMLButtonElement).disabled).toBe(false));
    expect(screen.queryByText(de["knowledge.dock.extractBusy"])).toBeNull();
    // The lane still holds the job: the click resumes the poll — never a
    // second enqueue over work the server may already be running.
    api.GET.mockImplementation(baseGet);
    suggestions = [suggestionRow()];
    const polls = () =>
      api.GET.mock.calls.filter(([path]) => path === "/api/jobs/{job_id}").length;
    const before = polls();
    fireEvent.click(trigger);
    await waitFor(() => expect(polls()).toBeGreaterThan(before), { timeout: 5000 });
    await waitFor(() => expect(screen.queryByText(de["knowledge.dock.extractBusy"])).toBeNull(), {
      timeout: 5000,
    });
    expect(
      api.POST.mock.calls.filter(([path]) => path === "/api/knowledge/extraction/{novel_id}"),
    ).toHaveLength(1);
    expect(await screen.findByTestId("knowledge-suggestion")).toBeTruthy();
  });

  it("a poll that answers 404 clears the lane — the click enqueues fresh, never resumes a dead row", async () => {
    jobKind = "extraction";
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/jobs/{job_id}") {
        return Promise.resolve({ data: undefined, response: new Response(null, { status: 404 }) });
      }
      return baseGet(path);
    });
    await renderDock();
    const trigger = await screen.findByRole("button", { name: de["knowledge.dock.extract"] });
    fireEvent.click(trigger);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.dock.extractPollFailed"])).toBeTruthy();
    await waitFor(() => expect((trigger as HTMLButtonElement).disabled).toBe(false));
    // The check lane's own pin's twin: the job row is gone (404 — the
    // server's answer for a destroyed id), and a resume would re-ask a
    // door that can never answer. The click enqueues FRESH over the
    // cleared lane; the fresh job is a new row that settles.
    api.GET.mockImplementation(baseGet);
    suggestions = [suggestionRow()];
    fireEvent.click(trigger);
    await waitFor(() =>
      expect(
        api.POST.mock.calls.filter(([path]) => path === "/api/knowledge/extraction/{novel_id}"),
      ).toHaveLength(2),
    );
    await waitFor(() => expect(screen.queryByText(de["knowledge.dock.extractBusy"])).toBeNull(), {
      timeout: 5000,
    });
    expect(await screen.findByTestId("knowledge-suggestion")).toBeTruthy();
  });

  it("closing the dock mid-job does not lose the lane — a reopened dock resumes and lands the settle", async () => {
    jobKind = "extraction";
    jobStatus = "running";
    const first = await renderDock();
    const trigger = await screen.findByRole("button", { name: de["knowledge.dock.extract"] });
    fireEvent.click(trigger);
    expect(await screen.findByText(de["knowledge.dock.extractBusy"])).toBeTruthy();
    // The dock closes while the job runs; the server finishes unwatched.
    first.unmount();
    jobStatus = "done";
    suggestions = [suggestionRow()];
    await renderDock();
    // The reopened dock resumes the busy face — the trigger never went
    // idle, so no second enqueue can pile onto work the server ran.
    expect(await screen.findByText(de["knowledge.dock.extractBusy"])).toBeTruthy();
    expect(
      api.POST.mock.calls.filter(([path]) => path === "/api/knowledge/extraction/{novel_id}"),
    ).toHaveLength(1);
    // The resumed poll answers done; the settle lands — the proposal
    // stands for review.
    await waitFor(() => expect(screen.queryByText(de["knowledge.dock.extractBusy"])).toBeNull(), {
      timeout: 5000,
    });
    expect(await screen.findByTestId("knowledge-suggestion")).toBeTruthy();
  });

  it("a novel without chapters keeps the trigger honest — the note, no ask", async () => {
    chapters = [];
    await renderDock();
    expect(await screen.findByText(de["knowledge.dock.noChapters"])).toBeTruthy();
    expect(screen.queryByRole("button", { name: de["knowledge.dock.extract"] })).toBeNull();
    expect(api.POST.mock.calls.filter(([path]) => path === "/api/knowledge/extraction/{novel_id}")).toHaveLength(0);
  });

  it("an unavailable chapter list names itself and offers the retry", async () => {
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/writing/novels/{novel_id}/chapters") {
        return Promise.resolve({ data: undefined, response: new Response(null, { status: 500 }) });
      }
      return baseGet(path);
    });
    await renderDock();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.dock.chaptersFailed"])).toBeTruthy();
    api.GET.mockImplementation(baseGet);
    fireEvent.click(within(alert).getByRole("button", { name: de["knowledge.dock.retry"] }));
    expect(await screen.findByRole("button", { name: de["knowledge.dock.extract"] })).toBeTruthy();
  });
});

describe("the suggestion review is real mutations", () => {
  it("renders the proposal — name, type badge, description, proposed relations", async () => {
    suggestions = [suggestionRow(), S2];
    await renderDock();
    const cards = await screen.findAllByTestId("knowledge-suggestion");
    expect(cards).toHaveLength(2);
    expect(within(cards[0]).getByText("Dr. Maya Chen")).toBeTruthy();
    expect(within(cards[0]).getByText(de["knowledge.dock.suggestion"])).toBeTruthy();
    expect(within(cards[0]).getByText(de["knowledge.type.character"])).toBeTruthy();
    expect(within(cards[0]).getByText("Chefingenieurin der Tiefraum-Mission.")).toBeTruthy();
    // The proposal's edges ride the card: the target's name and the
    // vocabulary's wording for the type.
    expect(within(cards[0]).getByText(/Horizon Station/)).toBeTruthy();
    expect(within(cards[0]).getByText(de["knowledge.relation.located_in"])).toBeTruthy();
    // A null description renders no paragraph; an empty edge list no block.
    expect(within(cards[1]).getByText("Resonanz-Transmitter")).toBeTruthy();
    expect(within(cards[1]).queryByText(/Chefingenieurin/)).toBeNull();
    expect(within(cards[1]).queryByText(de["knowledge.dock.suggestionRelations"])).toBeNull();
    // The queue ask carries the pending question.
    const call = api.GET.mock.calls.find(([path]) => path === "/api/knowledge/novels/{novel_id}/suggestions");
    expect(call?.[1]).toEqual({
      params: { path: { novel_id: NOVEL_ID }, query: { status: "pending" } },
    });
  });

  it("a free-text relation type reads as itself — the vocabulary is a suggestion, not a constraint", async () => {
    suggestions = [suggestionRow({ relations: [{ target_name: "ARIA", relation_type: "schwebt über" }] })];
    await renderDock();
    const card = await screen.findByTestId("knowledge-suggestion");
    expect(within(card).getByText(/schwebt über/)).toBeTruthy();
  });

  it("accept posts the suggestion's door — the entity is born and the chips refetch", async () => {
    suggestions = [suggestionRow()];
    entities = [];
    await renderDock();
    const card = await screen.findByTestId("knowledge-suggestion");
    // The server creates the entity at the moment the POST lands: the
    // list the refetch reads already carries it — no race.
    entities = [entityRow({ id: "e-new", name: "Dr. Maya Chen" })];
    suggestions = [];
    fireEvent.click(within(card).getByRole("button", { name: de["knowledge.dock.accept"] }));
    await waitFor(() => {
      const call = api.POST.mock.calls.find(
        ([path]) => path === "/api/knowledge/suggestions/{suggestion_id}/accept",
      );
      expect(call?.[1]).toEqual({ params: { path: { suggestion_id: "s1" } } });
    });
    // The chip reads the refetched list — the server's truth, never an
    // optimistic insert; the consumed proposal leaves the queue.
    const chips = await screen.findAllByTestId("knowledge-entity-chip");
    expect(chips).toHaveLength(1);
    expect(within(chips[0]).getByText("Dr. Maya Chen")).toBeTruthy();
    await waitFor(() => expect(screen.queryByTestId("knowledge-suggestion")).toBeNull());
    expect(screen.getByText("1 Entität")).toBeTruthy();
  });

  it("discard posts the suggestion's door — the queue refetches, no entity born", async () => {
    suggestions = [suggestionRow()];
    await renderDock();
    const card = await screen.findByTestId("knowledge-suggestion");
    suggestions = [];
    fireEvent.click(within(card).getByRole("button", { name: de["knowledge.dock.discard"] }));
    await waitFor(() => {
      const call = api.POST.mock.calls.find(
        ([path]) => path === "/api/knowledge/suggestions/{suggestion_id}/discard",
      );
      expect(call?.[1]).toEqual({ params: { path: { suggestion_id: "s1" } } });
    });
    await waitFor(() => expect(screen.queryByTestId("knowledge-suggestion")).toBeNull());
    // The canon is untouched — the two chips the novel already had.
    expect(screen.getAllByTestId("knowledge-entity-chip")).toHaveLength(2);
    expect(screen.queryByText("Dr. Maya Chen")).toBeNull();
  });

  it("a pending decision wears the busy face — its own card alone", async () => {
    suggestions = [suggestionRow(), S2];
    let resolveAccept: (value: { data: Accept; response: Response }) => void = () => {};
    api.POST.mockImplementation(
      (path: string) =>
        new Promise((resolve) => {
          if (path === "/api/knowledge/suggestions/{suggestion_id}/accept") resolveAccept = resolve;
        }),
    );
    await renderDock();
    const cards = await screen.findAllByTestId("knowledge-suggestion");
    const accept = within(cards[0]).getByRole("button", { name: de["knowledge.dock.accept"] });
    fireEvent.click(accept);
    await waitFor(() => expect((accept as HTMLButtonElement).disabled).toBe(true));
    expect(accept.getAttribute("aria-busy")).toBe("true");
    // The card's OTHER door locks with it — the server consumes the
    // suggestion once, so a sibling click would race the same row into a 409.
    const ownDiscard = within(cards[0]).getByRole("button", { name: de["knowledge.dock.discard"] });
    expect((ownDiscard as HTMLButtonElement).disabled).toBe(true);
    expect(ownDiscard.getAttribute("aria-busy")).toBe("false");
    // The sibling card's decisions stay live — one pending ask locks one
    // card, never the whole queue.
    const siblingAccept = within(cards[1]).getByRole("button", { name: de["knowledge.dock.accept"] });
    expect((siblingAccept as HTMLButtonElement).disabled).toBe(false);
    const siblingDiscard = within(cards[1]).getByRole("button", { name: de["knowledge.dock.discard"] });
    expect((siblingDiscard as HTMLButtonElement).disabled).toBe(false);
    suggestions = [S2];
    resolveAccept({ data: { entity: entityRow({ id: "e-new" }), skipped_relations: [] }, response: ok() });
    await waitFor(() => expect(screen.getAllByTestId("knowledge-suggestion")).toHaveLength(1));
  });

  it("a pending discard locks its card's accept too — the guard is symmetric", async () => {
    suggestions = [suggestionRow(), S2];
    let resolveDiscard: (value: { data: Suggestion; response: Response }) => void = () => {};
    api.POST.mockImplementation(
      (path: string) =>
        new Promise((resolve) => {
          if (path === "/api/knowledge/suggestions/{suggestion_id}/discard") resolveDiscard = resolve;
        }),
    );
    await renderDock();
    const cards = await screen.findAllByTestId("knowledge-suggestion");
    const discard = within(cards[1]).getByRole("button", { name: de["knowledge.dock.discard"] });
    fireEvent.click(discard);
    await waitFor(() => expect((discard as HTMLButtonElement).disabled).toBe(true));
    expect(discard.getAttribute("aria-busy")).toBe("true");
    const ownAccept = within(cards[1]).getByRole("button", { name: de["knowledge.dock.accept"] });
    expect((ownAccept as HTMLButtonElement).disabled).toBe(true);
    expect(ownAccept.getAttribute("aria-busy")).toBe("false");
    const otherAccept = within(cards[0]).getByRole("button", { name: de["knowledge.dock.accept"] });
    expect((otherAccept as HTMLButtonElement).disabled).toBe(false);
    suggestions = [suggestionRow()];
    resolveDiscard({ data: suggestionRow({ id: "s2", status: "discarded" }), response: ok() });
    await waitFor(() => expect(screen.getAllByTestId("knowledge-suggestion")).toHaveLength(1));
  });

  it("a refused decision names itself on its card and unlocks it again", async () => {
    suggestions = [suggestionRow()];
    api.POST.mockImplementation(async (path: string) => {
      if (path === "/api/knowledge/suggestions/{suggestion_id}/accept") {
        return { data: undefined, response: new Response(null, { status: 409 }) };
      }
      throw new Error(`unexpected POST: ${path}`);
    });
    await renderDock();
    const card = await screen.findByTestId("knowledge-suggestion");
    const accept = within(card).getByRole("button", { name: de["knowledge.dock.accept"] });
    fireEvent.click(accept);
    const alert = await within(card).findByRole("alert");
    expect(within(alert).getByText(de["knowledge.dock.actionFailed"])).toBeTruthy();
    await waitFor(() => expect((accept as HTMLButtonElement).disabled).toBe(false));
    // The 409's refetch keeps the card standing — the queue is the truth.
    expect(screen.getAllByTestId("knowledge-suggestion")).toHaveLength(1);
  });

  it("two accepts in flight keep both cards busy — and a refusal names its own card alone", async () => {
    // The suggestion cards ride the same shared observers as the findings:
    // two accepts in flight must keep BOTH cards' faces honest, and the
    // refusal of one must never paint the other.
    suggestions = [suggestionRow(), S2];
    const answers = new Map<string, (value: { data: Accept | undefined; response: Response }) => void>();
    api.POST.mockImplementation((path: string, init: { params: { path: { suggestion_id: string } } }) =>
      new Promise((resolve) => {
        if (path === "/api/knowledge/suggestions/{suggestion_id}/accept") {
          answers.set(init.params.path.suggestion_id, resolve);
        }
      }),
    );
    await renderDock();
    const cards = await screen.findAllByTestId("knowledge-suggestion");
    const first = within(cards[0]).getByRole("button", { name: de["knowledge.dock.accept"] });
    const second = within(cards[1]).getByRole("button", { name: de["knowledge.dock.accept"] });
    fireEvent.click(first);
    await waitFor(() => expect((first as HTMLButtonElement).disabled).toBe(true));
    fireEvent.click(second);
    await waitFor(() => expect((second as HTMLButtonElement).disabled).toBe(true));
    // BOTH busy faces stand under concurrency — the second click repaints
    // neither card idle while its own accept still flies.
    expect((first as HTMLButtonElement).disabled).toBe(true);
    expect(first.getAttribute("aria-busy")).toBe("true");
    expect(second.getAttribute("aria-busy")).toBe("true");
    // The second card's refusal names its own card alone.
    answers.get("s2")?.({ data: undefined, response: new Response(null, { status: 409 }) });
    const refusal = await within(cards[1]).findByRole("alert");
    expect(within(refusal).getByText(de["knowledge.dock.actionFailed"])).toBeTruthy();
    expect(within(cards[0]).queryByRole("alert")).toBeNull();
    expect((first as HTMLButtonElement).disabled).toBe(true);
    // The first card's answer settles its own card; the queue refetches.
    suggestions = [S2];
    answers.get("s1")?.({
      data: { entity: entityRow({ id: "e-new", name: "Dr. Maya Chen" }), skipped_relations: [] },
      response: ok(),
    });
    await waitFor(() => expect(screen.getAllByTestId("knowledge-suggestion")).toHaveLength(1));
    expect(screen.getByText("Resonanz-Transmitter")).toBeTruthy();
  });

  it("accept announces the relations it could not place — once, and the next decision clears it", async () => {
    suggestions = [suggestionRow(), S2];
    api.POST.mockImplementation(async (path: string) => {
      if (path === "/api/knowledge/suggestions/{suggestion_id}/accept") {
        const accepted: Accept = {
          entity: entityRow({ id: "e-new", name: "Dr. Maya Chen" }),
          skipped_relations: [{ target_name: "Horizon Station", relation_type: "located_in" }],
        };
        return { data: accepted, response: ok() };
      }
      return basePost(path);
    });
    await renderDock();
    const cards = await screen.findAllByTestId("knowledge-suggestion");
    suggestions = [S2];
    fireEvent.click(within(cards[0]).getByRole("button", { name: de["knowledge.dock.accept"] }));
    // The skip is transient (D8): announced once, naming the target the
    // accept could not reach — persisted nowhere. The literal is the
    // catalog's own one-form with the name filled in.
    expect(await screen.findByText("Eine Beziehung konnte nicht gesetzt werden: Horizon Station")).toBeTruthy();
    // The next decision clears the note — it belongs to the one accept.
    suggestions = [];
    const remaining = await screen.findByTestId("knowledge-suggestion");
    fireEvent.click(within(remaining).getByRole("button", { name: de["knowledge.dock.discard"] }));
    await waitFor(() => expect(screen.queryByText(/konnte nicht gesetzt werden/)).toBeNull());
  });

  it("an empty queue reads as spent — the quiet empty face, not an outage", async () => {
    suggestions = [];
    await renderDock();
    expect(await screen.findByTestId("knowledge-suggestions-empty")).toBeTruthy();
    expect(screen.getByText(de["knowledge.dock.suggestionsEmpty"])).toBeTruthy();
    expect(screen.queryByTestId("knowledge-suggestion")).toBeNull();
  });

  it("a pending ask shows the loading face, never an invented card", async () => {
    let resolveSuggestions: (value: { data: Suggestion[]; response: Response }) => void = () => {};
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/knowledge/novels/{novel_id}/suggestions") {
        return new Promise((resolve) => {
          resolveSuggestions = resolve;
        });
      }
      return baseGet(path);
    });
    await renderDock();
    expect(await screen.findByText(de["knowledge.dock.suggestionsLoading"])).toBeTruthy();
    expect(screen.queryByTestId("knowledge-suggestion")).toBeNull();
    resolveSuggestions({ data: [suggestionRow()], response: ok() });
    expect(await screen.findByTestId("knowledge-suggestion")).toBeTruthy();
  });

  it("an unavailable queue names itself and offers the retry", async () => {
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/knowledge/novels/{novel_id}/suggestions") {
        return Promise.resolve({ data: undefined, response: new Response(null, { status: 500 }) });
      }
      return baseGet(path);
    });
    await renderDock();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.dock.suggestionsFailed"])).toBeTruthy();
    suggestions = [suggestionRow()];
    api.GET.mockImplementation(baseGet);
    fireEvent.click(within(alert).getByRole("button", { name: de["knowledge.dock.retry"] }));
    expect(await screen.findByTestId("knowledge-suggestion")).toBeTruthy();
  });
});

describe("the face speaks du-tone in every catalog — no German fallback", () => {
  it("the English face speaks the English catalog's own copy", async () => {
    applyLocale("en");
    queue = [findingRow()];
    await renderDock();
    const card = await screen.findByTestId("knowledge-finding");
    expect(within(card).getByRole("button", { name: "Acknowledge" })).toBeTruthy();
    expect(within(card).getByRole("button", { name: "Dismiss" })).toBeTruthy();
    expect(within(card).getByText("Conflict")).toBeTruthy();
    expect(screen.getByRole("button", { name: en["knowledge.dock.check"] })).toBeTruthy();
    expect(screen.getByText("1 open finding")).toBeTruthy();
    expect(screen.queryByText("Zur Kenntnis nehmen")).toBeNull();
    expect(screen.queryByText("Konsistenz prüfen")).toBeNull();
  });

  it("the English chips and review speak the English catalog too", async () => {
    applyLocale("en");
    suggestions = [suggestionRow()];
    await renderDock();
    const chips = await screen.findAllByTestId("knowledge-entity-chip");
    expect(within(chips[0]).getByText("Character")).toBeTruthy();
    expect(screen.getByText("2 entities")).toBeTruthy();
    expect(screen.getByRole("button", { name: en["knowledge.dock.extract"] })).toBeTruthy();
    const card = await screen.findByTestId("knowledge-suggestion");
    expect(within(card).getByRole("button", { name: "Accept" })).toBeTruthy();
    expect(within(card).getByRole("button", { name: "Discard" })).toBeTruthy();
    expect(within(card).getByText("Suggestion")).toBeTruthy();
    expect(within(card).getByText("Located in")).toBeTruthy();
    expect(screen.queryByText("Übernehmen")).toBeNull();
    expect(screen.queryByText("Kapitel extrahieren")).toBeNull();
  });

  it("the French face speaks the French catalog's own copy", async () => {
    applyLocale("fr");
    queue = [];
    await renderDock();
    const empty = await screen.findByTestId("knowledge-empty");
    expect(within(empty).getByText("Aucune fracture ouverte")).toBeTruthy();
    expect(screen.getByRole("button", { name: fr["knowledge.dock.check"] })).toBeTruthy();
    // French plural rules count 0 as „one" — the locale's own rule, not
    // the German other-form (the i18n gate's per-locale plural pin).
    expect(screen.getByText("0 constat ouvert")).toBeTruthy();
    expect(screen.queryByText("Keine offenen Brüche")).toBeNull();
  });

  it("the French chips count zero as one — the locale's own plural rule", async () => {
    applyLocale("fr");
    entities = [];
    await renderDock();
    expect(await screen.findByText("0 entité")).toBeTruthy();
    expect(screen.getByRole("button", { name: fr["knowledge.dock.extract"] })).toBeTruthy();
    const chipEmpty = await screen.findByTestId("knowledge-entities-empty");
    expect(within(chipEmpty).getByText("Aucune entité pour l'instant")).toBeTruthy();
    expect(screen.queryByText("Noch keine Entitäten")).toBeNull();
  });

  it("the three catalogs carry the face's keys in parity, each translated", () => {
    const keys = Object.keys(de).filter((key) => key.startsWith("knowledge."));
    expect(keys.length).toBeGreaterThan(0);
    for (const key of keys) {
      for (const locale of ["en", "fr"] as const) {
        expect(merged[locale][key as keyof typeof en], `${locale}/${key}`).toBeTruthy();
      }
    }
    const translated = [
      "knowledge.dock.accept",
      "knowledge.dock.acknowledge",
      "knowledge.dock.check",
      "knowledge.dock.checkBusy",
      "knowledge.dock.discard",
      "knowledge.dock.dismiss",
      "knowledge.dock.empty",
      "knowledge.dock.emptyNote",
      "knowledge.dock.entities",
      "knowledge.dock.entitiesEmpty",
      "knowledge.dock.extract",
      "knowledge.dock.extractBusy",
      "knowledge.dock.extraction",
      "knowledge.dock.suggestion",
      "knowledge.dock.suggestionsEmpty",
      "knowledge.dockTitle",
      "knowledge.heading",
      "knowledge.type.character",
      "knowledge.relation.located_in",
    ] as const;
    for (const key of translated) {
      expect(en[key], key).not.toBe(de[key]);
      expect(fr[key], key).not.toBe(de[key]);
    }
  });

  it("the German copy keeps the du register — no Sie form sneaks in", () => {
    for (const [key, value] of Object.entries(de)) {
      if (!key.startsWith("knowledge.")) continue;
      expect(value, key).not.toMatch(/\b(Sie|Ihnen|Ihr|Ihre)\b/);
    }
    // The du forms are present, not merely the absence of Sie.
    expect(de["knowledge.dock.emptyNote"]).toContain("deinem");
    expect(de["knowledge.dock.actionFailed"]).toContain("Versuche");
    expect(de["knowledge.dock.entitiesEmptyNote"]).toContain("deinem");
    expect(de["knowledge.dock.extractFailed"]).toContain("Versuche");
  });
});
