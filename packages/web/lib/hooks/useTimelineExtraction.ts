"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { confirmExtractedEvent, extractExpressionsSSE, timelineApi } from "@/lib/api/timeline";
import type {
  CharacterAgeReport,
  ExtractedEvent,
  TemporalConsistency,
  TimelineEvent,
} from "@/types/timeline";

/**
 * Extract temporal expressions from chapters via SSE streaming.
 * Events are accumulated progressively as SSE chunks arrive.
 * Invalidates the events list on completion.
 */
export function useSSEExtraction(novelId: string) {
  const queryClient = useQueryClient();
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractedEvents, setExtractedEvents] = useState<ExtractedEvent[]>([]);
  const [extractError, setExtractError] = useState<string | null>(null);

  const startExtraction = useCallback(
    (chapterIds: string[]) => {
      setIsExtracting(true);
      setExtractedEvents([]);
      setExtractError(null);

      const abortController = new AbortController();

      extractExpressionsSSE(
        novelId,
        chapterIds,
        {
          onEvent: (event) => {
            setExtractedEvents((prev) => [...prev, event]);
          },
          onComplete: () => {
            setIsExtracting(false);
            void queryClient.invalidateQueries({ queryKey: ["timeline", novelId, "events"] });
          },
          onError: (error) => {
            setIsExtracting(false);
            setExtractError(error.message);
          },
        },
        abortController.signal,
      );

      return () => abortController.abort();
    },
    [novelId, queryClient],
  );

  const reset = useCallback(() => {
    setExtractedEvents([]);
    setExtractError(null);
  }, []);

  return { isExtracting, extractedEvents, extractError, startExtraction, reset };
}

/**
 * Confirm an extracted expression and persist it as a timeline event.
 * Preserves source='extracted', confidence, and is_confirmed metadata.
 */
export function useConfirmExtractedEvent(novelId: string) {
  const queryClient = useQueryClient();
  return useMutation<TimelineEvent, Error, ExtractedEvent>({
    mutationFn: (extracted) => confirmExtractedEvent(novelId, extracted),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["timeline", novelId, "events"] });
    },
  });
}

/** Check temporal consistency for a novel. */
export function useTimelineConsistency(novelId: string) {
  return useQuery<TemporalConsistency>({
    queryKey: ["timeline", novelId, "consistency"],
    queryFn: () => timelineApi.checkConsistency(novelId),
    enabled: !!novelId,
  });
}

/** Fetch character age report from KB metadata. */
export function useCharacterAges(novelId: string) {
  return useQuery<CharacterAgeReport>({
    queryKey: ["timeline", novelId, "character-ages"],
    queryFn: () => timelineApi.getCharacterAges(novelId),
    enabled: !!novelId,
  });
}
