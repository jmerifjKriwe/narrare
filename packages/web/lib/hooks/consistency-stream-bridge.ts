/**
 * SSE → Promise bridge for useConsistencyStream (ADR-044 / CONS-001).
 *
 * Turns the callback-based {@link streamConsistencyCheck} transport into the
 * `execute(signal) => Promise<T>` contract required by {@link useAIOperation}:
 * a settled-state guard (resolve/reject exactly once), abort → AbortError
 * translation (swallowed by useAIOperation on cancel), and forwarding of stage
 * events as typed {@link ConsistencyStagePayload} snapshots plus progressive
 * issues.
 *
 * Extracted from useConsistencyStream for RULE-04 modularity, mirroring how
 * use-ai-operation delegates its execute logic to ai-operation-execute. The
 * hook retains React state (progress/issues) and stream liveness (notifyData);
 * this module owns the transport/promise boundary and is unit-testable without
 * React.
 *
 * @module consistency-stream-bridge
 */

import type { ConsistencyIssue } from "@/lib/api/analysis";
import type {
  ConsistencyCheckRequest,
  ConsistencyResultPayload,
} from "@/lib/api/consistency-stream";
import { streamConsistencyCheck } from "@/lib/api/consistency-stream";
import type { ConsistencyStagePayload } from "./useConsistencyStream.types";

/** Arguments for {@link bridgeConsistencyStream}. */
export interface BridgeConsistencyStreamArgs {
  /** Novel to check (URL query parameter for the stream endpoint). */
  novelId: string;
  /** Request body (chapter_ids, check_types, include_kb). */
  request: ConsistencyCheckRequest;
  /** Abort signal from useAIOperation — aborting rejects with AbortError. */
  signal: AbortSignal;
  /** Forwarded (as a typed payload) on every stage event. */
  onStage: (payload: ConsistencyStagePayload) => void;
  /** Forwarded for each progressive issue emitted during checking. */
  onIssue: (issue: ConsistencyIssue) => void;
}

/**
 * Run a consistency-check stream and resolve/reject its terminal result.
 *
 * The returned promise settles exactly once: `onComplete` resolves with the
 * {@link ConsistencyResultPayload}, `onError` rejects, and an aborted `signal`
 * rejects with an `AbortError` (which useAIOperation swallows on cancel).
 *
 * @returns The terminal {@link ConsistencyResultPayload}.
 */
export function bridgeConsistencyStream(
  args: BridgeConsistencyStreamArgs,
): Promise<ConsistencyResultPayload> {
  const { novelId, request, signal, onStage, onIssue } = args;

  return new Promise<ConsistencyResultPayload>((resolve, reject) => {
    let settled = false;

    const onAbort = () => {
      if (!settled) {
        settled = true;
        reject(new DOMException("Aborted", "AbortError"));
      }
    };
    signal.addEventListener("abort", onAbort, { once: true });

    streamConsistencyCheck(
      novelId,
      request,
      {
        onStage: (stage, status, progress, message, factsExtracted, issuesFound) => {
          onStage({ stage, status, progress, message, factsExtracted, issuesFound });
        },
        onIssue,
        onComplete: (result) => {
          if (!settled) {
            settled = true;
            signal.removeEventListener("abort", onAbort);
            resolve(result);
          }
        },
        onError: (err) => {
          if (!settled) {
            settled = true;
            signal.removeEventListener("abort", onAbort);
            reject(err);
          }
        },
      },
      signal,
    );
  });
}
