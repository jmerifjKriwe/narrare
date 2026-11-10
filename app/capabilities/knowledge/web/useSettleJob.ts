import { useEffect } from "react";

import { queryClient } from "@shell/lib/query";

/** The queue a settled job releases: the extraction's pending suggestions
 *  or the whole-novel check's pending findings. */
export type SettleQueue = "suggestions" | "findings";

/**
 * The settle beat the knowledge panels and the palette's job dialogs
 * share: the row turning done or failed is the moment the queue it feeds
 * exists (or provably will not), so that is when the queue refetches —
 * the poll publishes its own finding.
 *
 * Between the enqueue and that answer the trigger stays closed (one job
 * at a time): `busy` holds while the enqueue POST is in flight or the
 * filed job is still outstanding. Three things hand the button back: a
 * settled row, a poll that met the dead service (an unanswered poll is an
 * error, not a promise of movement — otherwise an outage would lock the
 * trigger for its whole duration), and a refused enqueue (no job filed,
 * nothing outstanding).
 */
export function useSettleJob({
  jobId,
  status,
  pollError,
  enqueuePending,
  novelId,
  queue,
}: {
  jobId: string | null;
  status: string | undefined;
  pollError: boolean;
  enqueuePending: boolean;
  novelId: string;
  queue: SettleQueue;
}): { settled: boolean; pollFailed: boolean; busy: boolean } {
  const settled = status === "done" || status === "failed";
  useEffect(() => {
    if (!settled) return;
    void queryClient.invalidateQueries({ queryKey: ["knowledge", queue, novelId] });
  }, [settled, novelId, queue]);

  const pollFailed = jobId !== null && pollError;
  const busy = enqueuePending || (jobId !== null && !settled && !pollFailed);
  return { settled, pollFailed, busy };
}
