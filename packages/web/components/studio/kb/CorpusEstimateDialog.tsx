"use client";

import * as AlertDialog from "@radix-ui/react-alert-dialog";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect } from "react";
import { bulkExtractionApi, isSplitFirstBulkError } from "@/lib/api/bulkExtraction";
import { useCorpusPassStart } from "@/lib/hooks/useCorpusPassStart";

/**
 * CorpusEstimateDialog — honest pre-run confirm for the corpus pass
 * (F3, plan Task 4; spec §4.3/§8, D20a).
 *
 * Fetches the estimate when opened (loading / load-error / 422 split-first
 * degrade states) and renders it verbatim: `"{chapter_count} chapters (of
 * {total_chapters}) · {word_count} words · {ai_calls} AI calls"` — the
 * "(of N)" clause ONLY when capped — plus the pacing note (D7a: one call per
 * chapter, shared budget) and, when a D20a cap truncated the selection, the
 * `cap_reason`-keyed explanation of what remains. `Start` →
 * `startCorpusPass` → `onStart(job_id)`; the caller owns closing the dialog
 * and mounting `BulkExtractionPanel` with the started job id.
 *
 * The cap values are display mirrors of the protocol constants in
 * `apps/api/narrare/kb/bulk_extraction/corpus.py` (RULE-18b — no settings
 * surface; pinned by tests on BOTH sides, plan contract table "Caps").
 */
const CORPUS_PASS_MAX_CHAPTERS = 120;
const CORPUS_PASS_MAX_WORDS = 200_000;

interface CorpusEstimateDialogProps {
  readonly novelId: string;
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  /** Called with the started corpus job id (spec §8 — opens the F2 panel). */
  readonly onStart: (jobId: string) => void;
}

export function CorpusEstimateDialog({
  novelId,
  open,
  onOpenChange,
  onStart,
}: CorpusEstimateDialogProps) {
  const t = useTranslations("studio");
  // Start action owned by the shared corpus-start hook (used by the panel's
  // restart too); the raw error is classified, the UI shows catalog copy.
  const { isStarting, startError, isSplitFirst, start, clearError } = useCorpusPassStart(novelId);

  // Estimate fetch is bound to the open state: every reopen re-fetches (the
  // server re-validates at start time anyway — the dialog must not show a
  // stale cache as current truth).
  const estimateQuery = useQuery({
    queryKey: ["novels", novelId, "kb", "corpus-estimate"],
    queryFn: ({ signal }) => bulkExtractionApi.corpusEstimate(novelId, signal),
    enabled: open,
  });

  // Reopening starts the start-action fresh — a stale error must never
  // resurface for a start the user already saw fail.
  useEffect(() => {
    if (open) clearError();
  }, [open, clearError]);

  const estimate = estimateQuery.data ?? null;
  const estimateSplitFirst = estimateQuery.isError && isSplitFirstBulkError(estimateQuery.error);

  const handleStart = async () => {
    const jobId = await start();
    if (jobId !== null) onStart(jobId);
  };

  const remaining = estimate === null ? 0 : estimate.total_chapters - estimate.chapter_count;

  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm" />
        <AlertDialog.Content className="fixed left-1/2 top-1/2 z-50 flex w-full max-w-xl -translate-x-1/2 -translate-y-1/2 flex-col rounded-xl border border-border bg-card p-6 shadow-2xl">
          <AlertDialog.Title className="text-lg font-medium text-foreground">
            {t("kb.corpusPass.title")}
          </AlertDialog.Title>

          {estimateQuery.isPending && (
            <AlertDialog.Description
              className="mt-3 text-sm text-muted-foreground"
              data-testid="corpus-estimate-loading"
            >
              {t("kb.corpusPass.loading")}
            </AlertDialog.Description>
          )}

          {estimateQuery.isError && (
            <AlertDialog.Description
              className="mt-3 text-sm"
              role="alert"
              data-testid={
                estimateSplitFirst ? "corpus-split-first-error" : "corpus-estimate-error"
              }
            >
              {estimateSplitFirst
                ? t("kb.corpusPass.splitFirstError")
                : t("kb.corpusPass.loadFailed")}
            </AlertDialog.Description>
          )}
          {estimateQuery.isError && !estimateSplitFirst && (
            <div className="mt-4 flex justify-end">
              <button
                type="button"
                data-testid="corpus-estimate-retry"
                onClick={() => void estimateQuery.refetch()}
                className="rounded-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground hover:bg-accent transition-colors"
              >
                {t("kb.corpusPass.retry")}
              </button>
            </div>
          )}

          {estimate !== null && (
            <>
              {/* The honest line (spec §4.3) — the "(of N)" clause renders
                  only when a cap truncated the selection. */}
              <p className="mt-3 text-sm font-medium" data-testid="corpus-estimate-line">
                {t("kb.corpusPass.estimateLine", {
                  chapterCount: estimate.chapter_count,
                  wordCount: estimate.word_count,
                  aiCalls: estimate.ai_calls,
                  ofTotal: estimate.capped
                    ? t("kb.corpusPass.ofTotal", { total: estimate.total_chapters })
                    : "",
                })}
              </p>
              {estimate.capped && (
                <p className="mt-2 text-sm text-muted-foreground" data-testid="corpus-cap-note">
                  {estimate.cap_reason === "chapters"
                    ? t("kb.corpusPass.cappedChapters", {
                        max: CORPUS_PASS_MAX_CHAPTERS,
                        remaining,
                      })
                    : t("kb.corpusPass.cappedWords", {
                        max: CORPUS_PASS_MAX_WORDS,
                        remaining,
                      })}
                </p>
              )}
              <AlertDialog.Description
                className="mt-3 text-xs text-muted-foreground"
                data-testid="corpus-pacing-note"
              >
                {t("kb.corpusPass.pacingNote")}
              </AlertDialog.Description>

              {startError !== null && (
                <p
                  role="alert"
                  className="mt-3 text-sm text-destructive"
                  data-testid={isSplitFirst ? "corpus-split-first-error" : "corpus-start-error"}
                >
                  {isSplitFirst
                    ? t("kb.corpusPass.splitFirstError")
                    : t("kb.corpusPass.startFailed")}
                </p>
              )}

              <div className="mt-6 flex justify-end gap-3">
                <AlertDialog.Cancel
                  data-testid="corpus-estimate-cancel-btn"
                  className="rounded-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground hover:bg-accent transition-colors"
                >
                  {t("kb.corpusPass.cancel")}
                </AlertDialog.Cancel>
                <button
                  type="button"
                  data-testid="corpus-estimate-start-btn"
                  onClick={() => void handleStart()}
                  disabled={isStarting}
                  className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
                >
                  {t("kb.corpusPass.start")}
                </button>
              </div>
            </>
          )}
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}
