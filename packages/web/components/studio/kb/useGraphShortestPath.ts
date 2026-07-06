/**
 * Shortest-path interaction extracted from KnowledgeGraphController
 * (RULE-04 / AUFG-03-04).
 *
 * Implements the "double-click two nodes to find the shortest path"
 * interaction: the first dblclick sets the source, the second dblclick
 * resolves the path via pathMutation and highlights it on the graph.
 */

import type { Core as CytoscapeCore } from "cytoscape";
import { type MutableRefObject, useCallback, useEffect, useState } from "react";
import type { ShortestPathResponse } from "@/lib/api/kb-graph";
import { useKBGraphPath } from "@/lib/hooks/useKBGraph";
import { CLEAR_CLASSES } from "./useGraphCytoscape";

interface UseGraphShortestPathParams {
  novelId: string;
  cyRef: MutableRefObject<CytoscapeCore | null>;
}

export function useGraphShortestPath({ novelId, cyRef }: UseGraphShortestPathParams) {
  const [pathSourceId, setPathSourceId] = useState<string | null>(null);
  const [pathResult, setPathResult] = useState<ShortestPathResponse | null>(null);
  const pathMutation = useKBGraphPath(novelId);

  const highlightPath = useCallback(
    (path: string[]) => {
      const cy = cyRef.current;
      if (!cy) return;
      cy.elements().removeClass("path-node path-edge");
      for (const nodeId of path) cy.getElementById(nodeId).addClass("path-node");
      for (let index = 0; index < path.length - 1; index++) {
        cy.getElementById(path[index])
          .edgesTo(cy.getElementById(path[index + 1]))
          .addClass("path-edge");
      }
    },
    [cyRef],
  );

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
      const nodeId = (evt.target as { id: () => string }).id();
      if (pathSourceId === null) setPathSourceId(nodeId);
      else if (pathSourceId !== nodeId) handleFindPath(pathSourceId, nodeId);
    };
    cy.on("dblclick", "node", handleDblClick);
    return () => {
      cy.off("dblclick", "node", handleDblClick);
    };
  }, [cyRef, pathSourceId, handleFindPath]);

  const handleClosePathPanel = useCallback(() => {
    setPathResult(null);
    setPathSourceId(null);
    cyRef.current?.elements().removeClass("path-node path-edge");
  }, [cyRef]);

  return {
    pathSourceId,
    setPathSourceId,
    pathResult,
    pathMutation,
    handleClosePathPanel,
  };
}

export { CLEAR_CLASSES };
