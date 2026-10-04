"use client";

/**
 * useBulkExtractionController — orchestration for BulkExtractionPanel
 * (F2 T7 + F3 T4, ADR-092 spec §8.2). Extracted from the panel shell to
 * keep the component under the RULE-04 size limit; the shell only maps
 * `mode` → view. Owns everything the three modes render from:
 *
 * - one job lifecycle via `useBulkExtraction` (mount: adopt a PRE-started
 *   corpus job or start over the seed chapters),
 * - restart (interrupted mode): corpus jobs re-run the CORPUS start via
 *   `useCorpusPassStart` (a fresh start-time prefix), explicit jobs
 *   re-start over the seed; review-walking marks reset either way,
 * - resume (cancelled/failed): invalidates cached results, bumps the poll
 *   epoch,
 * - review walking via `useBulkReviewWalk` + full outputs for done chapters
 *   (results endpoint; done outputs are immutable → cached per job).
 *
 * @module useBulkExtractionController
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { bulkExtractionApi } from "@/lib/api/bulkExtraction";
import { useBulkExtraction } from "@/lib/hooks/useBulkExtraction";
import { useCorpusPassStart } from "@/lib/hooks/useCorpusPassStart";
import { useBulkReviewWalk } from "./useBulkReviewWalk";

/** Query key root for the results endpoint (full outputs, done chapters). */
const RESULTS_QUERY_KEY = "bulk-extraction-results";

export type BulkPanelMode = "progress" | "interrupted" | "review";

interface UseBulkExtractionControllerArgs {
  readonly novelId: string;
  /** Seed chapters — an explicit job is started over this list on mount. */
  readonly chapterIds: string[];
  /**
   * Pre-started job id (F3 corpus pass): adopted and polled on mount instead
   * of starting an explicit job over `chapterIds`; restart re-runs the corpus
   * start, never an explicit start over an empty seed.
   */
  readonly initialJobId?: string;
}

export function useBulkExtractionController({
  novelId,
  chapterIds,
  initialJobId,
}: UseBulkExtractionControllerArgs) {
  const queryClient = useQueryClient();
  const bulk = useBulkExtraction(novelId);
  const corpusStart = useCorpusPassStart(novelId);
  const walk = useBulkReviewWalk(bulk.chapters);

  // Mount-only job start (chapterIds is the seed captured at open); the
  // corpus pass arrives pre-started and is adopted instead.
  const startedRef = useRef(false);
  // biome-ignore lint/correctness/useExhaustiveDependencies: Runs once on mount — intentional mount-trigger pattern
  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    if (initialJobId !== undefined) {
      bulk.adopt(initialJobId);
    } else {
      void bulk.start(chapterIds);
    }
  }, []);

  const mode: BulkPanelMode = bulk.isInterrupted
    ? "interrupted"
    : bulk.isActive || bulk.status === null
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
    walk.activeChapter !== null
      ? (resultsQuery.data?.chapters.find((c) => c.chapter_id === walk.activeChapter.chapter_id)
          ?.output ?? null)
      : null;

  const resume = () => {
    if (bulk.jobId !== null) {
      void queryClient.invalidateQueries({ queryKey: [RESULTS_QUERY_KEY, novelId, bulk.jobId] });
    }
    void bulk.resume();
  };

  const restart = () => {
    walk.reset();
    bulk.reset();
    if (initialJobId !== undefined) {
      // Corpus restart re-runs the CORPUS start (a fresh start-time prefix),
      // never an explicit start over the empty seed.
      void corpusStart.start().then((jobId) => {
        if (jobId !== null) bulk.adopt(jobId);
      });
    } else {
      void bulk.start(chapterIds);
    }
  };

  return {
    bulk,
    mode,
    isCorpus: initialJobId !== undefined,
    totals: bulk.totals,
    chapters: bulk.chapters,
    walk,
    activeOutput,
    resultsPending: resultsQuery.isPending,
    resultsFailed: resultsQuery.isError || activeOutput === null,
    retryResults: () => void resultsQuery.refetch(),
    hasRestartError: corpusStart.startError !== null,
    restart,
    resume,
  };
}
