// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRoute, createRouter, Outlet, RouterProvider } from "@tanstack/react-router";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@shell/lib/api/client";
import { rootRoute } from "@shell/routes/__root";
import { EntitiesPanel } from "./EntitiesPanel";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

const api = client as unknown as { GET: ReturnType<typeof vi.fn>; POST: ReturnType<typeof vi.fn> };
const entity = (id: string, type: string, tags: string[] = []) => ({
  id, novel_id: "novel", name: id, type, description: null, aliases: [], tags,
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
});

function renderPanel() {
  const novel = createRoute({
    getParentRoute: () => rootRoute,
    path: "/novels/$id",
    component: Outlet,
  });
  const wissen = createRoute({
    getParentRoute: () => novel,
    path: "wissen",
    component: EntitiesPanel,
    validateSearch: (search: Record<string, unknown>) => ({ entity: search.entity as string | undefined }),
  });
  const router = createRouter({
    routeTree: rootRoute.addChildren([novel.addChildren([wissen])]),
    history: createMemoryHistory({ initialEntries: ["/novels/novel/wissen"] }),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}><RouterProvider router={router} /></QueryClientProvider>);
  return queryClient;
}

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("EntitiesPanel filters", () => {
  it("clears selected type and tag after their last entity disappears", async () => {
    let entities = [entity("Aster", "character", ["myth"]), entity("Harbor", "location", ["coast"])];
    api.GET.mockImplementation(async (_path: string, options: { params?: { query?: { type?: string; tag?: string } } }) => {
      const { type, tag } = options?.params?.query ?? {};
      const filtered = entities.filter((item) => (!type || item.type === type) && (!tag || item.tags.includes(tag)));
      return { data: filtered, response: { ok: true } };
    });
    api.POST.mockResolvedValue({ data: [], response: { ok: true } });
    const queryClient = renderPanel();
    const user = userEvent.setup();

    await screen.findByText("Aster");
    const filter = screen.getByLabelText("Filter by type");
    const tagFilter = screen.getByLabelText("Filter by tag");
    await user.selectOptions(filter, "character");
    await screen.findByText("Aster");
    await user.selectOptions(tagFilter, "myth");
    await screen.findByText("Aster");

    entities = [entity("Harbor", "location", ["coast"])];
    const callsBeforeRefresh = api.GET.mock.calls.length;
    await act(async () => {
      await queryClient.invalidateQueries({ queryKey: ["knowledge", "entities", "novel"] });
    });

    await waitFor(() => expect((filter as HTMLSelectElement).value).toBe(""));
    await waitFor(() => expect((tagFilter as HTMLSelectElement).value).toBe(""));
    await waitFor(() => expect(api.GET.mock.calls.slice(callsBeforeRefresh).some(([, options]) => {
      const query = (options as { params?: { query?: { type?: string; tag?: string } } })?.params?.query;
      return !query?.type && !query?.tag;
    })).toBe(true));
    expect(await screen.findByText("Harbor")).toBeTruthy();
  });
});
