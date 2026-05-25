"use client";

/**
 * WorldBuilding — 3-column KB browser.
 *
 * Column 1: Entity type tabs with counts
 * Column 2: Entry list with search
 * Column 3: Detail/edit panel or create form or assisted creation panel
 *
 * Replaces the previous mock-data version with real API-backed data
 * via TanStack Query hooks.
 */

import { useState } from "react";
import type { KBEntityType } from "@/lib/api/kb";
import { useKBEntries, useKBEntry, useKBRelationships } from "@/lib/hooks/useKB";
import { KBAssistedCreationPanel } from "./kb/KBAssistedCreationPanel";
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
  const [isAssistedSession, setIsAssistedSession] = useState(false);
  const [assistedEntityType, setAssistedEntityType] = useState<KBEntityType | null>(null);

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
    setIsAssistedSession(false);
  }

  function handleSelectEntry(entryId: string) {
    setSelectedEntryId(entryId);
    setIsCreating(false);
    setIsAssistedSession(false);
  }

  function handleCreateNew() {
    setIsCreating(true);
    setSelectedEntryId(null);
    setIsAssistedSession(false);
  }

  function handleCreateAssisted() {
    setIsAssistedSession(true);
    setAssistedEntityType(activeType ?? "character");
    setIsCreating(false);
    setSelectedEntryId(null);
  }

  function handleCreateCancel() {
    setIsCreating(false);
  }

  function handleAssistedCancel() {
    setIsAssistedSession(false);
    setAssistedEntityType(null);
  }

  function handleAssistedComplete(entryId: string) {
    setIsAssistedSession(false);
    setAssistedEntityType(null);
    setSelectedEntryId(entryId);
  }

  function handleCreated(entryId: string) {
    setIsCreating(false);
    setSelectedEntryId(entryId);
  }

  function handleDeleted() {
    setSelectedEntryId(null);
  }

  // Column 3: Assisted creation panel takes priority
  if (isAssistedSession && assistedEntityType) {
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
          onCreateAssisted={handleCreateAssisted}
        />
        <KBAssistedCreationPanel
          novelId={novelId}
          entityType={assistedEntityType}
          onComplete={handleAssistedComplete}
          onCancel={handleAssistedCancel}
        />
      </div>
    );
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
        onCreateAssisted={handleCreateAssisted}
      />
      <KBDetailPanel
        novelId={novelId}
        entry={selectedEntry ?? null}
        relationships={relationships}
        isCreating={isCreating}
        initialEntityType={activeType ?? undefined}
        onCreateCancel={handleCreateCancel}
        onCreated={handleCreated}
        onDeleted={handleDeleted}
      />
    </div>
  );
}
