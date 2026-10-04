"use client";

/**
 * BulkExtractionPanel — modal panel for the bulk KB extraction job (F2 T7,
 * ADR-092 spec §8.2), in the visual family of `ExtractionPanel`.
 *
 * SHELL ONLY (RULE-04): job lifecycle, restart/resume semantics, review
 * walking and results fetching are orchestrated by
 * `useBulkExtractionController`; the mode views live in `BulkProgressView`,
 * `BulkInterruptedView` and `BulkReviewView` — same shell/sub-view split as
 * `ExtractionPanel` / `ExtractionContent`. This component maps mode → view.
 *
 * D7a honesty: the cost note states the shared analysis budget — one AI
 * call per chapter, same budget as interactive extraction. The count is
 * only rendered once it is KNOWN — an adopted corpus job has no seed to
 * fall back to, and "0 AI calls" would be a lie (F3 T4).
 *
 * @module BulkExtractionPanel
 */

import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import { dialogVariants, overlayVariants } from "@/lib/motion-variants";
import { BulkInterruptedView } from "./BulkInterruptedView";
import { BulkProgressView } from "./BulkProgressView";
import { BulkReviewView } from "./BulkReviewView";
import { DedupCard } from "./DedupCard";
import { ExtractionHeader } from "./ExtractionHeader";
import { useBulkExtractionController } from "./useBulkExtractionController";

interface BulkExtractionPanelProps {
  readonly novelId: string;
  /** Seed chapters — the job is started over exactly this list on mount. */
  readonly chapterIds: string[];
  /**
   * Pre-started job id (F3 corpus pass): adopted and polled on mount instead
   * of starting an explicit job over `chapterIds`; restart re-runs the corpus
   * start, never an explicit start over an empty seed.
   */
  readonly initialJobId?: string;
  readonly onClose: () => void;
}

export function BulkExtractionPanel({
  novelId,
  chapterIds,
  initialJobId,
  onClose,
}: BulkExtractionPanelProps) {
  const t = useTranslations("studio");
  const ctl = useBulkExtractionController({ novelId, chapterIds, initialJobId });
  const { mode, walk } = ctl;
  const dedup = ctl.bulk.status?.dedup ?? null;

  const title =
    mode === "interrupted"
      ? t("kb.bulkExtraction.interruptedTitle")
      : mode === "review"
        ? t("kb.bulkExtraction.reviewTitle")
        : t("kb.bulkExtraction.title");

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      variants={overlayVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
    >
      <motion.div
        className="bg-background rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col"
        variants={dialogVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <ExtractionHeader title={title} closeLabel={t("kb.extractionCancel")} onClose={onClose} />

        <div className="flex-1 overflow-y-auto p-6">
          {(ctl.totals !== null || !ctl.isCorpus) && (
            <p className="mb-4 text-sm text-muted-foreground">
              {t("kb.bulkExtraction.costNote", { count: ctl.totals?.total ?? chapterIds.length })}
            </p>
          )}
          {/* Corpus restart failure (rare: the re-created job was rejected) —
              surfaced as catalog copy in progress mode (RULE-11: visible,
              never silent; ADR-043 §16.5: no raw server text). Without a
              retry affordance the progress view's "Starting…" would be a
              dead end — the failure leaves no job to poll. */}
          {ctl.hasRestartError && (
            <>
              <p
                role="alert"
                className="mb-2 text-sm text-destructive"
                data-testid="bulk-restart-error"
              >
                {t("kb.bulkExtraction.restartFailed")}
              </p>
              <button
                type="button"
                onClick={ctl.restart}
                data-testid="bulk-restart-retry"
                className="mb-4 block text-sm text-primary hover:underline"
              >
                {t("kb.extractionRetry")}
              </button>
            </>
          )}

          {/* Dedup card (F3 §6.3, review mode only): hidden for explicit
              jobs (dedup null); the card owns the honest pre-apply count,
              the lazy suggestions review and the on-demand Re-check
              semantics (see DedupCard, copy ruling T3). */}
          {mode === "review" && dedup !== null && <DedupCard novelId={novelId} dedup={dedup} />}

          {mode === "progress" && (
            <BulkProgressView
              title={title}
              totals={ctl.totals}
              chapters={ctl.chapters}
              jobStatus={ctl.bulk.status?.status ?? null}
              error={ctl.bulk.error}
              isStarting={ctl.bulk.isStarting}
              onCancel={() => void ctl.bulk.cancel()}
              onRetryStart={
                // Corpus mode retries through the corpus restart/adopt path —
                // an explicit start over the empty seed would 422 (the adopted
                // job's transient poll failure must not offer the wrong
                // domain). Explicit jobs retry over their seed as before.
                ctl.isCorpus ? ctl.restart : () => void ctl.bulk.start(chapterIds)
              }
            />
          )}

          {mode === "interrupted" && <BulkInterruptedView title={title} onRestart={ctl.restart} />}

          {mode === "review" && (
            <BulkReviewView
              novelId={novelId}
              title={title}
              jobStatus={ctl.bulk.status?.status ?? null}
              statusError={ctl.bulk.status?.error ?? null}
              chapters={ctl.chapters}
              activeChapter={walk.activeChapter}
              appliedIds={walk.appliedIds}
              skippedIds={walk.skippedIds}
              unreviewedCount={walk.unreviewedDone.length}
              nextChapter={walk.nextChapter}
              resultsPending={ctl.resultsPending}
              resultsFailed={ctl.resultsFailed}
              activeOutput={ctl.activeOutput}
              onSelectChapter={walk.setActiveChapterId}
              onApplied={walk.markApplied}
              onSkipped={walk.markSkipped}
              onRetryResults={ctl.retryResults}
              onResume={ctl.resume}
            />
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}
