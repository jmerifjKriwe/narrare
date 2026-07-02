import { create } from "zustand";
import {
  CLOSED_EDITOR_RIGHT_PANEL_STATE,
  closeEditorRightPanel,
  openEditorRightPanel,
  toggleEditorRightPanel,
} from "./editorRightPanelState";
import type { EditorState } from "./editorStoreTypes";

export const useEditorStore = create<EditorState>((set) => ({
  activeChapterId: null,
  activeVolumeId: null,
  saveStatus: "idle",
  lastSavedAt: null,
  sidebarOpen: true,
  rightPanel: CLOSED_EDITOR_RIGHT_PANEL_STATE,
  focusMode: false,
  storyboardOpen: false,
  editor: null,
  isDragging: false,
  isGenerating: false,
  activeRequestId: null,
  generationMode: null,
  draftText: "",
  sessionActive: false,
  extractionPanelOpen: false,
  betaReaderResult: null,
  betaReaderLoading: false,
  sentimentResult: null,
  sentimentLoading: false,
  consistencyResult: null,
  consistencyLoading: false,

  openRightPanel: (panel, requestedBy) =>
    set((s) => ({ rightPanel: openEditorRightPanel(s.rightPanel, panel, requestedBy) })),
  closeRightPanel: (panel) =>
    set((s) => ({ rightPanel: closeEditorRightPanel(s.rightPanel, panel ?? s.rightPanel.active) })),
  toggleRightPanel: (panel, requestedBy) =>
    set((s) => ({ rightPanel: toggleEditorRightPanel(s.rightPanel, panel, requestedBy) })),
  toggleContextPanel: () =>
    set((s) => ({ rightPanel: toggleEditorRightPanel(s.rightPanel, "metadata", "toolbar") })),
  toggleGenerationPanel: () =>
    set((s) => ({ rightPanel: toggleEditorRightPanel(s.rightPanel, "generation", "toolbar") })),
  setSessionActive: (sessionActive) =>
    set((s) => ({
      sessionActive,
      rightPanel: sessionActive
        ? openEditorRightPanel(s.rightPanel, "session", "recovery")
        : closeEditorRightPanel(s.rightPanel, "session"),
    })),
  toggleBetaReaderPanel: () =>
    set((s) => ({ rightPanel: toggleEditorRightPanel(s.rightPanel, "beta_reader", "toolbar") })),
  toggleSentimentPanel: () =>
    set((s) => ({ rightPanel: toggleEditorRightPanel(s.rightPanel, "sentiment", "toolbar") })),
  toggleConsistencyPanel: () =>
    set((s) => ({ rightPanel: toggleEditorRightPanel(s.rightPanel, "consistency", "toolbar") })),
  toggleReadabilityPanel: () =>
    set((s) => ({ rightPanel: toggleEditorRightPanel(s.rightPanel, "readability", "toolbar") })),
  togglePovPanel: () =>
    set((s) => ({ rightPanel: toggleEditorRightPanel(s.rightPanel, "pov", "toolbar") })),
  toggleCoreferencePanel: () =>
    set((s) => ({ rightPanel: toggleEditorRightPanel(s.rightPanel, "coreference", "toolbar") })),
  toggleCharacterVoicePanel: () =>
    set((s) => ({
      rightPanel: toggleEditorRightPanel(s.rightPanel, "character_voice", "toolbar"),
    })),
  toggleVoiceCheckPanel: () =>
    set((s) => ({ rightPanel: toggleEditorRightPanel(s.rightPanel, "voice_check", "toolbar") })),

  setActiveChapterId: (id) => set({ activeChapterId: id }),
  setActiveVolumeId: (id) => set({ activeVolumeId: id }),
  setSaveStatus: (saveStatus) =>
    set({ saveStatus, lastSavedAt: saveStatus === "saved" ? new Date() : null }),
  setEditor: (editor) => set({ editor }),
  setIsDragging: (isDragging) => set({ isDragging }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  toggleFocusMode: () =>
    set((s) => ({
      focusMode: !s.focusMode,
      sidebarOpen: s.focusMode,
    })),
  toggleStoryboard: () => set((s) => ({ storyboardOpen: !s.storyboardOpen })),

  /** Pure function: caller syncs returned chapter array to TanStack Query cache. */
  updateChapterWordCount: (chapterId, wordCount, chapters) =>
    chapters.map((c) => (c.id === chapterId ? { ...c, word_count: wordCount } : c)),

  setGenerating: (isGenerating) => set({ isGenerating }),
  setActiveRequestId: (activeRequestId) => set({ activeRequestId }),
  setGenerationMode: (generationMode) => set({ generationMode }),
  setDraftText: (draftText) => set({ draftText }),
  toggleExtractionPanel: () => set((s) => ({ extractionPanelOpen: !s.extractionPanelOpen })),
  setBetaReaderResult: (betaReaderResult) => set({ betaReaderResult }),
  setBetaReaderLoading: (betaReaderLoading) => set({ betaReaderLoading }),
  setSentimentResult: (sentimentResult) => set({ sentimentResult }),
  setSentimentLoading: (sentimentLoading) => set({ sentimentLoading }),
  setConsistencyResult: (consistencyResult) => set({ consistencyResult }),
  setConsistencyLoading: (consistencyLoading) => set({ consistencyLoading }),
}));
