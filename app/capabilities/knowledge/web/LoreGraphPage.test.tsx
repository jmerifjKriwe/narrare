// @vitest-environment jsdom
/**
 * The lore graph page (W5 Task 3) — the harmonized `lore-graph-2` draft on
 * the shell's tokens, driven through the real API seam (the client mocked at
 * its module boundary, the house pattern). The nodes are the novel's real
 * EntityRead rows, the edges its RelationRead rows; the layout is the pure
 * deterministic pass (pinned separately in graphLayout.test.ts). A node click
 * opens the dossier with the REAL fields and the invented ones as honest
 * disabled gaps; an edge click opens its note popover; the type chips and the
 * name search narrow the canvas client-side and compose; zoom and the honest
 * reset move the viewport; the empty canon, the loading and the outage each
 * answer with their own face. The `entity` search param is the dock chip's
 * deep link. The face speaks du-tone in all three catalogs.
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
import { act, cleanup, configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import { client, type AssistantSession, type Entity, type Relation } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";
import { ToastProvider } from "@shell/ui/toast";

import { fitTransform, graphBounds, layoutGraph } from "./graphLayout";
import { LoreGraphPage } from "./LoreGraphPage";

const de = catalogs.de;
const api = client as unknown as Record<"GET" | "POST" | "DELETE", ReturnType<typeof vi.fn>>;

configure({ asyncUtilTimeout: 5000 });

const NOVEL_ID = "11111111-1111-1111-1111-111111111111";
const GRAPH_PATH = "/novels/$novelId/knowledge/graph";

function ok(): Response {
  return new Response(null, { status: 200 });
}

function entityRow(overrides: Partial<Entity> & { id: string; name: string }): Entity {
  return {
    novel_id: NOVEL_ID,
    type: "character",
    aliases: [],
    tags: [],
    content: "",
    created_at: "2026-11-18T10:00:00Z",
    updated_at: "2026-11-18T10:00:00Z",
    ...overrides,
  };
}

const MAYA = entityRow({ id: "e1", name: "Dr. Maya Chen", content: "Leitende Bio-Physikerin." });
const ARIA = entityRow({ id: "e2", name: "ARIA", content: "Autonome Schiffs-KI." });
const STATION = entityRow({ id: "e3", name: "Station 7", type: "location", content: "Nevada Deep-Array." });
const RELIKT = entityRow({ id: "e4", name: "Relikt", type: "object", content: "" });

function relationRow(overrides: Partial<Relation> & { id: string }): Relation {
  return {
    from_entity_id: "e1",
    to_entity_id: "e2",
    relation_type: "ally_of",
    note: null,
    created_at: "2026-11-18T10:00:00Z",
    ...overrides,
  };
}

const R1 = relationRow({ id: "r1", from_entity_id: "e1", to_entity_id: "e2", relation_type: "ally_of", note: "Symbiotische Co-Pilotin." });
const R2 = relationRow({ id: "r2", from_entity_id: "e1", to_entity_id: "e3", relation_type: "located_in", note: "Suchziel." });
const R3 = relationRow({ id: "r3", from_entity_id: "e2", to_entity_id: "e3", relation_type: "related_to", note: null });

let entities: Entity[];
let relations: Relation[];

/** An interview row the door counts; the graph only reads `closed_at`. */
function sessionSummary(id: string) {
  return {
    id,
    novel_id: NOVEL_ID,
    mode: "knowledge.entity",
    entity_type: "object",
    target_id: null,
    name: null,
    closed_at: null,
    created_at: "2026-11-24T14:00:00Z",
    updated_at: "2026-11-24T14:00:00Z",
  };
}

/** A full interview read with one named proposal, as the handover needs it. */
function sessionWithProposal(id: string, name: string): AssistantSession {
  return {
    ...sessionSummary(id),
    proposal: {
      name,
      name_suggested: false,
      aliases: [],
      tags: [],
      content: "",
      relations: [],
    },
    turns: [],
  } as AssistantSession;
}

function baseGet(path: string): Promise<{ data: unknown; response: Response }> {
  if (path === "/api/knowledge/novels/{novel_id}/entities") {
    return Promise.resolve({ data: entities, response: ok() });
  }
  if (path === "/api/knowledge/novels/{novel_id}/relations") {
    return Promise.resolve({ data: relations, response: ok() });
  }
  if (path === "/api/chat/sessions") {
    return Promise.resolve({ data: { items: [] }, response: ok() });
  }
  throw new Error(`unexpected GET: ${path}`);
}

/** The page on a harness route whose id is the real graph path, so the
 *  page's useParams/useSearch/navigate all resolve against it. */
const harnessRoot = createRootRoute({ component: () => <Outlet /> });

async function renderGraph(entry = `/novels/${NOVEL_ID}/knowledge/graph`) {
  const graph = createRoute({
    getParentRoute: () => harnessRoot,
    path: GRAPH_PATH,
    validateSearch: (search: Record<string, unknown>): { entity?: string; interview?: string } => {
      const next: { entity?: string; interview?: string } = {};
      if (typeof search.entity === "string" && search.entity !== "") next.entity = search.entity;
      if (typeof search.interview === "string" && search.interview !== "") next.interview = search.interview;
      return next;
    },
    component: LoreGraphPage,
  });
  // The dossiers stub the subbar's sibling door navigates to (W5 Task 5);
  // the dossiers page itself is pinned in its own file.
  const dossiers = createRoute({
    getParentRoute: () => harnessRoot,
    path: "/novels/$novelId/knowledge/dossiers",
    validateSearch: (search: Record<string, unknown>): { entity?: string } =>
      typeof search.entity === "string" && search.entity !== "" ? { entity: search.entity } : {},
    component: () => <p>dossiers face</p>,
  });
  // The sources stub the third sibling door navigates to (W5 Task 6); the
  // archive carries no entity selection, so the route takes no search param.
  const sources = createRoute({
    getParentRoute: () => harnessRoot,
    path: "/novels/$novelId/knowledge/sources",
    component: () => <p>sources face</p>,
  });
  const router = createRouter({
    routeTree: harnessRoot.addChildren([graph, dossiers, sources]),
    history: createMemoryHistory({ initialEntries: [entry] }),
  });
  await router.load();
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return router;
}

/** The world layer's current scale, read off its transform. */
function worldScale(): number {
  const world = screen.getByTestId("graph-world");
  const match = /scale\(([^)]+)\)/.exec(world.style.transform);
  return match === null ? NaN : Number(match[1]);
}

/** An edge's drawn curve — the first path inside its button group. */
function edgePath(edge: Element): string {
  return edge.querySelector("path")?.getAttribute("d") ?? "";
}

/** An edge's label position — the translate of its label group. */
function edgeLabel(edge: Element): string {
  return edge.querySelector("g[transform]")?.getAttribute("transform") ?? "";
}

/** Every x coordinate a geometry attribute carries (paths alternate x, y). */
function xValues(geometry: string): number[] {
  const numbers = (geometry.match(/-?\d+(?:\.\d+)?/g) ?? []).map(Number);
  return numbers.filter((_, at) => at % 2 === 0);
}

let canvasRect: MockInstance | null = null;

/** The canvas element reports a real viewport — jsdom's rects are all zero,
 *  so unstubbed the measure guard keeps the 800×600 default. Restored in
 *  afterEach, never at the test's end: a failing (RED) assertion must not
 *  leak the stub rect into the rest of the file (clearAllMocks clears
 *  calls, not spies). A second call re-points the same spy. */
function stubCanvasRect(width: number, height: number) {
  canvasRect ??= vi.spyOn(HTMLElement.prototype, "getBoundingClientRect");
  canvasRect.mockReturnValue({
    x: 0,
    y: 0,
    top: 0,
    left: 0,
    right: width,
    bottom: height,
    width,
    height,
    toJSON: () => ({}),
  } as DOMRect);
}

/** A ResizeObserver stand-in: jsdom ships none, and the page's typeof guard
 *  would skip the observer entirely. Each instance captures the callback it
 *  was given, so a test can drive a resize by hand. */
