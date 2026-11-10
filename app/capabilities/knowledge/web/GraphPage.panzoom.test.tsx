// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRoute, createRouter, RouterProvider } from "@tanstack/react-router";
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
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

function renderGraph(search: string, queryClient?: QueryClient) {
  const route = createRoute({
    getParentRoute: () => rootRoute,
    path: "/knowledge/graph",
    component: GraphPage,
    validateSearch: (search: Record<string, unknown>) => ({
      novel: typeof search.novel === "string" ? search.novel : undefined,
    }),
  });
  const router = createRouter({
    routeTree: rootRoute.addChildren([route]),
    history: createMemoryHistory({ initialEntries: [`/knowledge/graph${search}`] }),
  });
  const client = queryClient ?? new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  return router;
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

function viewBoxOf(canvas: Element): [number, number, number, number] {
  const raw = canvas.getAttribute("viewBox") ?? "";
  const parts = raw.split(/\s+/).map(Number);
  expect(parts).toHaveLength(4);
  return parts as [number, number, number, number];
}

describe("GraphPage pan and zoom", () => {
  it("zoom in narrows the rendered viewBox around the graph's centre", async () => {
    mockNovel();
    renderGraph("?novel=novel-1");
    const canvas = await screen.findByRole("group", { name: "Entity graph" });
    const fit = viewBoxOf(canvas);
    expect(fit).toEqual([0, 0, 960, 600]);

    await userEvent.setup().click(screen.getByRole("button", { name: "Zoom in" }));
    const zoomed = viewBoxOf(canvas);
    // A smaller window onto the same layout: the visible centre stays put.
    expect(zoomed[2]).toBeLessThan(fit[2]);
    expect(zoomed[3]).toBeLessThan(fit[3]);
    expect(zoomed[0] + zoomed[2] / 2).toBeCloseTo(fit[0] + fit[2] / 2, 5);
    expect(zoomed[1] + zoomed[3] / 2).toBeCloseTo(fit[1] + fit[3] / 2, 5);
  });

  it("zoom out is clamped at the lower bound", async () => {
    mockNovel();
    renderGraph("?novel=novel-1");
    const user = userEvent.setup();
    const canvas = await screen.findByRole("group", { name: "Entity graph" });
    const out = screen.getByRole("button", { name: "Zoom out" });
    for (let i = 0; i < 12; i += 1) await user.click(out);
    const clamped = viewBoxOf(canvas);
    // 0.5× of the fit scale: the window never grows past twice the layout.
    expect(clamped[2]).toBeLessThanOrEqual(1920);
    expect(clamped[3]).toBeLessThanOrEqual(1200);
    await user.click(out);
    expect(viewBoxOf(canvas)).toEqual(clamped);
  });

  it("reset returns to the fitted view in one action", async () => {
    mockNovel();
    renderGraph("?novel=novel-1");
    const user = userEvent.setup();
    const canvas = await screen.findByRole("group", { name: "Entity graph" });
    const fit = viewBoxOf(canvas);
    await user.click(screen.getByRole("button", { name: "Zoom in" }));
    expect(viewBoxOf(canvas)).not.toEqual(fit);
    await user.click(screen.getByRole("button", { name: "Reset view" }));
    expect(viewBoxOf(canvas)).toEqual(fit);
  });

  it("a far drag cannot move the graph out of reach", async () => {
    mockNovel();
    renderGraph("?novel=novel-1");
    const user = userEvent.setup();
    const canvas = await screen.findByRole("group", { name: "Entity graph" });
    await user.click(screen.getByRole("button", { name: "Zoom in" }));
    await user.click(screen.getByRole("button", { name: "Zoom in" }));
    const zoomed = viewBoxOf(canvas);

    // jsdom lays nothing out: hand the canvas its rendered box so the
    // drag travels real pixels and the clamp has something to hold.
    vi.spyOn(canvas, "getBoundingClientRect").mockReturnValue({
      width: 960, height: 600, left: 0, top: 0, right: 960, bottom: 600, x: 0, y: 0,
      toJSON: () => {},
    } as DOMRect);

    fireEvent.pointerDown(canvas, { button: 0, clientX: 480, clientY: 300, pointerId: 1 });
    fireEvent.pointerMove(canvas, { clientX: 480 + 5000, clientY: 300 + 5000, pointerId: 1 });
    fireEvent.pointerUp(canvas, { pointerId: 1 });

    // The window stays inside the layout: the graph is still under it.
    const [x, y, w, h] = viewBoxOf(canvas);
    expect(x).toBeGreaterThanOrEqual(0);
    expect(y).toBeGreaterThanOrEqual(0);
    expect(x + w).toBeLessThanOrEqual(960);
    expect(y + h).toBeLessThanOrEqual(600);
    expect([w, h]).toEqual([zoomed[2], zoomed[3]]);
  });

  it("the three controls are keyboard-reachable and operate", async () => {
    mockNovel();
    renderGraph("?novel=novel-1");
    const canvas = await screen.findByRole("group", { name: "Entity graph" });
    const fit = viewBoxOf(canvas);
    const zoomIn = screen.getByRole("button", { name: "Zoom in" });
    const zoomOut = screen.getByRole("button", { name: "Zoom out" });
    const reset = screen.getByRole("button", { name: "Reset view" });

    zoomIn.focus();
    expect(zoomIn).toBe(document.activeElement);
    const user = userEvent.setup();
    await user.keyboard("{Enter}");
    expect(viewBoxOf(canvas)).not.toEqual(fit);

    // Tab order carries through all three controls.
    zoomIn.focus();
    await user.tab();
    expect(zoomOut).toBe(document.activeElement);
    await user.tab();
    expect(reset).toBe(document.activeElement);
    await user.keyboard("{Enter}");
    expect(viewBoxOf(canvas)).toEqual(fit);
  });

  it("a wheel turn zooms on a cold mount: the listener rides with the canvas", async () => {
    mockNovel();
    // A fresh client is the cold load: nothing cached, the canvas appears
    // only after the reads resolve — the wheel listener must still be there.
    renderGraph("?novel=novel-1");
    const canvas = await screen.findByRole("group", { name: "Entity graph" });
    const fit = viewBoxOf(canvas);
    expect(fit).toEqual([0, 0, 960, 600]);

    fireEvent.wheel(canvas, { deltaX: 0, deltaY: -120 });
    const zoomed = viewBoxOf(canvas);
    expect(zoomed[2]).toBeLessThan(fit[2]);
    expect(zoomed[3]).toBeLessThan(fit[3]);
  });

  it("a sideways scroll leaves the zoom alone and keeps the gesture", async () => {
    mockNovel();
    // Cold mount, like the wheel test above: no warmed cache, the canvas
    // appears after the reads resolve and the listener rides with it.
    renderGraph("?novel=novel-1");
    const canvas = await screen.findByRole("group", { name: "Entity graph" });
    const fit = viewBoxOf(canvas);
    // A horizontal trackpad scroll carries no vertical delta: the canvas must
    // not read it as zoom-out, and the gesture stays unprevented so the
    // page (or the trackpad's own sideways scroll) can have it.
    const sideways = fireEvent.wheel(canvas, { deltaX: 24, deltaY: 0 });
    expect(sideways).toBe(true);
    expect(viewBoxOf(canvas)).toEqual(fit);
    // The control: a real vertical turn still zooms (up zooms in).
    fireEvent.wheel(canvas, { deltaX: 0, deltaY: -120 });
    expect(viewBoxOf(canvas)[2]).toBeLessThan(fit[2]);
  });

  it("switching novels resets the view to fit instead of keeping the old zoom", async () => {
    mockNovel();
    const router = renderGraph("?novel=novel-1");
    const user = userEvent.setup();
    const canvas = await screen.findByRole("group", { name: "Entity graph" });
    await user.click(screen.getByRole("button", { name: "Zoom in" }));
    expect(viewBoxOf(canvas)[2]).toBeLessThan(960);

    await act(async () => {
      await router.navigate({ to: "/knowledge/graph", search: { novel: "novel-2" } });
    });
    // The new novel's canvas: same data shape, the fitted window again.
    const next = await screen.findByRole("group", { name: "Entity graph" });
    expect(viewBoxOf(next)).toEqual([0, 0, 960, 600]);
  });

  it("selection still works after zoom", async () => {
    mockNovel();
    renderGraph("?novel=novel-1");
    const user = userEvent.setup();
    await screen.findByRole("group", { name: "Entity graph" });
    await user.click(screen.getByRole("button", { name: "Zoom in" }));
    await user.click(await screen.findByText("Mira"));
    const detail = await screen.findByRole("region", { name: "Mira" });
    expect(within(detail).getByText("Character")).toBeTruthy();
  });
});
