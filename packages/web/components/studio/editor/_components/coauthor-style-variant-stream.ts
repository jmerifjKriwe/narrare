/**
 * Co-Author Style-Variant SSE → Promise bridge (CR-AUFG-07-22 Increment B).
 *
 * Bridges the callback-based SSE transport ({@link streamStyleVariantRegeneration})
 * to {@link useAIOperation}'s `execute(signal) => Promise<T>` contract. Extracted
 * from {@link useCoAuthorStyleVariant} for modularity (RULE-04); behavior is
 * unchanged.
 *
 * ADR-043 compliance — the bridge mechanism:
 *   - `onAlternative` notifies the hook (loading → streaming) and stores text
 *   - stream completion resolves the promise (status → complete)
 *   - `onError` rejects the promise; errors map via the hook's `mapSSEError`
 *   - cancel/abort is translated to an AbortError rejection (swallowed → idle)
 *
 * Increment B: the source is a Co-Author output, so the request always carries
 * `source_mode: "co_author"` and the Co-Author's streamed output as
 * `source_text`.
 *
 * @module coauthor-style-variant-stream
 */

import { type StyleVariant, streamStyleVariantRegeneration } from "@/lib/api/generation";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";

// ---------------------------------------------------------------------------
// Hook contracts (co-located with the feature; re-exported by the hook)
// ---------------------------------------------------------------------------

/** Inputs the Co-Author style-variant hook reads from the Co-Author panel. */
export interface UseCoAuthorStyleVariantParams {
  readonly novelId: string | undefined;
  readonly chapterId: string | undefined;
  readonly locale: string;
  /**
   * The Co-Author's full revised output — becomes `source_text` for the
   * variant regeneration. Empty until the Co-Author stream completes.
   */
  readonly streamedText: string;
}

/** Memoized hook return — stable references for panel callbacks that depend on it. */
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

// ---------------------------------------------------------------------------
// Stream bridge
// ---------------------------------------------------------------------------

/** Inputs for a single Co-Author variant regeneration stream. */
export interface CoAuthorVariantStreamParams {
  readonly signal: AbortSignal;
  readonly chapterId: string | undefined;
  readonly novelId: string | undefined;
  readonly locale: string;
  /** Source text — the Co-Author's full revised output. */
  readonly streamedText: string;
  /** The variant staged for this request (null resolves immediately). */
  readonly variant: StyleVariant | null;
  /** Receives the regenerated alternative text (the hook notifies + stores). */
  readonly onAlternativeText: (text: string) => void;
}

/**
 * Run one Co-Author style-variant regeneration stream, returning a promise that
 * resolves with an empty string on completion and rejects on error/abort.
 *
 * Defensive: a start() without a staged request resolves immediately.
 */
export function runCoAuthorVariantStream({
  signal,
  chapterId,
  novelId,
  locale,
  streamedText,
  variant,
  onAlternativeText,
}: CoAuthorVariantStreamParams): Promise<string> {
  return new Promise<string>((resolve, reject) => {
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

    // Variant regeneration yields a single alternative; the text arrives when
    // the closing tag is parsed (onAlternative), and the stream resolves once
    // complete (same semantics as the rewrite surface — alternatives appear
    // when complete, not chunk-streamed).
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
          onAlternativeText(text);
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
  });
}
