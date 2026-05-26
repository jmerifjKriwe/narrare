/**
 * Cytoscape stylesheet for the knowledge graph visualization.
 *
 * Node colors by entity type match the TYPE_ICONS color scheme.
 * Edge styles support directed and mutual relationships.
 * Selected/hover states provide visual feedback.
 */

import type { StylesheetStyle } from "cytoscape";

/** Entity type → HSL color mapping. Matches TYPE_ICONS visual identity. */
export const ENTITY_TYPE_COLORS: Record<string, string> = {
  character: "hsl(220, 70%, 55%)", // blue
  concept: "hsl(30, 80%, 55%)", // orange
  faction: "hsl(280, 60%, 55%)", // purple
  location: "hsl(142, 50%, 45%)", // green
  object: "hsl(190, 60%, 50%)", // teal
  setting: "hsl(45, 70%, 55%)", // amber
  system: "hsl(0, 60%, 55%)", // red
  timeline: "hsl(260, 50%, 55%)", // indigo
};

/** Default color for unknown entity types. */
const DEFAULT_NODE_COLOR = "hsl(0, 0%, 60%)";

/** Build the Cytoscape stylesheet. */
export function buildGraphStyles(): StylesheetStyle[] {
  return [
    // --- Node defaults ---
    {
      selector: "node",
      style: {
        "background-color": DEFAULT_NODE_COLOR,
        label: "data(label)",
        "text-wrap": "ellipsis",
        "text-max-width": "80px",
        "font-size": "11px",
        color: "#fff",
        "text-outline-color": "#000",
        "text-outline-width": 2,
        "text-valign": "bottom",
        "text-margin-y": -4,
        width: 30,
        height: 30,
        "border-width": 2,
        "border-color": "#fff",
        "border-opacity": 0.8,
      } as Record<string, unknown>,
    },

    // --- Node colors by entity type ---
    ...Object.entries(ENTITY_TYPE_COLORS).map(
      ([entityType, color]): StylesheetStyle => ({
        selector: `node[entity_type = "${entityType}"]`,
        style: {
          "background-color": color,
        } as Record<string, unknown>,
      }),
    ),

    // --- Node size by degree ---
    {
      selector: "node",
      style: {
        // Degree-based sizing: base 24 + degree * 2, capped at 50
        width: "data(degreeSize)",
        height: "data(degreeSize)",
      } as Record<string, unknown>,
    },

    // --- Isolated nodes (degree 0) ---
    {
      selector: "node[degree = 0]",
      style: {
        opacity: 0.4,
        "border-style": "dashed",
      } as Record<string, unknown>,
    },

    // --- Selected node ---
    {
      selector: "node.selected",
      style: {
        "border-width": 4,
        "border-color": "#3b82f6",
        "border-opacity": 1,
        "font-size": "13px",
        "font-weight": "bold",
        width: "data(degreeSizeSelected)",
        height: "data(degreeSizeSelected)",
      } as Record<string, unknown>,
    },

    // --- Highlighted node (connected to selected) ---
    {
      selector: "node.highlighted",
      style: {
        opacity: 1,
        "border-width": 3,
        "border-color": "#93c5fd",
      } as Record<string, unknown>,
    },

    // --- Dimmed node (not connected to selected) ---
    {
      selector: "node.dimmed",
      style: {
        opacity: 0.2,
      } as Record<string, unknown>,
    },

    // --- Search match node ---
    {
      selector: "node.search-match",
      style: {
        "border-width": 4,
        "border-color": "#f59e0b",
        "border-opacity": 1,
      } as Record<string, unknown>,
    },

    // --- Path node ---
    {
      selector: "node.path-node",
      style: {
        "border-width": 4,
        "border-color": "#f59e0b",
        "border-opacity": 1,
        "background-color": "#f59e0b",
      } as Record<string, unknown>,
    },

    // --- Edge defaults ---
    {
      selector: "edge",
      style: {
        width: 2,
        "line-color": "#94a3b8",
        "target-arrow-color": "#94a3b8",
        "target-arrow-shape": "triangle",
        "curve-style": "bezier",
        label: "data(label)",
        "font-size": "9px",
        "text-rotation": "autorotate",
        "text-outline-color": "#fff",
        "text-outline-width": 2,
        "text-opacity": 0.7,
        opacity: 0.6,
      } as Record<string, unknown>,
    },

    // --- Mutual (undirected) edges: no arrow ---
    {
      selector: 'edge[direction = "mutual"]',
      style: {
        "target-arrow-shape": "none",
      } as Record<string, unknown>,
    },

    // --- Selected edge ---
    {
      selector: "edge.selected",
      style: {
        width: 4,
        "line-color": "#3b82f6",
        "target-arrow-color": "#3b82f6",
        "text-opacity": 1,
        opacity: 1,
      } as Record<string, unknown>,
    },

    // --- Highlighted edge (connected to selected node) ---
    {
      selector: "edge.highlighted",
      style: {
        width: 3,
        "line-color": "#60a5fa",
        "target-arrow-color": "#60a5fa",
        "text-opacity": 1,
        opacity: 1,
      } as Record<string, unknown>,
    },

    // --- Dimmed edge ---
    {
      selector: "edge.dimmed",
      style: {
        opacity: 0.1,
      } as Record<string, unknown>,
    },

    // --- Path edge ---
    {
      selector: "edge.path-edge",
      style: {
        width: 4,
        "line-color": "#f59e0b",
        "target-arrow-color": "#f59e0b",
        "line-style": "dashed",
        opacity: 1,
      } as Record<string, unknown>,
    },
  ];
}
