/**
 * Graph utility functions for the knowledge graph visualization.
 *
 * Pure functions for transforming API data into Cytoscape elements,
 * computing node sizes, and client-side search/filter.
 */

import type { ElementDefinition } from "cytoscape";
import type { GraphEdge, GraphNode, GraphResponse } from "@/lib/api/kb-graph";

/** Compute node size based on degree (relationship count). */
export function computeNodeSize(degree: number): number {
  // Base 24px + 2px per degree, capped at 50px
  return Math.min(24 + degree * 2, 50);
}

/** Compute selected node size (slightly larger for emphasis). */
export function computeSelectedNodeSize(degree: number): number {
  return Math.min(computeNodeSize(degree) + 8, 58);
}

/** Convert GraphResponse to Cytoscape element definitions. */
export function graphToElements(data: GraphResponse): ElementDefinition[] {
  const nodes: ElementDefinition[] = data.nodes.map((node: GraphNode) => ({
    group: "nodes" as const,
    data: {
      id: node.id,
      label: node.label,
      entity_type: node.entity_type,
      status: node.status,
      tags: node.tags,
      degree: node.degree,
      degreeSize: computeNodeSize(node.degree),
      degreeSizeSelected: computeSelectedNodeSize(node.degree),
    },
  }));

  const edges: ElementDefinition[] = data.edges.map((edge: GraphEdge) => ({
    group: "edges" as const,
    data: {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.label ?? edge.rel_type,
      rel_type: edge.rel_type,
      direction: edge.direction,
      weight: edge.weight,
    },
  }));

  return [...nodes, ...edges];
}

/** Filter graph data by entity types. Returns a new GraphResponse. */
export function filterByEntityTypes(data: GraphResponse, entityTypes: Set<string>): GraphResponse {
  if (entityTypes.size === 0) return data;

  const filteredNodes = data.nodes.filter((n) => entityTypes.has(n.entity_type));
  const nodeIds = new Set(filteredNodes.map((n) => n.id));

  // Keep edges where both source and target are in the filtered node set
  const filteredEdges = data.edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));

  // Recompute stats for filtered data
  const entity_type_counts: Record<string, number> = {};
  for (const n of filteredNodes) {
    entity_type_counts[n.entity_type] = (entity_type_counts[n.entity_type] ?? 0) + 1;
  }

  const rel_type_counts: Record<string, number> = {};
  for (const e of filteredEdges) {
    rel_type_counts[e.rel_type] = (rel_type_counts[e.rel_type] ?? 0) + 1;
  }

  const nodeIdsWithEdges = new Set<string>();
  for (const e of filteredEdges) {
    nodeIdsWithEdges.add(e.source);
    nodeIdsWithEdges.add(e.target);
  }

  return {
    nodes: filteredNodes,
    edges: filteredEdges,
    stats: {
      node_count: filteredNodes.length,
      edge_count: filteredEdges.length,
      isolated_count: filteredNodes.filter((n) => !nodeIdsWithEdges.has(n.id)).length,
      connected_components: 0, // Expensive to recompute; skip
      entity_type_counts,
      rel_type_counts,
    },
  };
}

/** Search nodes by label (case-insensitive substring match). */
export function searchNodes(nodes: GraphNode[], query: string): GraphNode[] {
  if (!query.trim()) return [];
  const lower = query.toLowerCase();
  return nodes.filter((n) => n.label.toLowerCase().includes(lower));
}

/** Get unique entity types from graph data. */
export function getEntityTypes(data: GraphResponse): string[] {
  const types = new Set(data.nodes.map((n) => n.entity_type));
  return Array.from(types).sort();
}

/** Get unique relationship types from graph data. */
export function getRelTypes(data: GraphResponse): string[] {
  const types = new Set(data.edges.map((e) => e.rel_type));
  return Array.from(types).sort();
}
