import type { Core as CytoscapeCore, EdgeSingular, NodeSingular } from "cytoscape";
import cytoscape from "cytoscape";
import { type RefObject, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ShortestPathResponse } from "@/lib/api/kb-graph";
import { useKBGraph, useKBGraphPath } from "@/lib/hooks/useKBGraph";
import { LAYOUT_CONFIGS } from "./graph-layouts";
import { buildGraphStyles } from "./graph-styles";
import { filterByEntityTypes, graphToElements, searchNodes } from "./graph-utils";
import type { LayoutName } from "./KnowledgeGraphView";

interface ControllerParams {
  novelId: string;
  onSelectEntry: (entryId: string) => void;
  containerRef: RefObject<HTMLDivElement | null>;
}

const CLEAR_CLASSES = "selected highlighted dimmed path-node path-edge";

export function useKnowledgeGraphController({
  novelId,
  onSelectEntry,
  containerRef,
}: ControllerParams) {
  const [layout, setLayout] = useState<LayoutName>("cose");
  const [entityTypeFilter, setEntityTypeFilter] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [, setSelectedEdgeId] = useState<string | null>(null);
  const [pathSourceId, setPathSourceId] = useState<string | null>(null);
  const [pathResult, setPathResult] = useState<ShortestPathResponse | null>(null);
  const cyRef = useRef<CytoscapeCore | null>(null);

  const { data: graphData, isLoading, error } = useKBGraph(novelId);
  const pathMutation = useKBGraphPath(novelId);
  const filteredData = useMemo(
    () => (graphData ? filterByEntityTypes(graphData, entityTypeFilter) : null),
    [graphData, entityTypeFilter],
  );
  const elements = useMemo(
    () => (filteredData ? graphToElements(filteredData) : []),
    [filteredData],
  );
  const stylesheet = useMemo(() => buildGraphStyles(), []);

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
      setSelectedNodeId(node.id());
    });

    cy.on("dblclick", "node", (evt) => onSelectEntry((evt.target as NodeSingular).id()));
    cy.on("tap", "edge", (evt) => {
      const edge = evt.target as EdgeSingular;
      setSelectedEdgeId(edge.id());
      setSelectedNodeId(null);
      cy.elements().removeClass("selected highlighted dimmed");
      edge.addClass("selected");
    });
    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        cy.elements().removeClass(CLEAR_CLASSES);
        setSelectedNodeId(null);
        setSelectedEdgeId(null);
      }
    });

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [containerRef, elements, stylesheet, layout, onSelectEntry]);

  const highlightPath = useCallback((path: string[]) => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass("path-node path-edge");
    for (const nodeId of path) cy.getElementById(nodeId).addClass("path-node");
    for (let index = 0; index < path.length - 1; index++) {
      cy.getElementById(path[index])
        .edgesTo(cy.getElementById(path[index + 1]))
        .addClass("path-edge");
    }
  }, []);

  const handleFindPath = useCallback(
    (sourceId: string, targetId: string) => {
      setPathSourceId(sourceId);
      pathMutation.mutate(
        { sourceId, targetId },
        {
          onSuccess: (data) => {
            setPathResult(data);
            if (data.path) highlightPath(data.path);
          },
        },
      );
    },
    [pathMutation, highlightPath],
  );

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    const handleDblClick = (evt: cytoscape.EventObject) => {
      const nodeId = (evt.target as NodeSingular).id();
      if (pathSourceId === null) setPathSourceId(nodeId);
      else if (pathSourceId !== nodeId) handleFindPath(pathSourceId, nodeId);
    };
    cy.on("dblclick", "node", handleDblClick);
    return () => {
      cy.off("dblclick", "node", handleDblClick);
    };
  }, [pathSourceId, handleFindPath]);

  return {
    layout,
    entityTypeFilter,
    setEntityTypeFilter,
    searchQuery,
    setSearchQuery,
    selectedNodeId,
    pathSourceId,
    setPathSourceId,
    pathResult,
    pathMutation,
    cyRef,
    graphData,
    filteredData,
    isLoading,
    error,
    handleLayoutChange: (newLayout: LayoutName) => {
      setLayout(newLayout);
      cyRef.current?.elements().removeClass(CLEAR_CLASSES);
      cyRef.current?.layout(LAYOUT_CONFIGS[newLayout] as cytoscape.LayoutOptions).run();
    },
    handleSearchSubmit: () => {
      const cy = cyRef.current;
      if (!graphData || !searchQuery.trim() || !cy) return;
      cy.elements().removeClass("search-match");
      const firstMatch = searchNodes(graphData.nodes, searchQuery)[0];
      if (!firstMatch) return;
      const node = cy.getElementById(firstMatch.id);
      if (node.length > 0) {
        node.addClass("search-match");
        cy.animate({ center: { eles: node }, zoom: 2, duration: 400 });
      }
    },
    handleSearchClear: () => {
      setSearchQuery("");
      cyRef.current?.elements().removeClass("search-match");
    },
    handleZoomIn: () => {
      cyRef.current?.zoom((cyRef.current?.zoom() ?? 1) * 1.3);
      cyRef.current?.center();
    },
    handleZoomOut: () => {
      cyRef.current?.zoom((cyRef.current?.zoom() ?? 1) / 1.3);
      cyRef.current?.center();
    },
    handleFit: () => cyRef.current?.fit(undefined, 30),
    handleClosePathPanel: () => {
      setPathResult(null);
      setPathSourceId(null);
      cyRef.current?.elements().removeClass("path-node path-edge");
    },
  };
}
