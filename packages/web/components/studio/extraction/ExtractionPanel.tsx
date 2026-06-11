"use client";

/**
 * ExtractionPanel — Main orchestration container for KB extraction.
 *
 * Thin presentational shell that delegates all phase management
 * to useExtractionPhase and renders the appropriate sub-components.
 *
 * Phase state machine: loading → review → applying → done | error
 * §16 compliance: AbortController cancel, useConnectionLost,
 * studio.aiActions.* labels, actionable error messages.
 */

import { useTranslations } from "next-intl";
import { ConnectionLostBanner } from "@/components/ui/connection-lost-banner";
import { ExtractionContent } from "./ExtractionContent";
import { ExtractionFooter } from "./ExtractionFooter";
import { ExtractionHeader } from "./ExtractionHeader";
import { useExtractionPhase } from "./useExtractionPhase";

interface ExtractionPanelProps {
  novelId: string;
  chapterId: string;
  onClose: () => void;
  onApplied: () => void;
}

export function ExtractionPanel({ novelId, chapterId, onClose, onApplied }: ExtractionPanelProps) {
  const t = useTranslations("studio");

  const {
    phase,
    errorMsg,
    isConnectionLost,
    selectedItems,
    selectedIndices,
    analysisNotes,
    handleApply,
    handleRetry,
    handleCancelExtraction,
    retryConnection,
    toggleItem,
    selectAll,
    selectNone,
  } = useExtractionPhase({ novelId, chapterId, onClose, onApplied, t });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-background rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        <ExtractionHeader
          title={phase === "done" ? t("kb.extractionComplete") : t("kb.extractionLoadingTitle")}
          closeLabel={t("kb.extractionCancel")}
          onClose={onClose}
        />
        {isConnectionLost && (
          <div className="px-4 pt-4">
            <ConnectionLostBanner onRetry={retryConnection} />
          </div>
        )}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-3xl mx-auto">
            <ExtractionContent
              phase={phase}
              items={selectedItems}
              selectedIndices={selectedIndices}
              analysisNotes={analysisNotes}
              errorMsg={errorMsg}
              onToggleItem={toggleItem}
              onSelectAll={selectAll}
              onSelectNone={selectNone}
              onRetry={handleRetry}
              onCancel={phase === "loading" ? handleCancelExtraction : undefined}
            />
          </div>
        </div>
        {(phase === "review" || phase === "applying") && (
          <ExtractionFooter
            selectedCount={selectedIndices.size}
            totalCount={selectedItems.length}
            isApplying={phase === "applying"}
            onCancel={onClose}
            onApply={handleApply}
          />
        )}
      </div>
    </div>
  );
}
