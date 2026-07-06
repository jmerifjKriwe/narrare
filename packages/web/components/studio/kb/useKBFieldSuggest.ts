/**
 * Field-suggest AI operation extracted from KBAssistedCreationController
 * (RULE-04 / AUFG-03-04).
 *
 * Wraps the per-field suggestion flow in `useAIOperation` so it gets the
 * §16 lifecycle (loading/streaming/error/connection-lost) for free. Owns
 * the in-flight field key (only one suggestion can be active at a time)
 * and surfaces the structured error to the panel.
 */

import { useRef, useState } from "react";
import { mapSSEError } from "@/lib/api/ai-error-mapping";
import type { KBSuggestionResult } from "@/lib/api/kb-sessions";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import { useKBSessionSuggest } from "@/lib/hooks/useKBSessions";

interface UseKBFieldSuggestParams {
  novelId: string;
  sessionId: string | null;
}

interface UseKBFieldSuggestResult {
  suggestingFieldKey: string | null;
  suggestionError: AIErrorResponse | null;
  suggestionErrorFieldKey: string | null;
  suggestMutation: ReturnType<typeof useKBSessionSuggest>;
  handleSuggest: (fieldKey: string) => void;
  handleCancelSuggest: () => void;
}

export function useKBFieldSuggest({
  novelId,
  sessionId,
}: UseKBFieldSuggestParams): UseKBFieldSuggestResult {
  const [suggestingFieldKey, setSuggestingFieldKey] = useState<string | null>(null);
  const [suggestionError, setSuggestionError] = useState<AIErrorResponse | null>(null);
  const [suggestionErrorFieldKey, setSuggestionErrorFieldKey] = useState<string | null>(null);
  const pendingSuggestFieldKey = useRef<string | null>(null);
  const suggestMutation = useKBSessionSuggest(novelId, sessionId ?? "");

  const suggestOp = useAIOperation<KBSuggestionResult>({
    execute: async (signal) => {
      const fieldKey = pendingSuggestFieldKey.current;
      if (!sessionId || !fieldKey) throw new Error("No active field suggestion");
      return suggestMutation.mutateAsync({ fieldKey, signal });
    },
    errorMapper: mapSSEError,
    onSuccess: () => {
      pendingSuggestFieldKey.current = null;
      setSuggestingFieldKey(null);
      setSuggestionError(null);
      setSuggestionErrorFieldKey(null);
    },
    onError: (error) => {
      const fieldKey = pendingSuggestFieldKey.current;
      pendingSuggestFieldKey.current = null;
      setSuggestingFieldKey(null);
      setSuggestionError(error);
      setSuggestionErrorFieldKey(fieldKey);
    },
  });

  function handleSuggest(fieldKey: string): void {
    if (!sessionId) return;
    setSuggestionError(null);
    setSuggestionErrorFieldKey(null);
    setSuggestingFieldKey(fieldKey);
    pendingSuggestFieldKey.current = fieldKey;
    suggestOp.start();
  }

  function handleCancelSuggest(): void {
    suggestOp.cancel();
    pendingSuggestFieldKey.current = null;
    setSuggestingFieldKey(null);
  }

  return {
    suggestingFieldKey,
    suggestionError,
    suggestionErrorFieldKey,
    suggestMutation,
    handleSuggest,
    handleCancelSuggest,
  };
}
