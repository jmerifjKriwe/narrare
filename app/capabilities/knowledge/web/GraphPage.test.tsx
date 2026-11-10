// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRoute, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@shell/lib/api/client";
import { rootRoute } from "@shell/routes/__root";
import { GraphPage } from "./GraphPage";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

const api = client as unknown as {
  GET: ReturnType<typeof vi.fn>;
};

const mira = {
  id: "e-mira", novel_id: "novel-1", name: "Mira", type: "character",
  description: null, aliases: ["Miri"], tags: ["crew"], content: "Mira wuchs an der Bucht auf.",
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
};
const leuchtturm = {
  id: "e-tur", novel_id: "novel-1", name: "Leuchtturm", type: "location",
  description: null, aliases: [], tags: [], content: "",
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
};
const edge = {
  id: "r-1", novel_id: "novel-1", from_entity_id: "e-mira", to_entity_id: "e-tur",
  relation_type: "friend_of", note: null,
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
};

function renderGraph(search: string) {
  const graph = createRoute({
    getParentRoute: () => rootRoute,
    path: "/knowledge/graph",
    component: GraphPage,
    validateSearch: (search: Record<string, unknown>) => ({
      novel: typeof search.novel === "string" ? search.novel : undefined,
    }),
  });
  const router = createRouter({
    routeTree: rootRoute.addChildren([graph]),
    history: createMemoryHistory({ initialEntries: [`/knowledge/graph${search}`] }),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}><RouterProvider router={router} /></QueryClientProvider>);
  return queryClient;
}

function mockNovel() {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/writing/novels") return { data: [], response: { ok: true } };
    if (path.includes("/entities")) return { data: [mira, leuchtturm], response: { ok: true } };
    if (path.includes("/relations")) return { data: [edge], response: { ok: true } };
    throw new Error(`unexpected GET ${path}`);
  });
}

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("GraphPage canvas", () => {
  it("renders the novel's nodes by name with the edge between them", async () => {
    mockNovel();
    renderGraph("?novel=novel-1");
    // Both entities are nodes on the canvas, named where the reader finds them.
    expect(await screen.findByText("Mira")).toBeTruthy();
    expect(await screen.findByText("Leuchtturm")).toBeTruthy();
    // The one edge is a drawn line between the two nodes.
    const canvas = await screen.findByRole("group", { name: "Entity graph" });
    expect(canvas.querySelectorAll("line")).toHaveLength(1);
    // Nothing truncated: the whole novel is on the canvas.
    expect(screen.getByText("Showing 2 of 2 entities · 1 of 1 relations")).toBeTruthy();
  });

  it("selecting a node shows its read-only detail with the dock door", async () => {
    mockNovel();
    renderGraph("?novel=novel-1");
    const user = userEvent.setup();
    await user.click(await screen.findByText("Mira"));
    const detail = await screen.findByRole("region", { name: "Mira" });
    // The glance: type wording, alias chip, body's first line.
    expect(within(detail).getByText("Character")).toBeTruthy();
    expect(within(detail).getByText("Miri", { exact: true })).toBeTruthy();
    expect(within(detail).getByText("Mira wuchs an der Bucht auf.")).toBeTruthy();
    // The edge in the detail's own words — the graph stays read-only,
    // so the one door out names the dock, never an inline editor.
    expect(within(detail).getByText("Leuchtturm · Friend of")).toBeTruthy();
    const edit = within(detail).getByRole("link", { name: "Edit in dock" });
    expect(edit.getAttribute("href")).toBe("/novels/novel-1/knowledge?entity=e-mira");
    expect(within(detail).queryByRole("button")).toBeNull();
  });

  it("a keyboard-focused node shows the focus indicator", async () => {
    mockNovel();
    renderGraph("?novel=novel-1");
    const node = await screen.findByRole("button", { name: "Mira" });
    node.focus();
    expect(node).toBe(document.activeElement);
    // The file's ring idiom, pinned on the canvas: the links carry
    // focus-visible:ring-2, the node the outline twin — a box-shadow
    // ring would not paint on an inner SVG element. Before the fix the
    // node wore only cursor-pointer, and a keyboard's position died
    // silently on the graph. (getAttribute: an SVG element's className
    // is an SVGAnimatedString, not a string.)
    const worn = node.getAttribute("class") ?? "";
    expect(worn).toContain("focus-visible:outline-2");
    expect(worn).toContain("focus-visible:outline-focus");
  });

  it("an entity-free novel owns its empty state, not an empty viewport", async () => {
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/writing/novels") return { data: [], response: { ok: true } };
      return { data: [], response: { ok: true } };
    });
    renderGraph("?novel=novel-1");
    expect(await screen.findByText("No entities yet")).toBeTruthy();
  });

  it("a refused read names the outage and its retry heals", async () => {
    const refused = new Set<string>();
    api.GET.mockImplementation(async (path: string) => {
      // Each read refuses once, then heals: the page shows the outage
      // while either answer is missing, and the retry re-asks both.
      if (!refused.has(path)) {
        refused.add(path);
        return { data: undefined, response: { ok: false, status: 500 } };
      }
      if (path.includes("/entities")) return { data: [mira, leuchtturm], response: { ok: true } };
      if (path.includes("/relations")) return { data: [edge], response: { ok: true } };
      return { data: [], response: { ok: true } };
    });
    renderGraph("?novel=novel-1");
    const user = userEvent.setup();
    expect(await screen.findByText("Your entities could not be loaded. Is the local service running?")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.queryByText("Mira")).toBeTruthy());
  });

  it("a self-loop relation renders as a loop glyph, not a zero-length line", async () => {
    const loop = {
      id: "r-loop", novel_id: "novel-1", from_entity_id: "e-mira", to_entity_id: "e-mira",
      relation_type: "friend_of", note: null,
      created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
    };
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/writing/novels") return { data: [], response: { ok: true } };
      if (path.includes("/entities")) return { data: [mira], response: { ok: true } };
      if (path.includes("/relations")) return { data: [loop], response: { ok: true } };
      throw new Error(`unexpected GET ${path}`);
    });
    renderGraph("?novel=novel-1");
    const canvas = await screen.findByRole("group", { name: "Entity graph" });
    // The loop glyph stands in for the edge: no zero-length line remains.
    expect(canvas.querySelectorAll("line")).toHaveLength(0);
    const glyph = canvas.querySelector('[data-testid="self-loop"]');
    expect(glyph).toBeTruthy();
    // Pure decoration: clicks pass through to the node button, screen readers use the node + detail.
    expect(glyph?.getAttribute("pointer-events")).toBe("none");
    expect(glyph?.getAttribute("aria-hidden")).toBe("true");
  });

  it("without a novel it offers the novels instead of guessing one", async () => {
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/writing/novels") {
        return { data: [{ id: "novel-1", title: "Die Bucht" }], response: { ok: true } };
      }
      throw new Error(`unexpected GET ${path}`);
    });
    renderGraph("");
    expect(await screen.findByRole("link", { name: "Die Bucht" })).toBeTruthy();
    // No entity read went out: the picker asks for the novel first.
    expect(api.GET).not.toHaveBeenCalledWith(
      expect.stringContaining("/entities"),
      expect.anything(),
    );
    expect(api.GET).not.toHaveBeenCalledWith(
      expect.stringContaining("/relations"),
      expect.anything(),
    );
  });
});
