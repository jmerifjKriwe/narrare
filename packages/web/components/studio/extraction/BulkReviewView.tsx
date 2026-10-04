"use client";

/**
 * BulkReviewView — REVIEW mode of `BulkExtractionPanel` (F2 T7): resume
 * banner for cancelled/failed jobs, position-ordered chapter rail with
 * applied/skipped badges, the active chapter's review body (`BulkChapterReview`
 * reusing the single-chapter review stack), and the next-unreviewed walking
 * footer.
 *
 * @module BulkReviewView
 */

import { useTranslations } from "next-intl";
import type { BulkChapterStatusView, BulkJobStatus } from "@/lib/api/bulkExtraction";
import type { ExtractionOutput } from "@/lib/api/extraction";
import { BulkChapterReview } from "./BulkChapterReview";
import { BulkStateChip } from "./BulkStateChip";

interface BulkReviewViewProps {
  readonly novelId: string;
  readonly title: string;
  readonly jobStatus: BulkJobStatus | null;
  readonly statusError: string | null;
  readonly chapters: readonly BulkChapterStatusView[];
  readonly activeChapter: BulkChapterStatusView | null;
  readonly appliedIds: ReadonlySet<string>;
  readonly skippedIds: ReadonlySet<string>;
  readonly unreviewedCount: number;
  readonly nextChapter: BulkChapterStatusView | null;
  readonly resultsPending: boolean;
  /** Results fetch failed or the active chapter has no output. */
  readonly resultsFailed: boolean;
  readonly activeOutput: ExtractionOutput | null;
  readonly onSelectChapter: (chapterId: string) => void;
  readonly onApplied: (chapterId: string) => void;
  readonly onSkipped: (chapterId: string) => void;
  readonly onRetryResults: () => void;
  readonly onResume: () => void;
}

export function BulkReviewView({
  novelId,
  title,
  jobStatus,
  statusError,
  chapters,
  activeChapter,
  appliedIds,
  skippedIds,
  unreviewedCount,
  nextChapter,
  resultsPending,
  resultsFailed,
  activeOutput,
  onSelectChapter,
  onApplied,
  onSkipped,
  onRetryResults,
  onResume,
}: BulkReviewViewProps) {
  const t = useTranslations("studio");

  return (
    <section aria-label={title} className="space-y-4">
      {(jobStatus === "cancelled" || jobStatus === "failed") && (
        <div className="flex items-center justify-between gap-3 p-3 rounded-md border border-border bg-muted/30">
          <div className="min-w-0">
            <p className="text-sm font-medium">
              {jobStatus === "cancelled"
                ? t("kb.bulkExtraction.cancelled")
                : t("kb.bulkExtraction.stateFailed")}
            </p>
            {statusError !== null && (
              <p className="text-sm text-destructive truncate">{statusError}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onResume}
            className="px-4 py-2 text-sm rounded-md border border-border hover:bg-accent transition-colors shrink-0"
          >
            {t("kb.bulkExtraction.resume")}
          </button>
        </div>
      )}

      {/* Chapter rail, position-ordered, with ✓/– review badges */}
      <ul className="space-y-2">
        {chapters.map((c) => (
          <li key={c.chapter_id}>
            <button
              type="button"
              onClick={() => onSelectChapter(c.chapter_id)}
              disabled={c.state !== "done"}
              aria-current={activeChapter?.chapter_id === c.chapter_id || undefined}
              className="w-full flex items-center justify-between gap-3 p-2 rounded-md border border-border text-left hover:bg-accent/50 disabled:opacity-60 disabled:cursor-not-allowed transition-colors data-[active=true]:border-primary data-[active=true]:bg-accent/30"
              data-active={activeChapter?.chapter_id === c.chapter_id || undefined}
            >
              <span className="text-sm truncate">{c.title}</span>
              <span className="flex items-center gap-2 shrink-0">
                {appliedIds.has(c.chapter_id) && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary">
                    <span aria-hidden="true">✓</span> <span>{t("kb.bulkExtraction.applied")}</span>
                  </span>
                )}
                {skippedIds.has(c.chapter_id) && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                    <span aria-hidden="true">–</span> <span>{t("kb.bulkExtraction.skipped")}</span>
                  </span>
                )}
                {c.state === "done" && (
                  <span className="text-xs text-muted-foreground">
                    {t("kb.extractionResultsSummary", { count: c.item_count ?? 0 })}
                  </span>
                )}
                <BulkStateChip state={c.state} />
              </span>
            </button>
          </li>
        ))}
      </ul>

      {/* Active chapter review body (reused single-chapter stack) */}
      {activeChapter !== null &&
        (resultsPending ? (
          <p className="text-sm text-muted-foreground">{t("kb.bulkExtraction.resultsLoading")}</p>
        ) : resultsFailed || activeOutput === null ? (
          <div className="space-y-2">
            <p role="alert" className="text-sm text-destructive">
              {t("kb.bulkExtraction.resultsError")}
            </p>
            <button
              type="button"
              onClick={onRetryResults}
              className="text-sm text-primary hover:underline"
            >
              {t("kb.extractionRetry")}
            </button>
          </div>
        ) : (
          <BulkChapterReview
            // Remount per chapter (T8 rider): wipes per-chapter local state —
            // selection AND a failed apply's error — on chapter switch.
            key={activeChapter.chapter_id}
            novelId={novelId}
            chapterId={activeChapter.chapter_id}
            output={activeOutput}
            onApplied={onApplied}
            onSkipped={onSkipped}
          />
        ))}

      {/* Next-unreviewed walking footer */}
      <div className="flex items-center justify-between pt-2">
        <span className="text-sm text-muted-foreground">
          {unreviewedCount === 0 ? t("kb.bulkExtraction.allReviewed") : ""}
        </span>
        <button
          type="button"
          onClick={() => {
            if (nextChapter !== null) onSelectChapter(nextChapter.chapter_id);
          }}
          disabled={nextChapter === null}
          className="px-4 py-2 text-sm rounded-md border border-border hover:bg-accent disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {t("kb.bulkExtraction.nextChapter")}
        </button>
      </div>
    </section>
  );
}
