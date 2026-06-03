"use client";

/**
 * KB Assisted Creation Panel — Main container for AI-assisted KB entry creation.
 *
 * Orchestrates the session lifecycle and routes between sub-views:
 * - Field list view (default)
 * - Interview view
 * - Enhance review view
 *
 * Follows RULE-06 (one responsibility): this component only manages
 * view state and session lifecycle — actual field rendering and
 * interaction logic delegated to sub-components.
 */

import { Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import type { KBEntityType } from "@/lib/api/kb";
import { TYPE_ICONS } from "./constants";
import { useKBAssistedCreationController } from "./KBAssistedCreationController";
import { KBAssistedCreationFooter } from "./KBAssistedCreationFooter";
import { KBAssistedCreationHeader } from "./KBAssistedCreationHeader";
import { KBEnhanceReview } from "./KBEnhanceReview";
import { KBInterviewView } from "./KBInterviewView";
import { KBSessionFieldList } from "./KBSessionFieldList";

export type AssistedView = "fields" | "interview" | "enhance";

interface KBAssistedCreationPanelProps {
  novelId: string;
  entityType: KBEntityType;
  onComplete: (entryId: string) => void;
  onCancel: () => void;
  /** If resuming, pass the existing session ID to skip creation. */
  resumeSessionId?: string | null;
}

export function KBAssistedCreationPanel({
  novelId,
  entityType,
  onComplete,
  onCancel,
  resumeSessionId,
}: KBAssistedCreationPanelProps) {
  const t = useTranslations("studio");
  const controller = useKBAssistedCreationController({
    novelId,
    entityType,
    resumeSessionId,
    onComplete,
    onCancel,
    t,
  });

  // --- Get icon for entity type ---
  const EntityIcon = TYPE_ICONS[entityType] || Sparkles;

  // --- Loading state ---
  if (controller.isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-background">
        <div className="text-center">
          <EntityIcon className="w-12 h-12 mx-auto mb-4 text-muted-foreground opacity-50 animate-pulse" />
          <p className="text-muted-foreground">
            {t("kb.creatingSession") || "Creating session..."}
          </p>
        </div>
      </div>
    );
  }

  // --- Error state ---
  if (controller.isError || !controller.session) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-background">
        <div className="text-center max-w-md">
          <p className="text-red-500 mb-4">
            {controller.errorMessage || t("kb.sessionCreateFailed") || "Failed to create session"}
          </p>
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 border border-border rounded-md hover:bg-muted transition-colors text-sm"
          >
            {t("kb.cancel")}
          </button>
        </div>
      </div>
    );
  }

  // --- Interview view ---
  if (controller.view === "interview") {
    return (
      <KBInterviewView
        novelId={novelId}
        sessionId={controller.sessionId ?? ""}
        session={controller.session}
        onRequestQuestion={controller.handleRequestInterview}
        onSubmitAnswer={controller.handleSubmitInterviewAnswer}
        onBack={() => controller.setView("fields")}
      />
    );
  }

  // --- Enhance review view ---
  if (controller.view === "enhance") {
    return (
      <KBEnhanceReview
        session={controller.session}
        onRequestEnhance={controller.handleRequestEnhance}
        onAcceptEnhancement={controller.handleAcceptEnhancement}
        onApplySelected={controller.handleApplySelectedEnhancements}
        onBack={() => controller.setView("fields")}
      />
    );
  }

  // --- Main: Field list view ---
  return (
    <div className="flex-1 flex flex-col bg-background">
      <KBAssistedCreationHeader
        entityType={entityType}
        EntityIcon={EntityIcon}
        session={controller.session}
        filledFields={controller.filledFields}
        totalFields={controller.totalFields}
        resumePersistenceEnabled={controller.resumePersistenceEnabled}
        onResumePersistenceChange={controller.handleResumePersistenceChange}
        onAbandon={controller.handleAbandon}
        t={t}
      />

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto">
          <KBSessionFieldList
            session={controller.session}
            onSuggest={controller.handleSuggest}
            onAnswer={controller.handleAnswer}
            onAcceptSuggestion={controller.handleAcceptSuggestion}
            onRejectSuggestion={controller.handleRejectSuggestion}
            onStartInterview={() => controller.setView("interview")}
            onEnhance={() => controller.setView("enhance")}
            suggestingFieldKey={controller.suggestingFieldKey}
          />
        </div>
      </div>

      {/* Footer: name input + actions */}
      <KBAssistedCreationFooter
        session={controller.session}
        entryName={controller.entryName}
        setEntryName={controller.setEntryName}
        view={controller.view}
        setView={controller.setView}
        filledFields={controller.filledFields}
        completePending={controller.completePending}
        onCancel={onCancel}
        onCompleteAndSave={controller.handleCompleteAndSave}
      />

      {/* Cancel confirmation dialog */}
      <ConfirmDialog
        open={controller.confirmAbandon}
        onOpenChange={controller.setConfirmAbandon}
        title={t("kb.interview.cancelConfirmTitle")}
        description={
          controller.resumePersistenceEnabled
            ? t("kb.interview.cancelConfirmDescription")
            : t("kb.interview.cancelConfirmNoSaveDescription")
        }
        confirmLabel={t("kb.interview.cancelConfirmAction")}
        onConfirm={controller.handleConfirmAbandon}
        variant="destructive"
      />
    </div>
  );
}
