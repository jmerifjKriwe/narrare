"use client";

import { EditorContent } from "@tiptap/react";
import { useLocale, useTranslations } from "next-intl";
import { useMemo } from "react";
import { BlockControls } from "./BlockControls";
import { AIAnnotationActions } from "./editor/AIAnnotationActions";
import { GhostTextOnboarding } from "./editor/GhostTextOnboarding";
import { RewriteErrorBanner } from "./editor/RewriteErrorBanner";
import { RewriteModeSelector } from "./editor/RewriteModeSelector";
import { RewriteSuggestionModal } from "./editor/RewriteSuggestionModal";
import {
  AI_SLASH_COMMANDS,
  type SlashCommandDispatchContext,
  type SlashCommandHandlers,
  SlashCommandMenu,
  useSlashCommandState,
} from "./editor/slash-commands";
import { TipTapBubbleMenu } from "./editor/TipTapBubbleMenu";
import { useTipTapEditorController } from "./editor/TipTapEditorController";

const noop = (): void => {};
const noopAsk = (): void => {};

interface TipTapEditorProps {
  content: string;
  onChange: (content: string) => void;
  onAutosave?: (content: string) => Promise<void>;
  autosaveInterval?: number;
  chapterId?: string;
  novelId?: string;
  /**
   * Host-supplied handlers for the slash commands the editor does not own
   * (continue / generate / co-author / chat / explain). `rewrite` is always
   * wired from the editor controller. Omitted handlers render their command
   * unavailable with actionable guidance.
   */
  slashCommandHandlers?: Partial<SlashCommandHandlers>;
}

export function TipTapEditor({
  content,
  onChange,
  onAutosave,
  autosaveInterval,
  chapterId,
  novelId,
  slashCommandHandlers,
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

  // --- Slash commands (CR-AUFG-07-20) -------------------------------------
  // `rewrite` is wired from the editor controller (always available when the
  // selection is valid). The remaining operations are supplied by the host.
  const wiredOps = useMemo(() => {
    const ops = new Set<string>(["writing.rewrite"]);
    if (slashCommandHandlers?.onContinue) ops.add("writing.continue");
    if (slashCommandHandlers?.onGenerate) ops.add("writing.generation");
    if (slashCommandHandlers?.onCoAuthor) ops.add("writing.co_author");
    if (slashCommandHandlers?.onAskChat || slashCommandHandlers?.onExplainSelection)
      ops.add("chat.free_assistant");
    return ops;
  }, [slashCommandHandlers]);

  const dispatchContext = useMemo<SlashCommandDispatchContext>(
    () => ({
      rewriteSelection: controller.handleAIRewrite,
      continueWriting: slashCommandHandlers?.onContinue ?? noop,
      generateDraft: slashCommandHandlers?.onGenerate ?? noop,
      coAuthorSelection: slashCommandHandlers?.onCoAuthor ?? noop,
      askChat: slashCommandHandlers?.onAskChat ?? noopAsk,
      explainSelection: slashCommandHandlers?.onExplainSelection ?? noop,
    }),
    [controller.handleAIRewrite, slashCommandHandlers],
  );

  // Adapt the next-intl translator to the slash-command module's plain signature
  // so the registry/parser/menu stay decoupled from next-intl.
  const slashT = (key: string, params?: Record<string, unknown>): string => t(key, params as never);

  const slash = useSlashCommandState({
    editor: controller.editor,
    commands: AI_SLASH_COMMANDS,
    dispatchContext,
    wiredOps,
    t: slashT,
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

      {slash.open && (
        <SlashCommandMenu
          items={slash.items}
          activeIndex={slash.activeIndex}
          query={slash.query}
          position={slash.position}
          onActiveIndexChange={slash.setActiveIndex}
          onSelect={slash.selectIndex}
          onDismiss={slash.dismiss}
          t={slashT}
        />
      )}

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
          styleVariant={controller.styleVariant}
          onSelectStyleVariant={controller.handleStyleVariantRegenerate}
          onReject={controller.rejectSuggestion}
          onInsertAsNew={controller.insertAsNew}
          onNewSuggestions={controller.handleAIRewrite}
          onAccept={controller.acceptSuggestion}
          t={t}
        />
      )}

      {controller.rewriteError && !controller.aiSuggestion && (
        <RewriteErrorBanner
          error={controller.rewriteError}
          onRetry={() => {
            controller.setRewriteError(null);
            controller.handleAIRewrite();
          }}
          onDismiss={() => controller.setRewriteError(null)}
          t={t}
        />
      )}
    </div>
  );
}
