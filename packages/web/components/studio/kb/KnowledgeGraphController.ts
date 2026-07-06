import { type RefObject, useCallback, useMemo, useState } from "react";
import { useKBGraph } from "@/lib/hooks/useKBGraph";
import { LAYOUT_CONFIGS } from "./graph-layouts";
import { filterByEntityTypes, graphToElements, searchNodes } from "./graph-utils";
import type { LayoutName } from "./KnowledgeGraphView";
import { CLEAR_CLASSES, useGraphCytoscape } from "./useGraphCytoscape";
import { useGraphShortestPath } from "./useGraphShortestPath";

interface ControllerParams {
  novelId: string;
  onSelectEntry: (entryId: string) => void;
  containerRef: RefObject<HTMLDivElement | null>;
}

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

  const { data: graphData, isLoading, error } = useKBGraph(novelId);
  const filteredData = useMemo(
    () => (graphData ? filterByEntityTypes(graphData, entityTypeFilter) : null),
    [graphData, entityTypeFilter],
  );
  const elements = useMemo(
    () => (filteredData ? graphToElements(filteredData) : []),
    [filteredData],
  );

  const { cyRef } = useGraphCytoscape({
    containerRef,
    elements,
    layout,
    onSelectEntry,
    onNodeSelect: (id) => setSelectedNodeId(id || null),
    onEdgeSelect: (id) => setSelectedEdgeId(id),
    onBackgroundClick: () => {
      setSelectedNodeId(null);
      setSelectedEdgeId(null);
    },
  });

  const { pathSourceId, setPathSourceId, pathResult, pathMutation, handleClosePathPanel } =
    useGraphShortestPath({ novelId, cyRef });

  const handleLayoutChange = useCallback(
    (newLayout: LayoutName) => {
      setLayout(newLayout);
      cyRef.current?.elements().removeClass(CLEAR_CLASSES);
      cyRef.current?.layout(LAYOUT_CONFIGS[newLayout] as cytoscape.LayoutOptions).run();
    },
    [cyRef],
  );

  const handleSearchSubmit = useCallback(() => {
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
  }, [cyRef, graphData, searchQuery]);

  const handleSearchClear = useCallback(() => {
    setSearchQuery("");
    cyRef.current?.elements().removeClass("search-match");
  }, [cyRef]);

  const handleZoomIn = useCallback(() => {
    cyRef.current?.zoom((cyRef.current?.zoom() ?? 1) * 1.3);
    cyRef.current?.center();
  }, [cyRef]);
  const handleZoomOut = useCallback(() => {
    cyRef.current?.zoom((cyRef.current?.zoom() ?? 1) / 1.3);
    cyRef.current?.center();
  }, [cyRef]);

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
    handleLayoutChange,
    handleSearchSubmit,
    handleSearchClear,
    handleZoomIn,
    handleZoomOut,
    handleFit: () => cyRef.current?.fit(undefined, 30),
    handleClosePathPanel,
  };
}
