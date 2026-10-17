"use client";

/**
 * TanStack Query hooks for KB creation sessions.
 *
 * Query keys follow the pattern ["kb-sessions", novelId, ...]
 * to avoid collision with regular KB entry keys.
 *
 * The assist-mode mutations (suggest/interview/enhance) and the shared
 * key factory live in kbSessionsSupport.ts (RULE-04 split) and are
 * re-exported here for existing consumers.
 */

import { type UseQueryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type KBCreationSession,
  type KBSessionCompleteResponse,
  kbSessionApi,
} from "@/lib/api/kb-sessions";
import { kbSessionKeys } from "./kbSessionsSupport";

// Re-exported for backwards compatibility (the implementations live in
// kbSessionsSupport.ts to keep this lifecycle module within size limits).
export {
  kbSessionKeys,
  useKBSessionEnhance,
  useKBSessionInterview,
  useKBSessionSuggest,
} from "./kbSessionsSupport";

// --- Query hooks ---

/**
 * Fetch a single KB creation session.
 * Pass null sessionId to disable.
 * Uses refetchInterval for active sessions to poll for updates.
 */
export function useKBSession(
  novelId: string,
  sessionId: string | null,
  options?: Partial<UseQueryOptions<KBCreationSession | null>>,
) {
  return useQuery<KBCreationSession | null>({
    queryKey: kbSessionKeys.session(novelId, sessionId ?? ""),
    queryFn: () =>
      sessionId ? kbSessionApi.getSession(novelId, sessionId) : Promise.resolve(null),
    enabled: !!novelId && !!sessionId,
    placeholderData: (previousData) => previousData,
    // Poll every 2 seconds for active sessions to catch up with SSE side-effects
    refetchInterval: sessionId ? 2000 : false,
    ...options,
  });
}

// --- Mutation hooks: REST lifecycle ---

/** Create a new KB creation session. */
export function useCreateKBSession(novelId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (entityType: string) => kbSessionApi.createSession(novelId, entityType),
    onSuccess: (data) => {
      // Cache the new session
      void queryClient.setQueryData(kbSessionKeys.session(novelId, data.id), data);
    },
  });
}

/** Answer a field with user input. */
export function useAnswerField(novelId: string, sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ fieldKey, value }: { fieldKey: string; value: string }) =>
      kbSessionApi.answerField(novelId, sessionId, fieldKey, value),
    onSuccess: (data) => {
      // Update session cache
      void queryClient.setQueryData(kbSessionKeys.session(novelId, sessionId), data);
    },
  });
}

/**
 * Complete a session and create the KB entry.
 * Takes the collected entry name (F9-1) — it fills the session's name on
 * the backend before the entry is mapped. Returns the entry_id via onSuccess.
 */
export function useCompleteKBSession(novelId: string, sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => kbSessionApi.completeSession(novelId, sessionId, name),
    onSuccess: (_data: KBSessionCompleteResponse) => {
      // Invalidate KB entries list to show the new entry
      void queryClient.invalidateQueries({ queryKey: ["kb", novelId, "entries"] });
      // Remove session from cache
      void queryClient.removeQueries({ queryKey: kbSessionKeys.session(novelId, sessionId) });
    },
  });
}

/** Abandon and delete a session. */
export function useAbandonKBSession(novelId: string, sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => kbSessionApi.abandonSession(novelId, sessionId),
    onSuccess: () => {
      // Remove session from cache
      void queryClient.removeQueries({ queryKey: kbSessionKeys.session(novelId, sessionId) });
    },
  });
}
