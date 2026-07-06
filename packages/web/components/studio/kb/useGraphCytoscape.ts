/**
 * Cytoscape graph instance lifecycle extracted from KnowledgeGraphController
 * (RULE-04 / AUFG-03-04).
 *
 * Owns: graph instance creation, element/style/layout wiring, and the
 * core interactivity events (node tap to highlight neighborhood, edge
 * tap to select, background tap to clear). The dblclick → onSelectEntry
 * handler is registered here too.
 *
 * Does NOT own: shortest-path highlighting (lives in the controller,
 * which wires pathMutation + highlightPath), search, or zoom controls.
 */

import type { Core as CytoscapeCore, EdgeSingular, NodeSingular } from "cytoscape";
import cytoscape from "cytoscape";
import { type RefObject, useEffect, useRef } from "react";
import { LAYOUT_CONFIGS } from "./graph-layouts";
import { buildGraphStyles } from "./graph-styles";
import type { graphToElements } from "./graph-utils";
import type { LayoutName } from "./KnowledgeGraphView";

const CLEAR_CLASSES = "selected highlighted dimmed path-node path-edge";

interface UseGraphCytoscapeParams {
  containerRef: RefObject<HTMLDivElement | null>;
  elements: ReturnType<typeof graphToElements>;
  layout: LayoutName;
  onSelectEntry: (entryId: string) => void;
  onNodeSelect: (nodeId: string) => void;
  onEdgeSelect: (edgeId: string) => void;
  onBackgroundClick: () => void;
}

export function useGraphCytoscape({
  containerRef,
  elements,
  layout,
  onSelectEntry,
  onNodeSelect,
  onEdgeSelect,
  onBackgroundClick,
}: UseGraphCytoscapeParams) {
  const cyRef = useRef<CytoscapeCore | null>(null);
  const stylesheet = buildGraphStyles();

  useEffect(() => {
    if (!containerRef.current || elements.length === 0) return;
    cyRef.current?.destroy();

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: stylesheet,
      layout: LAYOUT_CONFIGS[layout] as cytoscape.LayoutOptions,
      minZoom: 0.3,
      maxZoom: 3,
      wheelSensitivity: 0.3,
    });
    cyRef.current = cy;

    cy.on("tap", "node", (evt) => {
      const node = evt.target as NodeSingular;
      const connectedEdges = node.connectedEdges();
      const connectedNodes = node.neighborhood().nodes();
      cy.elements().removeClass(CLEAR_CLASSES);
      node.addClass("selected");
      connectedEdges.addClass("highlighted");
      connectedNodes.addClass("highlighted");
      cy.elements().not(node).not(connectedNodes).not(connectedEdges).addClass("dimmed");
      onNodeSelect(node.id());
    });

    cy.on("dblclick", "node", (evt) => onSelectEntry((evt.target as NodeSingular).id()));
    cy.on("tap", "edge", (evt) => {
      const edge = evt.target as EdgeSingular;
      onEdgeSelect(edge.id());
      onNodeSelect("");
      cy.elements().removeClass("selected highlighted dimmed");
      edge.addClass("selected");
    });
    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        cy.elements().removeClass(CLEAR_CLASSES);
        onBackgroundClick();
      }
    });

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [
    containerRef,
    elements,
    stylesheet,
    layout,
    onSelectEntry,
    onNodeSelect,
    onEdgeSelect,
    onBackgroundClick,
  ]);

  return { cyRef, stylesheet };
}

export { CLEAR_CLASSES };
