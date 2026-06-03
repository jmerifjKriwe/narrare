"use client";

import { Maximize, ZoomIn, ZoomOut } from "lucide-react";

interface KnowledgeGraphZoomControlsProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFit: () => void;
}

export function KnowledgeGraphZoomControls({
  onZoomIn,
  onZoomOut,
  onFit,
}: KnowledgeGraphZoomControlsProps) {
  return (
    <div className="absolute bottom-3 right-3 z-10 flex flex-col gap-1">
      <button
        type="button"
        onClick={onZoomIn}
        className="bg-card/90 backdrop-blur-sm border border-border rounded-lg p-2 hover:bg-accent transition-colors"
        aria-label="Zoom in"
      >
        <ZoomIn className="w-4 h-4" />
      </button>
      <button
        type="button"
        onClick={onZoomOut}
        className="bg-card/90 backdrop-blur-sm border border-border rounded-lg p-2 hover:bg-accent transition-colors"
        aria-label="Zoom out"
      >
        <ZoomOut className="w-4 h-4" />
      </button>
      <button
        type="button"
        onClick={onFit}
        className="bg-card/90 backdrop-blur-sm border border-border rounded-lg p-2 hover:bg-accent transition-colors"
        aria-label="Fit to view"
      >
        <Maximize className="w-4 h-4" />
      </button>
    </div>
  );
}
