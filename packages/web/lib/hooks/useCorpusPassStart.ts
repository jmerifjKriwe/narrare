"use client";

/**
 * useCorpusPassStart — start/restart action for a corpus pass job (F3 T4,
 * spec §4.3). One consumer action with two surfaces: the estimate dialog's
 * Start button and the panel's corpus restart.
 *
 * The raw error OBJECT is kept for classification (split-first 422 degrade);
 * the UI always renders catalog copy — the server detail is never shown
 * (ADR-043 §16.5: no raw backend text in AI surfaces).
 *
 * @module useCorpusPassStart
 */

import { useCallback, useState } from "react";
import { bulkExtractionApi, isSplitFirstBulkError } from "@/lib/api/bulkExtraction";

export function useCorpusPassStart(novelId: string) {
  const [isStarting, setIsStarting] = useState(false);
  const [startError, setStartError] = useState<unknown>(null);

  /**
   * Start the corpus pass; resolves the new job id, or null on failure
   * (the rejection is kept in `startError` for classification/display).
   */
  const start = useCallback(async (): Promise<string | null> => {
    setIsStarting(true);
    setStartError(null);
    try {
      const view = await bulkExtractionApi.startCorpusPass(novelId);
      return view.job_id;
    } catch (err) {
      setStartError(err);
      return null;
    } finally {
      setIsStarting(false);
    }
  }, [novelId]);

  /** Drop a surfaced start error (a dialog reopen starts the action fresh). */
  const clearError = useCallback(() => setStartError(null), []);

  return {
    isStarting,
    startError,
    isSplitFirst: isSplitFirstBulkError(startError),
    start,
    clearError,
  };
}