class ResizeObserverStub {
  callback: ResizeObserverCallback;
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
    resizeObservers.push(this);
  }
}
let resizeObservers: ResizeObserverStub[] = [];

/** An uncached load: the entities ask stays pending until the harness
 *  resolves it, so the page mounts its loading face first and the canvas
 *  appears only when the data lands. */
function deferredEntities(): (rows: Entity[]) => void {
  let resolveEntities: (value: { data: Entity[]; response: Response }) => void = () => {};
  api.GET.mockImplementation((path: string) => {
    if (path === "/api/knowledge/novels/{novel_id}/entities") {
      return new Promise((resolve) => {
        resolveEntities = resolve;
      });
    }
    return baseGet(path);
  });
  return (rows: Entity[]) => resolveEntities({ data: rows, response: ok() });
}

beforeEach(() => {
  applyLocale("de");
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
  entities = [MAYA, ARIA, STATION, RELIKT];
  relations = [R1, R2, R3];
  api.GET.mockImplementation(baseGet);
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  canvasRect?.mockRestore();
  canvasRect = null;
  vi.unstubAllGlobals();
});

describe("the graph draws the novel's real web", () => {
  it("renders a node per entity and an edge per relation, with the real counts", async () => {
    await renderGraph();
    const nodes = await screen.findAllByTestId("graph-node");
    expect(nodes).toHaveLength(4);
    expect(screen.getAllByTestId("graph-edge")).toHaveLength(3);
    expect(within(nodes[0]).getByText("Dr. Maya Chen")).toBeTruthy();
    // The legend counts the whole web in the locale's own plural.
    expect(screen.getByText("4 Entitäten • 3 Relationen")).toBeTruthy();
    // The reads carry the novel.
    expect(api.GET.mock.calls.some(([p]) => p === "/api/knowledge/novels/{novel_id}/entities")).toBe(true);
    expect(api.GET.mock.calls.some(([p]) => p === "/api/knowledge/novels/{novel_id}/relations")).toBe(true);
  });

  it("the type chips name the types the canon carries, with their counts", async () => {
    await renderGraph();
    // The subbar stands in every state now, so its All chip exists before
    // the web lands — the counts are owed the populated body, awaited first.
    await screen.findAllByTestId("graph-node");
    const chips = screen.getAllByTestId("type-chip");
    // All + character + location + object.
    expect(chips).toHaveLength(4);
    expect(within(chips[0]).getByText(de["knowledge.graph.allTypes"])).toBeTruthy();
    expect(screen.getByText(`${de["knowledge.type.character"]} (2)`)).toBeTruthy();
    expect(screen.getByText(`${de["knowledge.type.location"]} (1)`)).toBeTruthy();
    expect(screen.getByText(`${de["knowledge.type.object"]} (1)`)).toBeTruthy();
  });
});

describe("a node click opens the dossier with the real fields", () => {
  it("shows name, type, the body as description and the entity's relations", async () => {
    await renderGraph();
    const nodes = await screen.findAllByTestId("graph-node");
    fireEvent.click(within(nodes[0]).getByRole("button"));
    const dossier = await screen.findByTestId("entity-dossier");
    expect(within(dossier).getByText("Dr. Maya Chen")).toBeTruthy();
    expect(within(dossier).getByText(de["knowledge.type.character"])).toBeTruthy();
    expect(within(dossier).getByText("Leitende Bio-Physikerin.")).toBeTruthy();
    // Maya's two edges (r1 outgoing to ARIA, r2 outgoing to Station 7).
    expect(within(dossier).getByText("ARIA")).toBeTruthy();
    expect(within(dossier).getByText("Station 7")).toBeTruthy();
    expect(within(dossier).getByText("Symbiotische Co-Pilotin.")).toBeTruthy();
    // The selection rides the URL — the clicked node wears the pressed face.
    expect(within(nodes[0]).getByRole("button").getAttribute("aria-pressed")).toBe("true");
  });

  it("the invented fields stand as honest disabled gaps, never fake content", async () => {
    await renderGraph();
    const nodes = await screen.findAllByTestId("graph-node");
    fireEvent.click(within(nodes[0]).getByRole("button"));
    const dossier = await screen.findByTestId("entity-dossier");
    // Manuscript excerpts: the gap note, no invented quotation.
    expect(within(dossier).getByText(de["knowledge.dossier.excerptsGap"])).toBeTruthy();
    // The status gap row (no model carries a status).
    expect(within(dossier).getByText(de["knowledge.dossier.status"])).toBeTruthy();
    // Edit is live now (Task 4's dialog); jump stays a disabled gap.
    const edit = within(dossier).getByRole("button", { name: new RegExp(de["knowledge.dossier.edit"]) });
    expect((edit as HTMLButtonElement).disabled).toBe(false);
    const jump = within(dossier).getByRole("button", { name: new RegExp(de["knowledge.dossier.jump"]) });
    expect((jump as HTMLButtonElement).disabled).toBe(true);
  });

  it("an empty body reads as empty, not an invented description", async () => {
    await renderGraph();
    const nodes = await screen.findAllByTestId("graph-node");
    // Relikt (e4) has an empty body.
    fireEvent.click(within(nodes[3]).getByRole("button"));
    const dossier = await screen.findByTestId("entity-dossier");
    expect(within(dossier).getByText(de["knowledge.dossier.noDescription"])).toBeTruthy();
  });

  it("a relation card selects the other end", async () => {
    await renderGraph();
    const nodes = await screen.findAllByTestId("graph-node");
    fireEvent.click(within(nodes[0]).getByRole("button"));
    const dossier = await screen.findByTestId("entity-dossier");
    fireEvent.click(within(dossier).getByText("ARIA"));
    await waitFor(() => expect(within(screen.getByTestId("entity-dossier")).getByText("Autonome Schiffs-KI.")).toBeTruthy());
  });

  it("the close door folds the dossier and clears the selection", async () => {
    await renderGraph();
    const nodes = await screen.findAllByTestId("graph-node");
    fireEvent.click(within(nodes[0]).getByRole("button"));
    const dossier = await screen.findByTestId("entity-dossier");
    fireEvent.click(within(dossier).getByRole("button", { name: de["knowledge.dossier.close"] }));
    await waitFor(() => expect(screen.queryByTestId("entity-dossier")).toBeNull());
  });

  it("the entity search param opens the dossier on arrival — the dock chip's deep link", async () => {
    await renderGraph(`/novels/${NOVEL_ID}/knowledge/graph?entity=e3`);
    const dossier = await screen.findByTestId("entity-dossier");
    expect(within(dossier).getByText("Station 7")).toBeTruthy();
    expect(within(dossier).getByText("Nevada Deep-Array.")).toBeTruthy();
  });
});

describe("an edge click opens the note popover", () => {
  it("shows the ends, the type and the note", async () => {
    await renderGraph();
    const edges = await screen.findAllByTestId("graph-edge");
    fireEvent.click(edges[0]);
    const popover = await screen.findByTestId("edge-popover");
    expect(within(popover).getByText(/Dr\. Maya Chen → ARIA/)).toBeTruthy();
    expect(within(popover).getByText(de["knowledge.relation.ally_of"])).toBeTruthy();
    expect(within(popover).getByText("Symbiotische Co-Pilotin.")).toBeTruthy();
  });

  it("a null note reads as the honest no-note face", async () => {
    await renderGraph();
    const edges = await screen.findAllByTestId("graph-edge");
    // r3 (ARIA → Station 7) carries no note.
    fireEvent.click(edges[2]);
    const popover = await screen.findByTestId("edge-popover");
    expect(within(popover).getByText(de["knowledge.graph.edgeNoNote"])).toBeTruthy();
  });

  it("the close door dismisses the popover", async () => {
    await renderGraph();
    const edges = await screen.findAllByTestId("graph-edge");
    fireEvent.click(edges[0]);
    const popover = await screen.findByTestId("edge-popover");
    fireEvent.click(within(popover).getByRole("button", { name: de["knowledge.graph.closeNote"] }));
    await waitFor(() => expect(screen.queryByTestId("edge-popover")).toBeNull());
  });
});

