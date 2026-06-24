"use client";

/**
 * usePromptHistory — data layer for the Prompt History panel (RULE-04 split).
 *
 * Owns:
 *   - Revision list query (``["prompt-history", promptId]``).
 *   - From/To selection state + compare query (enabled only when BOTH set).
 *   - Restore / clear mutations (append-only restore + history clear).
 *
 * The hook stays UI-agnostic: it returns queries/mutations + selection. The
 * panel wires confirmations and toasts. ``onRestored`` / ``onCleared`` let the
 * parent (PromptEditor) invalidate the prompt-detail query so the editor
 * reflects the restored active content.
 *
 * RULE-17: ``scope`` is never sent (resolved server-side to PROJECT).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { promptsApi } from "@/lib/api/prompts";

const LIST_KEY = "prompt-history";
const COMPARE_KEY = "prompt-history-compare";

export interface UsePromptHistoryOptions {
  /** Called after a successful restore (e.g. invalidate prompt-detail query). */
  readonly onRestored?: () => void;
  /** Called after history is cleared. */
  readonly onCleared?: () => void;
}

export function usePromptHistory(promptId: string, options?: UsePromptHistoryOptions) {
  const queryClient = useQueryClient();

  const [fromId, setFromId] = useState<string | null>(null);
  const [toId, setToId] = useState<string | null>(null);
  const [lastRestoredRevisionId, setLastRestoredRevisionId] = useState<string | null>(null);

  const list = useQuery({
    queryKey: [LIST_KEY, promptId],
    queryFn: () => promptsApi.listHistory(promptId),
  });

  const compare = useQuery({
    queryKey: [COMPARE_KEY, promptId, fromId, toId],
    queryFn: () => promptsApi.compareRevisions(promptId, fromId as string, toId as string),
    enabled: fromId !== null && toId !== null,
  });

  const restoreMutation = useMutation({
    mutationFn: (revisionId: string) => promptsApi.restoreRevision(promptId, revisionId),
    onSuccess: (data) => {
      setLastRestoredRevisionId(data.restored_revision.id);
      void queryClient.invalidateQueries({ queryKey: [LIST_KEY, promptId] });
      void queryClient.invalidateQueries({ queryKey: [COMPARE_KEY, promptId] });
      options?.onRestored?.();
    },
  });

  const clearMutation = useMutation({
    mutationFn: () => promptsApi.clearHistory(promptId),
    onSuccess: () => {
      setFromId(null);
      setToId(null);
      void queryClient.invalidateQueries({ queryKey: [LIST_KEY, promptId] });
      void queryClient.invalidateQueries({ queryKey: [COMPARE_KEY, promptId] });
      options?.onCleared?.();
    },
  });

  return {
    list,
    fromId,
    toId,
    setFromId,
    setToId,
    compare,
    restoreMutation,
    clearMutation,
    lastRestoredRevisionId,
  };
}
