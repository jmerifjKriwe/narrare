// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@shell/lib/api/client";
import { rootRoute } from "@shell/routes/__root";
import { NeighborhoodLens } from "./NeighborhoodLens";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

const api = client as unknown as {
  GET: ReturnType<typeof vi.fn>;
};

const stamp = "2026-01-01T00:00:00Z";
const entity = (id: string, name: string, type: string) => ({
  id,
  novel_id: "novel",
  name,
  type,
  description: null,
  aliases: [],
  tags: [],
  content: "",
  created_at: stamp,
  updated_at: stamp,
});
const mira = entity("e-mira", "Mira", "character");
const haus = entity("e-haus", "Haus", "location");
const turm = entity("e-turm", "Leuchtturm", "location");

const relation = (id: string, from: string, to: string) => ({
  id,
  novel_id: "novel",
  from_entity_id: from,
  to_entity_id: to,
  relation_type: "related_to",
  note: null,
  created_at: stamp,
  updated_at: stamp,
});

function mockNovel(ents: unknown[], rels: unknown[]) {
  api.GET.mockImplementation(async (path: string) => {
    if (path.includes("relations")) return { data: rels, response: { ok: true } };
    if (path.includes("entities")) return { data: ents, response: { ok: true } };
    throw new Error(`unexpected GET ${path}`);
  });
}

function renderLens(entry: string) {
  const novel = createRoute({
    getParentRoute: () => rootRoute,
    path: "/novels/$id",
    component: Outlet,
  });
  const knowledge = createRoute({
    getParentRoute: () => novel,
    path: "knowledge",
    component: NeighborhoodLens,
    validateSearch: (search: Record<string, unknown>) => ({
      entity: search.entity as string | undefined,
    }),
  });
  const router = createRouter({
    routeTree: rootRoute.addChildren([novel.addChildren([knowledge])]),
    history: createMemoryHistory({ initialEntries: [entry] }),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
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
});

describe("NeighborhoodLens selection", () => {
  it("names the next step when nothing is selected", async () => {
    mockNovel([mira, haus], []);
    renderLens("/novels/novel/knowledge");

    // The honest state: no crash, no empty SVG — the next step in words.
    expect(
      await screen.findByText("Select an entity in the list to see its neighborhood."),
    ).toBeTruthy();
    expect(screen.queryByRole("region", { name: "Neighborhood" })).toBeNull();
  });

  it("a stale id degrades to the empty state and leaves the address", async () => {
    mockNovel([mira, haus], []);
    const router = renderLens("/novels/novel/knowledge?entity=dead-id");

    // The list's degradation: no selection, never an error — and the dead
    // value leaves the address, like the list's own cleanup.
    expect(
      await screen.findByText("Select an entity in the list to see its neighborhood."),
    ).toBeTruthy();
    expect(screen.queryByRole("region", { name: "Neighborhood" })).toBeNull();
    await waitFor(() =>
      expect(
        (router.state.location.search as { entity?: string }).entity,
      ).toBeUndefined(),
    );
  });
});

describe("NeighborhoodLens graph", () => {
  it("renders the selected entity with its two neighbors and both edges", async () => {
    mockNovel(
      [mira, haus, turm],
      [relation("r-1", "e-mira", "e-haus"), relation("r-2", "e-turm", "e-mira")],
    );
    const router = renderLens("/novels/novel/knowledge?entity=e-mira");
    const user = userEvent.setup();

    // Hop-1: the selected entity plus exactly its direct neighbors — one
    // outgoing edge, one incoming, both touching Mira.
    expect(await screen.findByText("Haus")).toBeTruthy();
    expect(await screen.findByText("Leuchtturm")).toBeTruthy();
    const canvas = await screen.findByRole("region", { name: "Neighborhood" });
    expect(canvas.querySelectorAll("line")).toHaveLength(2);
    // The selected node is marked, the neighbors are plain buttons.
    expect(screen.getByRole("button", { name: "Mira" }).getAttribute("aria-pressed")).toBe(
      "true",
    );
    expect(screen.getByRole("button", { name: "Haus" }).getAttribute("aria-pressed")).toBe(
      "false",
    );

    // A neighbor click re-targets the lens through the same `?entity=`
    // address the list writes.
    await user.click(screen.getByRole("button", { name: "Haus" }));
    await waitFor(() =>
      expect((router.state.location.search as { entity?: string }).entity).toBe("e-haus"),
    );
  });

  it("renders the entity alone and says so when it has no relations", async () => {
    mockNovel([mira, haus], []);
    renderLens("/novels/novel/knowledge?entity=e-mira");

    expect(await screen.findByText("Mira has no relations yet.")).toBeTruthy();
    const canvas = await screen.findByRole("region", { name: "Neighborhood" });
    expect(canvas.querySelectorAll("line")).toHaveLength(0);
    expect(screen.getByRole("button", { name: "Mira" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Haus" })).toBeNull();
  });

  it("the cross-link carries the novel to the graph canvas", async () => {
    mockNovel([mira, haus], [relation("r-1", "e-mira", "e-haus")]);
    renderLens("/novels/novel/knowledge?entity=e-mira");

    const open = await screen.findByRole("link", { name: "Open in graph" });
    expect(open.getAttribute("href")).toBe("/knowledge/graph?novel=novel");
  });
});
