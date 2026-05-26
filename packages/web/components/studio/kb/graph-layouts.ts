/**
 * Cytoscape layout configurations for the knowledge graph.
 *
 * Each layout config is a plain object passed to cy.layout().
 * Layouts are selected by the user via the controls panel.
 */

import type { ConcentricLayoutOptions, CoseLayoutOptions } from "cytoscape";

/** Force-directed layout — organic, shows clusters. Default. */
export const coseLayout: CoseLayoutOptions = {
  name: "cose",
  // Recommended defaults for 50-500 nodes
  animate: true,
  animationDuration: 800,
  animationEasing: "ease-out" as const,
  // Iteration settings
  numIter: 2000,
  // Node repulsion (higher = more spread)
  nodeRepulsion: () => 8000,
  idealEdgeLength: () => 80,
  edgeElasticity: () => 0.45,
  nestingFactor: 1.2,
  gravity: 0.25,
  // Cooling
  initialTemp: 200,
  coolingFactor: 0.95,
  minTemp: 1.0,
  // Randomize initial positions
  randomize: true,
  fit: true,
  padding: 30,
};

/** Hierarchical (DAG) layout — top-down by entity type. Requires cytoscape-dagre. */
export const dagreLayout = {
  name: "dagre" as const,
  // Direction of the layout
  rankDir: "TB",
  // Spacing
  nodeSep: 50,
  rankSep: 80,
  // Other
  animate: true,
  animationDuration: 600,
  animationEasing: "ease-out" as const,
  fit: true,
  padding: 30,
  randomize: false,
};

/** Concentric layout — hubs in center, spokes outward. */
export const concentricLayout: ConcentricLayoutOptions = {
  name: "concentric",
  // Concentric circles
  concentric: (node) => node.data("degree") ?? 1,
  // Spacing
  spacingFactor: 1.2,
  // Other
  animate: true,
  animationDuration: 600,
  animationEasing: "ease-out" as const,
  fit: true,
  padding: 30,
  startAngle: (Math.PI * 0) / 180,
  clockwise: true,
};

/** Layout name → config mapping. */
export const LAYOUT_CONFIGS: Record<string, object> = {
  cose: coseLayout,
  dagre: dagreLayout,
  concentric: concentricLayout,
};

/** Layout display names (i18n keys). */
export const LAYOUT_LABEL_KEYS: Record<string, string> = {
  cose: "graph.forceLayout",
  dagre: "graph.hierarchicalLayout",
  concentric: "graph.concentricLayout",
};
