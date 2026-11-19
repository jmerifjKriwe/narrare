// @vitest-environment jsdom
/**
 * The dossiers page (W5 Task 5) — the harmonized `dossiers-2` draft on the
 * shell's tokens, driven through the real API seam (the client mocked at its
 * module boundary, the house pattern). The grid browses the novel's real
 * EntityRead rows: the contract's eight types as filter tabs, a search over
 * name AND body, and each card showing only real fields (type glyph, name,
 * the description excerpt, the honest relation count — never the draft's
 * invented „Aktiv" status). A card opens the shared EntityDossier (one
 * component, two homes); the draft's invented profile fields stand as honest
 * disabled areas with their gap notes. The `entity` search param is the deep
 * link, the subbar door and the rail's graph door connect the sibling
 * surfaces. The face speaks du-tone in all three catalogs.
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

import { client, type Entity, type Relation } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";

import { DossiersPage } from "./DossiersPage";

const de = catalogs.de;
const api = client as unknown as Record<"GET" | "POST" | "DELETE", ReturnType<typeof vi.fn>>;

configure({ asyncUtilTimeout: 5000 });

const NOVEL_ID = "11111111-1111-1111-1111-111111111111";
const DOSSIERS_PATH = "/novels/$novelId/knowledge/dossiers";
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

function baseGet(path: string): Promise<{ data: unknown; response: Response }> {
  if (path === "/api/knowledge/novels/{novel_id}/entities") {
    return Promise.resolve({ data: entities, response: ok() });
  }
  if (path === "/api/knowledge/novels/{novel_id}/relations") {
    return Promise.resolve({ data: relations, response: ok() });
  }
  throw new Error(`unexpected GET: ${path}`);
}

/** The page on a harness route whose id is the real dossiers path, beside a
 *  graph stub the sibling doors navigate to (the graph page itself is pinned
 *  in its own file). */
const harnessRoot = createRootRoute({ component: () => <Outlet /> });

function validateEntitySearch(search: Record<string, unknown>): { entity?: string } {
  return typeof search.entity === "string" && search.entity !== "" ? { entity: search.entity } : {};
}

