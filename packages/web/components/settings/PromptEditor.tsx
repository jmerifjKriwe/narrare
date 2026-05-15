"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { promptsApi } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { PromptDiff } from "./PromptDiff";

interface PromptEditorProps {
  readonly promptId: string;
  readonly hasUpdate: boolean;
  readonly onBack: () => void;
}

export function PromptEditor({ promptId, hasUpdate, onBack }: PromptEditorProps) {
  const t = useTranslations("settings");
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
      setStatusMessage({ type: "success", text: t("saveSuccess") });
      setEditMode(false);
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
      queryClient.invalidateQueries({ queryKey: ["prompt", promptId] });
    },
    onError: () => {
      setStatusMessage({ type: "error", text: t("saveFailed") });
    },
  });

  const resetMutation = useMutation({
    mutationFn: () => promptsApi.reset(promptId),
    onSuccess: () => {
      setStatusMessage({ type: "success", text: t("resetSuccess") });
      setEditMode(false);
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
      queryClient.invalidateQueries({ queryKey: ["prompt", promptId] });
      queryClient.invalidateQueries({ queryKey: ["prompts-updates"] });
    },
    onError: () => {
      setStatusMessage({ type: "error", text: t("resetFailed") });
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
    if (window.confirm(t("confirmReset"))) {
      resetMutation.mutate();
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <p className="text-[var(--color-text-tertiary)] text-[0.875rem]">{t("loadingPrompt")}</p>
      </div>
    );
  }

  if (error || !prompt) {
    return (
      <div className="flex flex-col gap-4">
        <div
          className="bg-[var(--color-error)]/10 text-[var(--color-error)] rounded-lg p-3 text-[0.875rem]"
          role="alert"
        >
          {t("loadFailed")}
        </div>
        <Button variant="secondary" onClick={onBack}>
          {t("back")}
        </Button>
      </div>
    );
  }

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

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={onBack}
          className="text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors text-[0.875rem]"
          aria-label={t("backToPrompts")}
        >
          {t("back")}
        </button>
        <h2 className="text-xl font-semibold text-[var(--color-text-primary)]">{promptId}</h2>
      </div>

      {/* Source indicator */}
      <div className="flex items-center gap-3">
        <span
          className={cn(
            "inline-flex items-center px-2.5 py-0.5 rounded-full text-[0.75rem] font-semibold",
            prompt.is_overridden
              ? "bg-[var(--color-accent-light)] text-[var(--color-accent)]"
              : "bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)]",
          )}
        >
          {prompt.is_overridden ? t("sourceOverride") : t("sourceBundled")}
        </span>
        {hasUpdate && (
          <button
            type="button"
            onClick={() => setShowDiff(true)}
            className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[0.75rem] font-semibold bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400 hover:bg-orange-200 dark:hover:bg-orange-900/50 transition-colors"
          >
            {t("updateAvailable")}
          </button>
        )}
      </div>

      {/* Status message */}
      {statusMessage && (
        <div
          className={cn(
            "rounded-lg p-3 text-[0.875rem]",
            statusMessage.type === "success"
              ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
              : "bg-[var(--color-error)]/10 text-[var(--color-error)]",
          )}
          role="status"
        >
          {statusMessage.text}
        </div>
      )}

      {/* Content area */}
      <div className="flex gap-6">
        {/* Main content */}
        <div className="flex-1 flex flex-col gap-4">
          {editMode ? (
            <>
              <label
                htmlFor="prompt-editor"
                className="text-[0.75rem] font-semibold uppercase tracking-[0.1em] text-[var(--color-text-tertiary)]"
              >
                {t("promptContent")}
              </label>
              <textarea
                id="prompt-editor"
                value={editedContent}
                onChange={(e) => setEditedContent(e.target.value)}
                className="w-full min-h-[400px] px-4 py-3 border border-[var(--color-border)] rounded-xl bg-[var(--color-surface)] text-[var(--color-text-primary)] text-[0.875rem] font-mono transition-all duration-200 outline-none focus:border-[var(--color-accent)] focus:ring-2 focus:ring-[var(--color-accent)]/15 resize-y"
              />
              <div className="flex justify-end gap-3">
                <Button variant="secondary" onClick={() => setEditMode(false)}>
                  {t("cancel")}
                </Button>
                <Button onClick={handleSave} loading={saveMutation.isPending}>
                  {t("saveOverride")}
                </Button>
              </div>
            </>
          ) : (
            <>
              <label
                htmlFor="prompt-viewer"
                className="text-[0.75rem] font-semibold uppercase tracking-[0.1em] text-[var(--color-text-tertiary)]"
              >
                {prompt.is_overridden ? t("promptContent") : t("baseContent")}
              </label>
              <div
                id="prompt-viewer"
                className="w-full min-h-[400px] px-4 py-3 border border-[var(--color-border)] rounded-xl bg-[var(--color-bg-secondary)] text-[var(--color-text-primary)] text-[0.875rem] font-mono whitespace-pre-wrap overflow-auto"
              >
                {prompt.content}
              </div>
              <div className="flex justify-end gap-3">
                <Button
                  variant="danger"
                  onClick={handleReset}
                  loading={resetMutation.isPending}
                  disabled={!prompt.is_overridden}
                >
                  {t("resetToDefault")}
                </Button>
                <Button onClick={handleStartEdit}>{t("editOverride")}</Button>
              </div>
            </>
          )}
        </div>

        {/* Variables sidebar */}
        <PromptVariables variables={prompt.variables} />
      </div>
    </div>
  );
}

function PromptVariables({ variables }: { readonly variables: string[] }) {
  const t = useTranslations("settings");

  if (variables.length === 0) return null;

  return (
    <aside className="w-52 shrink-0">
      <h4 className="text-[0.75rem] font-semibold uppercase tracking-[0.1em] text-[var(--color-text-tertiary)] mb-3">
        {t("variables")}
      </h4>
      <ul className="flex flex-col gap-1.5">
        {variables.map((variable) => (
          <li
            key={variable}
            className="px-3 py-1.5 rounded-lg bg-[var(--color-bg-secondary)] text-[0.8125rem] font-mono text-[var(--color-text-secondary)]"
          >
            {`{{${variable}}}`}
          </li>
        ))}
      </ul>
    </aside>
  );
}
