"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { promptsApi } from "@/lib/api/client";
import { PromptDiff } from "./PromptDiff";
import { PromptEditorEditMode } from "./PromptEditorEditMode";
import { PromptEditorHeader } from "./PromptEditorHeader";
import { PromptEditorViewMode } from "./PromptEditorViewMode";
import { PromptVariablesAside } from "./PromptVariablesAside";

// --- Types ---

interface PromptEditorProps {
  readonly promptId: string;
  readonly hasUpdate: boolean;
  readonly onBack: () => void;
}

// --- Component ---

export function PromptEditor({ promptId, hasUpdate, onBack }: PromptEditorProps) {
  const t = useTranslations("studio");
  const queryClient = useQueryClient();
  const [editMode, setEditMode] = useState(false);
  const [editedContent, setEditedContent] = useState("");
  const [showDiff, setShowDiff] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [previewMode, setPreviewMode] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const {
    data: prompt,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["prompt", promptId],
    queryFn: () => promptsApi.get(promptId),
  });

  const saveMutation = useMutation({
    mutationFn: (content: string) => promptsApi.save(promptId, content),
    onSuccess: () => {
      setStatusMessage({ type: "success", text: t("settings.prompts.saveSuccess") });
      setEditMode(false);
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
      queryClient.invalidateQueries({ queryKey: ["prompt", promptId] });
    },
    onError: () => {
      setStatusMessage({ type: "error", text: t("settings.prompts.saveFailed") });
    },
  });

  const resetMutation = useMutation({
    mutationFn: () => promptsApi.reset(promptId),
    onSuccess: () => {
      setStatusMessage({ type: "success", text: t("settings.prompts.resetSuccess") });
      setEditMode(false);
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
      queryClient.invalidateQueries({ queryKey: ["prompt", promptId] });
      queryClient.invalidateQueries({ queryKey: ["prompts-updates"] });
    },
    onError: () => {
      setStatusMessage({ type: "error", text: t("settings.prompts.resetFailed") });
    },
  });

  const handleStartEdit = () => {
    if (prompt) {
      setEditedContent(prompt.content);
    }
    setEditMode(true);
    setPreviewMode(false);
    setStatusMessage(null);
  };

  const handleSave = () => {
    saveMutation.mutate(editedContent);
  };

  const handleReset = () => {
    setShowResetConfirm(true);
  };

  // Diff view
  if (showDiff) {
    return (
      <PromptDiff
        promptId={promptId}
        onBack={() => setShowDiff(false)}
        onResolved={() => {
          setShowDiff(false);
          queryClient.invalidateQueries({ queryKey: ["prompts"] });
          queryClient.invalidateQueries({ queryKey: ["prompt", promptId] });
          queryClient.invalidateQueries({ queryKey: ["prompts-updates"] });
        }}
      />
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">
          {t("settings.prompts.loadingPrompt")}
        </span>
      </div>
    );
  }

  // Error state
  if (error || !prompt) {
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

  return (
    <div>
      <PromptEditorHeader
        promptId={promptId}
        isOverridden={prompt.is_overridden}
        hasUpdate={hasUpdate}
        statusMessage={statusMessage}
        onBack={onBack}
        onShowDiff={() => setShowDiff(true)}
      />

      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex gap-6">
          {/* Main content */}
          <div className="flex-1 space-y-4">
            {editMode ? (
              <PromptEditorEditMode
                editedContent={editedContent}
                onContentChange={setEditedContent}
                onSave={handleSave}
                onCancel={() => setEditMode(false)}
                isSavePending={saveMutation.isPending}
              />
            ) : (
              <PromptEditorViewMode
                content={prompt.content}
                isOverridden={prompt.is_overridden}
                variables={prompt.variables}
                previewMode={previewMode}
                onSetPreviewMode={setPreviewMode}
                onStartEdit={handleStartEdit}
                onReset={handleReset}
                isResetPending={resetMutation.isPending}
              />
            )}
          </div>

          {/* Variables sidebar */}
          {prompt.variables.length > 0 && <PromptVariablesAside variables={prompt.variables} />}
        </div>
      </div>

      {/* Reset confirmation dialog */}
      <ConfirmDialog
        open={showResetConfirm}
        onOpenChange={setShowResetConfirm}
        title={t("settings.prompts.resetToDefault")}
        description={t("settings.prompts.confirmReset")}
        confirmLabel={t("settings.prompts.resetToDefault")}
        variant="destructive"
        onConfirm={() => {
          resetMutation.mutate();
          setShowResetConfirm(false);
        }}
      />
    </div>
  );
}
