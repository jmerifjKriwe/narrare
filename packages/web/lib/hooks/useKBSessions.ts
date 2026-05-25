"use client";

/**
 * TanStack Query hooks for KB creation sessions.
 *
 * Query keys follow the pattern ["kb-sessions", novelId, ...]
 * to avoid collision with regular KB entry keys.
 */

import { type UseQueryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import {
  type KBCreationSession,
  type KBSessionCompleteResponse,
  kbSessionApi,
  requestEnhance,
  requestInterview,
  suggestField,
} from "@/lib/api/kb-sessions";

// --- Query key factory ---

const kbSessionKeys = {
  all: (novelId: string) => ["kb-sessions", novelId] as const,
  sessions: (novelId: string) => [...kbSessionKeys.all(novelId), "sessions"] as const,
  session: (novelId: string, sessionId: string) =>
    [...kbSessionKeys.sessions(novelId), sessionId] as const,
};

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
    refetchIntervalInBackground: false,
    ...options,
  });
}

// --- Mutation hooks: REST ---

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

/** Complete a session and create the KB entry. Returns the entry_id via onSuccess. */
export function useCompleteKBSession(novelId: string, sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => kbSessionApi.completeSession(novelId, sessionId),
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

// --- Mutation hooks: SSE (AI operations) ---

/**
 * Request AI suggestion for a field.
 * On success, invalidates session query to refresh state.
 */
export function useKBSessionSuggest(novelId: string, sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ fieldKey, signal }: { fieldKey: string; signal?: AbortSignal }) =>
      suggestField(novelId, sessionId, fieldKey, signal),
    onSuccess: () => {
      // Invalidate session query to get updated ai_suggested_value from backend
      void queryClient.invalidateQueries({ queryKey: kbSessionKeys.session(novelId, sessionId) });
    },
  });
}

/**
 * Request interview question from AI.
 * On success, invalidates session query.
 */
export function useKBSessionInterview(novelId: string, sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (signal?: AbortSignal) => requestInterview(novelId, sessionId, signal),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: kbSessionKeys.session(novelId, sessionId) });
    },
  });
}

/**
 * Request AI enhancement for all fields.
 * On success, invalidates session query.
 */
export function useKBSessionEnhance(novelId: string, sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (signal?: AbortSignal) => requestEnhance(novelId, sessionId, signal),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: kbSessionKeys.session(novelId, sessionId) });
    },
  });
}
