"use client";

import { type MutableRefObject, useCallback } from "react";
import { useRecordFeedback } from "@/lib/hooks/useMemory";
import type { FeedbackAction, FeedbackRequest } from "@/types";
import type { CapturedMarkData } from "./useAnnotationActions";
import type { PendingMarkInfo } from "./useAnnotationMarkTracker";

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

interface UseAnnotationRatingOptions {
  readonly projectId: string;
  readonly chapterId?: string;
  readonly showRating: "accept" | "reject" | null;
  readonly setShowRating: (rating: "accept" | "reject" | null) => void;
  readonly setMarkInfo: (info: PendingMarkInfo | null) => void;
  readonly capturedRef: MutableRefObject<CapturedMarkData | null>;
}

/** Handles rating submission and dismissal for AI annotation feedback. */
export function useAnnotationRating({
  projectId,
  chapterId,
  showRating,
  setShowRating,
  setMarkInfo,
  capturedRef,
}: UseAnnotationRatingOptions) {
  const recordFeedback = useRecordFeedback(projectId);

  const handleRatingSubmit = useCallback(
    (data: { rating: number; reason?: string }) => {
      const captured = capturedRef.current;
      if (!captured) {
        setShowRating(null);
        setMarkInfo(null);
        return;
      }

      // Record a follow-up feedback event with the rating
      const action: FeedbackAction =
        showRating === "accept" ? (captured.modification ? "modify" : "accept") : "reject";

      const feedbackData: FeedbackRequest = {
        action,
        suggestion_id: captured.requestId,
        intent: captured.source,
        suggestion_text: captured.originalText || captured.currentText,
        modification: captured.modification?.current ?? null,
        rating: data.rating,
        context: data.reason ? { reject_reason: data.reason } : undefined,
        project_id: projectId,
        chapter_id: chapterId ?? null,
        mode: captured.source,
      };
      recordFeedback.mutate(feedbackData, {
        onError: () => {
          /* Non-blocking */
        },
      });

      capturedRef.current = null;
      setShowRating(null);
      setMarkInfo(null);
    },
    [showRating, projectId, chapterId, recordFeedback, setShowRating, setMarkInfo, capturedRef],
  );

  const handleRatingDismiss = useCallback(() => {
    // User skipped rating — no additional feedback event needed
    capturedRef.current = null;
    setShowRating(null);
    setMarkInfo(null);
  }, [setShowRating, setMarkInfo, capturedRef]);

  return { handleRatingSubmit, handleRatingDismiss };
}
