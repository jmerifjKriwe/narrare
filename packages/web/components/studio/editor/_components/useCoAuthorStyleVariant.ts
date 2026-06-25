"use client";

/**
 * Co-Author Style-Variant Regeneration hook (CR-AUFG-07-22 Increment B).
 *
 * Owns the variant lifecycle for the Co-Author output review surface: the
 * selected variant, the streamed result, and any structured error. Selecting a
 * variant regenerates the Co-Author's full revised output (`streamedText`) in
 * the chosen creative direction.
 *
 * ADR-043 compliance: the streaming lifecycle (AbortController management,
 * loading/streaming/error state, connection-loss detection, retry) runs through
 * {@link useAIOperation} — no manual AbortController. The callback-based SSE
 * transport ({@link streamStyleVariantRegeneration}) is bridged to the hook's
 * `execute(signal) => Promise<T>` contract the same way `useUnblockStream`
 * bridges `streamStorySuggestions` and `useContinueStream` bridges `streamExtend`:
 *
 *   - `onAlternative` notifies the hook (loading → streaming) and stores text
 *   - stream completion resolves the promise (status → complete)
 *   - `onError` rejects the promise; errors map via {@link mapSSEError}
 *   - cancel/abort is translated to an AbortError rejection (swallowed → idle)
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
 * @module useCoAuthorStyleVariant
 */

import { useCallback, useMemo, useRef, useState } from "react";
import { mapSSEError } from "@/lib/api/ai-error-mapping";
import { type StyleVariant, streamStyleVariantRegeneration } from "@/lib/api/generation";
import { type AIErrorResponse, useAIOperation } from "@/lib/hooks/use-ai-operation";

/** Inputs the hook reads from the Co-Author panel. */
interface UseCoAuthorStyleVariantParams {
  readonly novelId: string | undefined;
  readonly chapterId: string | undefined;
  readonly locale: string;
  /**
   * The Co-Author's full revised output — becomes `source_text` for the
   * variant regeneration. Empty until the Co-Author stream completes.
   */
  readonly streamedText: string;
}

/** Memoized return — stable references for panel callbacks that depend on it. */
export interface UseCoAuthorStyleVariantResult {
  /** Currently selected variant, or null when nothing chosen yet. */
  readonly selectedVariant: StyleVariant | null;
  /** Regenerated passage text (empty until the variant stream completes). */
  readonly variantText: string;
  /** True while a variant regeneration is loading or streaming. */
  readonly isVariantStreaming: boolean;
  /** Structured error from the last variant stream (null when none). */
  readonly variantError: AIErrorResponse | null;
  /** Fire when the writer picks a variant from the dropdown. */
  readonly handleVariantSelect: (variant: StyleVariant) => void;
  /** Abort any in-flight variant stream (RULE-20 visible cancel). */
  readonly cancel: () => void;
  /** Reset the whole variant surface: cancel, clear text/variant/error. */
  readonly reset: () => void;
}

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
      new Promise<string>((resolve, reject) => {
        const variant = pendingVariantRef.current;
        // Defensive: a start() without a staged request resolves immediately.
        if (!variant || !chapterId || !novelId) {
          resolve("");
          return;
        }

        let settled = false;

        const onAbort = () => {
          if (!settled) {
            settled = true;
            reject(new DOMException("Aborted", "AbortError"));
          }
        };
        signal.addEventListener("abort", onAbort, { once: true });

        // Bridge the callback-based SSE stream to execute()'s Promise
        // contract. Variant regeneration yields a single alternative; the
        // text arrives when the closing tag is parsed (onAlternative), and
        // the stream resolves once complete (same semantics as the rewrite
        // surface — alternatives appear when complete, not chunk-streamed).
        streamStyleVariantRegeneration(
          chapterId,
          novelId,
          {
            source_text: streamedText,
            style_variant: variant,
            language: locale,
            // Increment B: the source is a Co-Author output, not a rewrite selection.
            source_mode: "co_author",
          },
          {
            onAlternative: (_label, text) => {
              notifyData();
              setVariantText(text);
            },
            onError: (error: Error) => {
              if (!settled) {
                settled = true;
                signal.removeEventListener("abort", onAbort);
                reject(error);
              }
            },
          },
          signal,
        ).then(
          () => {
            if (!settled) {
              settled = true;
              signal.removeEventListener("abort", onAbort);
              resolve("");
            }
          },
          (error: unknown) => {
            if (!settled) {
              settled = true;
              signal.removeEventListener("abort", onAbort);
              reject(error instanceof Error ? error : new Error(String(error)));
            }
          },
        );
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
