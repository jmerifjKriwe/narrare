import type { Editor } from "@tiptap/react";
import type { Dispatch, SetStateAction } from "react";
import { useCallback } from "react";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
import { insertAIContentAt, replaceSelectionWithAIContent } from "./extensions/AIAnnotation";
import type { AISuggestion, RewritePhase, RewriteSelection } from "./TipTapEditorController";

/**
 * Variant + rewrite lifecycle operations the resolution actions drive.
 *
 * Defined structurally so the hook depends only on the methods it uses, not on
 * the full {@link useAIOperation} / {@link useStyleVariantRegeneration} return
 * types.
 */
export interface RewriteActionOps {
  /** Cancels an in-flight variant stream and clears the selected variant. */
  readonly handleVariantCancel: () => void;
  /** Resets the rewrite AI operation lifecycle to idle. */
  readonly reset: () => void;
  /** Cancels the in-flight rewrite AI operation. */
  readonly cancel: () => void;
}

/** Controller state setters the resolution actions drive. */
export interface RewriteActionSetters {
  readonly setAiSuggestion: Dispatch<SetStateAction<AISuggestion | null>>;
  readonly setRewritePhase: Dispatch<SetStateAction<RewritePhase>>;
  readonly setRewriteSelection: Dispatch<SetStateAction<RewriteSelection | null>>;
  readonly setShowRejectionInput: Dispatch<SetStateAction<boolean>>;
  readonly setRejectionReason: Dispatch<SetStateAction<string>>;
  readonly setRewriteError: Dispatch<SetStateAction<AIErrorResponse | null>>;
}

interface UseRewriteActionsParams {
  readonly editor: Editor | null;
  readonly aiSuggestion: AISuggestion | null;
  readonly selectedSuggestion: number;
  readonly rejectionReason: string;
  /** Stable lifecycle handles from useRewriteFlow's generation hooks. */
  readonly ops: RewriteActionOps;
  readonly setters: RewriteActionSetters;
}

/**
 * Resolves a rewrite suggestion: accept, insert-as-new, or reject, plus the
 * shared reset/cancel teardown.
 *
 * Single responsibility: translate a generated rewrite suggestion into an
 * editor mutation (replace selection or insert after) and tear down the
 * rewrite state machine. The suggestion data, editor, lifecycle handles, and
 * shared setters are supplied by {@link useRewriteFlow}; this hook owns only
 * the resolution callbacks.
 */
export function useRewriteActions({
  editor,
  aiSuggestion,
  selectedSuggestion,
  rejectionReason,
  ops,
  setters,
}: UseRewriteActionsParams) {
  const {
    setAiSuggestion,
    setRewritePhase,
    setRewriteSelection,
    setShowRejectionInput,
    setRejectionReason,
    setRewriteError,
  } = setters;

  const resetRewriteState = useCallback(() => {
    ops.handleVariantCancel();
    setAiSuggestion(null);
    setRewritePhase("idle");
    setRewriteSelection(null);
    setShowRejectionInput(false);
    setRejectionReason("");
    setRewriteError(null);
    ops.reset();
  }, [
    ops,
    setAiSuggestion,
    setRewritePhase,
    setRewriteSelection,
    setShowRejectionInput,
    setRejectionReason,
    setRewriteError,
  ]);

  const acceptSuggestion = useCallback(() => {
    if (!editor || !aiSuggestion) return;
    replaceSelectionWithAIContent(
      editor,
      `rewrite-${Date.now()}`,
      "rewrite",
      aiSuggestion.suggestions[selectedSuggestion],
      aiSuggestion.position.from,
      aiSuggestion.position.to,
    );
    resetRewriteState();
  }, [editor, aiSuggestion, selectedSuggestion, resetRewriteState]);

  const insertAsNew = useCallback(() => {
    if (!editor || !aiSuggestion) return;
    insertAIContentAt(
      editor,
      `rewrite-${Date.now()}`,
      "rewrite",
      aiSuggestion.suggestions[selectedSuggestion],
      aiSuggestion.position.to,
    );
    resetRewriteState();
  }, [editor, aiSuggestion, selectedSuggestion, resetRewriteState]);

  const rejectSuggestion = useCallback(() => {
    if (rejectionReason.trim()) resetRewriteState();
    else setShowRejectionInput(true);
  }, [rejectionReason, resetRewriteState, setShowRejectionInput]);

  const handleRewriteCancel = useCallback(() => {
    ops.handleVariantCancel();
    ops.cancel();
    setRewritePhase("idle");
    setRewriteSelection(null);
  }, [ops, setRewritePhase, setRewriteSelection]);

  return { acceptSuggestion, insertAsNew, rejectSuggestion, handleRewriteCancel };
}
