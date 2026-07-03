"use client";

/**
 * WorldBuilding — shared 3-column layout wrapper.
 *
 * Column 1: KBCategorySidebar
 * Column 2: KBEntryList
 * Column 3: children (detail panel, analysis, consistency, etc.)
 */

import type { ReactNode } from "react";

import type { KBEntityType, KBEntry } from "@/lib/api/kb";

import { KBCategorySidebar } from "../kb/KBCategorySidebar";
import { KBEntryList } from "../kb/KBEntryList";

interface WorldBuildingLayoutProps {
  novelId: string;
  activeType: KBEntityType | null;
  entries: KBEntry[];
  entriesLoading: boolean;
  selectedEntryId: string | null;
  onSelectEntry: (entryId: string) => void;
  onCreateNew: () => void;
  onCreateAssisted: () => void;
  onTypeChange: (type: KBEntityType | null) => void;
  onAnalyze: () => void;
  onConsistencyCheck: () => void;
  onShowGraph: () => void;
  onShowWiki: () => void;
  showGraph: boolean;
  showWiki: boolean;
  searchQuery?: string;
  onSearchQueryChange?: (query: string) => void;
  children?: ReactNode;
}

export function WorldBuildingLayout({
  novelId,
  activeType,
  entries,
  entriesLoading,
  selectedEntryId,
  onSelectEntry,
  onCreateNew,
  onCreateAssisted,
  onTypeChange,
  onAnalyze,
  onConsistencyCheck,
  onShowGraph,
  onShowWiki,
  showGraph,
  showWiki,
  searchQuery,
  onSearchQueryChange,
  children,
}: WorldBuildingLayoutProps) {
  return (
    <div data-testid="kb-responsive-layout" className="flex-1 flex min-h-0 flex-col lg:flex-row">
      <div className="shrink-0 border-b border-border lg:w-56 lg:border-b-0 lg:border-r">
        <KBCategorySidebar
          novelId={novelId}
          activeType={activeType}
          onTypeChange={onTypeChange}
          onAnalyze={onAnalyze}
          onConsistencyCheck={onConsistencyCheck}
          onShowGraph={onShowGraph}
          onShowWiki={onShowWiki}
          showGraph={showGraph}
          showWiki={showWiki}
        />
      </div>
      {!showGraph && (
        <div className="shrink-0 border-b border-border lg:w-64 lg:border-b-0 lg:border-r">
          <KBEntryList
            novelId={novelId}
            entries={entries}
            isLoading={entriesLoading}
            selectedEntryId={selectedEntryId}
            activeType={activeType}
            onSelectEntry={onSelectEntry}
            onCreateNew={onCreateNew}
            onCreateAssisted={onCreateAssisted}
            searchQuery={searchQuery}
            onSearchQueryChange={onSearchQueryChange}
          />
        </div>
      )}
      <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
    </div>
  );
}
