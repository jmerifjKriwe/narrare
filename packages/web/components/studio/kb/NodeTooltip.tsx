"use client";

import type { Core as CytoscapeCore } from "cytoscape";

interface NodeTooltipProps {
  cy: CytoscapeCore;
  nodeId: string;
  onFindPath: () => void;
  pathSourceId: string | null;
}

export function NodeTooltip({ cy, nodeId, onFindPath, pathSourceId }: NodeTooltipProps) {
  const node = cy.getElementById(nodeId);
  if (node.length === 0) return null;

  const label = node.data("label") as string;
  const entityType = node.data("entity_type") as string;
  const degree = node.data("degree") as number;
  const position = node.renderedPosition();

  return (
    <div
      className="z-20 bg-card border border-border rounded-lg px-3 py-2 shadow-lg text-sm max-w-48"
      style={{
        position: "absolute",
        left: `${position.x + 20}px`,
        top: `${position.y - 10}px`,
        pointerEvents: "auto",
      }}
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
          pathSourceId === nodeId
            ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
            : "bg-accent text-foreground hover:bg-accent/80"
        }`}
      >
        {pathSourceId === nodeId ? "Path start ✓" : "Find path from here"}
      </button>
    </div>
  );
}
