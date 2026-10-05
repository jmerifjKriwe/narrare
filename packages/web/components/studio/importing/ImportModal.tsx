"use client";

import * as AlertDialog from "@radix-ui/react-alert-dialog";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { importApi } from "@/lib/api/client";
import { buildAdjustments } from "@/lib/importing/simulateOperations";
import type { ImportCommitResponse, ImportSelection } from "@/types";
import { ImportPreviewPanel } from "./ImportPreviewPanel";

/**
 * Import dialog for EXISTING novels (sidebar entry). Commit + chapters-query
 * invalidation + failure-flag cleanup live here; the panel is shared with
 * the wizard (spec §6). Alert-dialog semantics are intentional: the append
 * is irreversible (no undo).
 *
 * Post-commit CTA (F2 T8, ADR-092 spec §8.1, D9a): a successful commit no
 * longer closes the dialog immediately. It first shows a success card with
 * the cost of a bulk extraction (chapters · words · AI calls, straight from
 * the commit response) and two actions — "Extract to Knowledge Base" (closes
 * + hands the committed chapter ids to the parent, which mounts
 * `BulkExtractionPanel`) and "Not now" (plain close). The suggestion is
 * opt-in here; the wizard path uses the sessionStorage flag instead.
 */
interface ImportModalProps {
  readonly novelId: string;
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  /** Called with the committed chapter ids when the user accepts the CTA. */
  readonly onExtract?: (chapterIds: string[]) => void;
}

export function ImportModal({ novelId, open, onOpenChange, onExtract }: ImportModalProps) {
  const t = useTranslations("importing");
  const queryClient = useQueryClient();
  const [selection, setSelection] = useState<ImportSelection | null>(null);
  const [isCommitting, setIsCommitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<ImportCommitResponse | null>(null);

  // Reopening the dialog starts fresh — a stale success card must never
  // resurface for a commit the user already acted on.
  useEffect(() => {
    if (open) setSuccess(null);
  }, [open]);

  const totalWords = success?.chapters.reduce((sum, c) => sum + c.word_count, 0) ?? 0;

  const handleCommit = async () => {
    if (!selection || selection.includedCount === 0) return;
    setIsCommitting(true);
    setError(null);
    try {
      const result = await importApi.commit(selection.files, novelId, buildAdjustments(selection));
      sessionStorage.removeItem(`narrare:importFailed:${novelId}`);
      await queryClient.invalidateQueries({ queryKey: ["novels", novelId, "chapters"] });
      setSuccess(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsCommitting(false);
    }
  };

  const handleExtract = () => {
    if (!success) return;
    const chapterIds = success.chapters.map((c) => c.id);
    setSuccess(null);
    onOpenChange(false);
    onExtract?.(chapterIds);
  };

  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm" />
        <AlertDialog.Content className="fixed left-1/2 top-1/2 z-50 flex w-full max-w-xl -translate-x-1/2 -translate-y-1/2 flex-col rounded-xl border border-border bg-card p-6 shadow-2xl">
          {success ? (
            <>
              <AlertDialog.Title
                className="text-lg font-medium text-foreground"
                data-testid="import-success-card"
              >
                <span aria-hidden="true" className="text-primary">
                  ✓{" "}
                </span>
                {t("suggestExtract.successTitle", { count: success.chapters.length })}
              </AlertDialog.Title>
              <AlertDialog.Description className="mt-1 text-sm text-muted-foreground">
                {t("suggestExtract.costLine", {
                  chapters: success.chapters.length,
                  words: totalWords,
                  calls: success.chapters.length,
                })}
              </AlertDialog.Description>

              <div className="mt-6 flex justify-end gap-3">
                <button
                  type="button"
                  data-testid="import-notnow-btn"
                  onClick={() => onOpenChange(false)}
                  className="rounded-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground hover:bg-accent transition-colors"
                >
                  {t("suggestExtract.notNow")}
                </button>
                {/* Nothing imported → nothing to extract: plain close only. */}
                {success.chapters.length > 0 && (
                  <button
                    type="button"
                    data-testid="import-extract-btn"
                    onClick={handleExtract}
                    className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
                  >
                    {t("suggestExtract.start")}
                  </button>
                )}
              </div>
              <p className="mt-3 text-xs text-muted-foreground">{t("suggestExtract.pacingNote")}</p>
            </>
          ) : (
            <>
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
            </>
          )}
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}
