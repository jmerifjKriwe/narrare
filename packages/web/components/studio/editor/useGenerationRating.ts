/**
 * Generation rating/feedback handler extracted from generationPanelController
 * (RULE-04 / AUFG-03-04).
 *
 * Owns the accept/reject feedback submission to the memory service
 * (POST /memory/feedback). Derives whether the user modified the draft
 * (vs. accepted as-is) by comparing against the captured original text.
 */

import {
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
  useCallback,
  useState,
} from "react";
import type { GenerationMode } from "@/lib/api/generation";
import { useRecordFeedback } from "@/lib/hooks/useMemory";
import type { FeedbackRequest } from "@/types";

type RatingAction = "accept" | "reject";

interface UseGenerationRatingParams {
  novelId: string;
  chapterId: string;
  mode: GenerationMode;
  draftText: string;
  requestId: string | null;
  originalTextRef: MutableRefObject<string>;
}

interface UseGenerationRatingResult {
  showRating: RatingAction | null;
  setShowRating: Dispatch<SetStateAction<RatingAction | null>>;
  captureOriginal: () => void;
  handleRatingDone: (rating?: number, reason?: string) => void;
  recordFeedback: ReturnType<typeof useRecordFeedback>;
}

export function useGenerationRating({
  novelId,
  chapterId,
  mode,
  draftText,
  requestId,
  originalTextRef,
}: UseGenerationRatingParams): UseGenerationRatingResult {
  const [showRating, setShowRating] = useState<RatingAction | null>(null);
  const recordFeedback = useRecordFeedback(novelId);

  const captureOriginal = useCallback(() => {
    if (!originalTextRef.current) originalTextRef.current = draftText;
  }, [draftText, originalTextRef]);

  const handleRatingDone = useCallback(
    (rating?: number, reason?: string) => {
      if (!showRating) return;
      const originalText = originalTextRef.current;
      const isModified = originalText !== draftText && originalText.length > 0;
      const action: FeedbackRequest["action"] =
        showRating === "accept" ? (isModified ? "modify" : "accept") : "reject";
      recordFeedback.mutate(
        {
          action,
          suggestion_id: requestId ?? "",
          intent: mode,
          suggestion_text: originalText || draftText,
          modification: isModified ? draftText : undefined,
          rating: rating ?? undefined,
          context: reason ? { reject_reason: reason } : undefined,
          project_id: novelId,
          chapter_id: chapterId,
          mode,
        },
        { onError: () => undefined },
      );
    },
    [showRating, draftText, requestId, mode, novelId, chapterId, recordFeedback, originalTextRef],
  );

  return {
    showRating,
    setShowRating,
    captureOriginal,
    handleRatingDone,
    recordFeedback,
  };
}

export type { RatingAction };