describe("the type filter and the name search compose client-side", () => {
  it("a type chip narrows the canvas to that type", async () => {
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    fireEvent.click(screen.getByText(`${de["knowledge.type.location"]} (1)`));
    await waitFor(() => expect(screen.getAllByTestId("graph-node")).toHaveLength(1));
    expect(screen.getByText("Station 7")).toBeTruthy();
    // Only edges between visible nodes survive — none here.
    expect(screen.queryAllByTestId("graph-edge")).toHaveLength(0);
    expect(screen.getByText("1 Entität • 0 Relationen")).toBeTruthy();
  });

  it("the name search narrows by substring, case-insensitive", async () => {
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    fireEvent.change(screen.getByTestId("graph-search"), { target: { value: "maya" } });
    await waitFor(() => expect(screen.getAllByTestId("graph-node")).toHaveLength(1));
    expect(screen.getByText("Dr. Maya Chen")).toBeTruthy();
  });

  it("type and search compose — both must match", async () => {
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    fireEvent.click(screen.getByText(`${de["knowledge.type.character"]} (2)`));
    fireEvent.change(screen.getByTestId("graph-search"), { target: { value: "aria" } });
    await waitFor(() => expect(screen.getAllByTestId("graph-node")).toHaveLength(1));
    expect(screen.getByText("ARIA")).toBeTruthy();
    // A character filter plus a location name matches nothing.
    fireEvent.change(screen.getByTestId("graph-search"), { target: { value: "station" } });
    expect(await screen.findByTestId("graph-no-results")).toBeTruthy();
  });

  it("the no-results face clears both filters", async () => {
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    fireEvent.change(screen.getByTestId("graph-search"), { target: { value: "zzz" } });
    const empty = await screen.findByTestId("graph-no-results");
    fireEvent.click(within(empty).getByRole("button", { name: de["knowledge.graph.clearFilters"] }));
    await waitFor(() => expect(screen.getAllByTestId("graph-node")).toHaveLength(4));
  });
});

describe("zoom and the honest reset", () => {
  it("zoom in raises the scale, zoom out lowers it, reset returns to the fit", async () => {
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    const fit = worldScale();
    fireEvent.click(screen.getByTestId("zoom-in"));
    await waitFor(() => expect(worldScale()).toBeGreaterThan(fit));
    const zoomed = worldScale();
    fireEvent.click(screen.getByTestId("zoom-out"));
    await waitFor(() => expect(worldScale()).toBeLessThan(zoomed));
    fireEvent.click(screen.getByTestId("reset-view"));
    await waitFor(() => expect(worldScale()).toBeCloseTo(fit, 5));
  });
});

describe("the honest states", () => {
  it("an empty canon answers the empty face, not an outage", async () => {
    entities = [];
    relations = [];
    await renderGraph();
    const empty = await screen.findByTestId("graph-empty");
    expect(within(empty).getByText(de["knowledge.graph.empty"])).toBeTruthy();
    expect(within(empty).getByText(de["knowledge.graph.emptyNote"])).toBeTruthy();
    expect(screen.queryByTestId("graph-node")).toBeNull();
  });

  it("a pending ask shows the loading face, never an invented web", async () => {
    let resolveEntities: (value: { data: Entity[]; response: Response }) => void = () => {};
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/knowledge/novels/{novel_id}/entities") {
        return new Promise((resolve) => {
          resolveEntities = resolve;
        });
      }
      return baseGet(path);
    });
    await renderGraph();
    expect(await screen.findByTestId("graph-loading")).toBeTruthy();
    expect(screen.queryByTestId("graph-node")).toBeNull();
    resolveEntities({ data: [MAYA], response: ok() });
    expect(await screen.findByTestId("graph-node")).toBeTruthy();
  });

  it("an unavailable web names itself and offers the retry", async () => {
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/knowledge/novels/{novel_id}/entities") {
        return Promise.resolve({ data: undefined, response: new Response(null, { status: 500 }) });
      }
      return baseGet(path);
    });
    await renderGraph();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.graph.loadFailed"])).toBeTruthy();
    api.GET.mockImplementation(baseGet);
    fireEvent.click(within(alert).getByRole("button", { name: de["knowledge.graph.retry"] }));
    expect(await screen.findAllByTestId("graph-node")).toHaveLength(4);
  });
});

describe("the subbar stands in every state — the sibling doors never vanish (PR #923 fix)", () => {
  it("the pending face keeps the doors — the loading answer still navigates", async () => {
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/knowledge/novels/{novel_id}/entities") {
        return new Promise(() => {});
      }
      return baseGet(path);
    });
    await renderGraph();
    expect(await screen.findByTestId("graph-loading")).toBeTruthy();
    expect(screen.getByTestId("graph-dossiers-door")).toBeTruthy();
    expect(screen.getByTestId("graph-sources-door")).toBeTruthy();
    expect(screen.getByText(de["knowledge.graph.title"])).toBeTruthy();
  });

  it("the failed face keeps the doors — the outage answer still navigates", async () => {
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/knowledge/novels/{novel_id}/entities") {
        return Promise.resolve({ data: undefined, response: new Response(null, { status: 500 }) });
      }
      return baseGet(path);
    });
    await renderGraph();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.graph.loadFailed"])).toBeTruthy();
    expect(screen.getByTestId("graph-dossiers-door")).toBeTruthy();
    expect(screen.getByTestId("graph-sources-door")).toBeTruthy();
    expect(screen.getByText(de["knowledge.graph.title"])).toBeTruthy();
  });

  it("the empty canon keeps the doors beside the empty face", async () => {
    entities = [];
    relations = [];
    await renderGraph();
    expect(await screen.findByTestId("graph-empty")).toBeTruthy();
    expect(screen.getByTestId("graph-dossiers-door")).toBeTruthy();
    expect(screen.getByTestId("graph-sources-door")).toBeTruthy();
    expect(screen.getByText(de["knowledge.graph.title"])).toBeTruthy();
  });
});

describe("the face speaks du-tone in every catalog — no German fallback", () => {
  it("the English face speaks the English catalog's own copy", async () => {
    applyLocale("en");
    const en = catalogs.en;
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    expect(screen.getByText(en["knowledge.graph.allTypes"])).toBeTruthy();
    expect(screen.getByText("4 entities • 3 relations")).toBeTruthy();
    expect(screen.getByTestId("graph-search").getAttribute("placeholder")).toBe(en["knowledge.graph.search"]);
    expect(screen.queryByText(de["knowledge.graph.allTypes"])).toBeNull();
  });

  it("the French face counts zero as one — the locale's own plural rule", async () => {
    applyLocale("fr");
    const fr = catalogs.fr;
    entities = [];
    relations = [];
    await renderGraph();
    const empty = await screen.findByTestId("graph-empty");
    expect(within(empty).getByText(fr["knowledge.graph.empty"])).toBeTruthy();
    expect(screen.queryByText(de["knowledge.graph.empty"])).toBeNull();
  });

  it("the three catalogs carry the graph's keys in parity, each translated", () => {
    const keys = Object.keys(catalogs.de).filter((key) => key.startsWith("knowledge.graph.") || key.startsWith("knowledge.dossier."));
    expect(keys.length).toBeGreaterThan(0);
    for (const key of keys) {
      for (const locale of ["en", "fr"] as const) {
        expect(catalogs[locale][key as keyof typeof catalogs.en], `${locale}/${key}`).toBeTruthy();
      }
    }
    const translated = ["knowledge.graph.title", "knowledge.graph.allTypes", "knowledge.graph.empty", "knowledge.dossier.title", "knowledge.dossier.description"] as const;
    for (const key of translated) {
      expect(catalogs.en[key], key).not.toBe(catalogs.de[key]);
      expect(catalogs.fr[key], key).not.toBe(catalogs.de[key]);
    }
  });

  it("the German copy keeps the du register — no Sie form sneaks in", () => {
    for (const [key, value] of Object.entries(catalogs.de)) {
      if (!key.startsWith("knowledge.graph.") && !key.startsWith("knowledge.dossier.")) continue;
      expect(value, key).not.toMatch(/\b(Sie|Ihnen|Ihr|Ihre)\b/);
    }
    expect(catalogs.de["knowledge.graph.emptyNote"]).toContain("deinem");
    expect(catalogs.de["knowledge.graph.noResults"]).toContain("deinem");
  });
});

