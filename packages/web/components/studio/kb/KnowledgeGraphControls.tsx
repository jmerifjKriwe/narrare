/**
 * KnowledgeGraphControls — Layout selector, entity type filter, and search.
 *
 * Overlay panel positioned at the top-right of the graph view.
 * Provides controls for layout selection, entity type filtering,
 * and node search.
 */

"use client";

import { Search, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback } from "react";
import { ENTITY_TYPES } from "./constants";
import { ENTITY_TYPE_COLORS } from "./graph-styles";

export type LayoutName = "cose" | "dagre" | "concentric";

interface KnowledgeGraphControlsProps {
  /** Currently selected layout. */
  layout: LayoutName;
  /** Callback when layout changes. */
  onLayoutChange: (layout: LayoutName) => void;
  /** Currently active entity type filters (empty = all shown). */
  entityTypeFilter: Set<string>;
  /** Callback when entity type filter changes. */
  onEntityTypeFilterChange: (filter: Set<string>) => void;
  /** Search query value. */
  searchQuery: string;
  /** Callback when search query changes. */
  onSearchQueryChange: (query: string) => void;
  /** Callback when search is submitted (Enter key). */
  onSearchSubmit: () => void;
  /** Callback to clear search. */
  onSearchClear: () => void;
  /** Whether the graph is loading. */
  isLoading: boolean;
  /** Total node count for stats display. */
  nodeCount: number;
  /** Total edge count for stats display. */
  edgeCount: number;
}

export function KnowledgeGraphControls({
  layout,
  onLayoutChange,
  entityTypeFilter,
  onEntityTypeFilterChange,
  searchQuery,
  onSearchQueryChange,
  onSearchSubmit,
  onSearchClear,
  isLoading,
  nodeCount,
  edgeCount,
}: KnowledgeGraphControlsProps) {
  const t = useTranslations("studio");

  const handleToggleEntityType = useCallback(
    (entityType: string) => {
      const next = new Set(entityTypeFilter);
      if (next.has(entityType)) {
        next.delete(entityType);
      } else {
        next.add(entityType);
      }
      onEntityTypeFilterChange(next);
    },
    [entityTypeFilter, onEntityTypeFilterChange],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        onSearchSubmit();
      }
    },
    [onSearchSubmit],
  );

  return (
    <div className="absolute top-3 right-3 z-10 flex flex-col gap-2 w-64">
      {/* Stats bar */}
      <div className="bg-card/90 backdrop-blur-sm border border-border rounded-lg px-3 py-2 text-xs text-muted-foreground">
        {isLoading ? (
          t("graph.loading")
        ) : (
          <span>
            {nodeCount} {nodeCount === 1 ? "node" : "nodes"} · {edgeCount}{" "}
            {edgeCount === 1 ? "edge" : "edges"}
          </span>
        )}
      </div>

      {/* Search */}
      <div className="bg-card/90 backdrop-blur-sm border border-border rounded-lg px-3 py-2">
        <div className="flex items-center gap-2">
          <Search className="w-4 h-4 text-muted-foreground shrink-0" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchQueryChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("graph.searchPlaceholder")}
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={onSearchClear}
              className="text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Clear search"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Layout selector */}
      <div className="bg-card/90 backdrop-blur-sm border border-border rounded-lg px-3 py-2">
        <span className="text-xs text-muted-foreground uppercase tracking-wider block mb-1.5">
          {t("graph.layout")}
        </span>
        <div className="flex gap-1">
          {(["cose", "dagre", "concentric"] as LayoutName[]).map((name) => (
            <button
              key={name}
              type="button"
              onClick={() => onLayoutChange(name)}
              className={`flex-1 px-2 py-1.5 text-xs rounded-md transition-colors ${
                layout === name
                  ? "bg-primary text-primary-foreground font-medium"
                  : "hover:bg-accent text-foreground"
              }`}
            >
              {t(
                `graph.${name === "cose" ? "forceLayout" : name === "dagre" ? "hierarchicalLayout" : "concentricLayout"}`,
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Entity type filter */}
      <div className="bg-card/90 backdrop-blur-sm border border-border rounded-lg px-3 py-2">
        <span className="text-xs text-muted-foreground uppercase tracking-wider block mb-1.5">
          {t("graph.filter")}
        </span>
        <div className="space-y-1">
          {ENTITY_TYPES.map((entityType) => {
            const isActive = entityTypeFilter.size === 0 || entityTypeFilter.has(entityType);
            const color = ENTITY_TYPE_COLORS[entityType] ?? "hsl(0, 0%, 60%)";
            return (
              <button
                key={entityType}
                type="button"
                onClick={() => handleToggleEntityType(entityType)}
                className={`w-full flex items-center gap-2 px-2 py-1 rounded text-xs transition-colors ${
                  isActive
                    ? "text-foreground hover:bg-accent"
                    : "text-muted-foreground line-through opacity-50"
                }`}
              >
                <span
                  className="w-3 h-3 rounded-full shrink-0"
                  style={{ backgroundColor: color }}
                />
                <span className="capitalize">{entityType}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
