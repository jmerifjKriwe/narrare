// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@shell/lib/api/client";
import { rootRoute } from "@shell/routes/__root";
import { KnowledgeDock } from "./dock";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

const api = client as unknown as {
  GET: ReturnType<typeof vi.fn>;
  POST: ReturnType<typeof vi.fn>;
};

const mira = {
  id: "e-mira",
  novel_id: "novel",
  name: "Mira",
  type: "character",
  description: null,
  aliases: [],
  tags: [],
  content: "",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function renderDock(entry: string) {
  const novel = createRoute({
    getParentRoute: () => rootRoute,
    path: "/novels/$id",
    component: Outlet,
  });
  const knowledge = createRoute({
    getParentRoute: () => novel,
    path: "knowledge",
    component: KnowledgeDock,
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
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("KnowledgeDock view switcher", () => {
  it("shows the list by default and toggles to the lens and back", async () => {
    api.GET.mockImplementation(async (path: string) => {
      if (path.includes("relations")) return { data: [], response: { ok: true } };
      if (path.includes("entities")) return { data: [mira], response: { ok: true } };
      return { data: [], response: { ok: true } };
    });
    api.POST.mockResolvedValue({ data: [], response: { ok: true } });
    renderDock("/novels/novel/knowledge");
    const user = userEvent.setup();

    // The default is today's stacking: the entity list stands, the lens's
    // empty state does not.
    const list = await screen.findByRole("button", { name: "List" });
    expect(list.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Neighborhood" }).getAttribute("aria-pressed")).toBe(
      "false",
    );
    expect(screen.getByRole("region", { name: "Entities" })).toBeTruthy();

    // The switch: the lens stands where the stacking was.
    await user.click(screen.getByRole("button", { name: "Neighborhood" }));
    expect(
      await screen.findByText("Select an entity in the list to see its neighborhood."),
    ).toBeTruthy();
    expect(screen.queryByRole("region", { name: "Entities" })).toBeNull();

    // And back: the stacking returns, the lens leaves.
    await user.click(screen.getByRole("button", { name: "List" }));
    expect(await screen.findByRole("region", { name: "Entities" })).toBeTruthy();
    expect(
      screen.queryByText("Select an entity in the list to see its neighborhood."),
    ).toBeNull();
  });
});
