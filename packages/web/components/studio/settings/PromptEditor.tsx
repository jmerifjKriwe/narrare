"use client";

/**
 * PromptEditor — render-only orchestration of the prompt customisation view.
 *
 * After PROMPT-003 (CR-AUFG-07-16):
 *   - All state lives in :func:`usePromptEditorState` (RULE-04).
 *   - The local ``PromptPreview`` (EXAMPLE_VALUES substitution) is deleted;
 *     preview is API-driven via :component:`PromptPreviewDialog`.
 *   - The live-test flow is API-driven via :component:`PromptLiveTestDialog`
 *     (SSE through :func:`usePromptLiveTest`).
 *   - The reset flow surfaces effective-state metadata via
 *     :component:`PromptResetConfirmDialog`.
 */

import { useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { PromptDiff } from "./PromptDiff";
import { PromptEditorEditMode } from "./PromptEditorEditMode";
import { PromptEditorHeader } from "./PromptEditorHeader";
import { PromptEditorViewMode } from "./PromptEditorViewMode";
import { PromptLiveTestDialog } from "./PromptLiveTestDialog";
import { PromptPreviewDialog } from "./PromptPreviewDialog";
import { PromptResetConfirmDialog } from "./PromptResetConfirmDialog";
import { PromptVariablesAside } from "./PromptVariablesAside";
import { usePromptEditorState } from "./usePromptEditorState";

interface PromptEditorProps {
  readonly promptId: string;
  readonly hasUpdate: boolean;
  readonly onBack: () => void;
}

export function PromptEditor({ promptId, hasUpdate, onBack }: PromptEditorProps) {
  const t = useTranslations("studio");
  const queryClient = useQueryClient();
  const s = usePromptEditorState(promptId);

  // --- Diff view (full-screen replacement) ---
  if (s.showDiff) {
    return (
      <PromptDiff
        promptId={promptId}
        onBack={s.closeDiff}
        onResolved={() => {
          s.closeDiff();
          void queryClient.invalidateQueries({ queryKey: ["prompts"] });
          void queryClient.invalidateQueries({ queryKey: ["prompt", promptId] });
          void queryClient.invalidateQueries({ queryKey: ["prompts-updates"] });
        }}
      />
    );
  }

  // --- Loading ---
  if (s.isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">
          {t("settings.prompts.loadingPrompt")}
        </span>
      </div>
    );
  }

  // --- Error ---
  if (s.error || !s.prompt) {
    return (
      <div className="space-y-4">
        <div className="bg-destructive/10 text-destructive rounded-md p-3 text-sm" role="alert">
          {t("settings.prompts.loadFailed")}
        </div>
        <button
          type="button"
          onClick={onBack}
          className="px-4 py-2 bg-muted rounded-md hover:bg-accent transition-colors text-sm"
        >
          {t("settings.prompts.back")}
        </button>
      </div>
    );
  }

  // --- Main view ---
  return (
    <div>
      <PromptEditorHeader
        promptId={promptId}
        isOverridden={s.prompt.is_overridden}
        hasUpdate={hasUpdate}
        statusMessage={s.statusMessage}
        onBack={onBack}
        onShowDiff={s.openDiff}
      />

      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex gap-6">
          <div className="flex-1 space-y-4">
            {s.editMode ? (
              <PromptEditorEditMode
                editedContent={s.editedContent}
                onContentChange={s.setEditedContent}
                onSave={s.handleSave}
                onCancel={() => s.setEditMode(false)}
                isSavePending={s.saveMutation.isPending}
              />
            ) : (
              <PromptEditorViewMode
                content={s.prompt.content}
                isOverridden={s.prompt.is_overridden}
                variables={s.prompt.variables}
                onStartEdit={s.handleStartEdit}
                onOpenPreview={() => s.setShowPreviewDialog(true)}
                onOpenLiveTest={() => s.setShowLiveTestDialog(true)}
                onOpenReset={() => s.setShowResetConfirm(true)}
                isResetPending={s.resetMutation.isPending}
              />
            )}
          </div>

          {s.prompt.variables.length > 0 && <PromptVariablesAside variables={s.prompt.variables} />}
        </div>
      </div>

      {/* PROMPT-003 dialogs */}
      <PromptPreviewDialog
        open={s.showPreviewDialog}
        onOpenChange={s.setShowPreviewDialog}
        promptId={promptId}
        preview={s.preview ?? null}
        loading={s.previewLoading}
      />
      <PromptLiveTestDialog
        open={s.showLiveTestDialog}
        onOpenChange={s.setShowLiveTestDialog}
        promptId={promptId}
        acknowledged={s.liveTestAcknowledged}
        output={s.liveTestOutput}
        streaming={s.liveTestStreaming}
        error={s.liveTestError}
        onConfirm={s.handleConfirmLiveTest}
        onCancel={s.handleCancelLiveTest}
      />
      <PromptResetConfirmDialog
        open={s.showResetConfirm}
        onOpenChange={s.setShowResetConfirm}
        promptId={promptId}
        overrideContent={s.prompt.content}
        bundledContent={s.prompt.base_content}
        pending={s.resetMutation.isPending}
        onConfirm={() => {
          s.resetMutation.mutate();
          s.setShowResetConfirm(false);
        }}
      />
    </div>
  );
}
