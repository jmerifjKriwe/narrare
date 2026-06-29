/**
 * Rewrite Style-Variant SSE → Promise bridge (CR-AUFG-07-22).
 *
 * Bridges the callback-based SSE transport ({@link streamStyleVariantRegeneration})
 * to {@link useAIOperation}'s `execute(signal) => Promise<T>` contract. Extracted
 * from {@link useStyleVariantRegeneration} for modularity (RULE-04); behavior is
 * unchanged.
 *
 * ADR-043 compliance — the bridge mechanism:
 *   - `onAlternative` notifies the hook (loading → streaming) and drives the
 *     parent setters (aiSuggestion, selectedSuggestion, rewritePhase)
 *   - `onAlternativeFinal` drives the parent rewritePhase on stream completion
 *   - stream completion resolves the promise
 *   - `onError` rejects the promise; errors map via the hook's `mapSSEError`
 *     and the hook's `onError` callback drives setRewriteError + setRewritePhase
 *   - cancel/abort is translated to an AbortError rejection (swallowed → idle)
 *
 * Variant regeneration yields alternatives that accumulate into the shared
 * aiSuggestion state; the stream resolves once complete (same semantics as the
 * rewrite surface — alternatives appear when complete, not chunk-streamed).
 *
 * @module styleVariantRegenerationStream
 */

import type { Dispatch, SetStateAction } from "react";
import {
  type RewriteAlternative,
  type StyleVariant,
  streamStyleVariantRegeneration,
} from "@/lib/api/generation";
import type { AISuggestion, RewritePhase, RewriteSelection } from "./TipTapEditorController";

/** Inputs for a single rewrite variant regeneration stream. */
export interface RewriteVariantStreamParams {
  readonly signal: AbortSignal;
  readonly chapterId: string | undefined;
  readonly novelId: string | undefined;
  readonly locale: string;
  /** The variant staged for this request (null resolves immediately). */
  readonly variant: StyleVariant | null;
  /** The current rewrite selection (null resolves immediately). */
  readonly selection: RewriteSelection | null;
  /** Notifies useAIOperation that data is flowing (loading → streaming). */
  readonly notifyData: () => void;
  /** Parent setters the stream drives (rewrite state stays in the controller). */
  readonly setAiSuggestion: Dispatch<SetStateAction<AISuggestion | null>>;
  readonly setSelectedSuggestion: Dispatch<SetStateAction<number>>;
  readonly setRewritePhase: Dispatch<SetStateAction<RewritePhase>>;
}

/**
 * Run one rewrite style-variant regeneration stream, returning a promise that
 * resolves on completion and rejects on error/abort.
 *
 * Defensive: a start() without a staged request resolves immediately.
 */
export function runRewriteVariantStream({
  signal,
  chapterId,
  novelId,
  locale,
  variant,
  selection,
  notifyData,
  setAiSuggestion,
  setSelectedSuggestion,
  setRewritePhase,
}: RewriteVariantStreamParams): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const sel = selection;
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
  });
}