describe("the edges speak to the keyboard (review fix — the a11y finding)", () => {
  it("an edge is a focusable button named by its ends and type, in an un-hidden layer", async () => {
    await renderGraph();
    const edges = await screen.findAllByTestId("graph-edge");
    expect(edges[0].getAttribute("role")).toBe("button");
    expect(edges[0].getAttribute("tabindex")).toBe("0");
    const label = edges[0].getAttribute("aria-label") ?? "";
    expect(label).toContain("Dr. Maya Chen → ARIA");
    expect(label).toContain(de["knowledge.relation.ally_of"]);
    // The interactive layer is no longer hidden from assistive tech.
    expect(edges[0].closest("svg")?.getAttribute("aria-hidden")).toBeNull();
  });

  it("Enter opens the popover; Escape closes it and returns focus to the edge", async () => {
    await renderGraph();
    const edges = await screen.findAllByTestId("graph-edge");
    const edge = edges[0];
    edge.focus();
    expect(document.activeElement).toBe(edge);
    fireEvent.keyDown(edge, { key: "Enter" });
    const popover = await screen.findByTestId("edge-popover");
    expect(within(popover).getByText("Symbiotische Co-Pilotin.")).toBeTruthy();
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(screen.queryByTestId("edge-popover")).toBeNull());
    expect(document.activeElement).toBe(edge);
  });

  it("Space opens the popover too", async () => {
    await renderGraph();
    const edges = await screen.findAllByTestId("graph-edge");
    fireEvent.keyDown(edges[1], { key: " " });
    expect(await screen.findByTestId("edge-popover")).toBeTruthy();
  });
});

describe("the HUD and legend never seize a pan (review fix)", () => {
  it("a drag starting on the HUD or the legend leaves the viewport put", async () => {
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    const canvas = screen.getByTestId("graph-canvas");
    const before = screen.getByTestId("graph-world").style.transform;
    for (const id of ["graph-hud", "graph-legend"]) {
      fireEvent.pointerDown(screen.getByTestId(id), { clientX: 100, clientY: 100 });
      fireEvent.pointerMove(canvas, { clientX: 400, clientY: 400 });
      fireEvent.pointerUp(canvas);
      expect(screen.getByTestId("graph-world").style.transform).toBe(before);
    }
    // The control: a drag on the open canvas DOES pan — the guard is the
    // HUD/legend's own, not a dead canvas.
    fireEvent.pointerDown(canvas, { clientX: 500, clientY: 500 });
    fireEvent.pointerMove(canvas, { clientX: 560, clientY: 520 });
    fireEvent.pointerUp(canvas);
    expect(screen.getByTestId("graph-world").style.transform).not.toBe(before);
  });

  it("a press on the no-results face never starts a pan — the clear button's click is its own", async () => {
    // The live defect this pins: the canvas captures the pointer on any
    // unguarded press, and the captured click never reaches the clear
    // button (the E2E's clear-filters leg owns the browser proof; jsdom
    // has no pointer capture, so this pin reads the pan state through the
    // transform a drag would have moved — a panned view is what the
    // remounted world would inherit after the filters clear).
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    const canvas = screen.getByTestId("graph-canvas");
    const fit = screen.getByTestId("graph-world").style.transform;
    fireEvent.change(screen.getByTestId("graph-search"), { target: { value: "zzz" } });
    const empty = await screen.findByTestId("graph-no-results");
    fireEvent.pointerDown(empty, { clientX: 100, clientY: 100 });
    fireEvent.pointerMove(canvas, { clientX: 400, clientY: 400 });
    fireEvent.pointerUp(canvas);
    fireEvent.click(within(empty).getByRole("button", { name: de["knowledge.graph.clearFilters"] }));
    await screen.findAllByTestId("graph-node");
    expect(screen.getByTestId("graph-world").style.transform).toBe(fit);
  });
});

describe("an unchanged graph keeps your zoom (review fix)", () => {
  it("an identical-rows refetch preserves the current transform", async () => {
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    const fit = worldScale();
    fireEvent.click(screen.getByTestId("zoom-in"));
    await waitFor(() => expect(worldScale()).toBeGreaterThan(fit));
    const zoomed = screen.getByTestId("graph-world").style.transform;
    // A background refetch: fresh rows, the same set (only updated_at moves,
    // so the cache takes the new identity but the signature does not change).
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/knowledge/novels/{novel_id}/entities") {
        return Promise.resolve({
          data: entities.map((row) => ({ ...row, updated_at: "2026-11-19T00:00:00Z" })),
          response: ok(),
        });
      }
      if (path === "/api/knowledge/novels/{novel_id}/relations") {
        return Promise.resolve({ data: relations.map((row) => ({ ...row })), response: ok() });
      }
      return baseGet(path);
    });
    const before = api.GET.mock.calls.filter(([p]) => p === "/api/knowledge/novels/{novel_id}/entities").length;
    await queryClient.invalidateQueries({ queryKey: ["knowledge"] });
    await waitFor(() =>
      expect(api.GET.mock.calls.filter(([p]) => p === "/api/knowledge/novels/{novel_id}/entities").length).toBeGreaterThan(before),
    );
    // The refetch landed and re-rendered; the zoom is the user's still.
    await waitFor(() => expect(screen.getByTestId("graph-world").style.transform).toBe(zoomed));
    expect(worldScale()).toBeGreaterThan(fit);
  });
});

