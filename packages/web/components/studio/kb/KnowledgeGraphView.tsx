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

import cytoscape from "cytoscape";
// @ts-expect-error — cytoscape-dagre has no type declarations
import dagre from "cytoscape-dagre";
import { useTranslations } from "next-intl";
import { useMemo, useRef } from "react";
import { useKnowledgeGraphController } from "./KnowledgeGraphController";
import { KnowledgeGraphControls } from "./KnowledgeGraphControls";
import { KnowledgeGraphOverlays } from "./KnowledgeGraphOverlays";
import { KnowledgeGraphPathPanel } from "./KnowledgeGraphPathPanel";
import { KnowledgeGraphZoomControls } from "./KnowledgeGraphZoomControls";
import { NodeTooltip } from "./NodeTooltip";

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
  const containerRef = useRef<HTMLDivElement>(null);
  const controller = useKnowledgeGraphController({ novelId, onSelectEntry, containerRef });
  const cy = controller.cyRef.current;
  const graphIsEmpty = useMemo(
    () => !controller.isLoading && controller.graphData?.nodes.length === 0,
    [controller.graphData, controller.isLoading],
  );

  // --- Render ---
  if (controller.error) {
    return (
      <div className="flex-1 flex items-center justify-center text-destructive">
        <p>{controller.error.message || "Failed to load graph data"}</p>
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

      <KnowledgeGraphOverlays isLoading={controller.isLoading} isEmpty={graphIsEmpty} t={t} />

      {/* Controls overlay */}
      <KnowledgeGraphControls
        layout={controller.layout}
        onLayoutChange={controller.handleLayoutChange}
        entityTypeFilter={controller.entityTypeFilter}
        onEntityTypeFilterChange={controller.setEntityTypeFilter}
        searchQuery={controller.searchQuery}
        onSearchQueryChange={controller.setSearchQuery}
        onSearchSubmit={controller.handleSearchSubmit}
        onSearchClear={controller.handleSearchClear}
        isLoading={controller.isLoading}
        nodeCount={controller.filteredData?.stats.node_count ?? 0}
        edgeCount={controller.filteredData?.stats.edge_count ?? 0}
      />

      <KnowledgeGraphZoomControls
        onZoomIn={controller.handleZoomIn}
        onZoomOut={controller.handleZoomOut}
        onFit={controller.handleFit}
      />

      {/* Path result panel */}
      <KnowledgeGraphPathPanel
        pathResult={controller.pathResult}
        isLoading={controller.pathMutation.isPending}
        error={controller.pathMutation.error?.message ?? null}
        onClose={controller.handleClosePathPanel}
      />

      {controller.selectedNodeId && cy && (
        <NodeTooltip
          cy={cy}
          nodeId={controller.selectedNodeId}
          onFindPath={() => controller.setPathSourceId(controller.selectedNodeId)}
          pathSourceId={controller.pathSourceId}
        />
      )}
    </div>
  );
}
