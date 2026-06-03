"use client";

/**
 * WorldBuilding — 3-column KB browser.
 *
 * Column 1: Entity type tabs with counts
 * Column 2: Entry list with search
 * Column 3: Detail/edit panel or create form or assisted creation panel
 *
 * Supports an optional analysis mode that replaces the detail panel
 * with the WorldbuildingAnalysisPanel.
 */

import { useTranslations } from "next-intl";
import { useState } from "react";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import type { KBEntityType } from "@/lib/api/kb";
import { clearPendingInterview, getPendingInterview } from "@/lib/hooks/use-kb-interview-resume";
import { useKBEntries, useKBEntry, useKBRelationships } from "@/lib/hooks/useKB";
import { ConsistencyCheckPanel } from "./kb/ConsistencyCheckPanel";
import { KBAssistedCreationPanel } from "./kb/KBAssistedCreationPanel";
import { KBCategorySidebar } from "./kb/KBCategorySidebar";
import { KBDetailPanel } from "./kb/KBDetailPanel";
import { KBEntryList } from "./kb/KBEntryList";
import { KnowledgeGraphView } from "./kb/KnowledgeGraphView";
import { WikiOverviewPanel } from "./kb/WikiOverviewPanel";
import { WorldbuildingAnalysisPanel } from "./kb/WorldbuildingAnalysisPanel";

interface WorldBuildingProps {
  novelId: string;
}

