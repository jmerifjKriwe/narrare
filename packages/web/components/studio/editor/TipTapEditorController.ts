import type { useTranslations } from "next-intl";
import { useGhostTextOnboarding } from "./GhostTextOnboarding";
import { useEditorAutosave } from "./useEditorAutosave";
import { useEditorInstance } from "./useEditorInstance";
import { useGhostTextConfig } from "./useGhostTextConfig";
import { useGhostTextOnboardingAnchor } from "./useGhostTextOnboardingAnchor";
import { MAX_SELECTION_LENGTH, MIN_SELECTION_LENGTH, useRewriteFlow } from "./useRewriteFlow";

// Re-export the selection-length constants so existing consumers
// (e.g. TipTapBubbleMenu) keep resolving them from this module — the public
// import surface is unchanged. They are defined in useRewriteFlow, the rewrite
// feature that owns selection-length validation.
export { MAX_SELECTION_LENGTH, MIN_SELECTION_LENGTH };

type StudioTranslator = ReturnType<typeof useTranslations>;

export interface AISuggestion {
  original: string;
  suggestions: string[];
  labels: string[];
  position: { from: number; to: number };
}

export type RewritePhase = "idle" | "selecting-mode" | "streaming" | "showing-alternatives";

export interface RewriteSelection {
  text: string;
  from: number;
  to: number;
  contextBefore: string;
  contextAfter: string;
}

interface ControllerParams {
  content: string;
  onChange: (content: string) => void;
  onAutosave?: (content: string) => Promise<void>;
  autosaveInterval?: number;
  chapterId?: string;
  novelId?: string;
  locale: string;
  t: StudioTranslator;
}

/**
 * Thin composer for the studio editor's controller surface.
 *
 * Responsibilities are delegated to focused sub-hooks (RULE-04 / RULE-06):
 *
 * - {@link useEditorAutosave} — Autosave extension config + implicit-accept feedback.
 * - {@link useGhostTextConfig} — GhostText extension config (SSE fetcher + i18n strings).
 * - {@link useEditorInstance} — TipTap editor creation, content sync, store registration.
 * - {@link useGhostTextOnboardingAnchor} — DOM anchor for the onboarding callout.
 * - {@link useRewriteFlow} — AI rewrite state machine (trigger → stream → resolve).
 *
 * The public return shape is the stable contract consumed by `TipTapEditor`;
 * the sub-hooks are wired here and their outputs spread onto that shape.
 */
export function useTipTapEditorController({
  content,
  onChange,
  onAutosave,
  autosaveInterval,
  chapterId,
  novelId,
  locale,
  t,
}: ControllerParams) {
  const { shouldShow: showOnboarding, dismiss: dismissOnboarding } = useGhostTextOnboarding();

  const autosaveConfig = useEditorAutosave({
    onAutosave,
    autosaveInterval,
    novelId,
    chapterId,
  });
  const ghostTextConfig = useGhostTextConfig({ chapterId, locale, t });
  const editor = useEditorInstance({ content, onChange, autosaveConfig, ghostTextConfig, t });
  const onboardingAnchor = useGhostTextOnboardingAnchor({ editor, showOnboarding });
  const rewrite = useRewriteFlow({ editor, chapterId, novelId, locale });

  const selectionLength = editor
    ? editor.state.doc
        .textBetween(editor.state.selection.from, editor.state.selection.to, " ")
        .trim().length
    : 0;

  return {
    editor,
    aiSuggestion: rewrite.aiSuggestion,
    selectedSuggestion: rewrite.selectedSuggestion,
    setSelectedSuggestion: rewrite.setSelectedSuggestion,
    rejectionReason: rewrite.rejectionReason,
    setRejectionReason: rewrite.setRejectionReason,
    showRejectionInput: rewrite.showRejectionInput,
    rewritePhase: rewrite.rewritePhase,
    rewriteSelection: rewrite.rewriteSelection,
    rewriteError: rewrite.rewriteError,
    setRewriteError: rewrite.setRewriteError,
    showOnboarding,
    dismissOnboarding,
    onboardingAnchor,
    selectionLength,
    isRewriteEnabled:
      selectionLength >= MIN_SELECTION_LENGTH && selectionLength <= MAX_SELECTION_LENGTH,
    isRewriteStreaming: rewrite.isRewriteStreaming,
    handleAIRewrite: rewrite.handleAIRewrite,
    handleRewriteGenerate: rewrite.handleRewriteGenerate,
    styleVariant: rewrite.styleVariant,
    handleStyleVariantRegenerate: rewrite.handleStyleVariantRegenerate,
    handleRewriteCancel: rewrite.handleRewriteCancel,
    acceptSuggestion: rewrite.acceptSuggestion,
    insertAsNew: rewrite.insertAsNew,
    rejectSuggestion: rewrite.rejectSuggestion,
  };
}
