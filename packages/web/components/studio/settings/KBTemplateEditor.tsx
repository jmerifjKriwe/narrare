"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";
import { TYPE_ICONS, TYPE_LABEL_KEYS } from "@/components/studio/kb/constants";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { templatesApi } from "@/lib/api/client";

// --- Types ---

interface KBTemplateEditorProps {
  readonly novelId: string;
  readonly entityType: string;
  readonly hasUpdate: boolean;
  readonly onBack: () => void;
}

// --- Component ---

export function KBTemplateEditor({
  novelId,
  entityType,
  hasUpdate,
  onBack,
}: KBTemplateEditorProps) {
  const t = useTranslations("studio");
  const queryClient = useQueryClient();
  const [content, setContent] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const pendingAction = useRef<(() => void) | null>(null);

  const {
    data: detail,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["kb-template", novelId, entityType],
    queryFn: () => templatesApi.get(novelId, entityType),
  });

  // Initialize content when detail loads
  if (detail && content === null) {
    setContent(detail.content);
  }

  const saveMutation = useMutation({
    mutationFn: () =>
      templatesApi.save(novelId, entityType, content ?? "", detail?.based_on_version ?? undefined),
    onSuccess: () => {
      setStatusMessage({ type: "success", text: t("kb.templateSaved") });
      queryClient.invalidateQueries({ queryKey: ["kb-templates", novelId] });
      queryClient.invalidateQueries({ queryKey: ["kb-template", novelId, entityType] });
    },
    onError: () => {
      setStatusMessage({ type: "error", text: t("kb.failedToSaveTemplate") });
    },
  });

  const resetMutation = useMutation({
    mutationFn: () => templatesApi.reset(novelId, entityType),
    onSuccess: () => {
      setStatusMessage({ type: "success", text: t("kb.templateReset") });
      setContent(null);
      queryClient.invalidateQueries({ queryKey: ["kb-templates", novelId] });
      queryClient.invalidateQueries({ queryKey: ["kb-template", novelId, entityType] });
    },
    onError: () => {
      setStatusMessage({ type: "error", text: t("kb.failedToResetTemplate") });
    },
  });

  const Icon = TYPE_ICONS[entityType as keyof typeof TYPE_ICONS];

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Error state
  if (error || !detail) {
    return (
      <div className="space-y-4">
        <div className="bg-destructive/10 text-destructive rounded-md p-3 text-sm" role="alert">
          {t("kb.failedToLoadTemplate")}
        </div>
        <button
          type="button"
          onClick={onBack}
          className="px-4 py-2 bg-muted rounded-md hover:bg-accent transition-colors text-sm"
        >
          {t("kb.back")}
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* Back button + header */}
      <div className="flex items-center gap-4 mb-6">
        <button
          type="button"
          onClick={onBack}
          className="p-2 hover:bg-accent rounded-md transition-colors"
          aria-label="Back to templates list"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        {Icon && <Icon className="w-5 h-5 text-muted-foreground" />}
        <div>
          <h2 className="text-xl font-medium">
            {t(TYPE_LABEL_KEYS[entityType as keyof typeof TYPE_LABEL_KEYS] ?? `kb.${entityType}s`)}{" "}
            {t("kb.template")}
          </h2>
          <p className="text-sm text-muted-foreground">
            {t("kb.templateVersion", { version: detail.schema_version })}
            {detail.is_overridden ? ` · ${t("kb.custom")}` : ` · ${t("kb.defaultLabel")}`}
            {hasUpdate && ` · ${t("kb.updateAvailable")}`}
          </p>
        </div>
      </div>

      {/* Editor card */}
      <div className="bg-card border border-border rounded-lg">
        {/* Status message */}
        {statusMessage && (
          <div
            className={`mx-4 mt-4 rounded-md p-3 text-sm ${
              statusMessage.type === "success"
                ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                : "bg-destructive/10 text-destructive"
            }`}
            role="status"
          >
            {statusMessage.text}
          </div>
        )}

        <textarea
          value={content ?? ""}
          onChange={(e) => setContent(e.target.value)}
          className="w-full h-[60vh] p-4 bg-transparent text-sm font-mono resize-y focus:outline-none"
          spellCheck={false}
          aria-label="Template content editor"
        />

        {/* Actions */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-border">
          <button
            type="button"
            onClick={() => {
              pendingAction.current = () => resetMutation.mutate();
              setShowResetConfirm(true);
            }}
            disabled={!detail.is_overridden || resetMutation.isPending}
            className="px-4 py-2 text-sm text-destructive border border-destructive/30 rounded-md hover:bg-destructive/5 disabled:opacity-50"
          >
            {resetMutation.isPending ? t("kb.resetting") : t("kb.resetToDefault")}
          </button>

          <button
            type="button"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending || !content}
            className="px-5 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm font-medium disabled:opacity-50"
          >
            {saveMutation.isPending ? t("kb.saving") : t("kb.save")}
          </button>
        </div>
      </div>

      {/* Reset confirmation */}
      <ConfirmDialog
        open={showResetConfirm}
        onOpenChange={setShowResetConfirm}
        title={t("kb.resetToDefault")}
        description={t("kb.resetToDefaultConfirm")}
        confirmLabel={t("kb.resetToDefault")}
        variant="destructive"
        onConfirm={() => {
          pendingAction.current?.();
          pendingAction.current = null;
          setShowResetConfirm(false);
        }}
      />
    </div>
  );
}
