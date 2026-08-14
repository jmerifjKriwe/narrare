"use client";

import { useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useLocale } from "next-intl";
import { useCallback, useRef, useState } from "react";
import type { StorySuggestion } from "@/lib/api/story-suggest-stream";
import { crossfadeVariants } from "@/lib/motion-variants";
import { useEditorStore } from "@/lib/stores/editorStore";
import { UnblockPanel } from "./editor/UnblockPanel";
import { EditorHeader } from "./editor-view/EditorHeader";
import { EditorOverlays } from "./editor-view/EditorOverlays";
import { EditorRightPanelSlot } from "./editor-view/EditorRightPanelSlot";
import { EditorEmptyState, EditorLoadingState } from "./editor-view/EditorStates";
import { EditorToolbar } from "./editor-view/EditorToolbar";
import { EditorWorkspace } from "./editor-view/EditorWorkspace";
import { useActiveEditorRightPanel } from "./editor-view/useActiveEditorRightPanel";
import { useEditorChapterData } from "./editor-view/useEditorChapterData";
import { useEditorCommandPalette } from "./editor-view/useEditorCommandPalette";
import { useEditorGenerationActions } from "./editor-view/useEditorGenerationActions";
import { useEditorPersistence } from "./editor-view/useEditorPersistence";
import { useEditorUrlPanelSync } from "./editor-view/useEditorUrlPanelSync";
import { useWritingGraphSteps } from "./editor-view/useWritingGraphSteps";
import { PlanningPanel } from "./planning/PlanningPanel";
import { WritingGraphStatus } from "./writing/WritingGraphStatus";

interface EditorViewProps {
  novelId: string;
}

export function EditorView({ novelId }: EditorViewProps) {
  const locale = useLocale();
  const queryClient = useQueryClient();
  const activeChapterId = useEditorStore((s) => s.activeChapterId);
  const activeVolumeId = useEditorStore((s) => s.activeVolumeId);
  const editor = useEditorStore((s) => s.editor);
  const isGenerating = useEditorStore((s) => s.isGenerating);
  const setSaveStatus = useEditorStore((s) => s.setSaveStatus);
  const extractionPanelOpen = useEditorStore((s) => s.extractionPanelOpen);
  const toggleExtractionPanel = useEditorStore((s) => s.toggleExtractionPanel);
  const toggleRightPanel = useEditorStore((s) => s.toggleRightPanel);
  const closeRightPanel = useEditorStore((s) => s.closeRightPanel);
  const openRightPanel = useEditorStore((s) => s.openRightPanel);
  const openerRef = useRef<HTMLElement | null>(null);
  const [nameGeneratorOpen, setNameGeneratorOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);

  const writingSteps = useWritingGraphSteps(isGenerating, activeChapterId);
  const chapterData = useEditorChapterData({ novelId, activeChapterId, activeVolumeId, editor });
  const persistence = useEditorPersistence({
    novelId,
    activeChapterId,
    editor,
    content: chapterData.content,
    title: chapterData.title,
    locale,
    setSaveStatus,
    queryClient,
  });
  const generationActions = useEditorGenerationActions({
    editor,
    content: chapterData.content,
    handleAutosave: persistence.handleAutosave,
  });
  const commandPalette = useEditorCommandPalette({
    handleSave: persistence.handleSave,
    handleStartGeneration: generationActions.handleStartGeneration,
    handleStopGeneration: generationActions.handleStopGeneration,
    handleAcceptDraft: generationActions.handleAcceptDraft,
    handleRejectDraft: generationActions.handleRejectDraft,
  });
  const activeRightPanel = useActiveEditorRightPanel(activeChapterId);
  useEditorUrlPanelSync({ activeRightPanel, openRightPanel });

  // Writer's Unblock (WRITE-009): insert the accepted story-direction title into
  // the manuscript at the cursor and persist — mirrors handleDraftAccepted.
  const handleUnblockAccept = useCallback(
    (suggestion: StorySuggestion) => {
      if (editor) {
        editor.commands.insertContent(suggestion.title);
      }
      void persistence.handleAutosave(editor?.getHTML() ?? chapterData.content);
    },
    [editor, chapterData.content, persistence.handleAutosave],
  );

  return (
    <AnimatePresence mode="wait">
      {!activeChapterId ? (
        <EditorEmptyState key="empty" />
      ) : chapterData.isLoading ? (
        <EditorLoadingState key="loading" />
      ) : (
        <motion.div
          key="editor"
          variants={crossfadeVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="flex-1 flex flex-col h-full bg-background"
        >
          <PlanningPanel novelId={novelId} />
          <WritingGraphStatus steps={writingSteps} />
          <EditorHeader
            title={chapterData.title}
            setTitle={chapterData.setTitle}
            lastSaved={persistence.lastSaved}
            handleSave={persistence.handleSave}
            onExport={() => setExportOpen(true)}
          />
          <EditorToolbar
            editor={editor}
            activeRightPanel={activeRightPanel}
            extractionPanelOpen={extractionPanelOpen}
            toggleRightPanel={toggleRightPanel}
            toggleExtractionPanel={toggleExtractionPanel}
            openNameGenerator={() => setNameGeneratorOpen(true)}
            onRightPanelOpenerChange={(el) => {
              openerRef.current = el;
            }}
            novelId={novelId}
          />
          <div className="flex-1 flex min-h-0">
            <EditorWorkspace
              editor={editor}
              novelId={novelId}
              activeChapterId={activeChapterId}
              content={chapterData.content}
              setContent={chapterData.setContent}
              handleAutosave={persistence.handleAutosave}
            />
            <div className="flex items-center">
              <UnblockPanel
                novelId={novelId}
                chapterId={activeChapterId}
                onAccept={handleUnblockAccept}
              />
            </div>
            <EditorRightPanelSlot
              activePanel={activeRightPanel}
              closePanel={closeRightPanel}
              returnFocusTo={openerRef.current}
              novelId={novelId}
              activeChapterId={activeChapterId}
              content={chapterData.content}
              editor={editor}
              chapter={chapterData.chapter}
              chapters={chapterData.chapters}
              sessionStartWordCount={chapterData.sessionStartWordCount}
              volumeStats={chapterData.volumeStats}
              wordCount={chapterData.wordCount}
              charCount={chapterData.charCount}
              paragraphCount={chapterData.paragraphCount}
              sessionMode={generationActions.sessionMode}
              handleSessionClose={generationActions.handleSessionClose}
              handleDraftAccepted={generationActions.handleDraftAccepted}
              handleStartSession={generationActions.handleStartSession}
            />
          </div>
          <EditorOverlays
            editor={editor}
            novelId={novelId}
            activeChapterId={activeChapterId}
            commandPaletteOpen={commandPalette.commandPaletteOpen}
            setCommandPaletteOpen={commandPalette.setCommandPaletteOpen}
            commandContext={commandPalette.commandContext}
            commandState={commandPalette.commandState}
            nameGeneratorOpen={nameGeneratorOpen}
            setNameGeneratorOpen={setNameGeneratorOpen}
            exportOpen={exportOpen}
            setExportOpen={setExportOpen}
            extractionPanelOpen={extractionPanelOpen}
            toggleExtractionPanel={toggleExtractionPanel}
            queryClient={queryClient}
          />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
