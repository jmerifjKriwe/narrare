"use client"

import { useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import { chaptersApi, settingsApi } from "@/lib/api/client"
import { useEditorStore } from "@/lib/stores/editorStore"
import { ChapterSidebar } from "./ChapterSidebar"
import { EditorSurface } from "./EditorSurface"
import { EditorToolbar } from "./EditorToolbar"
import { ContextPanel } from "./ContextPanel"
import { StatusBar } from "./StatusBar"

interface EditorLayoutProps {
  novelId: string
}

export function EditorLayout({ novelId }: EditorLayoutProps) {
  const {
    setNovelId,
    setChapters,
    setActiveChapter,
    activeChapterId,
    sidebarOpen,
    contextPanelOpen,
    focusMode,
    toggleSidebar,
    toggleContextPanel,
    toggleFocusMode,
  } = useEditorStore()

  // Load project settings for autosave interval
  const { data: settings } = useQuery({
    queryKey: ["settings", "project", novelId],
    queryFn: () => settingsApi.getProject(novelId),
  })

  // Load chapter list
  const { data: chapters = [] } = useQuery({
    queryKey: ["chapters", novelId],
    queryFn: () => chaptersApi.list(novelId),
  })

  // Load active chapter content
  const { data: activeChapter } = useQuery({
    queryKey: ["chapter", novelId, activeChapterId],
    queryFn: () =>
      activeChapterId
        ? chaptersApi.get(novelId, activeChapterId)
        : Promise.resolve(null),
    enabled: !!activeChapterId,
  })

  // Sync store
  useEffect(() => { setNovelId(novelId) }, [novelId, setNovelId])
  useEffect(() => { setChapters(chapters) }, [chapters, setChapters])
  useEffect(() => {
    if (activeChapter) setActiveChapter(activeChapter)
  }, [activeChapter, setActiveChapter])

  // Auto-select first chapter on load
  useEffect(() => {
    if (chapters.length > 0 && !activeChapterId) {
      useEditorStore.getState().setActiveChapter({
        ...chapters[0],
        content: "",
        summary: "",
        pov_character_id: "",
        timeline_position: "",
        created_at: "",
        updated_at: "",
      })
    }
  }, [chapters, activeChapterId])

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "\\") {
        e.preventDefault()
        toggleSidebar()
      }
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === "F") {
        e.preventDefault()
        toggleFocusMode()
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [toggleSidebar, toggleFocusMode])

  const autosaveInterval = settings?.autosave_interval ?? 30

  return (
    <div
      className={[
        "editor-root",
        !sidebarOpen && "editor-root--sidebar-hidden",
        contextPanelOpen && "editor-root--panel-open",
        focusMode && "editor-root--focus",
      ]
        .filter(Boolean)
        .join(" ")}
    >
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

      <div className="editor-body">
        {/* Left sidebar */}
        {sidebarOpen && !focusMode && (
          <ChapterSidebar novelId={novelId} />
        )}

        {/* Main writing surface */}
        <main className="editor-main">
          <EditorSurface
            novelId={novelId}
            autosaveInterval={autosaveInterval}
          />
        </main>

        {/* Right context panel (empty slot at MVP) */}
        {contextPanelOpen && !focusMode && (
          <ContextPanel />
        )}
      </div>

      {/* Status bar — hidden in focus mode */}
      {!focusMode && <StatusBar />}

      <style jsx>{`
        .editor-root {
          height: 100vh;
          display: flex;
          flex-direction: column;
          background: var(--color-bg-primary);
          overflow: hidden;
        }
        .editor-body {
          flex: 1;
          display: flex;
          overflow: hidden;
        }
        .editor-main {
          flex: 1;
          overflow-y: auto;
          background: var(--color-bg-primary);
        }
        /* Focus mode: clean full-screen */
        .editor-root--focus .editor-main {
          background: var(--color-bg-primary);
        }
      `}</style>
    </div>
  )
}
