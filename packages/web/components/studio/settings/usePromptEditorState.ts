"use client";

/**
 * usePromptEditorState — all state for the PromptEditor (RULE-04 split).
 *
 * Owns:
 *   - Prompt fetch query.
 *   - Save / reset-with-metadata mutations.
 *   - Preview dialog open-flag + provider-free preview fetch.
 *   - Live-test state (delegated to :func:`usePromptLiveTest`).
 *   - Diff view open-flag + cache invalidation.
 *   - Local UI state: edit mode, edited content, status message.
 *
 * Stays under the 150-line hook limit by:
 *   - Delegating the SSE live-test lifecycle to :func:`usePromptLiveTest`.
 *   - Declaring public types in :file:`usePromptEditorState.types.ts`.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { promptsApi } from "@/lib/api/client";
import { buildSystemVariables } from "./promptVariables";
import type { UsePromptEditorStateReturn } from "./usePromptEditorState.types";
import { usePromptLiveTest } from "./usePromptLiveTest";

export function usePromptEditorState(
  promptId: string,
  language: "en" | "de" | "fr" = "en",
): UsePromptEditorStateReturn {
  const t = useTranslations("studio");
  const queryClient = useQueryClient();

  const [editMode, setEditMode] = useState(false);
  const [editedContent, setEditedContent] = useState("");
  const [showDiff, setShowDiff] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [showPreviewDialog, setShowPreviewDialog] = useState(false);
  const [showLiveTestDialog, setShowLiveTestDialogRaw] = useState(false);
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

  const { data: preview, isLoading: previewLoading } = useQuery({
    queryKey: ["prompt-preview", promptId, editMode ? editedContent : null],
    queryFn: () =>
      promptsApi.preview(promptId, {
        variables: buildSystemVariables(promptId, language),
        language,
        edited_override: editMode ? editedContent : undefined,
      }),
    enabled: showPreviewDialog,
  });

  const saveMutation = useMutation({
    mutationFn: (content: string) => promptsApi.save(promptId, content),
    onSuccess: () => {
      setStatusMessage({ type: "success", text: t("settings.prompts.saveSuccess") });
      setEditMode(false);
      void queryClient.invalidateQueries({ queryKey: ["prompts"] });
      void queryClient.invalidateQueries({ queryKey: ["prompt", promptId] });
    },
    onError: () => setStatusMessage({ type: "error", text: t("settings.prompts.saveFailed") }),
  });

  const resetMutation = useMutation({
    mutationFn: () => promptsApi.resetWithMetadata(promptId),
    onSuccess: () => {
      setStatusMessage({ type: "success", text: t("settings.prompts.resetSuccess") });
      setEditMode(false);
      void queryClient.invalidateQueries({ queryKey: ["prompts"] });
      void queryClient.invalidateQueries({ queryKey: ["prompt", promptId] });
      void queryClient.invalidateQueries({ queryKey: ["prompts-updates"] });
    },
    onError: () => setStatusMessage({ type: "error", text: t("settings.prompts.resetFailed") }),
  });

  const liveTest = usePromptLiveTest({
    promptId,
    language,
    editedOverride: editMode ? editedContent : null,
  });

  const setShowLiveTestDialog = (v: boolean) => {
    setShowLiveTestDialogRaw(v);
    if (!v) liveTest.reset();
  };

  const handleStartEdit = () => {
    if (prompt) setEditedContent(prompt.content);
    setEditMode(true);
    setStatusMessage(null);
  };

  return {
    prompt,
    isLoading,
    error,
    editMode,
    editedContent,
    setEditMode,
    setEditedContent,
    handleStartEdit,
    handleSave: () => saveMutation.mutate(editedContent),
    saveMutation,
    showResetConfirm,
    setShowResetConfirm,
    resetMutation,
    showDiff,
    openDiff: () => setShowDiff(true),
    closeDiff: () => setShowDiff(false),
    showPreviewDialog,
    setShowPreviewDialog,
    preview,
    previewLoading,
    showLiveTestDialog,
    setShowLiveTestDialog,
    liveTestAcknowledged: liveTest.acknowledged,
    liveTestOutput: liveTest.output,
    liveTestStreaming: liveTest.streaming,
    liveTestError: liveTest.error,
    handleConfirmLiveTest: liveTest.handleConfirm,
    handleCancelLiveTest: liveTest.handleCancel,
    statusMessage,
  };
}
