import { create } from "zustand"
import type { Chapter, ChapterSummary, SaveStatus } from "@/types"

interface EditorState {
  // Current novel context
  novelId: string | null
  chapters: ChapterSummary[]

  // Active chapter
  activeChapterId: string | null
  activeChapter: Chapter | null

  // Save state
  saveStatus: SaveStatus
  lastSavedAt: Date | null

  // UI state
  sidebarOpen: boolean
  contextPanelOpen: boolean
  focusMode: boolean

  // Actions
  setNovelId: (id: string) => void
  setChapters: (chapters: ChapterSummary[]) => void
  setActiveChapter: (chapter: Chapter) => void
  setSaveStatus: (status: SaveStatus) => void
  toggleSidebar: () => void
  toggleContextPanel: () => void
  toggleFocusMode: () => void
  updateChapterWordCount: (chapterId: string, wordCount: number) => void
}

export const useEditorStore = create<EditorState>((set) => ({
  novelId: null,
  chapters: [],
  activeChapterId: null,
  activeChapter: null,
  saveStatus: "idle",
  lastSavedAt: null,
  sidebarOpen: true,
  contextPanelOpen: false,
  focusMode: false,

  setNovelId: (id) => set({ novelId: id }),

  setChapters: (chapters) => set({ chapters }),

  setActiveChapter: (chapter) =>
    set({ activeChapter: chapter, activeChapterId: chapter.id }),

  setSaveStatus: (saveStatus) =>
    set({
      saveStatus,
      lastSavedAt: saveStatus === "saved" ? new Date() : undefined,
    }),

  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),

  toggleContextPanel: () =>
    set((s) => ({ contextPanelOpen: !s.contextPanelOpen })),

  toggleFocusMode: () =>
    set((s) => ({
      focusMode: !s.focusMode,
      sidebarOpen: s.focusMode, // restore sidebar when exiting focus
    })),

  updateChapterWordCount: (chapterId, wordCount) =>
    set((s) => ({
      chapters: s.chapters.map((c) =>
        c.id === chapterId ? { ...c, word_count: wordCount } : c
      ),
    })),
}))
