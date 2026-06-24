"use client";

/**
 * PromptHistoryPanel — orchestrator for the prompt revision history (CR-AUFG-07-19).
 *
 * Composes the existing building blocks into a single collapsible surface:
 *   - :func:`usePromptHistory` (data layer: list / compare / restore / clear).
 *   - :component:`PromptHistoryList` (presentational revision rows + restore).
 *   - :component:`PromptHistoryCompare` (from/to selector + shared AIDiffView).
 *   - :component:`PromptHistoryDialogs` (restore + clear confirmations).
 *
 * The panel is UI-only: it wires confirmations and success/error toasts
 * (sonner) and leaves data fetching to the hook. ``onRestored`` lets the parent
 * (:component:`PromptEditor`) invalidate the prompt-detail query so the editor
 * reflects the restored active content.
 *
 * RULE-04: stays lean by delegating list rows to PromptHistoryList and the
 * compare surface to PromptHistoryCompare. RULE-17: ``scope`` is never sent.
 */
import { ChevronDown, ChevronRight, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";
import type { PromptRevision } from "@/types";
import { PromptHistoryCompare } from "./PromptHistoryCompare";
import { PromptHistoryDialogs } from "./PromptHistoryDialogs";
import { PromptHistoryList } from "./PromptHistoryList";
import { PromptHistoryStatus } from "./PromptHistoryStatus";
import { usePromptHistory } from "./usePromptHistory";

interface PromptHistoryPanelProps {
  readonly promptId: string;
  /** Called after a successful restore (e.g. invalidate prompt-detail query). */
  readonly onRestored?: () => void;
  /** Called after history is cleared. */
  readonly onCleared?: () => void;
}

export function PromptHistoryPanel({ promptId, onRestored, onCleared }: PromptHistoryPanelProps) {
  const t = useTranslations("studio");
  const [expanded, setExpanded] = useState(false);
  const [restoreTarget, setRestoreTarget] = useState<PromptRevision | null>(null);
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  const h = usePromptHistory(promptId, { onRestored, onCleared });

  const revisions = h.list.data?.revisions ?? [];
  const total = h.list.data?.total ?? 0;
  const isEmpty = h.list.isSuccess && revisions.length === 0;
  const isRestoring = h.restoreMutation.isPending;

  const handleConfirmRestore = (): void => {
    const target = restoreTarget;
    if (!target) return;
    h.restoreMutation.mutate(target.id, {
      onSuccess: () => {
        toast.success(t("settings.prompts.promptHistory.restoreSuccess"));
        setRestoreTarget(null);
      },
      onError: () => {
        toast.error(t("settings.prompts.promptHistory.restoreFailed"));
        setRestoreTarget(null);
      },
    });
  };

  const handleConfirmClear = (): void => {
    setShowClearConfirm(false);
    h.clearMutation.mutate(undefined, {
      onSuccess: () => toast.success(t("settings.prompts.promptHistory.clearSuccess")),
      onError: () => toast.error(t("settings.prompts.promptHistory.clearFailed")),
    });
  };

  return (
    <section
      className="mt-6 rounded-lg border border-border bg-card p-4"
      aria-label={t("settings.prompts.promptHistory.title")}
    >
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-medium text-foreground">
            {t("settings.prompts.promptHistory.title")}
          </h3>
          <p className="text-xs text-muted-foreground">
            {t("settings.prompts.promptHistory.description")}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="inline-flex shrink-0 items-center gap-1 rounded-md bg-muted px-3 py-1.5 text-xs hover:bg-accent transition-colors"
        >
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
          {expanded
            ? t("settings.prompts.promptHistory.collapse")
            : t("settings.prompts.promptHistory.expand")}
          {!expanded && h.list.data
            ? ` · ${t("settings.prompts.promptHistory.count", { count: total })}`
            : ""}
        </button>
      </header>

      {expanded && (
        <div className="mt-4 space-y-4">
          {h.list.isLoading && <PromptHistoryStatus status="loading" />}

          {h.list.isError && (
            <PromptHistoryStatus status="error" onRetry={() => void h.list.refetch()} />
          )}

          {isEmpty && <PromptHistoryStatus status="empty" />}

          {!h.list.isLoading && !h.list.isError && !isEmpty && (
            <>
              <div className="flex items-center justify-between gap-3">
                <span className="text-xs text-muted-foreground">
                  {t("settings.prompts.promptHistory.count", { count: total })}
                </span>
                <button
                  type="button"
                  onClick={() => setShowClearConfirm(true)}
                  disabled={h.clearMutation.isPending}
                  className="inline-flex items-center gap-1 rounded-md bg-muted px-3 py-1.5 text-xs text-muted-foreground hover:bg-accent hover:text-foreground transition-colors disabled:opacity-50"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  {h.clearMutation.isPending
                    ? t("settings.prompts.promptHistory.clearing")
                    : t("settings.prompts.promptHistory.clear")}
                </button>
              </div>

              <PromptHistoryList
                revisions={revisions}
                onRestore={setRestoreTarget}
                isRestorePending={isRestoring}
                restoringId={isRestoring ? (restoreTarget?.id ?? null) : null}
              />

              <PromptHistoryCompare
                revisions={revisions}
                fromId={h.fromId}
                toId={h.toId}
                onFromChange={h.setFromId}
                onToChange={h.setToId}
                compare={h.compare.data}
                isLoading={h.compare.isLoading}
                isError={h.compare.isError}
              />
            </>
          )}
        </div>
      )}

      <PromptHistoryDialogs
        restoreOpen={restoreTarget !== null && !isRestoring}
        onRestoreOpenChange={(open) => {
          if (!open) setRestoreTarget(null);
        }}
        onRestoreConfirm={handleConfirmRestore}
        clearOpen={showClearConfirm}
        onClearOpenChange={setShowClearConfirm}
        onClearConfirm={handleConfirmClear}
      />
    </section>
  );
}
