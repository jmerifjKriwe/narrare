"use client";

/**
 * BulkProgressView — PROGRESS mode of `BulkExtractionPanel` (F2 T7): totals
 * summary, per-chapter rows with state chips (item counts when done, error
 * text when failed), start/retry error affordance, and cancel.
 *
 * @module BulkProgressView
 */

import { useTranslations } from "next-intl";
import type {
  BulkChapterStatusView,
  BulkExtractionTotals,
  BulkJobStatus,
} from "@/lib/api/bulkExtraction";
import { BulkStateChip } from "./BulkStateChip";

interface BulkProgressViewProps {
  readonly title: string;
  readonly totals: BulkExtractionTotals | null;
  readonly chapters: readonly BulkChapterStatusView[];
  readonly jobStatus: BulkJobStatus | null;
  readonly error: string | null;
  readonly isStarting: boolean;
  readonly onCancel: () => void;
  /** Restart the seed list after a failed start (no job id yet). */
  readonly onRetryStart: () => void;
}

export function BulkProgressView({
  title,
  totals,
  chapters,
  jobStatus,
  error,
  isStarting,
  onCancel,
  onRetryStart,
}: BulkProgressViewProps) {
  const t = useTranslations("studio");

  return (
    <section aria-label={title} className="space-y-4">
      {totals === null && chapters.length === 0 ? (
        <p className="text-sm">{t("kb.bulkExtraction.starting")}</p>
      ) : (
        <>
          <p className="text-lg font-medium">
            {t("kb.bulkExtraction.chaptersDone", {
              done: totals?.done ?? 0,
              total: totals?.total ?? 0,
            })}
          </p>
          <ul className="space-y-2">
            {chapters.map((c) => (
              <li
                key={c.chapter_id}
                className="flex items-center justify-between gap-3 p-2 rounded-md border border-border"
              >
                <span className="text-sm truncate">{c.title}</span>
                <span className="flex items-center gap-2 shrink-0">
                  {c.state === "done" && (
                    <span className="text-xs text-muted-foreground">
                      {t("kb.extractionResultsSummary", { count: c.item_count ?? 0 })}
                    </span>
                  )}
                  {c.state === "failed" && c.error !== null && (
                    <span className="text-xs text-destructive truncate max-w-48" title={c.error}>
                      {c.error}
                    </span>
                  )}
                  <BulkStateChip state={c.state} />
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
      {error !== null && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      {error !== null && jobStatus === null && (
        <button
          type="button"
          onClick={onRetryStart}
          className="text-sm text-primary hover:underline"
        >
          {t("kb.extractionRetry")}
        </button>
      )}
      <div className="flex justify-end pt-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={jobStatus === "cancelling" || isStarting}
          className="px-4 py-2 text-sm rounded-md border border-border hover:bg-accent disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {jobStatus === "cancelling"
            ? t("kb.bulkExtraction.cancelling")
            : t("kb.bulkExtraction.cancel")}
        </button>
      </div>
    </section>
  );
}
