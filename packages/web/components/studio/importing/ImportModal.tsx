"use client";

import * as AlertDialog from "@radix-ui/react-alert-dialog";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { importApi } from "@/lib/api/client";
import { buildAdjustments } from "@/lib/importing/simulateOperations";
import type { ImportSelection } from "@/types";
import { ImportPreviewPanel } from "./ImportPreviewPanel";

/**
 * Import dialog for EXISTING novels (sidebar entry). Commit + chapters-query
 * invalidation + failure-flag cleanup live here; the panel is shared with
 * the wizard (spec §6). Alert-dialog semantics are intentional: the append
 * is irreversible (no undo).
 */
interface ImportModalProps {
  readonly novelId: string;
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
}

export function ImportModal({ novelId, open, onOpenChange }: ImportModalProps) {
  const t = useTranslations("importing");
  const queryClient = useQueryClient();
  const [selection, setSelection] = useState<ImportSelection | null>(null);
  const [isCommitting, setIsCommitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCommit = async () => {
    if (!selection || selection.includedCount === 0) return;
    setIsCommitting(true);
    setError(null);
    try {
      await importApi.commit(selection.files, novelId, buildAdjustments(selection));
      sessionStorage.removeItem(`narrare:importFailed:${novelId}`);
      await queryClient.invalidateQueries({ queryKey: ["novels", novelId, "chapters"] });
      onOpenChange(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsCommitting(false);
    }
  };

  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm" />
        <AlertDialog.Content className="fixed left-1/2 top-1/2 z-50 flex w-full max-w-xl -translate-x-1/2 -translate-y-1/2 flex-col rounded-xl border border-border bg-card p-6 shadow-2xl">
          <AlertDialog.Title className="text-lg font-medium text-foreground">
            {t("title")}
          </AlertDialog.Title>
          <AlertDialog.Description className="mt-1 text-sm text-muted-foreground">
            {t("description")}
          </AlertDialog.Description>

          <div className="mt-4">
            <ImportPreviewPanel onSelectionChange={setSelection} />
          </div>

          {error && (
            <p
              className="bg-destructive/10 text-destructive mt-3 rounded-lg p-3 text-sm"
              role="alert"
            >
              {t("errors.commitFailed", { message: error })}
            </p>
          )}

          <div className="mt-6 flex justify-end gap-3">
            <AlertDialog.Cancel asChild>
              <button
                type="button"
                className="rounded-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground hover:bg-accent transition-colors"
              >
                {t("cancel")}
              </button>
            </AlertDialog.Cancel>
            <button
              type="button"
              data-testid="import-commit-btn"
              disabled={!selection || selection.includedCount === 0 || isCommitting}
              onClick={() => void handleCommit()}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {isCommitting
                ? t("importing")
                : selection
                  ? t("confirm", { count: selection.includedCount })
                  : t("confirm", { count: 0 })}
            </button>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}