export function WorldBuilding({ novelId }: WorldBuildingProps) {
  const t = useTranslations("studio");
  // UI state
  const [activeType, setActiveType] = useState<KBEntityType | null>(null);
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isAssistedSession, setIsAssistedSession] = useState(false);
  const [assistedEntityType, setAssistedEntityType] = useState<KBEntityType | null>(null);
  const [resumeSessionId, setResumeSessionId] = useState<string | null>(null);
  const [showResumeDialog, setShowResumeDialog] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);
  const [showConsistency, setShowConsistency] = useState(false);
  const [showGraph, setShowGraph] = useState(false);
  const [showWiki, setShowWiki] = useState(false);

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
    setShowAnalysis(false);
    setShowConsistency(false);
    setShowGraph(false);
    setShowWiki(false);
  }

  function handleSelectEntry(entryId: string) {
    setSelectedEntryId(entryId);
    setIsCreating(false);
    setIsAssistedSession(false);
    setShowAnalysis(false);
    setShowConsistency(false);
  }

  function handleCreateNew() {
    setIsCreating(true);
    setSelectedEntryId(null);
    setIsAssistedSession(false);
    setShowAnalysis(false);
    setShowConsistency(false);
  }

  function handleCreateAssisted() {
    // Check for a pending interview to resume
    const pending = getPendingInterview(novelId);
    if (pending) {
      setShowResumeDialog(true);
      return;
    }
    startNewAssistedSession();
  }

  function startNewAssistedSession() {
    clearPendingInterview(novelId);
    setIsAssistedSession(true);
    setAssistedEntityType(activeType ?? "character");
    setResumeSessionId(null);
    setIsCreating(false);
    setSelectedEntryId(null);
    setShowAnalysis(false);
    setShowConsistency(false);
  }

  function handleResumeInterview() {
    const pending = getPendingInterview(novelId);
    if (pending) {
      setIsAssistedSession(true);
      setAssistedEntityType(pending.entityType as KBEntityType);
      setResumeSessionId(pending.sessionId);
      setIsCreating(false);
      setSelectedEntryId(null);
      setShowAnalysis(false);
      setShowConsistency(false);
    }
    setShowResumeDialog(false);
  }

  function handleDiscardResume() {
    clearPendingInterview(novelId);
    setShowResumeDialog(false);
    startNewAssistedSession();
  }

  function handleCreateCancel() {
    setIsCreating(false);
  }

  function handleAssistedCancel() {
    setIsAssistedSession(false);
    setAssistedEntityType(null);
    setResumeSessionId(null);
  }

  function handleAssistedComplete(entryId: string) {
    setIsAssistedSession(false);
    setAssistedEntityType(null);
    setResumeSessionId(null);
    setSelectedEntryId(entryId);
  }

  function handleCreated(entryId: string) {
    setIsCreating(false);
    setSelectedEntryId(entryId);
  }

  function handleDeleted() {
    setSelectedEntryId(null);
  }

  function handleShowAnalysis() {
    setShowAnalysis(true);
    setSelectedEntryId(null);
    setIsCreating(false);
    setIsAssistedSession(false);
    setShowConsistency(false);
  }

  function handleShowConsistency() {
    setShowConsistency(true);
    setSelectedEntryId(null);
    setIsCreating(false);
    setIsAssistedSession(false);
    setShowAnalysis(false);
  }

  function handleShowGraph() {
    setShowGraph(true);
    setSelectedEntryId(null);
    setIsCreating(false);
    setIsAssistedSession(false);
    setShowAnalysis(false);
    setShowConsistency(false);
    setShowWiki(false);
  }

  function handleShowWiki() {
    setShowWiki(true);
    setSelectedEntryId(null);
    setIsCreating(false);
    setIsAssistedSession(false);
    setShowAnalysis(false);
    setShowConsistency(false);
    setShowGraph(false);
  }

  function handleCloseWiki() {
    setShowWiki(false);
  }

  // Column 3: Assisted creation panel takes priority
  if (isAssistedSession && assistedEntityType) {
    return (
      <div className="flex-1 flex h-full">
        <KBCategorySidebar
          novelId={novelId}
          activeType={activeType}
          onTypeChange={handleTypeChange}
          onAnalyze={handleShowAnalysis}
          onConsistencyCheck={handleShowConsistency}
          onShowGraph={handleShowGraph}
          onShowWiki={handleShowWiki}
          showGraph={showGraph}
          showWiki={showWiki}
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
          resumeSessionId={resumeSessionId}
        />
      </div>
    );
  }

  // Analysis mode: replaces column 3 with analysis panel
  if (showAnalysis) {
    return (
      <div className="flex-1 flex h-full">
        <KBCategorySidebar
          novelId={novelId}
          activeType={activeType}
          onTypeChange={handleTypeChange}
          onAnalyze={handleShowAnalysis}
          onConsistencyCheck={handleShowConsistency}
          onShowGraph={handleShowGraph}
          onShowWiki={handleShowWiki}
          showGraph={showGraph}
          showWiki={showWiki}
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
        <WorldbuildingAnalysisPanel novelId={novelId} onClose={() => setShowAnalysis(false)} />
      </div>
    );
  }

  // Consistency check mode: replaces column 3 with consistency panel
  if (showConsistency) {
    return (
      <div className="flex-1 flex h-full">
        <KBCategorySidebar
          novelId={novelId}
          activeType={activeType}
          onTypeChange={handleTypeChange}
          onAnalyze={handleShowAnalysis}
          onConsistencyCheck={handleShowConsistency}
          onShowGraph={handleShowGraph}
          onShowWiki={handleShowWiki}
          showGraph={showGraph}
          showWiki={showWiki}
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
        <ConsistencyCheckPanel
          novelId={novelId}
          onClose={() => setShowConsistency(false)}
          onEntityClick={(entityId) => {
            setSelectedEntryId(entityId);
            setShowConsistency(false);
          }}
        />
      </div>
    );
  }

  // Graph mode: replaces columns 2+3 with graph visualization
  if (showGraph) {
    return (
      <div className="flex-1 flex h-full">
        <KBCategorySidebar
          novelId={novelId}
          activeType={activeType}
          onTypeChange={handleTypeChange}
          onAnalyze={handleShowAnalysis}
          onConsistencyCheck={handleShowConsistency}
          onShowGraph={handleShowGraph}
          onShowWiki={handleShowWiki}
          showGraph={showGraph}
          showWiki={showWiki}
        />
        <KnowledgeGraphView novelId={novelId} onSelectEntry={handleSelectEntry} />
      </div>
    );
  }

  // Wiki mode: replaces columns 2+3 with wiki overview
  if (showWiki) {
    return (
      <div className="flex-1 flex h-full">
        <KBCategorySidebar
          novelId={novelId}
          activeType={activeType}
          onTypeChange={handleTypeChange}
          onAnalyze={handleShowAnalysis}
          onConsistencyCheck={handleShowConsistency}
          onShowGraph={handleShowGraph}
          onShowWiki={handleShowWiki}
          showGraph={showGraph}
          showWiki={showWiki}
        />
        <WikiOverviewPanel novelId={novelId} onClose={handleCloseWiki} />
      </div>
    );
  }

  return (
    <div className="flex-1 flex h-full">
      <KBCategorySidebar
        novelId={novelId}
        activeType={activeType}
        onTypeChange={handleTypeChange}
        onAnalyze={handleShowAnalysis}
        onConsistencyCheck={handleShowConsistency}
        onShowGraph={handleShowGraph}
        onShowWiki={handleShowWiki}
        showGraph={showGraph}
        showWiki={showWiki}
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

      {/* Resume interview dialog */}
      <ConfirmDialog
        open={showResumeDialog}
        onOpenChange={(open) => {
          setShowResumeDialog(open);
          if (!open) {
            // Dialog closed without confirming — user wants a new interview
            handleDiscardResume();
          }
        }}
        title={t("kb.interview.resumeTitle")}
        description={t("kb.interview.resumePrivacyDescription")}
        confirmLabel={t("kb.interview.resumeAction")}
        cancelLabel={t("kb.interview.startNew")}
        onConfirm={handleResumeInterview}
      />
    </div>
  );
}