describe("the subbar's CRUD doors (Task 4)", () => {
  function countGets(path: string): number {
    return api.GET.mock.calls.filter(([p]) => p === path).length;
  }

  it("addEdge, merge and the new-entity door are live", async () => {
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    const add = screen.getByRole("button", { name: de["knowledge.graph.addEdge"] });
    expect((add as HTMLButtonElement).disabled).toBe(false);
    const merge = screen.getByRole("button", { name: de["knowledge.graph.merge"] });
    expect((merge as HTMLButtonElement).disabled).toBe(false);
    const newEntity = screen.getByRole("button", { name: de["knowledge.graph.newEntity"] });
    expect((newEntity as HTMLButtonElement).disabled).toBe(false);
    // The door opens the interview on its chooser; «Von Hand anlegen» is the
    // quiet second path onto the same hand-made create — one dialog for both.
    fireEvent.click(newEntity);
    const panel = await screen.findByTestId("entity-interview");
    fireEvent.click(within(panel).getByTestId("entity-interview-manual"));
    const dialog = await screen.findByTestId("entity-create-dialog");
    expect(within(dialog).getByText(de["knowledge.create.title"])).toBeTruthy();
  });

  it("the door's spoken name carries the open interviews it stands for", async () => {
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/chat/sessions") {
        return Promise.resolve({ data: { items: [sessionSummary("s1"), sessionSummary("s2")] }, response: ok() });
      }
      return baseGet(path);
    });
    await renderGraph();
    await screen.findAllByTestId("graph-node");

    // The count is in the accessible name, not only in the aria-hidden badge.
    const door = await screen.findByRole("button", { name: "Neue Entität, 2 offene Interviews" });
    expect(door).toBe(screen.getByTestId("graph-new-entity"));
    // The title repeats none of it: assistive technology hears the count once.
    expect(door.getAttribute("title")).toBe(de["knowledge.graph.newEntity"]);
    expect(screen.getByTestId("graph-new-entity-count").textContent).toBe("2");
    expect(screen.getByTestId("graph-new-entity-count").getAttribute("aria-hidden")).toBe("true");
  });

  it("closing the panel returns focus to the door that opened it", async () => {
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    const door = screen.getByTestId("graph-new-entity");
    fireEvent.click(door);
    const panel = await screen.findByTestId("entity-interview");
    const close = within(panel).getByTestId("entity-interview-close");
    (close as HTMLElement).focus();
    fireEvent.click(close);

    await waitFor(() => expect(screen.queryByTestId("entity-interview")).toBeNull());
    expect(document.activeElement).toBe(door);
  });

  it("a saved row confirms in the shell's toast with its landed relation count", async () => {
    api.POST.mockResolvedValue({
      data: entityRow({ id: "e9", name: "Nebelhaus", type: "location" }),
      response: new Response(null, { status: 201 }),
    });
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    fireEvent.click(screen.getByRole("button", { name: de["knowledge.graph.newEntity"] }));
    const panel = await screen.findByTestId("entity-interview");
    fireEvent.click(within(panel).getByTestId("entity-interview-manual"));
    const dialog = await screen.findByTestId("entity-create-dialog");
    fireEvent.change(within(dialog).getByTestId("entity-create-name"), {
      target: { value: "Nebelhaus" },
    });
    fireEvent.change(within(dialog).getByTestId("entity-create-type"), {
      target: { value: "location" },
    });
    fireEvent.click(within(dialog).getByTestId("entity-create-save"));
    await waitFor(() => expect(screen.queryByTestId("entity-create-dialog")).toBeNull());
    const toast = await screen.findByTestId("toast");
    expect(toast.textContent).toContain("Entität angelegt · 0 Beziehungen verknüpft");
    // A polite live region, not an interruptive alert.
    expect(toast.parentElement?.getAttribute("aria-live")).toBe("polite");
  });

  it("the addEdge door opens the create dialog; a save refetches the edges", async () => {
    api.POST.mockResolvedValue({ data: R1, response: new Response(null, { status: 201 }) });
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    const before = countGets("/api/knowledge/novels/{novel_id}/relations");
    fireEvent.click(document.getElementById("graph-add-edge") as HTMLElement);
    const dialog = await screen.findByRole("dialog");
    // No selection stands, so the from end is selectable too.
    fireEvent.change(within(dialog).getByLabelText(de["knowledge.crud.fromLabel"]), { target: { value: "e1" } });
    fireEvent.change(within(dialog).getByLabelText(de["knowledge.crud.toLabel"]), { target: { value: "e2" } });
    fireEvent.change(within(dialog).getByLabelText(de["knowledge.crud.relationTypeLabel"]), { target: { value: "ally_of" } });
    fireEvent.click(within(dialog).getByRole("button", { name: de["knowledge.crud.save"] }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.POST).toHaveBeenCalledWith("/api/knowledge/entities/{entity_id}/relations", {
      params: { path: { entity_id: "e1" } },
      body: { to_entity_id: "e2", relation_type: "ally_of", note: undefined },
    });
    // The settled mutation invalidates the edges — the canvas refetches truth.
    await waitFor(() => expect(countGets("/api/knowledge/novels/{novel_id}/relations")).toBeGreaterThan(before));
  });

  it("the merge door opens the merge dialog; a merge refetches the canon and selects the survivor", async () => {
    api.POST.mockResolvedValue({ data: ARIA, response: new Response(null, { status: 200 }) });
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    const before = countGets("/api/knowledge/novels/{novel_id}/entities");
    fireEvent.click(document.getElementById("graph-merge") as HTMLElement);
    const dialog = await screen.findByRole("alertdialog");
    fireEvent.change(within(dialog).getByLabelText(de["knowledge.crud.mergeSourceLabel"]), { target: { value: "e1" } });
    fireEvent.change(within(dialog).getByLabelText(de["knowledge.crud.mergeTargetLabel"]), { target: { value: "e2" } });
    fireEvent.click(within(dialog).getByRole("button", { name: de["knowledge.crud.mergeConfirm"] }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(api.POST).toHaveBeenCalledWith("/api/knowledge/entities/{entity_id}/merge", {
      params: { path: { entity_id: "e1" } },
      body: { target_id: "e2" },
    });
    await waitFor(() => expect(countGets("/api/knowledge/novels/{novel_id}/entities")).toBeGreaterThan(before));
    // The survivor is selected — the dossier follows the merge's truth.
    expect(await screen.findByTestId("entity-dossier")).toBeTruthy();
    expect(within(screen.getByTestId("entity-dossier")).getByText("ARIA")).toBeTruthy();
  });

  it("the merge door is disabled with its note when fewer than two entities stand", async () => {
    entities = [MAYA];
    relations = [];
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    const merge = screen.getByRole("button", { name: new RegExp(de["knowledge.graph.merge"]) });
    expect((merge as HTMLButtonElement).disabled).toBe(true);
    expect(merge.getAttribute("title")).toContain(de["knowledge.crud.mergeNeedsTwo"]);
  });

  it("the addEdge door is disabled with its note on the empty canon — no dead-end dialog (PR #923 follow-up)", async () => {
    entities = [];
    relations = [];
    await renderGraph();
    expect(await screen.findByTestId("graph-empty")).toBeTruthy();
    const door = document.getElementById("graph-add-edge") as HTMLButtonElement;
    expect(door.disabled).toBe(true);
    expect(door.getAttribute("title")).toContain(de["knowledge.crud.relationNeedsTwo"]);
  });

  it("the addEdge door stays disabled with its note at one entity", async () => {
    entities = [MAYA];
    relations = [];
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    const door = document.getElementById("graph-add-edge") as HTMLButtonElement;
    expect(door.disabled).toBe(true);
    expect(door.getAttribute("title")).toContain(de["knowledge.crud.relationNeedsTwo"]);
  });

  it("the addEdge door opens the create dialog once two entities stand", async () => {
    entities = [MAYA, ARIA];
    relations = [];
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    const door = document.getElementById("graph-add-edge") as HTMLButtonElement;
    expect(door.disabled).toBe(false);
    fireEvent.click(door);
    expect(await screen.findByRole("dialog")).toBeTruthy();
  });

  it("a door returns focus to its trigger on a pristine Escape", async () => {
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    const trigger = document.getElementById("graph-add-edge") as HTMLElement;
    trigger.focus();
    fireEvent.click(trigger);
    await screen.findByRole("dialog");
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.activeElement).toBe(trigger);
  });

  it("an entity delete folds the dossier and lands focus on the graph page (review fix)", async () => {
    api.DELETE.mockResolvedValue({ data: undefined, response: new Response(null, { status: 204 }) });
    await renderGraph();
    const nodes = await screen.findAllByTestId("graph-node");
    fireEvent.click(within(nodes[0]).getByRole("button"));
    await screen.findByTestId("entity-dossier");
    fireEvent.click(document.getElementById("dossier-delete") as HTMLElement);
    const confirm = await screen.findByRole("alertdialog");
    fireEvent.click(within(confirm).getByRole("button", { name: de["knowledge.crud.deleteConfirm"] }));
    // The dossier folds (the selection clears); focus lands on the surviving
    // page container, never the body. The focus return rides the unmount's
    // passive cleanup, so it is awaited alongside the fold.
    await waitFor(() => {
      expect(screen.queryByTestId("entity-dossier")).toBeNull();
      expect(document.activeElement).toBe(document.getElementById("graph-page"));
    });
  });

  it("a close that fails after the handover keeps the panel and names the failure", async () => {
    let session = sessionWithProposal("s1", "Nebelhaus");
    let closeCalls = 0;
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/chat/sessions/{session_id}") {
        return Promise.resolve({ data: session, response: ok() });
      }
      return baseGet(path);
    });
    api.POST.mockImplementation((path: string) => {
      if (path === "/api/knowledge/entities") {
        return Promise.resolve({
          data: entityRow({ id: "e9", name: "Nebelhaus", type: "object" }),
          response: new Response(null, { status: 201 }),
        });
      }
      if (path === "/api/chat/sessions/{session_id}/close") {
        closeCalls += 1;
        if (closeCalls === 1) {
          return Promise.resolve({
            data: undefined,
            error: { detail: { code: "provider-error", detail: "offline" } },
            response: new Response(null, { status: 500 }),
          });
        }
        session = { ...session, closed_at: "2026-11-24T14:30:00Z" };
        return Promise.resolve({ data: session, response: ok() });
      }
      throw new Error(`unexpected POST: ${path}`);
    });

    const router = await renderGraph(`/novels/${NOVEL_ID}/knowledge/graph?interview=s1`);
    const panel = await screen.findByTestId("entity-interview");
    const saveDoor = (await within(panel).findByTestId("entity-interview-save")) as HTMLButtonElement;
    await waitFor(() => expect(saveDoor.disabled).toBe(false));
    fireEvent.click(saveDoor);
    const dialog = await screen.findByTestId("entity-create-dialog");
    fireEvent.click(within(dialog).getByTestId("entity-create-save"));

    // The row landed and confirmed, but the close failed: the panel stays
    // open beside the freshly selected row and names the failed end.
    await waitFor(() => expect(screen.queryByTestId("entity-create-dialog")).toBeNull());
    expect((await screen.findByTestId("toast")).textContent).toContain("Entität angelegt");
    const stayed = screen.getByTestId("entity-interview");
    expect(await within(stayed).findByText(de["knowledge.interview.endFailed"])).toBeTruthy();
    expect(router.state.location.search).toMatchObject({ entity: "e9", interview: "s1" });

    // The proposal is already an entity: while the failed end stands, the save
    // door is shut so a second press cannot create the same row again.
    expect((within(stayed).getByTestId("entity-interview-save") as HTMLButtonElement).disabled).toBe(
      true,
    );

    // The end action is the retry; its success reaches the ended face, where
    // the design lets an ended interview's proposal stay savable.
    const end = within(stayed).getByTestId("entity-interview-end");
    fireEvent.click(end);
    await screen.findByText(de["knowledge.interview.endedBanner"]);
    await waitFor(() =>
      expect(screen.queryByText(de["knowledge.interview.endFailed"])).toBeNull(),
    );
    expect((within(stayed).getByTestId("entity-interview-save") as HTMLButtonElement).disabled).toBe(
      false,
    );
  });

  it("the save door is shut while the handover's end request is in flight", async () => {
    const session = sessionWithProposal("s1", "Nebelhaus");
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/chat/sessions/{session_id}") {
        return Promise.resolve({ data: session, response: ok() });
      }
      return baseGet(path);
    });
    // The end request stands until the test settles it — exactly once.
    let releaseClose: (value: unknown) => void = () => {};
    const heldClose = new Promise((resolve) => {
      releaseClose = resolve;
    });
    api.POST.mockImplementation((path: string) => {
      if (path === "/api/knowledge/entities") {
        return Promise.resolve({
          data: entityRow({ id: "e9", name: "Nebelhaus", type: "object" }),
          response: new Response(null, { status: 201 }),
        });
      }
      if (path === "/api/chat/sessions/{session_id}/close") return heldClose;
      throw new Error(`unexpected POST: ${path}`);
    });

    await renderGraph(`/novels/${NOVEL_ID}/knowledge/graph?interview=s1`);
    const panel = await screen.findByTestId("entity-interview");
    const saveDoor = (await within(panel).findByTestId("entity-interview-save")) as HTMLButtonElement;
    await waitFor(() => expect(saveDoor.disabled).toBe(false));
    fireEvent.click(saveDoor);
    const dialog = await screen.findByTestId("entity-create-dialog");
    fireEvent.click(within(dialog).getByTestId("entity-create-save"));

    // The row landed; the end request is still out. The door must already be
    // shut, so a repeated Enter on it cannot open the handover again.
    await waitFor(() => expect(screen.queryByTestId("entity-create-dialog")).toBeNull());
    const staying = await screen.findByTestId("entity-interview");
    // The held request is settled exactly once, whatever the assertions do.
    let released = false;
    const finish = async () => {
      if (released) return;
      released = true;
      await act(async () => {
        releaseClose({
          data: { ...session, closed_at: "2026-11-24T14:30:00Z" },
          response: ok(),
        });
      });
    };
    try {
      expect(
        (within(staying).getByTestId("entity-interview-save") as HTMLButtonElement).disabled,
      ).toBe(true);
    } finally {
      await finish();
    }
    await waitFor(() => expect(screen.queryByTestId("entity-interview")).toBeNull());
  });

  it("hiding or re-selecting the handed-over interview keeps the door shut", async () => {
    const session = sessionWithProposal("s1", "Nebelhaus");
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/chat/sessions/{session_id}") {
        return Promise.resolve({ data: session, response: ok() });
      }
      if (path === "/api/chat/sessions") {
        return Promise.resolve({ data: { items: [sessionSummary("s1")] }, response: ok() });
      }
      return baseGet(path);
    });
    api.POST.mockImplementation((path: string) => {
      if (path === "/api/knowledge/entities") {
        return Promise.resolve({
          data: entityRow({ id: "e9", name: "Nebelhaus", type: "object" }),
          response: new Response(null, { status: 201 }),
        });
      }
      if (path === "/api/chat/sessions/{session_id}/close") {
        return Promise.resolve({
          data: undefined,
          error: { detail: { code: "provider-error", detail: "offline" } },
          response: new Response(null, { status: 500 }),
        });
      }
      throw new Error(`unexpected POST: ${path}`);
    });

    await renderGraph(`/novels/${NOVEL_ID}/knowledge/graph?interview=s1`);
    const panel = await screen.findByTestId("entity-interview");
    const saveDoor = (await within(panel).findByTestId("entity-interview-save")) as HTMLButtonElement;
    await waitFor(() => expect(saveDoor.disabled).toBe(false));
    fireEvent.click(saveDoor);
    const dialog = await screen.findByTestId("entity-create-dialog");
    fireEvent.click(within(dialog).getByTestId("entity-create-save"));
    await waitFor(() => expect(screen.queryByTestId("entity-create-dialog")).toBeNull());
    const stayed = await screen.findByTestId("entity-interview");
    await within(stayed).findByText(de["knowledge.interview.endFailed"]);

    // Hiding never closes the session: the graph's door reopens the same open
    // interview, and the mark the handover left still shuts its save door.
    fireEvent.click(within(stayed).getByTestId("entity-interview-close"));
    await waitFor(() => expect(screen.queryByTestId("entity-interview")).toBeNull());
    fireEvent.click(screen.getByTestId("graph-new-entity"));
    const reopened = await screen.findByTestId("entity-interview");
    await waitFor(() =>
      expect(
        (within(reopened).getByTestId("entity-interview-save") as HTMLButtonElement).disabled,
      ).toBe(true),
    );

    // Re-selecting it from the list is the same interview: the door stays shut.
    fireEvent.click(within(reopened).getByTestId("entity-interview-sessions"));
    const list = await within(reopened).findByTestId("entity-interview-list");
    fireEvent.click(
      await within(list).findByRole("button", { name: de["knowledge.interview.resume"] }),
    );
    await waitFor(() =>
      expect(
        (within(screen.getByTestId("entity-interview")).getByTestId(
          "entity-interview-save",
        ) as HTMLButtonElement).disabled,
      ).toBe(true),
    );
  });

  it("the manual create returns focus to the chooser's own button", async () => {
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    fireEvent.click(screen.getByTestId("graph-new-entity"));
    const panel = await screen.findByTestId("entity-interview");
    const manual = within(panel).getByTestId("entity-interview-manual");
    fireEvent.click(manual);
    const dialog = await screen.findByTestId("entity-create-dialog");
    fireEvent.click(within(dialog).getByTestId("entity-create-cancel"));

    await waitFor(() => expect(screen.queryByTestId("entity-create-dialog")).toBeNull());
    // The panel the writer was in stays open, and focus lands on the control
    // that opened the dialog — not on the door that opened the panel.
    expect(screen.getByTestId("entity-interview")).toBeTruthy();
    expect(document.activeElement).toBe(document.getElementById("entity-interview-manual"));
  });

  it("the handover create returns focus to the save door", async () => {
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/chat/sessions/{session_id}") {
        return Promise.resolve({ data: sessionWithProposal("s1", "Nebelhaus"), response: ok() });
      }
      return baseGet(path);
    });
    await renderGraph(`/novels/${NOVEL_ID}/knowledge/graph?interview=s1`);
    const panel = await screen.findByTestId("entity-interview");
    const saveDoor = (await within(panel).findByTestId("entity-interview-save")) as HTMLButtonElement;
    await waitFor(() => expect(saveDoor.disabled).toBe(false));
    fireEvent.click(saveDoor);
    const dialog = await screen.findByTestId("entity-create-dialog");
    fireEvent.click(within(dialog).getByTestId("entity-create-cancel"));

    await waitFor(() => expect(screen.queryByTestId("entity-create-dialog")).toBeNull());
    expect(screen.getByTestId("entity-interview")).toBeTruthy();
    expect(document.activeElement).toBe(document.getElementById("entity-interview-save"));
  });

  it("a closed interview dialog leaves no prefill for the next manual door", async () => {
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/chat/sessions/{session_id}") {
        return Promise.resolve({ data: sessionWithProposal("s1", "Nebelhaus"), response: ok() });
      }
      if (path === "/api/chat/sessions") {
        // Production's shape: the open session is the list's, so the door's
        // truth and the URL agree on it.
        return Promise.resolve({ data: { items: [sessionSummary("s1")] }, response: ok() });
      }
      return baseGet(path);
    });
    await renderGraph(`/novels/${NOVEL_ID}/knowledge/graph?interview=s1`);
    const panel = await screen.findByTestId("entity-interview");
    const saveDoor = (await within(panel).findByTestId("entity-interview-save")) as HTMLButtonElement;
    await waitFor(() => expect(saveDoor.disabled).toBe(false));

    fireEvent.click(saveDoor);
    const prefilled = await screen.findByTestId("entity-create-dialog");
    expect(within(prefilled).getByText(de["knowledge.create.sourceInterview"])).toBeTruthy();
    fireEvent.click(within(prefilled).getByTestId("entity-create-cancel"));
    await waitFor(() => expect(screen.queryByTestId("entity-create-dialog")).toBeNull());

    // Closing the handover dialog drops its draft. The door then opens the
    // open session the list carries, as production does; the list's «Neues
    // Interview» is the manual door's path to the chooser. It must open the
    // empty form, not the interview's proposal again.
    fireEvent.click(within(screen.getByTestId("entity-interview")).getByTestId("entity-interview-close"));
    await waitFor(() => expect(screen.queryByTestId("entity-interview")).toBeNull());
    fireEvent.click(screen.getByTestId("graph-new-entity"));
    const reopened = await screen.findByTestId("entity-interview");
    expect(within(reopened).queryByTestId("entity-interview-start")).toBeNull();
    expect(within(reopened).getByTestId("entity-interview-proposal").textContent).toContain(
      "Nebelhaus",
    );
    fireEvent.click(within(reopened).getByTestId("entity-interview-sessions"));
    const list = await within(reopened).findByTestId("entity-interview-list");
    fireEvent.click(within(list).getByRole("button", { name: de["knowledge.interview.newInterview"] }));
    const chooser = await screen.findByTestId("entity-interview");
    fireEvent.click(within(chooser).getByTestId("entity-interview-manual"));
    const manual = await screen.findByTestId("entity-create-dialog");
    expect(within(manual).getByText(de["knowledge.create.manualBadge"])).toBeTruthy();
    expect((within(manual).getByTestId("entity-create-name") as HTMLInputElement).value).toBe("");
  });
});

