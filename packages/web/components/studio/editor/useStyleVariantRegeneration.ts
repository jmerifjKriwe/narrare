import type { Dispatch, RefObject, SetStateAction } from "react";
import { useCallback, useMemo, useRef, useState } from "react";
import { mapSSEError } from "@/lib/api/ai-error-mapping";
import {
  type RewriteAlternative,
  type StyleVariant,
  streamStyleVariantRegeneration,
} from "@/lib/api/generation";
import { type AIErrorResponse, useAIOperation } from "@/lib/hooks/use-ai-operation";
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
 * ADR-043 compliance: the streaming lifecycle (AbortController management,
 * loading/streaming/error state, connection-loss detection) runs through
 * {@link useAIOperation} — no manual AbortController. The callback-based SSE
 * transport ({@link streamStyleVariantRegeneration}) is bridged to the hook's
 * `execute(signal) => Promise<T>` contract the same way `useUnblockStream`
 * bridges `streamStorySuggestions` and `useCoAuthorStyleVariant` bridges the
 * Co-Author variant stream:
 *
 *   - `onAlternative` notifies the hook (loading → streaming) and drives the
 *     parent setters (aiSuggestion, selectedSuggestion, rewritePhase)
 *   - `onAlternativeFinal` drives the parent rewritePhase on stream completion
 *   - stream completion resolves the promise
 *   - `onError` rejects the promise; errors map via {@link mapSSEError} and the
 *     hook's `onError` callback drives setRewriteError + setRewritePhase
 *   - cancel/abort is translated to an AbortError rejection (swallowed → idle)
 *
 * The hook owns the variant lifecycle (selected variant + in-flight operation)
 * via `useAIOperation`. The shared rewrite state-machine (phase, suggestion,
 * error) stays in the controller and is driven via `setters`, so the rewrite
 * flow keeps a single owner. `useAIOperation` manages the LIFECYCLE (loading,
 * error, cancel), while the parent setters manage the REWRITE STATE
 * (AISuggestion, RewritePhase) — these are separate concerns, no conflict.
 * The return value is memoized so controller callbacks depending on it stay
 * referentially stable across renders.
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
      new Promise<void>((resolve, reject) => {
        const variant = pendingVariantRef.current;
        const sel = rewriteSelectionRef.current;
        // Defensive: a start() without a staged request resolves immediately.
        if (!variant || !sel || !chapterId || !novelId) {
          resolve();
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
        // contract. Variant regeneration yields alternatives that accumulate
        // into the shared aiSuggestion state; the stream resolves once
        // complete (same semantics as the rewrite surface — alternatives
        // appear when complete, not chunk-streamed).
        const alternatives: RewriteAlternative[] = [];

        streamStyleVariantRegeneration(
          chapterId,
          novelId,
          {
            source_text: sel.text,
            context_before: sel.contextBefore,
            context_after: sel.contextAfter,
            style_variant: variant,
            language: locale,
          },
          {
            onAlternative: (label, text) => {
              notifyData();
              alternatives.push({ label, text });
              setAiSuggestion((prev) =>
                prev
                  ? {
                      ...prev,
                      suggestions: alternatives.map((a) => a.text),
                      labels: alternatives.map((a) => a.label),
                    }
                  : {
                      original: sel.text,
                      suggestions: alternatives.map((a) => a.text),
                      labels: alternatives.map((a) => a.label),
                      position: { from: sel.from, to: sel.to },
                    },
              );
              if (alternatives.length === 1) setSelectedSuggestion(0);
              setRewritePhase("showing-alternatives");
            },
            onAlternativeFinal: () => {
              setRewritePhase((prev) => (prev === "streaming" ? "showing-alternatives" : prev));
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
              resolve();
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
