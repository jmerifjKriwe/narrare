"use client";

/**
 * CR-AUFG-07-24 — UI-level state machine for rating submission.
 *
 * Wraps the existing `useRecordFeedback` TanStack mutation with the
 * idle/loading/success/error/skipped surface the `AIRating` component needs.
 *
 * The hook is **non-blocking**: rating failures never throw to the caller.
 * Per spec, a failed rating must NOT remove or alter the AI output. The host
 * component decides whether to render the error/retry affordance.
 *
 * RULE-06: this hook owns ONE responsibility — managing the rating submission
 * state machine. Payload construction is delegated to `buildFeedbackRequest`
 * (single source of truth for the POST body shape).
 *
 * @param vm immutable view model describing WHAT is being rated.
 */

import { useCallback, useState } from "react";
import { buildFeedbackRequest } from "@/lib/ai-rating/build-feedback";
import type { AIRatingInput, AIRatingState, AIRatingViewModel } from "@/lib/ai-rating/contracts";
import { useRecordFeedback } from "@/lib/hooks/useMemory";

export function useAIRating(vm: AIRatingViewModel) {
  const [state, setState] = useState<AIRatingState>("idle");
  const record = useRecordFeedback(vm.projectId);

  const submit = useCallback(
    (input: AIRatingInput) => {
      setState("loading");
      const payload = buildFeedbackRequest(vm, input);
      // onError is intentionally non-blocking per spec; we surface it as the
      // 'error' state so the UI can offer retry/skip without affecting the
      // original AI output.
      record.mutate(payload, {
        onSuccess: () => setState("success"),
        onError: () => setState("error"),
      });
    },
    [record, vm],
  );

  const skip = useCallback(() => setState("skipped"), []);
  const reset = useCallback(() => setState("idle"), []);

  return { state, submit, skip, reset } as const;
}
