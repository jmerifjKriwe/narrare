import type { Editor } from "@tiptap/react";
import { create } from "zustand";
import type { ChapterSummary, SaveStatus } from "@/types";

interface EditorState {
  // Active chapter (UI state: which tab is selected — data fetched via TanStack Query)
  activeChapterId: string | null;

  // Save state
  saveStatus: SaveStatus;
  lastSavedAt: Date | null;

  // UI toggles
  sidebarOpen: boolean;
  contextPanelOpen: boolean;
  focusMode: boolean;

  // Editor reference — set by EditorSurface, read by CommandPalette
  editor: Editor | null;

  // Drag state — true while a block drag is in progress
  isDragging: boolean;

  // Actions
  setActiveChapterId: (id: string | null) => void;
  setSaveStatus: (status: SaveStatus) => void;
  setEditor: (editor: Editor | null) => void;
  setIsDragging: (dragging: boolean) => void;
  toggleSidebar: () => void;
  toggleContextPanel: () => void;
  toggleFocusMode: () => void;
  updateChapterWordCount: (
    chapterId: string,
    wordCount: number,
    chapters: ChapterSummary[],
  ) => ChapterSummary[];
}

export const useEditorStore = create<EditorState>((set) => ({
  activeChapterId: null,
  saveStatus: "idle",
  lastSavedAt: null,
  sidebarOpen: true,
  contextPanelOpen: false,
  focusMode: false,
  editor: null,
  isDragging: false,

  setActiveChapterId: (id) => set({ activeChapterId: id }),

  setSaveStatus: (saveStatus) =>
    set({
      saveStatus,
      lastSavedAt: saveStatus === "saved" ? new Date() : undefined,
    }),

  setEditor: (editor) => set({ editor }),

  setIsDragging: (isDragging) => set({ isDragging }),

  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),

  toggleContextPanel: () => set((s) => ({ contextPanelOpen: !s.contextPanelOpen })),

  toggleFocusMode: () =>
    set((s) => ({
      focusMode: !s.focusMode,
      sidebarOpen: s.focusMode, // restore sidebar when exiting focus
    })),

  /**
   * Pure function: returns new chapters array with updated word count.
   * Caller is responsible for syncing back to TanStack Query cache.
   */
  updateChapterWordCount: (chapterId, wordCount, chapters) =>
    chapters.map((c) => (c.id === chapterId ? { ...c, word_count: wordCount } : c)),
}));
