"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { promptsApi } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { PromptDiff } from "./PromptDiff";

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
    setStatusMessage(null);
  };

  const handleSave = () => {
    saveMutation.mutate(editedContent);
  };

  const handleReset = () => {
    if (window.confirm(t("settings.prompts.confirmReset"))) {
      resetMutation.mutate();
    }
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
      {/* Header */}
      <div className="mb-6">
        <button
          type="button"
          onClick={onBack}
          className="text-sm text-muted-foreground hover:text-foreground transition-colors mb-2"
        >
          {t("settings.prompts.back")}
        </button>
        <h2 className="text-xl font-medium">{promptId}</h2>
      </div>

      <div className="space-y-4">
        {/* Source indicator + update badge */}
        <div className="flex items-center gap-3">
          <span
            className={cn(
              "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold",
              prompt.is_overridden
                ? "bg-accent text-accent-foreground"
                : "bg-muted text-muted-foreground",
            )}
          >
            {prompt.is_overridden
              ? t("settings.prompts.sourceOverride")
              : t("settings.prompts.sourceBundled")}
          </span>
          {hasUpdate && (
            <button
              type="button"
              onClick={() => setShowDiff(true)}
              className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 hover:bg-amber-200 dark:hover:bg-amber-900/50 transition-colors"
            >
              {t("settings.prompts.updateAvailable")}
            </button>
          )}
        </div>

        {/* Status message */}
        {statusMessage && (
          <div
            className={cn(
              "rounded-md p-3 text-sm",
              statusMessage.type === "success"
                ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                : "bg-destructive/10 text-destructive",
            )}
            role="status"
          >
            {statusMessage.text}
          </div>
        )}

        {/* Content area */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex gap-6">
            {/* Main content */}
            <div className="flex-1 space-y-4">
              {editMode ? (
                <>
                  <label htmlFor="prompt-editor" className="block text-sm font-medium">
                    {t("settings.prompts.promptContent")}
                  </label>
                  <textarea
                    id="prompt-editor"
                    value={editedContent}
                    onChange={(e) => setEditedContent(e.target.value)}
                    className="w-full min-h-[400px] px-4 py-3 border border-border rounded-md bg-background text-sm font-mono resize-y focus:outline-none focus:ring-2 focus:ring-ring/15"
                  />
                  <div className="flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={() => setEditMode(false)}
                      className="px-6 py-2 bg-muted rounded-md hover:bg-accent transition-colors text-sm"
                    >
                      {t("settings.prompts.cancel")}
                    </button>
                    <button
                      type="button"
                      onClick={handleSave}
                      disabled={saveMutation.isPending}
                      className="px-6 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm disabled:opacity-50"
                    >
                      {saveMutation.isPending
                        ? t("settings.ai.loading")
                        : t("settings.prompts.saveOverride")}
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <label htmlFor="prompt-viewer" className="block text-sm font-medium">
                    {prompt.is_overridden
                      ? t("settings.prompts.promptContent")
                      : t("settings.prompts.baseContent")}
                  </label>
                  <div className="w-full min-h-[400px] px-4 py-3 border border-border rounded-md bg-background text-sm font-mono whitespace-pre-wrap overflow-auto">
                    {prompt.content}
                  </div>
                  <div className="flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={handleReset}
                      disabled={resetMutation.isPending || !prompt.is_overridden}
                      className="px-6 py-2 bg-muted rounded-md hover:bg-accent transition-colors text-sm disabled:opacity-50"
                    >
                      {resetMutation.isPending
                        ? t("settings.ai.loading")
                        : t("settings.prompts.resetToDefault")}
                    </button>
                    <button
                      type="button"
                      onClick={handleStartEdit}
                      className="px-6 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm"
                    >
                      {t("settings.prompts.editOverride")}
                    </button>
                  </div>
                </>
              )}
            </div>

            {/* Variables sidebar */}
            {prompt.variables.length > 0 && (
              <aside className="w-48 shrink-0">
                <h4 className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-3">
                  {t("settings.prompts.variables")}
                </h4>
                <ul className="space-y-1.5">
                  {prompt.variables.map((variable) => (
                    <li
                      key={variable}
                      className="px-3 py-1.5 rounded-md bg-muted text-xs font-mono text-muted-foreground"
                    >
                      {`{{${variable}}}`}
                    </li>
                  ))}
                </ul>
              </aside>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
