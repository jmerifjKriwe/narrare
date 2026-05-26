/**
 * KnowledgeGraphPathPanel — Shortest path result display.
 *
 * Shows the path between two entities when found,
 * or a "no path" message. Positioned at the bottom of the graph view.
 */

"use client";

import { ArrowRight, Route, X } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ShortestPathResponse } from "@/lib/api/kb-graph";

interface KnowledgeGraphPathPanelProps {
  /** The path result to display. */
  pathResult: ShortestPathResponse | null;
  /** Whether the path mutation is loading. */
  isLoading: boolean;
  /** Error message if path finding failed. */
  error: string | null;
  /** Callback to close the panel. */
  onClose: () => void;
}

export function KnowledgeGraphPathPanel({
  pathResult,
  isLoading,
  error,
  onClose,
}: KnowledgeGraphPathPanelProps) {
  const t = useTranslations("studio");

  if (!pathResult && !isLoading && !error) return null;

  return (
    <div className="absolute bottom-3 left-3 right-3 z-10 bg-card/95 backdrop-blur-sm border border-border rounded-lg px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Route className="w-4 h-4 text-amber-500 shrink-0" />
            <span className="text-sm font-medium">{t("graph.findPath")}</span>
          </div>

          {isLoading && (
            <p className="text-xs text-muted-foreground animate-pulse">{t("graph.loading")}</p>
          )}

          {error && <p className="text-xs text-destructive">{error}</p>}

          {pathResult &&
            !isLoading &&
            (pathResult.path ? (
              <div className="flex items-center gap-1 flex-wrap">
                {pathResult.entity_names?.map((name) => (
                  <span key={`name-${name}`} className="flex items-center gap-1">
                    <ArrowRight className="w-3 h-3 text-muted-foreground" />
                    <span className="text-sm font-medium text-foreground">{name}</span>
                  </span>
                ))}
                <span className="text-xs text-muted-foreground ml-2">
                  ({pathResult.length} {pathResult.length === 1 ? "hop" : "hops"})
                </span>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">{t("graph.noPath")}</p>
            ))}
        </div>

        <button
          type="button"
          onClick={onClose}
          className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
          aria-label="Close path panel"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
