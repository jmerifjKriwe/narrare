import type { Editor } from "@tiptap/react";
import { useCallback, useMemo, useRef, useState } from "react";
import type { RewriteConfig } from "@/lib/api/generation";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
import type { AISuggestion, RewritePhase, RewriteSelection } from "./TipTapEditorController";
import { useRewriteActions } from "./useRewriteActions";
import { useRewriteOperation } from "./useRewriteOperation";
import { useStyleVariantRegeneration } from "./useStyleVariantRegeneration";

/** Minimum selection length (chars) required to trigger an AI rewrite. */
export const MIN_SELECTION_LENGTH = 50;
/** Maximum selection length (chars) accepted for an AI rewrite. */
export const MAX_SELECTION_LENGTH = 2000;

interface UseRewriteFlowParams {
  editor: Editor | null;
  chapterId?: string;
  novelId?: string;
  locale: string;
}

/**
 * Owns the AI rewrite feature lifecycle.
 *
 * Single responsibility: the rewrite state machine — from the selection
 * trigger (`handleAIRewrite`) through mode selection, SSE streaming of
 * alternatives (via {@link useAIOperation} + {@link runRewriteStream}),
 * style-variant regeneration (via {@link useStyleVariantRegeneration}), and
 * suggestion resolution (accept / insert-as-new / reject). All rewrite-facing
 * controller state and handlers live here; the composer re-exposes them on the
 * unchanged public controller surface.
 *
 * ADR-043 streaming lifecycle runs through `useAIOperation`; the SSE→Promise
 * bridge lives in {@link rewriteStream}.
 */
export function useRewriteFlow({ editor, chapterId, novelId, locale }: UseRewriteFlowParams) {
  const [aiSuggestion, setAiSuggestion] = useState<AISuggestion | null>(null);
  const [selectedSuggestion, setSelectedSuggestion] = useState(0);
  const [rejectionReason, setRejectionReason] = useState("");
  const [showRejectionInput, setShowRejectionInput] = useState(false);
  const [rewritePhase, setRewritePhase] = useState<RewritePhase>("idle");
  const [rewriteSelection, setRewriteSelection] = useState<RewriteSelection | null>(null);
  const [rewriteError, setRewriteError] = useState<AIErrorResponse | null>(null);
  const rewriteConfigRef = useRef<RewriteConfig | null>(null);
  const rewriteSelectionRef = useRef<RewriteSelection | null>(null);

  // --- Rewrite AI Operation (§16 lifecycle management) ---
  const rewriteAiOp = useRewriteOperation({
    chapterId,
    novelId,
    locale,
    rewriteConfigRef,
    rewriteSelectionRef,
    setters: { setAiSuggestion, setSelectedSuggestion, setRewritePhase, setRewriteError },
  });

  const getSelectionContext = useCallback(
    (from: number, to: number) => {
      if (!editor) return { contextBefore: "", contextAfter: "" };
      const contextRadius = 800;
      return {
        contextBefore: editor.state.doc.textBetween(Math.max(0, from - contextRadius), from, " "),
        contextAfter: editor.state.doc.textBetween(
          to,
          Math.min(editor.state.doc.content.size, to + contextRadius),
          " ",
        ),
      };
    },
    [editor],
  );

  const handleAIRewrite = useCallback(() => {
    if (!editor) return;
    const { from, to } = editor.state.selection;
    const selectedText = editor.state.doc.textBetween(from, to, " ");
    const trimmedLength = selectedText.trim().length;
    if (trimmedLength < MIN_SELECTION_LENGTH || trimmedLength > MAX_SELECTION_LENGTH) return;
    setRewriteSelection({ text: selectedText, from, to, ...getSelectionContext(from, to) });
    setRewritePhase("selecting-mode");
  }, [editor, getSelectionContext]);

  const handleRewriteGenerate = useCallback(
    (config: RewriteConfig) => {
      if (!editor || !rewriteSelection || !chapterId || !novelId) return;
      rewriteConfigRef.current = config;
      rewriteSelectionRef.current = rewriteSelection;
      setRewritePhase("streaming");
      setRewriteError(null);
      rewriteAiOp.start();
    },
    [editor, rewriteSelection, chapterId, novelId, rewriteAiOp],
  );

  const variantRegen = useStyleVariantRegeneration({
    context: { chapterId, locale, novelId, rewriteSelectionRef },
    setters: { setAiSuggestion, setSelectedSuggestion, setRewriteError, setRewritePhase },
  });

  // Suggestion resolution (accept / insert-as-new / reject / cancel) is owned
  // by useRewriteActions; the lifecycle handles are memoized on the same stable
  // objects the inline callbacks previously depended on, so identities match.
  const actionOps = useMemo(
    () => ({
      handleVariantCancel: variantRegen.handleVariantCancel,
      reset: rewriteAiOp.reset,
      cancel: rewriteAiOp.cancel,
    }),
    [variantRegen, rewriteAiOp],
  );
  const actions = useRewriteActions({
    editor,
    aiSuggestion,
    selectedSuggestion,
    rejectionReason,
    ops: actionOps,
    setters: {
      setAiSuggestion,
      setRewritePhase,
      setRewriteSelection,
      setShowRejectionInput,
      setRejectionReason,
      setRewriteError,
    },
  });

  return {
    aiSuggestion,
    selectedSuggestion,
    setSelectedSuggestion,
    rejectionReason,
    setRejectionReason,
    showRejectionInput,
    rewritePhase,
    rewriteSelection,
    rewriteError,
    isRewriteStreaming:
      rewritePhase === "streaming" || rewriteAiOp.isLoading || rewriteAiOp.isStreaming,
    handleAIRewrite,
    handleRewriteGenerate,
    styleVariant: variantRegen.styleVariant,
    handleStyleVariantRegenerate: variantRegen.handleStyleVariantRegenerate,
    handleRewriteCancel: actions.handleRewriteCancel,
    acceptSuggestion: actions.acceptSuggestion,
    insertAsNew: actions.insertAsNew,
    rejectSuggestion: actions.rejectSuggestion,
  };
}
