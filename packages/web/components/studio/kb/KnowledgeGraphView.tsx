/**
 * KnowledgeGraphView — Main graph visualization component.
 *
 * Uses Cytoscape.js directly (not react-cytoscapejs) for better
 * performance with 500+ elements. The Cytoscape instance is managed
 * via useRef + useEffect, following the same pattern as TipTap.
 *
 * Features:
 * - Force-directed, hierarchical, and concentric layouts
 * - Node click → highlight connected edges, show tooltip
 * - Double-click node → open KB entry detail
 * - Edge click → show relationship info
 * - Drag node → reposition (ephemeral, not persisted)
 * - Layout selector, entity type filter, search, zoom controls
 * - Shortest path visualization
 */

"use client";

import cytoscape, {
  type Core as CytoscapeCore,
  type EdgeSingular,
  type NodeSingular,
} from "cytoscape";
// @ts-expect-error — cytoscape-dagre has no type declarations
import dagre from "cytoscape-dagre";
import { Maximize, ZoomIn, ZoomOut } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useKBGraph, useKBGraphPath } from "@/lib/hooks/useKBGraph";
import { LAYOUT_CONFIGS } from "./graph-layouts";
import { buildGraphStyles } from "./graph-styles";
import { filterByEntityTypes, graphToElements, searchNodes } from "./graph-utils";
import { KnowledgeGraphControls } from "./KnowledgeGraphControls";
import { KnowledgeGraphPathPanel } from "./KnowledgeGraphPathPanel";

/** Layout name type matching available layouts. */
export type LayoutName = "cose" | "dagre" | "concentric";

// Register the dagre extension
cytoscape.use(dagre);

interface KnowledgeGraphViewProps {
  novelId: string;
  onSelectEntry: (entryId: string) => void;
}

