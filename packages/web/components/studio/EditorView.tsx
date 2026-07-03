"use client";

import { useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { StorySuggestion } from "@/lib/api/story-suggest-stream";
import { useEditorStore } from "@/lib/stores/editorStore";
import { searchParamsHref, setOptionalSearchParam } from "@/lib/url-state/searchParams";
import { UnblockPanel } from "./editor/UnblockPanel";
import { EditorHeader } from "./editor-view/EditorHeader";
import { EditorOverlays } from "./editor-view/EditorOverlays";
import { EditorRightPanelSlot } from "./editor-view/EditorRightPanelSlot";
import { EditorEmptyState, EditorLoadingState } from "./editor-view/EditorStates";
import { EditorToolbar } from "./editor-view/EditorToolbar";
import { EditorWorkspace } from "./editor-view/EditorWorkspace";
import {
  parseEditorRightPanelParam,
  serializeEditorRightPanelParam,
} from "./editor-view/editorRightPanelUrlState";
import { useActiveEditorRightPanel } from "./editor-view/useActiveEditorRightPanel";
import { useEditorChapterData } from "./editor-view/useEditorChapterData";
import { useEditorCommandPalette } from "./editor-view/useEditorCommandPalette";
import { useEditorGenerationActions } from "./editor-view/useEditorGenerationActions";
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
  const extractionPanelOpen = useEditorStore((s) => s.extractionPanelOpen);
  const toggleExtractionPanel = useEditorStore((s) => s.toggleExtractionPanel);
  const toggleRightPanel = useEditorStore((s) => s.toggleRightPanel);
  const closeRightPanel = useEditorStore((s) => s.closeRightPanel);
  const openRightPanel = useEditorStore((s) => s.openRightPanel);
  const openerRef = useRef<HTMLElement | null>(null);
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
  const activeRightPanel = useActiveEditorRightPanel(activeChapterId);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const searchParamsSnapshot = searchParams.toString();
  const parsedUrlPanel = useMemo(
    () => parseEditorRightPanelParam(new URLSearchParams(searchParamsSnapshot).get("panel")),
    [searchParamsSnapshot],
  );
  const rememberRightPanelOpener = useCallback((element: HTMLElement) => {
    openerRef.current = element;
  }, []);

  useEffect(() => {
    if (parsedUrlPanel !== null && activeRightPanel !== parsedUrlPanel) {
      openRightPanel(parsedUrlPanel, "url");
    }
  }, [activeRightPanel, openRightPanel, parsedUrlPanel]);

  useEffect(() => {
    if (parsedUrlPanel !== null && activeRightPanel !== parsedUrlPanel) return;
    const currentParams = new URLSearchParams(searchParamsSnapshot);
    const serializedPanel = serializeEditorRightPanelParam(activeRightPanel);
    if (currentParams.get("panel") === serializedPanel) return;
    const nextParams = setOptionalSearchParam(currentParams, "panel", serializedPanel);
    router.replace(searchParamsHref(pathname, nextParams), { scroll: false });
  }, [activeRightPanel, parsedUrlPanel, pathname, router, searchParamsSnapshot]);

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
        activeRightPanel={activeRightPanel}
        extractionPanelOpen={extractionPanelOpen}
        toggleRightPanel={toggleRightPanel}
        toggleExtractionPanel={toggleExtractionPanel}
        openNameGenerator={() => setNameGeneratorOpen(true)}
        onRightPanelOpenerChange={rememberRightPanelOpener}
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
        extractionPanelOpen={extractionPanelOpen}
        toggleExtractionPanel={toggleExtractionPanel}
        queryClient={queryClient}
      />
    </div>
  );
}
