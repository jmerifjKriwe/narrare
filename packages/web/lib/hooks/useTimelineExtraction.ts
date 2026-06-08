"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";
import { mapSSEError } from "@/lib/api/ai-error-mapping";
import { confirmExtractedEvent, extractExpressionsSSE, timelineApi } from "@/lib/api/timeline";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
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
 *
 * NOTE: Full useAIOperation migration is not possible here because the SSE
 * transport uses onEvent/onComplete/onError callbacks for progressive
 * accumulation, not a single Promise. We apply partial migration:
 * - Structured errors via mapSSEError (§16.5)
 * - AbortController exposed for cancel support (§16.2)
 */
export function useSSEExtraction(novelId: string) {
  const queryClient = useQueryClient();
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractedEvents, setExtractedEvents] = useState<ExtractedEvent[]>([]);
  const [extractError, setExtractError] = useState<AIErrorResponse | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const startExtraction = useCallback(
    (chapterIds: string[]) => {
      // Abort any previous extraction
      abortRef.current?.abort();

      setIsExtracting(true);
      setExtractedEvents([]);
      setExtractError(null);

      const controller = new AbortController();
      abortRef.current = controller;

      extractExpressionsSSE(
        novelId,
        chapterIds,
        {
          onEvent: (event) => {
            setExtractedEvents((prev) => [...prev, event]);
          },
          onComplete: () => {
            setIsExtracting(false);
            abortRef.current = null;
            void queryClient.invalidateQueries({ queryKey: ["timeline", novelId, "events"] });
          },
          onError: (error) => {
            setIsExtracting(false);
            abortRef.current = null;
            const mapped = mapSSEError(error);
            setExtractError(mapped);
          },
        },
        controller.signal,
      );
    },
    [novelId, queryClient],
  );

  const cancelExtraction = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsExtracting(false);
  }, []);

  const reset = useCallback(() => {
    setExtractedEvents([]);
    setExtractError(null);
  }, []);

  return { isExtracting, extractedEvents, extractError, startExtraction, cancelExtraction, reset };
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
