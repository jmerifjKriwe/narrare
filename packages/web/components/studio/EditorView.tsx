"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useLocale } from "next-intl";
import { useCallback, useState } from "react";
import type { StorySuggestion } from "@/lib/api/story-suggest-stream";
import { useEditorStore } from "@/lib/stores/editorStore";
import { UnblockPanel } from "./editor/UnblockPanel";
import { EditorHeader } from "./editor-view/EditorHeader";
import { EditorOverlays } from "./editor-view/EditorOverlays";
import { EditorSidePanels } from "./editor-view/EditorSidePanels";
import { EditorEmptyState, EditorLoadingState } from "./editor-view/EditorStates";
import { EditorToolbar } from "./editor-view/EditorToolbar";
import { EditorWorkspace } from "./editor-view/EditorWorkspace";
import { useEditorChapterData } from "./editor-view/useEditorChapterData";
import { useEditorCommandPalette } from "./editor-view/useEditorCommandPalette";
import { useEditorGenerationActions } from "./editor-view/useEditorGenerationActions";
import { useEditorPanelVisibility } from "./editor-view/useEditorPanelVisibility";
import { useEditorPersistence } from "./editor-view/useEditorPersistence";
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
  const generationPanelOpen = useEditorStore((s) => s.generationPanelOpen);
  const toggleGenerationPanel = useEditorStore((s) => s.toggleGenerationPanel);
  const extractionPanelOpen = useEditorStore((s) => s.extractionPanelOpen);
  const toggleExtractionPanel = useEditorStore((s) => s.toggleExtractionPanel);
  const toggleBetaReaderPanel = useEditorStore((s) => s.toggleBetaReaderPanel);
  const toggleSentimentPanel = useEditorStore((s) => s.toggleSentimentPanel);
  const toggleConsistencyPanel = useEditorStore((s) => s.toggleConsistencyPanel);
  const toggleReadabilityPanel = useEditorStore((s) => s.toggleReadabilityPanel);
  const togglePovPanel = useEditorStore((s) => s.togglePovPanel);
  const [nameGeneratorOpen, setNameGeneratorOpen] = useState(false);

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
  const panelVisibility = useEditorPanelVisibility(activeChapterId);

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

  if (!activeChapterId) {
    return <EditorEmptyState />;
  }

  if (chapterData.isLoading) {
    return <EditorLoadingState />;
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-background">
      <PlanningPanel novelId={novelId} />
      <WritingGraphStatus steps={writingSteps} />
      <EditorHeader
        title={chapterData.title}
        setTitle={chapterData.setTitle}
        lastSaved={persistence.lastSaved}
        handleSave={persistence.handleSave}
      />
      <EditorToolbar
        editor={editor}
        generationPanelOpen={generationPanelOpen}
        extractionPanelOpen={extractionPanelOpen}
        toggleGenerationPanel={toggleGenerationPanel}
        toggleExtractionPanel={toggleExtractionPanel}
        openNameGenerator={() => setNameGeneratorOpen(true)}
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
        <EditorSidePanels
          visibility={panelVisibility}
          novelId={novelId}
          activeChapterId={activeChapterId}
          content={chapterData.content}
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
          toggleGenerationPanel={toggleGenerationPanel}
          toggleBetaReaderPanel={toggleBetaReaderPanel}
          toggleReadabilityPanel={toggleReadabilityPanel}
          togglePovPanel={togglePovPanel}
          toggleSentimentPanel={toggleSentimentPanel}
          toggleConsistencyPanel={toggleConsistencyPanel}
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
        extractionPanelOpen={extractionPanelOpen}
        toggleExtractionPanel={toggleExtractionPanel}
        queryClient={queryClient}
      />
    </div>
  );
}
