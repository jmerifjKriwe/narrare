/**
 * Generation accept/reject mutations + derived phase extracted from
 * generationPanelController (RULE-04 / AUFG-03-04).
 *
 * The two mutations coordinate with the rating hook (capture original
 * text + show rating panel) and the parent's onDraftAccepted callback.
 * Phase is derived from the stream state + the stopped-with-output flag.
 */

import { useMutation } from "@tanstack/react-query";
import { writingApi } from "@/lib/api/generation";
import type { useGenerationRating } from "./useGenerationRating";
import type { useGenerationStream } from "./useGenerationStream";

type PanelPhase = "config" | "streaming" | "review" | "error";

interface UseGenerationMutationsParams {
  requestId: string | null;
  draftText: string;
  stoppedWithOutput: boolean;
  stream: Pick<
    ReturnType<typeof useGenerationStream>,
    "isIdle" | "isLoading" | "isStreaming" | "isComplete"
  >;
  rating: Pick<ReturnType<typeof useGenerationRating>, "captureOriginal" | "setShowRating">;
  onDraftAccepted: (text: string) => void;
}

export function useGenerationMutations({
  requestId,
  draftText,
  stoppedWithOutput,
  stream,
  rating,
  onDraftAccepted,
}: UseGenerationMutationsParams) {
  const acceptMutation = useMutation({
    mutationFn: () => writingApi.acceptDraft(requestId!),
    onSuccess: () => {
      rating.captureOriginal();
      onDraftAccepted(draftText);
      rating.setShowRating("accept");
    },
  });
  const rejectMutation = useMutation({
    mutationFn: () => writingApi.rejectDraft(requestId!),
    onSuccess: () => {
      rating.captureOriginal();
      rating.setShowRating("reject");
    },
  });

  const phase: PanelPhase = stoppedWithOutput
    ? "review"
    : stream.isIdle
      ? "config"
      : stream.isLoading || stream.isStreaming
        ? "streaming"
        : stream.isComplete
          ? "review"
          : "error";

  return { acceptMutation, rejectMutation, phase };
}
