/**
 * KB Graph API client — typed wrappers for graph visualization endpoints.
 *
 * Field names MUST match backend Pydantic schemas (RULE-17).
 * Components never call fetch directly — always use these functions
 * via TanStack Query hooks from lib/hooks/useKBGraph.ts.
 */

import { fetchApi } from "./client";

// --- Graph Node ---

export interface GraphNode {
  id: string;
  label: string;
  entity_type: string;
  status: string;
  tags: string[] | null;
  metadata: Record<string, unknown> | null;
  /** Computed: number of relationships this entity participates in */
  degree: number;
}

// --- Graph Edge ---

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string | null;
  rel_type: string;
  direction: string;
  weight: number;
}

// --- Graph Statistics ---

export interface GraphStats {
  node_count: number;
  edge_count: number;
  isolated_count: number;
  connected_components: number;
  entity_type_counts: Record<string, number>;
  rel_type_counts: Record<string, number>;
}

// --- Graph Filter ---

export interface GraphFilter {
  entity_types?: string[];
  rel_types?: string[];
  max_nodes?: number;
  max_edges?: number;
}

// --- Graph Response ---

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: GraphStats;
}

// --- Shortest Path Response ---

export interface ShortestPathResponse {
  path: string[] | null;
  length: number | null;
  entity_names: string[] | null;
}

// --- API functions ---

export const kbGraphApi = {
  /** Fetch full graph data for a novel's KB. */
  getGraph: (novelId: string, filter?: GraphFilter) => {
    const searchParams = new URLSearchParams();
    if (filter?.entity_types?.length) {
      searchParams.set("entity_types", filter.entity_types.join(","));
    }
    if (filter?.rel_types?.length) {
      searchParams.set("rel_types", filter.rel_types.join(","));
    }
    if (filter?.max_nodes) {
      searchParams.set("max_nodes", String(filter.max_nodes));
    }
    if (filter?.max_edges) {
      searchParams.set("max_edges", String(filter.max_edges));
    }
    const qs = searchParams.toString();
    return fetchApi<GraphResponse>(`/novels/${novelId}/kb/graph${qs ? `?${qs}` : ""}`);
  },

  /** Find shortest path between two entities. */
  getShortestPath: (novelId: string, sourceId: string, targetId: string) =>
    fetchApi<ShortestPathResponse>(
      `/novels/${novelId}/kb/graph/shortest-path?source_id=${sourceId}&target_id=${targetId}`,
    ),
};
