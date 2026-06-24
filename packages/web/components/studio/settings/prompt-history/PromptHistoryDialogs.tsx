"use client";

/**
 * PromptHistoryDialogs — the restore + clear confirmation dialogs (CR-AUFG-07-19).
 *
 * Purely presentational: receives controlled open-state and confirm callbacks.
 * Split out of :component:`PromptHistoryPanel` for RULE-04 (the panel orchestrates
 * state + data; this owns only the destructive-action confirmations). The
 * caller decides WHEN to open each dialog and WHAT happens on confirm.
 */
import { useTranslations } from "next-intl";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

interface PromptHistoryDialogsProps {
  /** Restore dialog open state. */
  readonly restoreOpen: boolean;
  readonly onRestoreOpenChange: (open: boolean) => void;
  readonly onRestoreConfirm: () => void;
  /** Clear dialog open state. */
  readonly clearOpen: boolean;
  readonly onClearOpenChange: (open: boolean) => void;
  readonly onClearConfirm: () => void;
}

export function PromptHistoryDialogs({
  restoreOpen,
  onRestoreOpenChange,
  onRestoreConfirm,
  clearOpen,
  onClearOpenChange,
  onClearConfirm,
}: PromptHistoryDialogsProps) {
  const t = useTranslations("studio");

  return (
    <>
      {/* Restore confirmation */}
      <ConfirmDialog
        open={restoreOpen}
        onOpenChange={onRestoreOpenChange}
        title={t("settings.prompts.promptHistory.restoreConfirmTitle")}
        description={t("settings.prompts.promptHistory.restoreConfirmDescription")}
        confirmLabel={t("settings.prompts.promptHistory.restore")}
        onConfirm={onRestoreConfirm}
      />

      {/* Clear confirmation (destructive) */}
      <ConfirmDialog
        open={clearOpen}
        onOpenChange={onClearOpenChange}
        title={t("settings.prompts.promptHistory.clearConfirmTitle")}
        description={t("settings.prompts.promptHistory.clearConfirmDescription")}
        confirmLabel={t("settings.prompts.promptHistory.clear")}
        onConfirm={onClearConfirm}
        variant="destructive"
      />
    </>
  );
}
