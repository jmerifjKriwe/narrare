"use client";

import { Loader2, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect } from "react";
import { useConfirmRemap, usePreviewRemap } from "@/lib/hooks/usePlanning";

interface StructureChangeDialogProps {
  open: boolean;
  novelId: string;
  newStructure: string;
  currentStructure: string;
  onClose: () => void;
  onCancel: () => void;
}

export function StructureChangeDialog({
  open,
  novelId,
  newStructure,
  currentStructure,
  onClose,
  onCancel,
}: StructureChangeDialogProps) {
  const t = useTranslations("studio");

  const previewMutation = usePreviewRemap(novelId, newStructure);
  const confirmMutation = useConfirmRemap(novelId, newStructure);

  // Fetch preview when dialog opens
  useEffect(() => {
    if (open) {
      previewMutation.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, previewMutation.mutate]);

  if (!open) return null;

  const preview = previewMutation.data;
  const isLoading = previewMutation.isPending || confirmMutation.isPending;

  /** Translate a stage ID using i18n for a given structure type. */
  function translateStage(stageId: string, structureType: string): string {
    if (!stageId) return stageId;
    try {
      return t(`storyboard.stages.${structureType}.${stageId}` as Parameters<typeof t>[0]);
    } catch {
      return stageId;
    }
  }

  function handleConfirm() {
    confirmMutation.mutate(undefined, {
      onSuccess: () => {
        onClose();
      },
    });
  }

  function handleCancel() {
    onCancel();
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div
        className="bg-card border border-border rounded-lg shadow-lg max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto"
        role="dialog"
        aria-modal="true"
        aria-label={t("storyboard.remap.title")}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-border">
          <h2 className="text-lg font-medium">{t("storyboard.remap.title")}</h2>
          <p className="text-sm text-muted-foreground mt-1">{t("storyboard.remap.description")}</p>
        </div>

        {/* Content */}
        <div className="px-6 py-4">
          {isLoading && !preview ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
            </div>
          ) : preview && preview.remapped.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4">{t("storyboard.remap.noChanges")}</p>
          ) : preview ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 font-medium">
                    {t("storyboard.remap.chapterTitle")}
                  </th>
                  <th className="text-left py-2 font-medium">
                    {t("storyboard.remap.currentStage")}
                  </th>
                  <th className="px-2 py-2">→</th>
                  <th className="text-left py-2 font-medium">{t("storyboard.remap.newStage")}</th>
                </tr>
              </thead>
              <tbody>
                {preview.remapped.map((item) => (
                  <tr key={item.chapter_id} className="border-b border-border/50">
                    <td className="py-2">{item.chapter_title}</td>
                    <td className="py-2 text-muted-foreground">
                      {translateStage(item.old_stage, currentStructure)}
                    </td>
                    <td className="px-2 py-2 text-muted-foreground">→</td>
                    <td className="py-2">
                      {translateStage(item.new_stage, newStructure)}
                      {item.ai_suggested_stage && item.ai_suggested_stage !== item.new_stage && (
                        <span className="ml-1 text-[10px] text-blue-500">
                          {t("storyboard.remap.aiSuggested")}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}

          {/* AI confidence badge */}
          {preview && preview.ai_confidence != null && preview.ai_confidence > 0 && (
            <div className="flex items-center gap-1.5 px-4 py-2 mt-3 bg-blue-50 dark:bg-blue-900/20 rounded-md text-xs text-blue-700 dark:text-blue-300">
              <Sparkles className="w-3.5 h-3.5" />
              {t("storyboard.remap.aiConfidence", {
                confidence: String(Math.round(preview.ai_confidence * 100)),
              })}
            </div>
          )}

          {previewMutation.isError && (
            <p className="text-sm text-destructive mt-2">
              {previewMutation.error?.message ?? "Failed to load preview"}
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-border flex justify-end gap-3">
          <button
            type="button"
            onClick={handleCancel}
            disabled={confirmMutation.isPending}
            className="px-4 py-2 text-sm rounded-md border border-border hover:bg-accent transition-colors disabled:opacity-50"
          >
            {t("storyboard.remap.cancel")}
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={confirmMutation.isPending || !preview || preview.remapped.length === 0}
            className="px-4 py-2 text-sm rounded-md bg-primary text-primary-foreground hover:opacity-90 transition-opacity shadow-sm disabled:opacity-50"
          >
            {confirmMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin inline-block" />
            ) : (
              t("storyboard.remap.confirm")
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
