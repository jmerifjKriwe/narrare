"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { chaptersApi, settingsApi } from "@/lib/api/client";
import { useEditorStore } from "@/lib/stores/editorStore";
import type { ChapterSummary } from "@/types";
import { ChapterSidebar } from "./ChapterSidebar";
import { ContextPanel } from "./ContextPanel";
import { EditorSurface } from "./EditorSurface";
import { EditorToolbar } from "./EditorToolbar";
import { StatusBar } from "./StatusBar";

interface EditorLayoutProps {
  novelId: string;
}

export function EditorLayout({ novelId }: EditorLayoutProps) {
  const {
    activeChapterId,
    setActiveChapterId,
    sidebarOpen,
    contextPanelOpen,
    focusMode,
    toggleSidebar,
    toggleContextPanel,
    toggleFocusMode,
  } = useEditorStore();

  const queryClient = useQueryClient();

  // Server data — direct from TanStack Query, no store sync
  const { data: chapters = [] } = useQuery({
    queryKey: ["chapters", novelId],
    queryFn: () => chaptersApi.list(novelId),
  });

  const { data: activeChapter } = useQuery({
    queryKey: ["chapter", novelId, activeChapterId],
    queryFn: () =>
      activeChapterId ? chaptersApi.get(novelId, activeChapterId) : Promise.resolve(null),
    enabled: !!activeChapterId,
  });

  const { data: settings } = useQuery({
    queryKey: ["settings", "project", novelId],
    queryFn: () => settingsApi.getProject(novelId),
  });

  // Auto-select first chapter when chapters load and none is active
  useEffect(() => {
    if (chapters.length > 0 && !activeChapterId) {
      setActiveChapterId(chapters[0].id);
    }
  }, [chapters, activeChapterId, setActiveChapterId]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "\\") {
        e.preventDefault();
        toggleSidebar();
      }
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === "F") {
        e.preventDefault();
        toggleFocusMode();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [toggleSidebar, toggleFocusMode]);

  const autosaveInterval = settings?.autosave_interval ?? 30;

  // Callback for word count optimistic updates — syncs TanStack Query cache
  const handleWordCountUpdate = (chapterId: string, wordCount: number) => {
    const currentChapters = queryClient.getQueryData<ChapterSummary[]>(["chapters", novelId]) ?? [];
    const updated = useEditorStore
      .getState()
      .updateChapterWordCount(chapterId, wordCount, currentChapters);
    queryClient.setQueryData(["chapters", novelId], updated);
  };

  return (
    <div className="h-full flex flex-col bg-[var(--color-bg-primary)] overflow-hidden">
      {/* Toolbar — hidden in focus mode */}
      {!focusMode && (
        <EditorToolbar
          onToggleSidebar={toggleSidebar}
          onTogglePanel={toggleContextPanel}
          onToggleFocus={toggleFocusMode}
          sidebarOpen={sidebarOpen}
          panelOpen={contextPanelOpen}
        />
      )}

      <div className="flex-1 flex overflow-hidden">
        {/* Left sidebar */}
        {sidebarOpen && !focusMode && (
          <ChapterSidebar
            novelId={novelId}
            chapters={chapters}
            activeChapterId={activeChapterId}
            onChapterSelect={setActiveChapterId}
          />
        )}

        {/* Main writing surface — convincing paper on desk */}
        <main
          className="flex-1 overflow-y-auto"
          style={{ background: "linear-gradient(180deg, #EDE9E1 0%, #E8E3DA 100%)" }}
        >
          <div className="flex justify-center py-6 px-4">
            <div
              className="w-full max-w-[780px] min-h-[calc(100vh-160px)] bg-[#FDFCFA] rounded-sm"
              style={{
                boxShadow:
                  "inset 0 0 0 1px rgba(0,0,0,0.03), 0 1px 3px rgba(44,40,37,0.06), 0 8px 24px rgba(44,40,37,0.08), 0 24px 48px rgba(44,40,37,0.04)",
              }}
            >
              <EditorSurface
                novelId={novelId}
                chapter={activeChapter ?? null}
                autosaveInterval={autosaveInterval}
                onWordCountUpdate={handleWordCountUpdate}
              />
            </div>
          </div>
        </main>

        {/* Right context panel (empty slot at MVP) */}
        {contextPanelOpen && !focusMode && <ContextPanel />}
      </div>

      {/* Status bar — hidden in focus mode */}
      {!focusMode && <StatusBar chapter={activeChapter ?? null} />}
    </div>
  );
}