export function KnowledgeGraphView({ novelId, onSelectEntry }: KnowledgeGraphViewProps) {
  const t = useTranslations("studio");

  // --- State ---
  const [layout, setLayout] = useState<LayoutName>("cose");
  const [entityTypeFilter, setEntityTypeFilter] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [, setSelectedEdgeId] = useState<string | null>(null);
  const [pathSourceId, setPathSourceId] = useState<string | null>(null);
  const [pathResult, setPathResult] = useState<{
    path: string[] | null;
    length: number | null;
    entity_names: string[] | null;
  } | null>(null);

  // --- Refs ---
  const cyRef = useRef<CytoscapeCore | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // --- Data ---
  const { data: graphData, isLoading, error } = useKBGraph(novelId);
  const pathMutation = useKBGraphPath(novelId);

  // --- Filtered data ---
  const filteredData = useMemo(() => {
    if (!graphData) return null;
    return filterByEntityTypes(graphData, entityTypeFilter);
  }, [graphData, entityTypeFilter]);

  // --- Cytoscape elements ---
  const elements = useMemo(() => {
    if (!filteredData) return [];
    return graphToElements(filteredData);
  }, [filteredData]);

  // --- Entity types for filter ---
  // Entity types available in the graph data (used by controls via filteredData)

  // --- Stylesheet ---
  const stylesheet = useMemo(() => buildGraphStyles(), []);

  // --- Initialize Cytoscape ---
  useEffect(() => {
    if (!containerRef.current || elements.length === 0) return;

    // Destroy previous instance
    if (cyRef.current) {
      cyRef.current.destroy();
      cyRef.current = null;
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: stylesheet,
      layout: LAYOUT_CONFIGS[layout] as cytoscape.LayoutOptions,
      // Interaction defaults
      minZoom: 0.3,
      maxZoom: 3,
      wheelSensitivity: 0.3,
    });

    cyRef.current = cy;

    // --- Node click: highlight connected edges ---
    cy.on("tap", "node", (evt) => {
      const node = evt.target as NodeSingular;
      const nodeId = node.id();

      // Clear previous highlights
      cy.elements().removeClass("selected highlighted dimmed path-node path-edge");

      // Highlight selected node
      node.addClass("selected");
      setSelectedNodeId(nodeId);

      // Highlight connected edges and their other nodes
      const connectedEdges = node.connectedEdges();
      connectedEdges.addClass("highlighted");
      const connectedNodes = node.neighborhood().nodes();
      connectedNodes.addClass("highlighted");

      // Dim everything else
      cy.elements().not(node).not(connectedNodes).not(connectedEdges).addClass("dimmed");
    });

    // --- Node double-click: open KB entry ---
    cy.on("dblclick", "node", (evt) => {
      const node = evt.target as NodeSingular;
      onSelectEntry(node.id());
    });

    // --- Edge click: show relationship info ---
    cy.on("tap", "edge", (evt) => {
      const edge = evt.target as EdgeSingular;
      setSelectedEdgeId(edge.id());
      setSelectedNodeId(null);

      // Clear node highlights
      cy.elements().removeClass("selected highlighted dimmed");
      edge.addClass("selected");
    });

    // --- Background click: clear selection ---
    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        cy.elements().removeClass("selected highlighted dimmed path-node path-edge");
        setSelectedNodeId(null);
        setSelectedEdgeId(null);
      }
    });

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [elements, stylesheet, layout, onSelectEntry]);

  // --- Run layout when layout changes ---
  const handleLayoutChange = useCallback((newLayout: LayoutName) => {
    setLayout(newLayout);
    if (cyRef.current) {
      cyRef.current.elements().removeClass("selected highlighted dimmed path-node path-edge");
      const layoutInstance = cyRef.current.layout(
        LAYOUT_CONFIGS[newLayout] as cytoscape.LayoutOptions,
      );
      layoutInstance.run();
    }
  }, []);

  // --- Search: highlight matching node and zoom ---
  const handleSearchSubmit = useCallback(() => {
    if (!graphData || !searchQuery.trim() || !cyRef.current) return;

    const cy = cyRef.current;
    cy.elements().removeClass("search-match");

    const matches = searchNodes(graphData.nodes, searchQuery);
    if (matches.length === 0) return;

    // Highlight first match and zoom to it
    const firstMatch = matches[0];
    const node = cy.getElementById(firstMatch.id);
    if (node.length > 0) {
      node.addClass("search-match");
      cy.animate({
        center: { eles: node },
        zoom: 2,
        duration: 400,
      });
    }
  }, [graphData, searchQuery]);

  const handleSearchClear = useCallback(() => {
    setSearchQuery("");
    if (cyRef.current) {
      cyRef.current.elements().removeClass("search-match");
    }
  }, []);

  // --- Path finding ---
  const handleFindPath = useCallback(
    (sourceId: string, targetId: string) => {
      setPathSourceId(sourceId);
      pathMutation.mutate(
        { sourceId, targetId },
        {
          onSuccess: (data) => {
            setPathResult(data);
            // Highlight path in graph
            if (cyRef.current && data.path) {
              const cy = cyRef.current;
              cy.elements().removeClass("path-node path-edge");

              // Highlight path nodes
              for (const nodeId of data.path) {
                const node = cy.getElementById(nodeId);
                node.addClass("path-node");
              }

              // Highlight path edges between consecutive nodes
              for (let i = 0; i < data.path.length - 1; i++) {
                const sourceNode = cy.getElementById(data.path[i]);
                const edges = sourceNode.edgesTo(cy.getElementById(data.path[i + 1]));
                edges.addClass("path-edge");
              }
            }
          },
        },
      );
    },
    [pathMutation],
  );

  // --- Zoom controls ---
  const handleZoomIn = useCallback(() => {
    cyRef.current?.zoom((cyRef.current?.zoom() ?? 1) * 1.3);
    cyRef.current?.center();
  }, []);

  const handleZoomOut = useCallback(() => {
    cyRef.current?.zoom((cyRef.current?.zoom() ?? 1) / 1.3);
    cyRef.current?.center();
  }, []);

  const handleFit = useCallback(() => {
    cyRef.current?.fit(undefined, 30);
  }, []);

  // --- Double-click handler for path finding ---
  // When a node is double-clicked while shift is held, set it as path source/target
  useEffect(() => {
    if (!cyRef.current) return;
    const cy = cyRef.current;

    const handleDblClick = (evt: cytoscape.EventObject) => {
      const node = evt.target as NodeSingular;
      const nodeId = node.id();

      if (pathSourceId === null) {
        setPathSourceId(nodeId);
      } else if (pathSourceId !== nodeId) {
        handleFindPath(pathSourceId, nodeId);
      }
    };

    cy.on("dblclick", "node", handleDblClick);
    return () => {
      cy.off("dblclick", "node", handleDblClick);
    };
  }, [pathSourceId, handleFindPath]);

  // --- Close path panel ---
  const handleClosePathPanel = useCallback(() => {
    setPathResult(null);
    setPathSourceId(null);
    if (cyRef.current) {
      cyRef.current.elements().removeClass("path-node path-edge");
    }
  }, []);

  // --- Render ---
  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center text-destructive">
        <p>{error.message || "Failed to load graph data"}</p>
      </div>
    );
  }

  return (
    <div className="flex-1 relative h-full">
      {/* Cytoscape container */}
      <div
        ref={containerRef}
        className="w-full h-full bg-background"
        style={{ minHeight: "400px" }}
      />

      {/* Loading overlay */}
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-20">
          <div className="flex flex-col items-center gap-2">
            <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-muted-foreground">{t("graph.loading")}</p>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && graphData && graphData.nodes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center z-20">
          <p className="text-muted-foreground">{t("graph.noEntities")}</p>
        </div>
      )}

      {/* Controls overlay */}
      <KnowledgeGraphControls
        layout={layout}
        onLayoutChange={handleLayoutChange}
        entityTypeFilter={entityTypeFilter}
        onEntityTypeFilterChange={setEntityTypeFilter}
        searchQuery={searchQuery}
        onSearchQueryChange={setSearchQuery}
        onSearchSubmit={handleSearchSubmit}
        onSearchClear={handleSearchClear}
        isLoading={isLoading}
        nodeCount={filteredData?.stats.node_count ?? 0}
        edgeCount={filteredData?.stats.edge_count ?? 0}
      />

      {/* Zoom controls */}
      <div className="absolute bottom-3 right-3 z-10 flex flex-col gap-1">
        <button
          type="button"
          onClick={handleZoomIn}
          className="bg-card/90 backdrop-blur-sm border border-border rounded-lg p-2 hover:bg-accent transition-colors"
          aria-label="Zoom in"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={handleZoomOut}
          className="bg-card/90 backdrop-blur-sm border border-border rounded-lg p-2 hover:bg-accent transition-colors"
          aria-label="Zoom out"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={handleFit}
          className="bg-card/90 backdrop-blur-sm border border-border rounded-lg p-2 hover:bg-accent transition-colors"
          aria-label="Fit to view"
        >
          <Maximize className="w-4 h-4" />
        </button>
      </div>

      {/* Path result panel */}
      <KnowledgeGraphPathPanel
        pathResult={pathResult}
        isLoading={pathMutation.isPending}
        error={pathMutation.error?.message ?? null}
        onClose={handleClosePathPanel}
      />

      {/* Selected node info tooltip */}
      {selectedNodeId && cyRef.current && (
        <NodeTooltip
          cy={cyRef.current}
          nodeId={selectedNodeId}
          onFindPath={() => setPathSourceId(selectedNodeId)}
          pathSourceId={pathSourceId}
        />
      )}
    </div>
  );
}

