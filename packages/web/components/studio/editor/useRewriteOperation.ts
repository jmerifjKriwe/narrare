import type { Dispatch, RefObject, SetStateAction } from "react";
import { mapSSEError } from "@/lib/api/ai-error-mapping";
import type { RewriteAlternative, RewriteConfig } from "@/lib/api/generation";
import { type AIErrorResponse, useAIOperation } from "@/lib/hooks/use-ai-operation";
import { runRewriteStream } from "./rewriteStream";
import type { AISuggestion, RewritePhase, RewriteSelection } from "./TipTapEditorController";

/** Controller state setters the rewrite operation drives on stream events. */
export interface RewriteOperationSetters {
  readonly setAiSuggestion: Dispatch<SetStateAction<AISuggestion | null>>;
  readonly setSelectedSuggestion: Dispatch<SetStateAction<number>>;
  readonly setRewritePhase: Dispatch<SetStateAction<RewritePhase>>;
  readonly setRewriteError: Dispatch<SetStateAction<AIErrorResponse | null>>;
}

interface UseRewriteOperationParams {
  readonly chapterId?: string;
  readonly novelId?: string;
  readonly locale: string;
  /** Refs holding the staged config + selection for the in-flight request. */
  readonly rewriteConfigRef: RefObject<RewriteConfig | null>;
  readonly rewriteSelectionRef: RefObject<RewriteSelection | null>;
  readonly setters: RewriteOperationSetters;
}

/**
 * Owns the rewrite alternatives AI streaming operation.
 *
 * Single responsibility: wrap the SSE rewrite stream ({@link runRewriteStream})
 * in a {@link useAIOperation} lifecycle (loading / streaming / error / cancel)
 * and drive the shared rewrite state on success/error. Mirrors
 * {@link useStyleVariantRegeneration}, which owns the variant sub-stream the
 * same way. ADR-043 streaming lifecycle runs through `useAIOperation`.
 */
export function useRewriteOperation({
  chapterId,
  novelId,
  locale,
  rewriteConfigRef,
  rewriteSelectionRef,
  setters,
}: UseRewriteOperationParams) {
  const { setAiSuggestion, setSelectedSuggestion, setRewritePhase, setRewriteError } = setters;

  return useAIOperation<RewriteAlternative[]>({
    execute: async (signal) =>
      runRewriteStream({
        signal,
        chapterId,
        novelId,
        locale,
        config: rewriteConfigRef.current,
        selection: rewriteSelectionRef.current,
        setAiSuggestion,
        setSelectedSuggestion,
        setRewritePhase,
      }),
    errorMapper: mapSSEError,
    onSuccess: () => {
      setRewriteError(null);
    },
    onError: (error) => {
      setRewriteError(error);
      // If no alternatives were generated, go back to idle
      setAiSuggestion((prev) => {
        if (!prev || prev.suggestions.length === 0) {
          setRewritePhase("idle");
          return null;
        }
        return prev;
      });
    },
    connectionLossTimeout: 20_000,
  });
}
