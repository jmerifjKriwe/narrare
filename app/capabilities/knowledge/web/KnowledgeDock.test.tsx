// @vitest-environment jsdom
/**
 * The knowledge dock face (W5 Task 1) — the findings queue on the real API
 * seam (the shell's query hooks, the client mocked at its module boundary
 * per house pattern): the list renders the rows the server files, the two
 * review decisions mutate with an honest pending face and name their
 * refusal, the consistency trigger rides the 202 job lane with its honest
 * busy („Prüfung läuft…") until the findings refetch lands, and an empty
 * queue reads as empty — never as an outage. The entity-chip area stands
 * neutral (INTERIM #867, Task 2 fills it).
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
} from "@tanstack/react-router";
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import { client, type Finding, type Job } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";

import { KnowledgeDock } from "./KnowledgeDock";

const de = catalogs.de;
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

function jobRow(status: string): Job {
  return { id: "j1", kind: "consistency", status, progress: null, result: null, error: null };
}

/** The face under the workspace route's own param — the harness mirrors
 *  the generated table's composition: the dock is a child of the
 *  workspace route, and the face reads the novel from the parent. */
const harnessRoot = createRootRoute({ component: () => <Outlet /> });

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
  const router = createRouter({
    routeTree: harnessRoot.addChildren([workspace.addChildren([dock])]),
    history: createMemoryHistory({ initialEntries: [`/novels/${NOVEL_ID}/knowledge`] }),
  });
  await router.load();
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

/** The findings answer the mock serves; the tests mutate it to model the
 *  server's queue after a review decision or a finished check. */
let queue: Finding[];
/** The job answer the mock serves; the tests advance it down the lane. */
let jobStatus: string;

beforeEach(() => {
  applyLocale("de");
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
  queue = [findingRow(), F2];
  jobStatus = "done";
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/knowledge/novels/{novel_id}/findings") {
      return { data: queue, response: ok() };
    }
    if (path === "/api/jobs/{job_id}") {
      return { data: jobRow(jobStatus), response: ok() };
    }
    throw new Error(`unexpected GET: ${path}`);
  });
  api.POST.mockImplementation(async (path: string) => {
    if (path === "/api/knowledge/consistency/{novel_id}") {
      return { data: { job_id: "j1" }, response: new Response(null, { status: 202 }) };
    }
    if (path === "/api/knowledge/findings/{finding_id}/acknowledge") {
      return { data: findingRow({ status: "acknowledged" }), response: ok() };
    }
    if (path === "/api/knowledge/findings/{finding_id}/dismiss") {
      return { data: findingRow({ status: "dismissed" }), response: ok() };
    }
    throw new Error(`unexpected POST: ${path}`);
  });
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
    api.GET.mockImplementation(
      (path: string) =>
        new Promise((resolve) => {
          if (path === "/api/knowledge/novels/{novel_id}/findings") resolveFindings = resolve;
        }),
    );
    await renderDock();
    expect(await screen.findByText(de["knowledge.dock.loading"])).toBeTruthy();
    expect(screen.queryByTestId("knowledge-finding")).toBeNull();
    resolveFindings({ data: [findingRow()], response: ok() });
    expect(await screen.findByTestId("knowledge-finding")).toBeTruthy();
  });

  it("an unavailable queue names itself and offers the retry", async () => {
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/knowledge/novels/{novel_id}/findings") {
        return { data: undefined, response: new Response(null, { status: 500 }) };
      }
      throw new Error(`unexpected GET: ${path}`);
    });
    await renderDock();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.dock.loadFailed"])).toBeTruthy();
    queue = [findingRow()];
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/knowledge/novels/{novel_id}/findings") return { data: queue, response: ok() };
      throw new Error(`unexpected GET: ${path}`);
    });
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
      if (path === "/api/knowledge/novels/{novel_id}/findings") {
        return Promise.resolve({ data: queue, response: ok() });
      }
      throw new Error(`unexpected GET: ${path}`);
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
  });
});

describe("the entity-chip area stands neutral (INTERIM #867)", () => {
  it("keeps the spotlight geometry with neutral fields and the disabled wiki door", async () => {
    await renderDock();
    const card = await screen.findByTestId("knowledge-entity");
    for (const key of [
      "knowledge.dock.entityName",
      "knowledge.dock.entityFirst",
      "knowledge.dock.entityBinding",
    ] as const) {
      expect(within(card).getByText(de[key])).toBeTruthy();
    }
    const wiki = within(card).getByRole("button", { name: de["knowledge.dock.wiki"] });
    expect(wiki.hasAttribute("disabled")).toBe(true);
    // No invented entity: the neutral dash is the whole content.
    expect(within(card).getAllByText("—").length).toBeGreaterThanOrEqual(3);
  });
});

describe("the face speaks du-tone in every catalog — no German fallback", () => {
  it("the English face speaks the English catalog's own copy", async () => {
    applyLocale("en");
    const en = catalogs.en;
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

  it("the French face speaks the French catalog's own copy", async () => {
    applyLocale("fr");
    const fr = catalogs.fr;
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

  it("the three catalogs carry the face's keys in parity, each translated", () => {
    const keys = Object.keys(catalogs.de).filter((key) => key.startsWith("knowledge."));
    expect(keys.length).toBeGreaterThan(0);
    for (const key of keys) {
      for (const locale of ["en", "fr"] as const) {
        expect(catalogs[locale][key as keyof typeof catalogs.en], `${locale}/${key}`).toBeTruthy();
      }
    }
    const translated = [
      "knowledge.dock.acknowledge",
      "knowledge.dock.check",
      "knowledge.dock.checkBusy",
      "knowledge.dock.dismiss",
      "knowledge.dock.empty",
      "knowledge.dock.emptyNote",
      "knowledge.dockTitle",
      "knowledge.heading",
    ] as const;
    for (const key of translated) {
      expect(catalogs.en[key], key).not.toBe(catalogs.de[key]);
      expect(catalogs.fr[key], key).not.toBe(catalogs.de[key]);
    }
  });

  it("the German copy keeps the du register — no Sie form sneaks in", () => {
    for (const [key, value] of Object.entries(catalogs.de)) {
      if (!key.startsWith("knowledge.")) continue;
      expect(value, key).not.toMatch(/\b(Sie|Ihnen|Ihr|Ihre)\b/);
    }
    // The du forms are present, not merely the absence of Sie.
    expect(catalogs.de["knowledge.dock.emptyNote"]).toContain("deinem");
    expect(catalogs.de["knowledge.dock.actionFailed"]).toContain("Versuche");
  });
});
