/**
 * Rewrite alternatives SSE → Promise bridge.
 *
 * Bridges the callback-based SSE transport ({@link streamRewrite}) to
 * {@link useAIOperation}'s `execute(signal) => Promise<T>` contract. Extracted
 * from {@link useRewriteFlow} for modularity (RULE-04); behavior is unchanged.
 *
 * ADR-043 compliance — the bridge mechanism:
 *   - `onAlternative` accumulates alternatives and drives the parent setters
 *     (aiSuggestion, selectedSuggestion, rewritePhase); alternatives appear as
 *     they arrive (loading → streaming → showing-alternatives).
 *   - stream completion resolves the promise with the accumulated alternatives.
 *   - `onError` re-throws so useAIOperation's error mapper + the hook's
 *     `onError` drive setRewriteError + setRewritePhase.
 *   - cancel/abort is translated to an AbortError rejection (swallowed → idle).
 *
 * @module rewriteStream
 */

import type { Dispatch, SetStateAction } from "react";
import { type RewriteAlternative, type RewriteConfig, streamRewrite } from "@/lib/api/generation";
import type { AISuggestion, RewritePhase, RewriteSelection } from "./TipTapEditorController";

/** Inputs for a single rewrite alternative-generation stream. */
export interface RewriteStreamParams {
  readonly signal: AbortSignal;
  readonly chapterId: string | undefined;
  readonly novelId: string | undefined;
  readonly locale: string;
  /** The rewrite config staged for this request (null resolves with []). */
  readonly config: RewriteConfig | null;
  /** The current rewrite selection (null resolves with []). */
  readonly selection: RewriteSelection | null;
  /** Parent setters the stream drives (rewrite state stays in the hook). */
  readonly setAiSuggestion: Dispatch<SetStateAction<AISuggestion | null>>;
  readonly setSelectedSuggestion: Dispatch<SetStateAction<number>>;
  readonly setRewritePhase: Dispatch<SetStateAction<RewritePhase>>;
}

/**
 * Run one rewrite alternative-generation stream, resolving with the
 * accumulated alternatives on completion and rejecting on error/abort.
 *
 * Defensive: a start() without a staged config/selection resolves with [].
 */
export async function runRewriteStream({
  signal,
  chapterId,
  novelId,
  locale,
  config,
  selection,
  setAiSuggestion,
  setSelectedSuggestion,
  setRewritePhase,
}: RewriteStreamParams): Promise<RewriteAlternative[]> {
  const sel = selection;
  if (!sel || !chapterId || !novelId || !config) {
    return [];
  }

  const alternatives: RewriteAlternative[] = [];

  await streamRewrite(
    chapterId,
    novelId,
    {
      selection_text: sel.text,
      context_before: sel.contextBefore,
      context_after: sel.contextAfter,
      mode: config.mode,
      options: config.mode !== "custom" ? { option: config.option } : undefined,
      count: config.count,
      custom_instructions: config.customInstructions,
      language: locale,
    },
    {
      onAlternative: (label, text) => {
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
        // Stream complete — alternatives already accumulated
      },
      onError: (error: Error) => {
        // Let useAIOperation's error mapper handle it
        throw error;
      },
    },
    signal,
  );

  return alternatives;
}
