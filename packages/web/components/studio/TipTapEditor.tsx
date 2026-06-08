"use client";

import { EditorContent } from "@tiptap/react";
import { useLocale, useTranslations } from "next-intl";
import { BlockControls } from "./BlockControls";
import { AIAnnotationActions } from "./editor/AIAnnotationActions";
import { GhostTextOnboarding } from "./editor/GhostTextOnboarding";
import { RewriteModeSelector } from "./editor/RewriteModeSelector";
import { RewriteSuggestionModal } from "./editor/RewriteSuggestionModal";
import { TipTapBubbleMenu } from "./editor/TipTapBubbleMenu";
import { useTipTapEditorController } from "./editor/TipTapEditorController";

interface TipTapEditorProps {
  content: string;
  onChange: (content: string) => void;
  onAutosave?: (content: string) => Promise<void>;
  autosaveInterval?: number;
  chapterId?: string;
  novelId?: string;
}

export function TipTapEditor({
  content,
  onChange,
  onAutosave,
  autosaveInterval,
  chapterId,
  novelId,
}: TipTapEditorProps) {
  const t = useTranslations("studio");
  const locale = useLocale();
  const controller = useTipTapEditorController({
    content,
    onChange,
    onAutosave,
    autosaveInterval,
    chapterId,
    novelId,
    locale,
    t,
  });

  if (!controller.editor) return null;

  return (
    <div className="relative flex-1">
      <TipTapBubbleMenu
        editor={controller.editor}
        isRewriteEnabled={controller.isRewriteEnabled}
        isRewriteStreaming={controller.isRewriteStreaming}
        selectionLength={controller.selectionLength}
        onAIRewrite={controller.handleAIRewrite}
        t={t}
      />

      <EditorContent editor={controller.editor} className="h-full" />
      <BlockControls editor={controller.editor} />

      {novelId && (
        <AIAnnotationActions editor={controller.editor} projectId={novelId} chapterId={chapterId} />
      )}

      {controller.showOnboarding && controller.onboardingAnchor && (
        <GhostTextOnboarding
          anchorElement={controller.onboardingAnchor}
          onDismiss={controller.dismissOnboarding}
        />
      )}

      {controller.rewritePhase === "selecting-mode" && controller.rewriteSelection && (
        <RewriteModeSelector
          selectionLength={controller.rewriteSelection.text.trim().length}
          onGenerate={controller.handleRewriteGenerate}
          onCancel={controller.handleRewriteCancel}
        />
      )}

      {controller.aiSuggestion && (
        <RewriteSuggestionModal
          aiSuggestion={controller.aiSuggestion}
          selectedSuggestion={controller.selectedSuggestion}
          onSelectedSuggestionChange={controller.setSelectedSuggestion}
          rejectionReason={controller.rejectionReason}
          onRejectionReasonChange={controller.setRejectionReason}
          showRejectionInput={controller.showRejectionInput}
          isRewriteStreaming={controller.isRewriteStreaming}
          rewriteError={controller.rewriteError}
          onReject={controller.rejectSuggestion}
          onInsertAsNew={controller.insertAsNew}
          onNewSuggestions={controller.handleAIRewrite}
          onAccept={controller.acceptSuggestion}
          t={t}
        />
      )}
    </div>
  );
}
