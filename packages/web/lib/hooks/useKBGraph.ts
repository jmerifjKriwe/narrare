"use client";

/**
 * TanStack Query hooks for KB graph visualization.
 *
 * All hooks accept novelId as the primary key parameter.
 * Query keys follow the pattern ["kb-graph", novelId, ...] for cache management.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { GraphFilter, GraphResponse, ShortestPathResponse } from "@/lib/api/kb-graph";
import { kbGraphApi } from "@/lib/api/kb-graph";

// --- Query key factory ---

const kbGraphKeys = {
  all: (novelId: string) => ["kb-graph", novelId] as const,
  graph: (novelId: string, filter?: GraphFilter) =>
    [...kbGraphKeys.all(novelId), "graph", filter] as const,
  path: (novelId: string, sourceId: string, targetId: string) =>
    [...kbGraphKeys.all(novelId), "path", sourceId, targetId] as const,
};

// --- Graph hooks ---

/** Fetch the full knowledge graph for a novel. */
export function useKBGraph(novelId: string, entityTypes?: string[]) {
  const filter: GraphFilter | undefined = entityTypes?.length
    ? { entity_types: entityTypes }
    : undefined;

  return useQuery<GraphResponse>({
    queryKey: kbGraphKeys.graph(novelId, filter),
    queryFn: () => kbGraphApi.getGraph(novelId, filter),
    enabled: !!novelId,
    staleTime: 30_000, // Graph data is relatively stable
  });
}

/** Find the shortest path between two entities. */
export function useKBGraphPath(novelId: string) {
  const queryClient = useQueryClient();

  return useMutation<ShortestPathResponse, Error, { sourceId: string; targetId: string }>({
    mutationFn: ({ sourceId, targetId }) => kbGraphApi.getShortestPath(novelId, sourceId, targetId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: kbGraphKeys.all(novelId) });
    },
  });
}
