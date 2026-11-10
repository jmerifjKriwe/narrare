// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRoute, createRouter, RouterProvider } from "@tanstack/react-router";
import type { UseQueryResult } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Entity, Relation } from "@shell/lib/api/client";
import { useEntitiesQuery, useNovelRelationsQuery } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";
import { GraphPage } from "./GraphPage";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

// The hooks, not the client: the pin is that both refetches go out even
// when one rejects, and a client mock cannot reject a refetch — TanStack
// settles a failed queryFn into the error state instead of throwing.
vi.mock("@shell/lib/query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@shell/lib/query")>();
  return { ...actual, useEntitiesQuery: vi.fn(), useNovelRelationsQuery: vi.fn() };
});

const entitiesHook = vi.mocked(useEntitiesQuery);
const relationsHook = vi.mocked(useNovelRelationsQuery);

function failedQuery<T>(refetch: () => Promise<unknown>): UseQueryResult<T> {
  return {
    isPending: false,
    isError: true,
    data: undefined,
    refetch,
  } as unknown as UseQueryResult<T>;
}

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
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  entitiesHook.mockReset();
  relationsHook.mockReset();
});

describe("GraphPage retry", () => {
  it("re-asks both reads even when the entities refetch rejects", async () => {
    const entitiesRefetch = vi.fn().mockRejectedValue(new Error("entities down"));
    const relationsRefetch = vi.fn().mockResolvedValue(undefined);
    entitiesHook.mockReturnValue(failedQuery<Entity[]>(entitiesRefetch));
    relationsHook.mockReturnValue(failedQuery<Relation[]>(relationsRefetch));
    renderGraph("?novel=novel-1");
    const user = userEvent.setup();
    // Sequential await would let the rejecting entities refetch swallow
    // the relations retry; allSettled sends both.
    await user.click(await screen.findByRole("button", { name: "Try again" }));
    await waitFor(() => {
      expect(entitiesRefetch).toHaveBeenCalledTimes(1);
      expect(relationsRefetch).toHaveBeenCalledTimes(1);
    });
  });
});
