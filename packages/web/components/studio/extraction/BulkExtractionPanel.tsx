"use client";

/**
 * BulkExtractionPanel — modal panel for the bulk KB extraction job (F2 T7,
 * ADR-092 spec §8.2), in the visual family of `ExtractionPanel`.
 *
 * Owns one job lifecycle via `useBulkExtraction`: starts on mount, routes by
 * mode — PROGRESS while active (totals + per-chapter state chips + cancel),
 * INTERRUPTED degrade on a 404 poll (explanation + restart via reset+start),
 * and REVIEW once terminal (chapter rail with applied/skipped badges,
 * `BulkChapterReview` reusing the single-chapter review stack, and
 * next-unreviewed walking). Resume is offered for cancelled/failed jobs;
 * done outputs stay reviewable across the resume.
 *
 * The mode views live in `BulkProgressView`, `BulkInterruptedView` and
 * `BulkReviewView` — same shell/sub-view split as `ExtractionPanel` /
 * `ExtractionContent` (RULE-04).
 *
 * D7a honesty: the cost note states the shared analysis budget — one AI
 * call per chapter, same budget as interactive extraction.
 *
 * @module BulkExtractionPanel
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { bulkExtractionApi } from "@/lib/api/bulkExtraction";
import { useBulkExtraction } from "@/lib/hooks/useBulkExtraction";
import { dialogVariants, overlayVariants } from "@/lib/motion-variants";
import { BulkInterruptedView } from "./BulkInterruptedView";
import { BulkProgressView } from "./BulkProgressView";
import { BulkReviewView } from "./BulkReviewView";
import { isUnreviewedDone, nextUnreviewedAfter } from "./bulkReviewWalk";
import { ExtractionHeader } from "./ExtractionHeader";

interface BulkExtractionPanelProps {
  readonly novelId: string;
  /** Seed chapters — the job is started over exactly this list on mount. */
  readonly chapterIds: string[];
  readonly onClose: () => void;
}

/** Query key root for the results endpoint (full outputs, done chapters). */
const RESULTS_QUERY_KEY = "bulk-extraction-results";

export function BulkExtractionPanel({ novelId, chapterIds, onClose }: BulkExtractionPanelProps) {
  const t = useTranslations("studio");
  const queryClient = useQueryClient();
  const bulk = useBulkExtraction(novelId);

  // Review-walking state (spec §8.2): marks are keyed by chapter id and kept
  // across resume; a restart (new job) starts with a clean slate.
  const [appliedIds, setAppliedIds] = useState<ReadonlySet<string>>(() => new Set());
  const [skippedIds, setSkippedIds] = useState<ReadonlySet<string>>(() => new Set());
  const [activeChapterId, setActiveChapterId] = useState<string | null>(null);

  // Mount-only job start (chapterIds is the seed captured at open).
  const startedRef = useRef(false);
  // biome-ignore lint/correctness/useExhaustiveDependencies: Runs once on mount — intentional mount-trigger pattern
  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    void bulk.start(chapterIds);
  }, []);

  const { status, chapters, totals } = bulk;
  const jobStatus = status?.status ?? null;
  const unreviewedDone = chapters.filter((c) => isUnreviewedDone(c, appliedIds, skippedIds));
  const activeChapter =
    chapters.find((c) => c.chapter_id === activeChapterId) ?? unreviewedDone[0] ?? null;
  const nextChapter =
    activeChapter !== null
      ? nextUnreviewedAfter(chapters, activeChapter, appliedIds, skippedIds)
      : null;

  const mode: "progress" | "interrupted" | "review" = bulk.isInterrupted
    ? "interrupted"
    : bulk.isActive || status === null
      ? "progress"
      : "review";

  // Full outputs for done chapters (results endpoint). Done outputs are
  // immutable → cached for the job; invalidated on resume (new done chapters).
  const resultsQuery = useQuery({
    queryKey: [RESULTS_QUERY_KEY, novelId, bulk.jobId],
    queryFn: ({ signal }) => bulkExtractionApi.bulkJobResults(novelId, bulk.jobId ?? "", signal),
    enabled: mode === "review" && bulk.jobId !== null,
    staleTime: Number.POSITIVE_INFINITY,
  });
  const activeOutput =
    activeChapter !== null
      ? (resultsQuery.data?.chapters.find((c) => c.chapter_id === activeChapter.chapter_id)
          ?.output ?? null)
      : null;

  const handleResume = () => {
    if (bulk.jobId !== null) {
      void queryClient.invalidateQueries({ queryKey: [RESULTS_QUERY_KEY, novelId, bulk.jobId] });
    }
    void bulk.resume();
  };

  const handleRestart = () => {
    setAppliedIds(new Set());
    setSkippedIds(new Set());
    setActiveChapterId(null);
    bulk.reset();
    void bulk.start(chapterIds);
  };

  const markReviewed =
    (setter: React.Dispatch<React.SetStateAction<ReadonlySet<string>>>) => (chapterId: string) =>
      setter((prev) => new Set(prev).add(chapterId));

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
          {/* Shared-budget honesty (D7a): one AI call per chapter, same budget
              as interactive extraction. Stated in every mode. */}
          <p className="mb-4 text-sm text-muted-foreground">
            {t("kb.bulkExtraction.costNote", { count: totals?.total ?? chapterIds.length })}
          </p>

          {mode === "progress" && (
            <BulkProgressView
              title={title}
              totals={totals}
              chapters={chapters}
              jobStatus={jobStatus}
              error={bulk.error}
              isStarting={bulk.isStarting}
              onCancel={() => void bulk.cancel()}
              onRetryStart={() => void bulk.start(chapterIds)}
            />
          )}

          {mode === "interrupted" && (
            <BulkInterruptedView title={title} onRestart={handleRestart} />
          )}

          {mode === "review" && (
            <BulkReviewView
              novelId={novelId}
              title={title}
              jobStatus={jobStatus}
              statusError={status?.error ?? null}
              chapters={chapters}
              activeChapter={activeChapter}
              appliedIds={appliedIds}
              skippedIds={skippedIds}
              unreviewedCount={unreviewedDone.length}
              nextChapter={nextChapter}
              resultsPending={resultsQuery.isPending}
              resultsFailed={resultsQuery.isError || activeOutput === null}
              activeOutput={activeOutput}
              onSelectChapter={setActiveChapterId}
              onApplied={markReviewed(setAppliedIds)}
              onSkipped={markReviewed(setSkippedIds)}
              onRetryResults={() => void resultsQuery.refetch()}
              onResume={handleResume}
            />
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}
