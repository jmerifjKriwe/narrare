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

import { useTranslations } from "next-intl";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useKBEntries, useKBEntry, useKBRelationships } from "@/lib/hooks/useKB";
import { WorldBuildingLayout } from "./_components/WorldBuildingLayout";
import { useWorldBuildingState } from "./_components/worldBuildingState";
import { ConsistencyCheckPanel } from "./kb/ConsistencyCheckPanel";
import { KBAssistedCreationPanel } from "./kb/KBAssistedCreationPanel";
import { KBDetailPanel } from "./kb/KBDetailPanel";
import { KnowledgeGraphView } from "./kb/KnowledgeGraphView";
import { WikiOverviewPanel } from "./kb/WikiOverviewPanel";
import { WorldbuildingAnalysisPanel } from "./kb/WorldbuildingAnalysisPanel";

interface WorldBuildingProps {
  novelId: string;
}

export function WorldBuilding({ novelId }: WorldBuildingProps) {
  const t = useTranslations("studio");
  const state = useWorldBuildingState(novelId);

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
    onSelectEntry: state.handleSelectEntry,
    onCreateNew: state.handleCreateNew,
    onCreateAssisted: state.handleCreateAssisted,
    onTypeChange: state.handleTypeChange,
    onAnalyze: state.handleShowAnalysis,
    onConsistencyCheck: state.handleShowConsistency,
    onShowGraph: state.handleShowGraph,
    onShowWiki: state.handleShowWiki,
    showGraph: state.showGraph,
    showWiki: state.showWiki,
  };

  // --- Third-column rendering ---

  if (state.isAssistedSession && state.assistedEntityType) {
    return (
      <WorldBuildingLayout {...layoutProps}>
        <KBAssistedCreationPanel
          novelId={novelId}
          entityType={state.assistedEntityType}
          onComplete={state.handleAssistedComplete}
          onCancel={state.handleAssistedCancel}
          resumeSessionId={state.resumeSessionId}
        />
      </WorldBuildingLayout>
    );
  }

  if (state.showAnalysis) {
    return (
      <WorldBuildingLayout {...layoutProps}>
        <WorldbuildingAnalysisPanel
          novelId={novelId}
          onClose={() => state.setShowAnalysis(false)}
        />
      </WorldBuildingLayout>
    );
  }

  if (state.showConsistency) {
    return (
      <WorldBuildingLayout {...layoutProps}>
        <ConsistencyCheckPanel
          novelId={novelId}
          onClose={() => state.setShowConsistency(false)}
          onEntityClick={(entityId) => {
            state.handleSelectEntry(entityId);
            state.setShowConsistency(false);
          }}
        />
      </WorldBuildingLayout>
    );
  }

  if (state.showGraph) {
    return (
      <WorldBuildingLayout {...layoutProps}>
        <KnowledgeGraphView novelId={novelId} onSelectEntry={state.handleSelectEntry} />
      </WorldBuildingLayout>
    );
  }

  if (state.showWiki) {
    return (
      <WorldBuildingLayout {...layoutProps}>
        <WikiOverviewPanel novelId={novelId} onClose={state.handleCloseWiki} />
      </WorldBuildingLayout>
    );
  }

  // Default: detail panel + resume dialog
  return (
    <WorldBuildingLayout {...layoutProps}>
      <KBDetailPanel
        novelId={novelId}
        entry={selectedEntry ?? null}
        relationships={relationships}
        isCreating={state.isCreating}
        initialEntityType={state.activeType ?? undefined}
        onCreateCancel={state.handleCreateCancel}
        onCreated={state.handleCreated}
        onDeleted={state.handleDeleted}
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
    </WorldBuildingLayout>
  );
}