describe("the subbar's sibling door (W5 Task 5 — the two surfaces connect)", () => {
  it("the dossiers door opens the dossiers page, carrying the selection across", async () => {
    const router = await renderGraph();
    const nodes = await screen.findAllByTestId("graph-node");
    fireEvent.click(within(nodes[0]).getByRole("button"));
    await screen.findByTestId("entity-dossier");
    fireEvent.click(screen.getByTestId("graph-dossiers-door"));
    await waitFor(() => expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}/knowledge/dossiers`));
    expect(router.state.location.search).toEqual({ entity: "e1" });
  });

  it("with no selection the door opens the dossiers unscoped", async () => {
    const router = await renderGraph();
    await screen.findAllByTestId("graph-node");
    fireEvent.click(screen.getByTestId("graph-dossiers-door"));
    await waitFor(() => expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}/knowledge/dossiers`));
    expect(router.state.location.search).toEqual({});
  });

  it("a dead id on the URL never travels — the door carries only a living selection", async () => {
    const router = await renderGraph(`/novels/${NOVEL_ID}/knowledge/graph?entity=ghost`);
    await screen.findAllByTestId("graph-node");
    // The unresolvable param opens no dossier; the door must not hand the
    // ghost to the sibling surface.
    expect(screen.queryByTestId("entity-dossier")).toBeNull();
    fireEvent.click(screen.getByTestId("graph-dossiers-door"));
    await waitFor(() => expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}/knowledge/dossiers`));
    expect(router.state.location.search).toEqual({});
  });

  it("the sources door opens the archive unscoped — documents are the library's, not an entity's (Task 6)", async () => {
    const router = await renderGraph();
    const nodes = await screen.findAllByTestId("graph-node");
    fireEvent.click(within(nodes[0]).getByRole("button"));
    await screen.findByTestId("entity-dossier");
    fireEvent.click(screen.getByTestId("graph-sources-door"));
    await waitFor(() => expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}/knowledge/sources`));
    expect(router.state.location.search).toEqual({});
  });
});