// --- Node Tooltip ---

interface NodeTooltipProps {
  cy: CytoscapeCore;
  nodeId: string;
  onFindPath: () => void;
  pathSourceId: string | null;
}

function NodeTooltip({ cy, nodeId, onFindPath, pathSourceId }: NodeTooltipProps) {
  const node = cy.getElementById(nodeId);
  if (node.length === 0) return null;

  const label = node.data("label") as string;
  const entityType = node.data("entity_type") as string;
  const degree = node.data("degree") as number;
  const isPathSource = pathSourceId === nodeId;

  // Get rendered position for tooltip placement
  const pos = node.renderedPosition();
  const tooltipStyle: React.CSSProperties = {
    position: "absolute",
    left: `${pos.x + 20}px`,
    top: `${pos.y - 10}px`,
    pointerEvents: "auto",
  };

  return (
    <div
      className="z-20 bg-card border border-border rounded-lg px-3 py-2 shadow-lg text-sm max-w-48"
      style={tooltipStyle}
    >
      <p className="font-medium text-foreground">{label}</p>
      <p className="text-xs text-muted-foreground capitalize">{entityType}</p>
      <p className="text-xs text-muted-foreground">
        {degree} {degree === 1 ? "connection" : "connections"}
      </p>
      <button
        type="button"
        onClick={onFindPath}
        className={`mt-1.5 text-xs px-2 py-0.5 rounded transition-colors ${
          isPathSource
            ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
            : "bg-accent text-foreground hover:bg-accent/80"
        }`}
      >
        {isPathSource ? "Path start ✓" : "Find path from here"}
      </button>
    </div>
  );
}
