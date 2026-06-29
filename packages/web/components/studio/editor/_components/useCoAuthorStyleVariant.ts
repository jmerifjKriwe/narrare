"use client";

/**
 * Co-Author Style-Variant Regeneration hook (CR-AUFG-07-22 Increment B).
 *
 * Owns the variant lifecycle for the Co-Author output review surface: the
 * selected variant, the streamed result, and any structured error. Selecting a
 * variant regenerates the Co-Author's full revised output (`streamedText`) in
 * the chosen creative direction.
 *
 * Why a dedicated hook and not a `source_mode` flag on
 * `useStyleVariantRegeneration`? The rewrite hook is coupled to the Rewrite
 * state machine (`AISuggestion`, `RewritePhase`, the editor's
 * `rewriteSelectionRef`) and therefore holds a governed ADR-043 exclusion
 * (it drives a shared parent state machine via injected setters). The Co-Author
 * surface has a different, self-contained state model (`CoAuthorPhase`,
 * `ChangeDetail[]`, a full revised passage), so this hook owns its state
 * directly (state-decouple-implementation) and CAN adopt `useAIOperation` — no
 * exclusion required. The two surfaces share the `streamStyleVariantRegeneration`
 * transport/primitive (already the correct reuse layer) and each owns its own
 * lifecycle — explicit variant hooks over a boolean mode.
 *
 * Per the spec, the original Co-Author output remains visible and unchanged; the
 * variant result is surfaced alongside it for comparison.
 *
 * ADR-043 streaming lifecycle (AbortController management, loading/streaming/
 * error state, connection-loss detection, retry) runs through
 * {@link useAIOperation} — no manual AbortController. The SSE→Promise bridge
 * (transport callbacks settled into execute()'s contract) lives in
 * {@link runCoAuthorVariantStream} (see coauthor-style-variant-stream.ts).
 *
 * @module useCoAuthorStyleVariant
 */

import { useCallback, useMemo, useRef, useState } from "react";
import { mapSSEError } from "@/lib/api/ai-error-mapping";
import type { StyleVariant } from "@/lib/api/generation";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import {
  runCoAuthorVariantStream,
  type UseCoAuthorStyleVariantParams,
  type UseCoAuthorStyleVariantResult,
} from "./coauthor-style-variant-stream";

// Re-export the public contract so existing imports of the result type from
// this module keep resolving (public API preserved during the RULE-04 split).
export type { UseCoAuthorStyleVariantResult };

export function useCoAuthorStyleVariant({
  novelId,
  chapterId,
  locale,
  streamedText,
}: UseCoAuthorStyleVariantParams): UseCoAuthorStyleVariantResult {
  const [selectedVariant, setSelectedVariant] = useState<StyleVariant | null>(null);
  const [variantText, setVariantText] = useState("");

  // The variant chosen for the in-flight request. Staged before start() so
  // execute() reads the current value via the ref (same pattern as
  // useUnblockStream's instructionsRef / useContinueStream's requestRef).
  const pendingVariantRef = useRef<StyleVariant | null>(null);

  // -- AI operation lifecycle via useAIOperation (ADR-043) --
  const {
    state,
    start,
    cancel,
    reset: resetLifecycle,
    notifyData,
    isLoading,
    isStreaming,
  } = useAIOperation<string>({
    errorMapper: mapSSEError,
    connectionLossTimeout: 15_000,
    execute: (signal) =>
      // The SSE→Promise bridge (transport callbacks, abort/settling) runs in
      // runCoAuthorVariantStream; the hook keeps the reactive state wiring.
      runCoAuthorVariantStream({
        signal,
        chapterId,
        novelId,
        locale,
        streamedText,
        variant: pendingVariantRef.current,
        onAlternativeText: (text) => {
          notifyData();
          setVariantText(text);
        },
      }),
  });

  /** Fire when the writer picks a variant from the dropdown. */
  const handleVariantSelect = useCallback(
    (variant: StyleVariant) => {
      if (!chapterId || !novelId) return;
      // source_text must meet the backend min_length; guard against an empty
      // Co-Author output so we never fire a request destined to 422.
      if (!streamedText.trim()) return;

      pendingVariantRef.current = variant;
      setSelectedVariant(variant);
      setVariantText("");

      // start() clears any prior error and transitions to loading. The picker
      // is disabled while streaming, so a concurrent start is not reachable; if
      // one were attempted, useAIOperation's start() no-ops while in flight.
      start();
    },
    [chapterId, novelId, streamedText, start],
  );

  /** Reset the whole variant surface: cancel, clear text/variant/error. */
  const reset = useCallback(() => {
    resetLifecycle();
    setSelectedVariant(null);
    setVariantText("");
  }, [resetLifecycle]);

  return useMemo(
    () => ({
      selectedVariant,
      variantText,
      // Covers both the loading and streaming phases — the spinner shows as
      // soon as the request is dispatched, matching the original behavior.
      isVariantStreaming: isLoading || isStreaming,
      variantError: state.error,
      handleVariantSelect,
      cancel,
      reset,
    }),
    [
      selectedVariant,
      variantText,
      isLoading,
      isStreaming,
      state.error,
      handleVariantSelect,
      cancel,
      reset,
    ],
  );
}