describe("the viewport wakes on an uncached load (Codacy fix — PR #912)", () => {
  it("frames the late-mounting canvas by its measured size, not the 800×600 default", async () => {
    stubCanvasRect(1200, 900);
    const resolve = deferredEntities();
    await renderGraph();
    expect(await screen.findByTestId("graph-loading")).toBeTruthy();
    resolve([MAYA, ARIA, STATION, RELIKT]);
    expect(await screen.findAllByTestId("graph-node")).toHaveLength(4);
    // The framing must be the pure fit of the same web in the MEASURED
    // viewport — the bug framed for the 800×600 default because the
    // measure pass ran while the container did not exist yet, then never
    // again. 72 is the page's fit padding; 1200×900 the stubbed canvas.
    const layout = layoutGraph([MAYA, ARIA, STATION, RELIKT], relations);
    const expected = fitTransform(graphBounds(layout.values()), 1200, 900, 72);
    expect(screen.getByTestId("graph-world").style.transform).toBe(
      `translate(${expected.x}px, ${expected.y}px) scale(${expected.k})`,
    );
  });

  it("the wheel listener installs on the late-mounting canvas — the wheel zooms", async () => {
    stubCanvasRect(1200, 900);
    const resolve = deferredEntities();
    await renderGraph();
    expect(await screen.findByTestId("graph-loading")).toBeTruthy();
    resolve([MAYA, ARIA, STATION, RELIKT]);
    expect(await screen.findAllByTestId("graph-node")).toHaveLength(4);
    const before = worldScale();
    fireEvent.wheel(screen.getByTestId("graph-canvas"), { deltaY: -240, clientX: 500, clientY: 400 });
    await waitFor(() => expect(worldScale()).toBeGreaterThan(before));
  });
});

describe("a resize keeps your zoom (review fix — round 2)", () => {
  it("the observer's new size updates the measure and the honest reset, never the user's view", async () => {
    resizeObservers = [];
    vi.stubGlobal("ResizeObserver", ResizeObserverStub);
    stubCanvasRect(1200, 900);
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    // Exactly one observer watches the canvas.
    expect(resizeObservers).toHaveLength(1);
    const fit = worldScale();
    fireEvent.click(screen.getByTestId("zoom-in"));
    await waitFor(() => expect(worldScale()).toBeGreaterThan(fit));
    const zoomed = screen.getByTestId("graph-world").style.transform;
    // A resize arrives: the new rect reaches the measure, and the view
    // keeps the user's zoom — only the first-ever measure reframes.
    stubCanvasRect(900, 700);
    act(() => {
      resizeObservers[0].callback([], resizeObservers[0] as unknown as ResizeObserver);
    });
    expect(screen.getByTestId("graph-world").style.transform).toBe(zoomed);
    // The honest reset frames with the MEASURED new size, not the stale one.
    fireEvent.click(screen.getByTestId("reset-view"));
    const layout = layoutGraph(entities, relations);
    const expected = fitTransform(graphBounds(layout.values()), 900, 700, 72);
    await waitFor(() =>
      expect(screen.getByTestId("graph-world").style.transform).toBe(
        `translate(${expected.x}px, ${expected.y}px) scale(${expected.k})`,
      ),
    );
  });
});

