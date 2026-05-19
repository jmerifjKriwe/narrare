"use client";

/**
 * WorldBuilding — 3-column KB browser.
 *
 * Column 1: Entity type tabs with counts
 * Column 2: Entry list with search
 * Column 3: Detail/edit panel or create form
 *
 * Replaces the previous mock-data version with real API-backed data
 * via TanStack Query hooks.
 */

import { useState } from "react";
import type { KBEntityType } from "@/lib/api/kb";
import { useKBEntries, useKBEntry, useKBRelationships } from "@/lib/hooks/useKB";
import { KBCategorySidebar } from "./kb/KBCategorySidebar";
import { KBDetailPanel } from "./kb/KBDetailPanel";
import { KBEntryList } from "./kb/KBEntryList";

interface WorldBuildingProps {
  novelId: string;
}

export function WorldBuilding({ novelId }: WorldBuildingProps) {
  // UI state
  const [activeType, setActiveType] = useState<KBEntityType | null>(null);
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  // Data queries
  const { data: entriesData, isLoading: entriesLoading } = useKBEntries(novelId, {
    entity_type: activeType ?? undefined,
  });
  const { data: selectedEntry } = useKBEntry(novelId, selectedEntryId);
  const { data: relationships = [] } = useKBRelationships(novelId, selectedEntryId);

  const entries = entriesData?.items ?? [];

  function handleTypeChange(type: KBEntityType | null) {
    setActiveType(type);
    setSelectedEntryId(null);
    setIsCreating(false);
  }

  function handleSelectEntry(entryId: string) {
    setSelectedEntryId(entryId);
    setIsCreating(false);
  }

  function handleCreateNew() {
    setIsCreating(true);
    setSelectedEntryId(null);
  }

  function handleCreateCancel() {
    setIsCreating(false);
  }

  function handleCreated(entryId: string) {
    setIsCreating(false);
    setSelectedEntryId(entryId);
  }

  function handleDeleted() {
    setSelectedEntryId(null);
  }

  return (
    <div className="flex-1 flex h-full">
      <KBCategorySidebar
        novelId={novelId}
        activeType={activeType}
        onTypeChange={handleTypeChange}
      />
      <KBEntryList
        novelId={novelId}
        entries={entries}
        isLoading={entriesLoading}
        selectedEntryId={selectedEntryId}
        activeType={activeType}
        onSelectEntry={handleSelectEntry}
        onCreateNew={handleCreateNew}
      />
      <KBDetailPanel
        novelId={novelId}
        entry={selectedEntry ?? null}
        relationships={relationships}
        isCreating={isCreating}
        onCreateCancel={handleCreateCancel}
        onCreated={handleCreated}
        onDeleted={handleDeleted}
      />
    </div>
  );
}
