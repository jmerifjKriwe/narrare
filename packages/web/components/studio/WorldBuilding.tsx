"use client";

/**
 * WorldBuilding — 3-column KB browser.
 *
 * Column 1: Entity type tabs with counts
 * Column 2: Entry list with search
 * Column 3: Detail/edit panel or create form or assisted creation panel
 *
 * Supports optional analysis, consistency, graph, and wiki modes
 * that replace the detail panel.
 */

import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { type ReactNode, useMemo } from "react";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useKBEntries, useKBEntry, useKBRelationships } from "@/lib/hooks/useKB";
import { useWorldBuildingUrlSync } from "./_components/useWorldBuildingUrlSync";
import { WorldBuildingLayout } from "./_components/WorldBuildingLayout";
import { useWorldBuildingState } from "./_components/worldBuildingState";
import { ConsistencyCheckPanel } from "./kb/ConsistencyCheckPanel";
import { KBAssistedCreationPanel } from "./kb/KBAssistedCreationPanel";
import { KBDetailPanel } from "./kb/KBDetailPanel";
import { KnowledgeGraphView } from "./kb/KnowledgeGraphView";
import { parseKBUrlState } from "./kb/kbUrlState";
import { WikiOverviewPanel } from "./kb/WikiOverviewPanel";
import { WorldbuildingAnalysisPanel } from "./kb/WorldbuildingAnalysisPanel";

interface WorldBuildingProps {
  novelId: string;
}

export function WorldBuilding({ novelId }: WorldBuildingProps) {
  const t = useTranslations("studio");
  const searchParams = useSearchParams();
  const searchParamsSnapshot = searchParams.toString();
  const urlState = useMemo(
    () => parseKBUrlState(new URLSearchParams(searchParamsSnapshot)),
    [searchParamsSnapshot],
  );
  const state = useWorldBuildingState(novelId, urlState);

  const {
    handleAnalyze,
    handleAssistedCancel,
    handleCloseMode,
    handleConsistencyCheck,
    handleCreateAssisted,
    handleCreateCancel,
    handleCreateNew,
    handleCreated,
    handleDeleted,
    handleSearchQueryChange,
    handleSelectEntry,
    handleShowGraph,
    handleShowWiki,
    handleTypeChange,
  } = useWorldBuildingUrlSync(state, urlState);

  const { data: entriesData, isLoading: entriesLoading } = useKBEntries(novelId, {
    entity_type: state.activeType ?? undefined,
  });
  const { data: selectedEntry } = useKBEntry(novelId, state.selectedEntryId);
  const { data: relationships = [] } = useKBRelationships(novelId, state.selectedEntryId);

  const entries = entriesData?.items ?? [];

  // --- Shared layout props ---

  const layoutProps = {
    novelId,
    activeType: state.activeType,
    entries,
    entriesLoading,
    selectedEntryId: state.selectedEntryId,
    onSelectEntry: handleSelectEntry,
    onCreateNew: handleCreateNew,
    onCreateAssisted: handleCreateAssisted,
    onTypeChange: handleTypeChange,
    onAnalyze: handleAnalyze,
    onConsistencyCheck: handleConsistencyCheck,
    onShowGraph: handleShowGraph,
    onShowWiki: handleShowWiki,
    showGraph: state.showGraph,
    showWiki: state.showWiki,
    searchQuery: urlState.query,
    onSearchQueryChange: handleSearchQueryChange,
  };

  const renderWorldBuildingView = (children: ReactNode) => (
    <section className="flex-1 min-h-0" aria-labelledby="kb-view-title">
      <h1 id="kb-view-title" className="sr-only">
        {t("worldbuilding.title")}
      </h1>
      <WorldBuildingLayout {...layoutProps}>{children}</WorldBuildingLayout>
    </section>
  );

  // --- Third-column rendering ---

  if (state.isAssistedSession && state.assistedEntityType) {
    return renderWorldBuildingView(
      <KBAssistedCreationPanel
        novelId={novelId}
        entityType={state.assistedEntityType}
        onComplete={handleCreated}
        onCancel={handleAssistedCancel}
        resumeSessionId={state.resumeSessionId}
      />,
    );
  }

  if (state.showAnalysis) {
    return renderWorldBuildingView(
      <WorldbuildingAnalysisPanel novelId={novelId} onClose={handleCloseMode} />,
    );
  }

  if (state.showConsistency) {
    return renderWorldBuildingView(
      <ConsistencyCheckPanel
        novelId={novelId}
        onClose={handleCloseMode}
        onEntityClick={(entityId) => {
          handleSelectEntry(entityId);
          state.setMode("detail");
        }}
      />,
    );
  }

  if (state.showGraph) {
    return renderWorldBuildingView(
      <KnowledgeGraphView novelId={novelId} onSelectEntry={handleSelectEntry} />,
    );
  }

  if (state.showWiki) {
    return renderWorldBuildingView(
      <WikiOverviewPanel novelId={novelId} onClose={handleCloseMode} />,
    );
  }

  // Default: detail panel + resume dialog
  return renderWorldBuildingView(
    <>
      <KBDetailPanel
        novelId={novelId}
        entry={selectedEntry ?? null}
        relationships={relationships}
        isCreating={state.isCreating}
        initialEntityType={state.activeType ?? undefined}
        onCreateCancel={handleCreateCancel}
        onCreated={handleCreated}
        onDeleted={handleDeleted}
      />
      <ConfirmDialog
        open={state.showResumeDialog}
        onOpenChange={(open) => {
          state.setShowResumeDialog(open);
          if (!open) state.handleDiscardResume();
        }}
        title={t("kb.interview.resumeTitle")}
        description={t("kb.interview.resumePrivacyDescription")}
        confirmLabel={t("kb.interview.resumeAction")}
        cancelLabel={t("kb.interview.startNew")}
        onConfirm={state.handleResumeInterview}
      />
    </>,
  );
}
