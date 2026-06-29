import type { Dispatch, RefObject, SetStateAction } from "react";
import { useCallback, useMemo, useRef, useState } from "react";
import { mapSSEError } from "@/lib/api/ai-error-mapping";
import type { StyleVariant } from "@/lib/api/generation";
import { type AIErrorResponse, useAIOperation } from "@/lib/hooks/use-ai-operation";
import { runRewriteVariantStream } from "./styleVariantRegenerationStream";
import type { AISuggestion, RewritePhase, RewriteSelection } from "./TipTapEditorController";

/** Stream inputs for variant regeneration — what to generate from. */
interface VariantStreamContext {
  chapterId: string | undefined;
  novelId: string | undefined;
  locale: string;
  /** Current rewrite selection (ref owned by the controller). */
  rewriteSelectionRef: RefObject<RewriteSelection | null>;
}

/** Controller state setters the hook drives — how results reach the rewrite machine. */
interface VariantStateSetters {
  setAiSuggestion: Dispatch<SetStateAction<AISuggestion | null>>;
  setSelectedSuggestion: Dispatch<SetStateAction<number>>;
  setRewritePhase: Dispatch<SetStateAction<RewritePhase>>;
  setRewriteError: Dispatch<SetStateAction<AIErrorResponse | null>>;
}

interface UseStyleVariantRegenerationParams {
  context: VariantStreamContext;
  setters: VariantStateSetters;
}

/**
 * Style-Variant Regeneration (CR-AUFG-07-22).
 *
 * Selecting a variant from the dropdown triggers a new generation using the
 * current selection text as source_text. The original output remains visible
 * in aiSuggestion.original until a variant is accepted.
 *
 * The hook owns the variant lifecycle (selected variant + in-flight operation)
 * via `useAIOperation`. The shared rewrite state-machine (phase, suggestion,
 * error) stays in the controller and is driven via `setters`, so the rewrite
 * flow keeps a single owner. `useAIOperation` manages the LIFECYCLE (loading,
 * error, cancel), while the parent setters manage the REWRITE STATE
 * (AISuggestion, RewritePhase) — these are separate concerns, no conflict.
 * The return value is memoized so controller callbacks depending on it stay
 * referentially stable across renders.
 *
 * ADR-043 streaming lifecycle runs through {@link useAIOperation}; the SSE→Promise
 * bridge (transport callbacks settled into execute()'s contract) lives in
 * {@link runRewriteVariantStream} (see styleVariantRegenerationStream.ts).
 */
export function useStyleVariantRegeneration({
  context,
  setters,
}: UseStyleVariantRegenerationParams) {
  const { chapterId, locale, novelId, rewriteSelectionRef } = context;
  const { setAiSuggestion, setSelectedSuggestion, setRewriteError, setRewritePhase } = setters;

  const [styleVariant, setStyleVariant] = useState<StyleVariant | null>(null);

  // The variant chosen for the in-flight request. Staged before start() so
  // execute() reads the current value via the ref (same pattern as
  // useUnblockStream's instructionsRef / useCoAuthorStyleVariant's pendingVariantRef).
  const pendingVariantRef = useRef<StyleVariant | null>(null);

  // -- AI operation lifecycle via useAIOperation (ADR-043) --
  const { start, cancel, notifyData } = useAIOperation<void>({
    errorMapper: mapSSEError,
    connectionLossTimeout: 15_000,
    onError: (mapped: AIErrorResponse) => {
      setRewriteError(mapped);
      setRewritePhase((prev) => (prev === "streaming" ? "showing-alternatives" : prev));
    },
    execute: (signal) =>
      // The SSE→Promise bridge (transport callbacks, abort/settling, setter
      // driving) runs in runRewriteVariantStream; the hook keeps the lifecycle.
      runRewriteVariantStream({
        signal,
        chapterId,
        novelId,
        locale,
        variant: pendingVariantRef.current,
        selection: rewriteSelectionRef.current,
        // Wrap notifyData in an arrow so the reference is deferred (matches the
        // coauthor sibling). A bare shorthand `notifyData,` makes TS treat it
        // as referenced in its own initializer (circular via useAIOperation's
        // return type inference) → TS7022/TS7023. Behavior is unchanged.
        notifyData: () => notifyData(),
        setAiSuggestion,
        setSelectedSuggestion,
        setRewritePhase,
      }),
  });

  const handleStyleVariantRegenerate = useCallback(
    (variant: StyleVariant) => {
      const sel = rewriteSelectionRef.current;
      if (!sel || !chapterId || !novelId) return;

      // Stage the variant so execute() reads it via the ref.
      pendingVariantRef.current = variant;
      setStyleVariant(variant);
      setRewritePhase("streaming");
      setRewriteError(null);

      // start() clears any prior error and transitions to loading. If a
      // previous variant stream is still in flight, useAIOperation's start()
      // cancels it first (abort → AbortError rejection → idle → loading).
      start();
    },
    [chapterId, novelId, rewriteSelectionRef, setRewriteError, setRewritePhase, start],
  );

  /**
   * Tear down the variant operation: cancel any in-flight stream and clear the
   * selected variant. Exposed so the controller's resetRewriteState and
   * handleRewriteCancel can release the variant operation, which is
   * encapsulated here.
   */
  const handleVariantCancel = useCallback(() => {
    cancel();
    setStyleVariant(null);
  }, [cancel]);

  return useMemo(
    () => ({ handleStyleVariantRegenerate, handleVariantCancel, styleVariant }),
    [handleStyleVariantRegenerate, handleVariantCancel, styleVariant],
  );
}