describe("parallel edges between the same pair separate (Codacy fix — PR #912)", () => {
  it("two relations on one pair bow apart — distinct curves, distinct labels, both notes reachable", async () => {
    relations = [
      R1,
      relationRow({ id: "r4", from_entity_id: "e1", to_entity_id: "e2", relation_type: "related_to", note: "Zweite Sicht." }),
    ];
    await renderGraph();
    const edges = await screen.findAllByTestId("graph-edge");
    expect(edges).toHaveLength(2);
    expect(edgePath(edges[0])).not.toBe(edgePath(edges[1]));
    expect(edgeLabel(edges[0])).not.toBe(edgeLabel(edges[1]));
    // Each curve still opens its own popover — the anchor follows each
    // curve's own midpoint, so the earlier note is reachable again.
    fireEvent.click(edges[0]);
    expect(await screen.findByTestId("edge-popover")).toBeTruthy();
    fireEvent.click(within(screen.getByTestId("edge-popover")).getByRole("button", { name: de["knowledge.graph.closeNote"] }));
    await waitFor(() => expect(screen.queryByTestId("edge-popover")).toBeNull());
    fireEvent.click(edges[1]);
    const popover = await screen.findByTestId("edge-popover");
    expect(within(popover).getByText("Zweite Sicht.")).toBeTruthy();
  });

  it("a single edge on a pair keeps the straight centre line", async () => {
    await renderGraph();
    for (const edge of await screen.findAllByTestId("graph-edge")) {
      expect(edgePath(edge)).toMatch(/^M -?\d+(?:\.\d+)? -?\d+(?:\.\d+)? L /);
      expect(edgePath(edge)).not.toContain(" Q ");
    }
  });

  it("reciprocal pairs — A→B and B→A — separate too", async () => {
    relations = [
      R1,
      relationRow({ id: "r4", from_entity_id: "e2", to_entity_id: "e1", relation_type: "related_to", note: null }),
    ];
    await renderGraph();
    const edges = await screen.findAllByTestId("graph-edge");
    expect(edges).toHaveLength(2);
    expect(edgePath(edges[0])).not.toBe(edgePath(edges[1]));
    expect(edgeLabel(edges[0])).not.toBe(edgeLabel(edges[1]));
  });

  it("two same-direction parallels end in distinct arrowheads (review fix — round 2)", async () => {
    relations = [
      R1,
      relationRow({ id: "r4", from_entity_id: "e1", to_entity_id: "e2", relation_type: "related_to", note: null }),
    ];
    await renderGraph();
    const edges = await screen.findAllByTestId("graph-edge");
    expect(edges).toHaveLength(2);
    const arrows = edges.map((edge) => edge.querySelector("polygon")?.getAttribute("points") ?? "");
    expect(arrows[0]).not.toBe(arrows[1]);
  });
});

describe("a self-loop clears its node card (Codacy fix — PR #912)", () => {
  // The card's render carries its width from NODE_CARD_WIDTH — 240px,
  // half-width 120. The test pins the literal on purpose: it is the drift
  // guard that keeps whatever the geometry derives from honest against the
  // render's real width.
  const CARD_HALF = 120;

  function selfLoopEdge(): Element {
    const loop = screen
      .getAllByTestId("graph-edge")
      .find((edge) => edge.getAttribute("data-edge-id") === "r9");
    expect(loop).toBeTruthy();
    return loop as Element;
  }

  it("the loop's arc, arrow and label stand outside the card's real bounds", async () => {
    entities = [MAYA, ARIA];
    relations = [
      R1,
      relationRow({ id: "r9", from_entity_id: "e1", to_entity_id: "e1", relation_type: "related_to", note: "Selbstbezug." }),
    ];
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    const loop = selfLoopEdge();
    const home = layoutGraph(entities, relations).get("e1");
    expect(home).toBeTruthy();
    // Every x of the drawn arc clears the card's half-width — the card
    // renders OVER the svg, so anything inside its bounds is unreachable.
    for (const x of xValues(edgePath(loop))) expect(x).toBeGreaterThan((home as { x: number }).x + CARD_HALF);
    for (const x of xValues(loop.querySelector("polygon")?.getAttribute("points") ?? "")) {
      expect(x).toBeGreaterThan((home as { x: number }).x + CARD_HALF);
    }
    const translate = /translate\(([-\d.]+), ([-\d.]+)\)/.exec(edgeLabel(loop));
    expect(translate).toBeTruthy();
    expect(Number(translate?.[1])).toBeGreaterThan((home as { x: number }).x + CARD_HALF);
  });

  it("the looped edge stays a reachable button that opens its note", async () => {
    entities = [MAYA, ARIA];
    relations = [
      R1,
      relationRow({ id: "r9", from_entity_id: "e1", to_entity_id: "e1", relation_type: "related_to", note: "Selbstbezug." }),
    ];
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    const loop = selfLoopEdge();
    expect(loop.getAttribute("role")).toBe("button");
    expect(loop.getAttribute("tabindex")).toBe("0");
    expect(loop.getAttribute("aria-label")).toContain("Dr. Maya Chen → Dr. Maya Chen");
    fireEvent.click(loop);
    const popover = await screen.findByTestId("edge-popover");
    expect(within(popover).getByText("Selbstbezug.")).toBeTruthy();
  });

  it("a lone self-loop keeps the round's exact pinned shape", async () => {
    entities = [MAYA, ARIA];
    relations = [
      R1,
      relationRow({ id: "r9", from_entity_id: "e1", to_entity_id: "e1", relation_type: "related_to", note: "Selbstbezug." }),
    ];
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    const home = layoutGraph(entities, relations).get("e1") as { x: number; y: number };
    const standX = home.x + CARD_HALF + 10;
    const bowX = home.x + CARD_HALF + 84;
    // The fan must not move the lone loop: standX, bowX and the cubic's
    // true t=0.5 midpoint stay exactly the round's constants.
    expect(edgePath(selfLoopEdge())).toBe(
      `M ${standX} ${home.y - 30} C ${bowX} ${home.y - 88}, ${bowX} ${home.y + 88}, ${standX} ${home.y + 30}`,
    );
    expect(edgeLabel(selfLoopEdge())).toBe(`translate(${(standX + 3 * bowX) / 4}, ${home.y})`);
  });
});

describe("multiple self-loops on one node fan apart (review fix — round 2)", () => {
  const CARD_HALF = 120;

  function edgeById(id: string): Element {
    const edge = screen.getAllByTestId("graph-edge").find((candidate) => candidate.getAttribute("data-edge-id") === id);
    expect(edge).toBeTruthy();
    return edge as Element;
  }

  it("two loops on one node draw distinct arcs and distinct labels, both clear of the card", async () => {
    entities = [MAYA, ARIA];
    relations = [
      R1,
      relationRow({ id: "r9", from_entity_id: "e1", to_entity_id: "e1", relation_type: "related_to", note: "Selbstbezug." }),
      relationRow({ id: "r10", from_entity_id: "e1", to_entity_id: "e1", relation_type: "ally_of", note: null }),
    ];
    await renderGraph();
    await screen.findAllByTestId("graph-node");
    const first = edgeById("r9");
    const second = edgeById("r10");
    expect(edgePath(first)).not.toBe(edgePath(second));
    expect(edgeLabel(first)).not.toBe(edgeLabel(second));
    // Both arcs stay outside the card's real half-width — the fan moves
    // them apart, never back under the card.
    const home = layoutGraph(entities, relations).get("e1") as { x: number };
    for (const x of [...xValues(edgePath(first)), ...xValues(edgePath(second))]) {
      expect(x).toBeGreaterThan(home.x + CARD_HALF);
    }
  });
});
