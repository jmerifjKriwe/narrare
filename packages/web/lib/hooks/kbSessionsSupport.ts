"use client";

/**
 * KB assist-session support — shared query-key factory plus the three
 * assist-mode mutation hooks (suggest / interview / enhance).
 *
 * Extracted from useKBSessions.ts per RULE-04; re-exported there for
 * existing consumers. Single-direction import (this module never imports
 * the parent), so the parent's re-export stays cycle-free.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { requestEnhance, requestInterview, suggestField } from "@/lib/api/kb-sessions";

// --- Query key factory ---

export const kbSessionKeys = {
  all: (novelId: string) => ["kb-sessions", novelId] as const,
  sessions: (novelId: string) => [...kbSessionKeys.all(novelId), "sessions"] as const,
  session: (novelId: string, sessionId: string) =>
    [...kbSessionKeys.sessions(novelId), sessionId] as const,
};

// --- Mutation hooks: AI assist operations (single-shot REST) ---

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