async function renderDossiers(entry = `/novels/${NOVEL_ID}/knowledge/dossiers`) {
  const dossiers = createRoute({
    getParentRoute: () => harnessRoot,
    path: DOSSIERS_PATH,
    validateSearch: validateEntitySearch,
    component: DossiersPage,
  });
  const graph = createRoute({
    getParentRoute: () => harnessRoot,
    path: GRAPH_PATH,
    validateSearch: validateEntitySearch,
    component: () => <p>graph face</p>,
  });
  // The sources stub the third sibling door navigates to (W5 Task 6); the
  // archive carries no entity selection, so the route takes no search param.
  const sources = createRoute({
    getParentRoute: () => harnessRoot,
    path: "/novels/$novelId/knowledge/sources",
    component: () => <p>sources face</p>,
  });
  const router = createRouter({
    routeTree: harnessRoot.addChildren([dossiers, graph, sources]),
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
  vi.unstubAllGlobals();
});

describe("the grid browses the novel's real cast", () => {
  it("renders a card per entity with the real fields and the honest relation count", async () => {
    await renderDossiers();
    const cards = await screen.findAllByTestId("dossier-card");
    expect(cards).toHaveLength(4);
    expect(within(cards[0]).getByText("Dr. Maya Chen")).toBeTruthy();
    expect(within(cards[0]).getByText(de["knowledge.type.character"])).toBeTruthy();
    expect(within(cards[0]).getByText("Leitende Bio-Physikerin.")).toBeTruthy();
    // Maya stands in two edges (r1, r2) — the count is the real number,
    // in the locale's own plural.
    expect(within(cards[0]).getByText("2 verknüpfte Relationen")).toBeTruthy();
    // Relikt stands in none — zero reads as zero, never hidden.
    expect(within(cards[3]).getByText("0 verknüpfte Relationen")).toBeTruthy();
    // The reads carry the novel.
    expect(api.GET.mock.calls.some(([p]) => p === "/api/knowledge/novels/{novel_id}/entities")).toBe(true);
    expect(api.GET.mock.calls.some(([p]) => p === "/api/knowledge/novels/{novel_id}/relations")).toBe(true);
  });

  it("the cards show only real fields — no invented status, no invented excerpt", async () => {
    await renderDossiers();
    const cards = await screen.findAllByTestId("dossier-card");
    for (const card of cards) {
      // The draft's „Aktiv" footer is invented — no model carries a status.
      expect(within(card).queryByText(/Aktiv/)).toBeNull();
    }
    // An empty body invents no excerpt (Relikt, e4).
    expect(within(cards[3]).queryByText(de["knowledge.dossier.noDescription"])).toBeNull();
    expect(within(cards[3]).getByText("Relikt")).toBeTruthy();
  });

  it("the type tabs name the contract's eight types with their real counts", async () => {
    await renderDossiers();
    // The subbar stands in every state now, so its tabs exist before the
    // cast lands — the counts are owed the populated body, awaited first.
    await screen.findAllByTestId("dossier-card");
    const tabs = screen.getAllByTestId("dossier-type-tab");
    // All + the contract's eight (character, location, faction, object,
    // system, timeline, event, generic) — the real set, not the draft's four.
    expect(tabs).toHaveLength(9);
    expect(within(tabs[0]).getByText(de["knowledge.graph.allTypes"])).toBeTruthy();
    expect(within(tabs[1]).getByText(de["knowledge.type.character"])).toBeTruthy();
    expect(within(tabs[1]).getByText("2")).toBeTruthy();
    expect(within(tabs[2]).getByText(de["knowledge.type.location"])).toBeTruthy();
    expect(within(tabs[2]).getByText("1")).toBeTruthy();
    // A type the canon does not carry stands at zero — honest, not hidden.
    expect(within(tabs[3]).getByText(de["knowledge.type.faction"])).toBeTruthy();
    expect(within(tabs[3]).getByText("0")).toBeTruthy();
  });

  it("a type tab narrows the grid; a second press restores the whole cast", async () => {
    await renderDossiers();
    const tabs = await screen.findAllByTestId("dossier-type-tab");
    fireEvent.click(within(tabs[2]).getByText(de["knowledge.type.location"]));
    await waitFor(() => expect(screen.getAllByTestId("dossier-card")).toHaveLength(1));
    expect(screen.getByText("Station 7")).toBeTruthy();
    expect(tabs[2].getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(within(tabs[2]).getByText(de["knowledge.type.location"]));
    await waitFor(() => expect(screen.getAllByTestId("dossier-card")).toHaveLength(4));
  });

  it("the search narrows by name, case-insensitive", async () => {
    await renderDossiers();
    await screen.findAllByTestId("dossier-card");
    fireEvent.change(screen.getByTestId("dossier-search"), { target: { value: "maya" } });
    await waitFor(() => expect(screen.getAllByTestId("dossier-card")).toHaveLength(1));
    expect(screen.getByText("Dr. Maya Chen")).toBeTruthy();
  });

  it("the search reads the body too — name or text, as the draft's placeholder promises", async () => {
    await renderDossiers();
    await screen.findAllByTestId("dossier-card");
    // „Nevada" stands only in Station 7's body, never in its name.
    fireEvent.change(screen.getByTestId("dossier-search"), { target: { value: "nevada" } });
    await waitFor(() => expect(screen.getAllByTestId("dossier-card")).toHaveLength(1));
    expect(screen.getByText("Station 7")).toBeTruthy();
  });

  it("the search box is named once — the label, not a doubled mechanism", async () => {
    await renderDossiers();
    await screen.findAllByTestId("dossier-card");
    const box = screen.getByRole("searchbox", { name: de["knowledge.dossiers.searchLabel"] });
    // One naming mechanism: the wrapping label's text, no redundant aria-label.
    expect(box.getAttribute("aria-label")).toBeNull();
    expect(screen.getByLabelText(de["knowledge.dossiers.searchLabel"])).toBe(box);
  });

  it("a self-loop counts once on the card — the same single edge the dossier lists", async () => {
    relations = [relationRow({ id: "r4", from_entity_id: "e1", to_entity_id: "e1", relation_type: "related_to", note: null })];
    await renderDossiers();
    const cards = await screen.findAllByTestId("dossier-card");
    expect(within(cards[0]).getByText("1 verknüpfte Relation")).toBeTruthy();
    fireEvent.click(cards[0]);
    const dossier = await screen.findByTestId("entity-dossier");
    expect(within(dossier).getByText(`${de["knowledge.dossier.relations"]} (1)`)).toBeTruthy();
  });

  it("the excerpt clamps to two lines — no display utility overrides the clamp", async () => {
    await renderDossiers();
    const cards = await screen.findAllByTestId("dossier-card");
    const excerpt = within(cards[0]).getByText("Leitende Bio-Physikerin.");
    expect(excerpt.className).toContain("line-clamp-2");
    // `block` sets display:block and defeats the clamp's -webkit-box — the
    // live look caught exactly that override (a whole body in one card).
    expect(excerpt.className.split(/\s+/)).not.toContain("block");
  });

  it("type and search compose — both must match; the no-results face clears both", async () => {
    await renderDossiers();
    const tabs = await screen.findAllByTestId("dossier-type-tab");
    fireEvent.click(within(tabs[1]).getByText(de["knowledge.type.character"]));
    fireEvent.change(screen.getByTestId("dossier-search"), { target: { value: "aria" } });
    await waitFor(() => expect(screen.getAllByTestId("dossier-card")).toHaveLength(1));
    expect(screen.getByText("ARIA")).toBeTruthy();
    // A character filter plus a location's body matches nothing.
    fireEvent.change(screen.getByTestId("dossier-search"), { target: { value: "nevada" } });
    const empty = await screen.findByTestId("dossiers-no-results");
    expect(within(empty).getByText(de["knowledge.graph.noResults"])).toBeTruthy();
    fireEvent.click(within(empty).getByRole("button", { name: de["knowledge.graph.clearFilters"] }));
    await waitFor(() => expect(screen.getAllByTestId("dossier-card")).toHaveLength(4));
    expect((screen.getByTestId("dossier-search") as HTMLInputElement).value).toBe("");
  });
});

describe("a card opens the shared dossier — one component, two homes", () => {
  it("shows the real fields, wears the pressed face and rides the URL", async () => {
    const router = await renderDossiers();
    const cards = await screen.findAllByTestId("dossier-card");
    fireEvent.click(cards[0]);
    const dossier = await screen.findByTestId("entity-dossier");
    expect(within(dossier).getByText("Dr. Maya Chen")).toBeTruthy();
    expect(within(dossier).getByText("Leitende Bio-Physikerin.")).toBeTruthy();
    expect(within(dossier).getByText("ARIA")).toBeTruthy();
    expect(within(dossier).getByText("Station 7")).toBeTruthy();
    expect(cards[0].getAttribute("aria-pressed")).toBe("true");
    expect(router.state.location.search).toEqual({ entity: "e1" });
  });

  it("the entity search param opens the dossier on arrival — the deep link", async () => {
    await renderDossiers(`/novels/${NOVEL_ID}/knowledge/dossiers?entity=e3`);
    const dossier = await screen.findByTestId("entity-dossier");
    expect(within(dossier).getByText("Station 7")).toBeTruthy();
    expect(within(dossier).getByText("Nevada Deep-Array.")).toBeTruthy();
  });

  it("a relation card selects the other end", async () => {
    await renderDossiers();
    const cards = await screen.findAllByTestId("dossier-card");
    fireEvent.click(cards[0]);
    const dossier = await screen.findByTestId("entity-dossier");
    fireEvent.click(within(dossier).getByText("ARIA"));
    await waitFor(() => expect(within(screen.getByTestId("entity-dossier")).getByText("Autonome Schiffs-KI.")).toBeTruthy());
  });

  it("the close door folds the dossier and clears the selection", async () => {
    const router = await renderDossiers();
    const cards = await screen.findAllByTestId("dossier-card");
    fireEvent.click(cards[0]);
    const dossier = await screen.findByTestId("entity-dossier");
    fireEvent.click(within(dossier).getByRole("button", { name: de["knowledge.dossier.close"] }));
    await waitFor(() => expect(screen.queryByTestId("entity-dossier")).toBeNull());
    expect(router.state.location.search).toEqual({});
  });

  it("with no selection the detail stands an honest prompt, not an invented dossier", async () => {
    await renderDossiers();
    await screen.findAllByTestId("dossier-card");
    expect(screen.getByTestId("dossiers-no-selection")).toBeTruthy();
    expect(screen.getByText(de["knowledge.dossiers.noSelection"])).toBeTruthy();
    expect(screen.queryByTestId("entity-dossier")).toBeNull();
    expect(screen.queryByTestId("dossier-overview")).toBeNull();
  });

  it("an entity delete folds the dossier and lands focus on the dossiers page", async () => {
    api.DELETE.mockResolvedValue({ data: undefined, response: new Response(null, { status: 204 }) });
    await renderDossiers();
    const cards = await screen.findAllByTestId("dossier-card");
    fireEvent.click(cards[0]);
    await screen.findByTestId("entity-dossier");
    fireEvent.click(document.getElementById("dossier-delete") as HTMLElement);
    const confirm = await screen.findByRole("alertdialog");
    fireEvent.click(within(confirm).getByRole("button", { name: de["knowledge.crud.deleteConfirm"] }));
    // The focus return rides the unmount's passive cleanup — awaited with the fold.
    await waitFor(() => {
      expect(screen.queryByTestId("entity-dossier")).toBeNull();
      expect(document.activeElement).toBe(document.getElementById("dossiers-page"));
    });
  });
});

describe("the invented fields stand as honest disabled gaps", () => {
  it("the new-dossier door is disabled with the permanent truth — no create endpoint exists", async () => {
    await renderDossiers();
    await screen.findAllByTestId("dossier-card");
    const door = screen.getByRole("button", { name: new RegExp(de["knowledge.dossiers.newDossier"]) });
    expect((door as HTMLButtonElement).disabled).toBe(true);
    expect(door.getAttribute("title")).toContain(de["knowledge.graph.newEntityNote"]);
    expect(de["knowledge.graph.newEntityNote"]).not.toContain("CRUD");
  });

  it("the draft's profile areas stand disabled inside the dossier, with their gap note", async () => {
    await renderDossiers();
    const cards = await screen.findAllByTestId("dossier-card");
    fireEvent.click(cards[0]);
    const dossier = await screen.findByTestId("entity-dossier");
    // Want/Need/Lie geometry and the dialogue patterns: no model fields exist.
    const psych = within(dossier).getByTestId("dossier-psych-gap");
    expect(psych.getAttribute("aria-disabled")).toBe("true");
    expect(within(psych).getByText(de["knowledge.dossiers.psychProfile"])).toBeTruthy();
    expect(within(psych).getByText(de["knowledge.dossiers.laterWaveNote"])).toBeTruthy();
    const linguistic = within(dossier).getByTestId("dossier-linguistic-gap");
    expect(linguistic.getAttribute("aria-disabled")).toBe("true");
    expect(within(linguistic).getByText(de["knowledge.dossiers.linguisticProfile"])).toBeTruthy();
  });

  it("the shared dossier keeps its own honesty on the second home — status row, excerpts, export", async () => {
    await renderDossiers();
    const cards = await screen.findAllByTestId("dossier-card");
    fireEvent.click(cards[0]);
    const dossier = await screen.findByTestId("entity-dossier");
    expect(within(dossier).getByText(de["knowledge.dossier.status"])).toBeTruthy();
    expect(within(dossier).getByText(de["knowledge.dossier.excerptsGap"])).toBeTruthy();
    const exportDoor = within(dossier).getByRole("button", { name: new RegExp(de["knowledge.dossier.export"]) });
    expect((exportDoor as HTMLButtonElement).disabled).toBe(true);
  });

  it("the AI-sparring area stands disabled with its note — never a fake simulation", async () => {
    await renderDossiers();
    const cards = await screen.findAllByTestId("dossier-card");
    fireEvent.click(cards[0]);
    const area = await screen.findByTestId("dossier-ai-gap");
    expect(area.getAttribute("aria-disabled")).toBe("true");
    expect(within(area).getByText(de["knowledge.dossiers.aiSparring"])).toBeTruthy();
    expect(within(area).getByText(de["knowledge.dossiers.laterWaveNote"])).toBeTruthy();
  });
});

describe("the overview rail names the real model", () => {
  it("shows the selection's real name, type and relation count — nothing invented", async () => {
    await renderDossiers();
    const cards = await screen.findAllByTestId("dossier-card");
    fireEvent.click(cards[0]);
    const overview = await screen.findByTestId("dossier-overview");
    expect(within(overview).getByText(de["knowledge.dossiers.overview"])).toBeTruthy();
    expect(within(overview).getByText("Dr. Maya Chen")).toBeTruthy();
    expect(within(overview).getByText(de["knowledge.type.character"])).toBeTruthy();
    expect(within(overview).getByText("2 verknüpft")).toBeTruthy();
    // No status row — the taxonomy is invented.
    expect(within(overview).queryByText(de["knowledge.dossier.status"])).toBeNull();
  });

  it("the graph area is a live door — the graph went live this wave, so it opens with the selection", async () => {
    const router = await renderDossiers();
    const cards = await screen.findAllByTestId("dossier-card");
    fireEvent.click(cards[0]);
    const door = await screen.findByTestId("dossier-open-graph");
    fireEvent.click(door);
    await waitFor(() => expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}/knowledge/graph`));
    expect(router.state.location.search).toEqual({ entity: "e1" });
  });
});

describe("the subbar's sibling door connects the two surfaces", () => {
  it("the graph door carries the selection across", async () => {
    const router = await renderDossiers();
    const cards = await screen.findAllByTestId("dossier-card");
    fireEvent.click(cards[0]);
    // The selection's navigate commits before the door reads it — the
    // dossier's presence is the settled state (the graph test's discipline).
    await screen.findByTestId("entity-dossier");
    fireEvent.click(screen.getByTestId("dossiers-graph-door"));
    await waitFor(() => expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}/knowledge/graph`));
    expect(router.state.location.search).toEqual({ entity: "e1" });
  });

  it("with no selection the door opens the graph unscoped", async () => {
    const router = await renderDossiers();
    await screen.findAllByTestId("dossier-card");
    fireEvent.click(screen.getByTestId("dossiers-graph-door"));
    await waitFor(() => expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}/knowledge/graph`));
    expect(router.state.location.search).toEqual({});
  });

  it("a dead id on the URL never travels — the door carries only a living selection", async () => {
    const router = await renderDossiers(`/novels/${NOVEL_ID}/knowledge/dossiers?entity=ghost`);
    await screen.findAllByTestId("dossier-card");
    // The unresolvable param opens no dossier; the door must not hand the
    // ghost to the sibling surface.
    expect(screen.queryByTestId("entity-dossier")).toBeNull();
    fireEvent.click(screen.getByTestId("dossiers-graph-door"));
    await waitFor(() => expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}/knowledge/graph`));
    expect(router.state.location.search).toEqual({});
  });

  it("the sources door opens the archive unscoped — documents are the library's, not an entity's (Task 6)", async () => {
    const router = await renderDossiers();
    const cards = await screen.findAllByTestId("dossier-card");
    fireEvent.click(cards[0]);
    await screen.findByTestId("entity-dossier");
    fireEvent.click(screen.getByTestId("dossiers-sources-door"));
    await waitFor(() => expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}/knowledge/sources`));
    expect(router.state.location.search).toEqual({});
  });
});

describe("the honest states", () => {
  it("an empty canon answers the empty face, not an outage", async () => {
    entities = [];
    relations = [];
    await renderDossiers();
    const empty = await screen.findByTestId("dossiers-empty");
    expect(within(empty).getByText(de["knowledge.graph.empty"])).toBeTruthy();
    expect(within(empty).getByText(de["knowledge.graph.emptyNote"])).toBeTruthy();
    expect(screen.queryByTestId("dossier-card")).toBeNull();
  });

  it("a pending ask shows the loading face, never an invented cast", async () => {
    let resolveEntities: (value: { data: Entity[]; response: Response }) => void = () => {};
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/knowledge/novels/{novel_id}/entities") {
        return new Promise((resolve) => {
          resolveEntities = resolve;
        });
      }
      return baseGet(path);
    });
    await renderDossiers();
    expect(await screen.findByTestId("dossiers-loading")).toBeTruthy();
    expect(screen.queryByTestId("dossier-card")).toBeNull();
    resolveEntities({ data: [MAYA], response: ok() });
    expect(await screen.findByTestId("dossier-card")).toBeTruthy();
  });

  it("an unavailable cast names itself and offers the retry", async () => {
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/knowledge/novels/{novel_id}/entities") {
        return Promise.resolve({ data: undefined, response: new Response(null, { status: 500 }) });
      }
      return baseGet(path);
    });
    await renderDossiers();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.dossiers.loadFailed"])).toBeTruthy();
    api.GET.mockImplementation(baseGet);
    fireEvent.click(within(alert).getByRole("button", { name: de["knowledge.graph.retry"] }));
    expect(await screen.findAllByTestId("dossier-card")).toHaveLength(4);
  });
});

describe("the subbar stands in every state — the sibling doors never vanish (PR #923 fix)", () => {
  it("the empty canon still offers both sibling doors beside the empty face", async () => {
    entities = [];
    relations = [];
    await renderDossiers();
    expect(await screen.findByTestId("dossiers-empty")).toBeTruthy();
    expect(screen.getByTestId("dossiers-graph-door")).toBeTruthy();
    expect(screen.getByTestId("dossiers-sources-door")).toBeTruthy();
    // The view label stands too — the bar names the surface it is on.
    expect(screen.getByText(de["knowledge.dossiers.title"])).toBeTruthy();
  });

  it("the pending face keeps the doors — the loading answer still navigates", async () => {
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/knowledge/novels/{novel_id}/entities") {
        return new Promise(() => {});
      }
      return baseGet(path);
    });
    await renderDossiers();
    expect(await screen.findByTestId("dossiers-loading")).toBeTruthy();
    expect(screen.getByTestId("dossiers-graph-door")).toBeTruthy();
    expect(screen.getByTestId("dossiers-sources-door")).toBeTruthy();
    expect(screen.getByText(de["knowledge.dossiers.title"])).toBeTruthy();
  });

  it("the failed face keeps the doors — the outage answer still navigates", async () => {
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/knowledge/novels/{novel_id}/entities") {
        return Promise.resolve({ data: undefined, response: new Response(null, { status: 500 }) });
      }
      return baseGet(path);
    });
    await renderDossiers();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(de["knowledge.dossiers.loadFailed"])).toBeTruthy();
    expect(screen.getByTestId("dossiers-graph-door")).toBeTruthy();
    expect(screen.getByTestId("dossiers-sources-door")).toBeTruthy();
    expect(screen.getByText(de["knowledge.dossiers.title"])).toBeTruthy();
  });
});

describe("the face speaks du-tone in every catalog — no German fallback", () => {
  it("the English face speaks the English catalog's own copy", async () => {
    applyLocale("en");
    const en = catalogs.en;
    await renderDossiers();
    const cards = await screen.findAllByTestId("dossier-card");
    expect(screen.getByTestId("dossier-search").getAttribute("placeholder")).toBe(en["knowledge.dossiers.search"]);
    expect(within(cards[0]).getByText("2 linked relations")).toBeTruthy();
    expect(screen.queryByText(de["knowledge.dossiers.search"])).toBeNull();
  });

  it("the French face counts zero as one — the locale's own plural rule", async () => {
    applyLocale("fr");
    const fr = catalogs.fr;
    await renderDossiers();
    const cards = await screen.findAllByTestId("dossier-card");
    // CLDR fr puts 0 in the „one" category — the catalog's plural carries
    // the rule, never a hard-coded German zero.
    expect(within(cards[3]).getByText("0 relation liée")).toBeTruthy();
    expect(screen.getByTestId("dossier-search").getAttribute("placeholder")).toBe(fr["knowledge.dossiers.search"]);
    expect(screen.queryByText(de["knowledge.dossiers.search"])).toBeNull();
  });

  it("the three catalogs carry the dossiers' keys in parity, each translated", () => {
    const keys = Object.keys(catalogs.de).filter((key) => key.startsWith("knowledge.dossiers."));
    expect(keys.length).toBeGreaterThan(0);
    for (const key of keys) {
      for (const locale of ["en", "fr"] as const) {
        expect(catalogs[locale][key as keyof typeof catalogs.en], `${locale}/${key}`).toBeTruthy();
      }
    }
    const translated = [
      "knowledge.dossiers.search",
      "knowledge.dossiers.listHint",
      "knowledge.dossiers.loadFailed",
      "knowledge.dossiers.psychProfile",
    ] as const;
    for (const key of translated) {
      expect(catalogs.en[key], key).not.toBe(catalogs.de[key]);
      expect(catalogs.fr[key], key).not.toBe(catalogs.de[key]);
    }
  });

  it("the German copy keeps the du register — no Sie form sneaks in", () => {
    for (const [key, value] of Object.entries(catalogs.de)) {
      if (!key.startsWith("knowledge.dossiers.")) continue;
      expect(value, key).not.toMatch(/\b(Sie|Ihnen|Ihr|Ihre)\b/);
    }
    expect(catalogs.de["knowledge.dossiers.listHint"]).toContain("deinem");
    expect(catalogs.de["knowledge.dossiers.noSelection"]).toContain("Wähle");
  });
});
