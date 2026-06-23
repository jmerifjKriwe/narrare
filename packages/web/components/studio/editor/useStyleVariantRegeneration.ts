import type { Dispatch, RefObject, SetStateAction } from "react";
import { useCallback, useMemo, useRef, useState } from "react";
import { mapSSEError } from "@/lib/api/ai-error-mapping";
import {
  type RewriteAlternative,
  type StyleVariant,
  streamStyleVariantRegeneration,
} from "@/lib/api/generation";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
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
 * Owns the variant lifecycle (selected variant + in-flight abort controller +
 * regenerate handler). The shared rewrite state-machine (phase, suggestion,
 * error) stays in the controller and is driven via `setters`, so the rewrite
 * flow keeps a single owner. The return value is memoized so controller
 * callbacks depending on it stay referentially stable across renders.
 */
export function useStyleVariantRegeneration({
  context,
  setters,
}: UseStyleVariantRegenerationParams) {
  const { chapterId, locale, novelId, rewriteSelectionRef } = context;
  const { setAiSuggestion, setSelectedSuggestion, setRewriteError, setRewritePhase } = setters;

  const [styleVariant, setStyleVariant] = useState<StyleVariant | null>(null);
  const variantAbortRef = useRef<AbortController | null>(null);

  const handleStyleVariantRegenerate = useCallback(
    (variant: StyleVariant) => {
      const sel = rewriteSelectionRef.current;
      if (!sel || !chapterId || !novelId) return;

      // Abort any in-flight variant stream (RULE-20 visible cancel)
      variantAbortRef.current?.abort();
      const abortController = new AbortController();
      variantAbortRef.current = abortController;

      setStyleVariant(variant);
      setRewritePhase("streaming");
      setRewriteError(null);

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
            const mapped = mapSSEError(error);
            if (mapped) {
              setRewriteError(mapped);
              setRewritePhase((prev) => (prev === "streaming" ? "showing-alternatives" : prev));
            }
          },
        },
        abortController.signal,
      );
    },
    [
      chapterId,
      locale,
      novelId,
      rewriteSelectionRef,
      setAiSuggestion,
      setSelectedSuggestion,
      setRewriteError,
      setRewritePhase,
    ],
  );

  /**
   * Tear down the variant operation: abort any in-flight stream and clear the
   * selected variant. Exposed so the controller's resetRewriteState and
   * handleRewriteCancel can release variantAbortRef, which is encapsulated here.
   */
  const handleVariantCancel = useCallback(() => {
    variantAbortRef.current?.abort();
    setStyleVariant(null);
  }, []);

  return useMemo(
    () => ({ handleStyleVariantRegenerate, handleVariantCancel, styleVariant }),
    [handleStyleVariantRegenerate, handleVariantCancel, styleVariant],
  );
}
