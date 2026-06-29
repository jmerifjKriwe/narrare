import { create } from "zustand";
import {
  toggleBetaReaderPanel,
  toggleCharacterVoicePanel,
  toggleConsistencyPanel,
  toggleCoreferencePanel,
  togglePovPanel,
  toggleReadabilityPanel,
  toggleSentimentPanel,
} from "./editorPanelToggles";
import type { EditorState } from "./editorStoreTypes";

export const useEditorStore = create<EditorState>((set) => ({
  activeChapterId: null,
  activeVolumeId: null,
  saveStatus: "idle",
  lastSavedAt: null,
  sidebarOpen: true,
  contextPanelOpen: false,
  focusMode: false,
  storyboardOpen: false,
  editor: null,
  isDragging: false,
  isGenerating: false,
  activeRequestId: null,
  generationMode: null,
  draftText: "",
  sessionActive: false,
  generationPanelOpen: false,
  extractionPanelOpen: false,
  betaReaderPanelOpen: false,
  betaReaderResult: null,
  betaReaderLoading: false,
  sentimentPanelOpen: false,
  sentimentResult: null,
  sentimentLoading: false,
  consistencyPanelOpen: false,
  consistencyResult: null,
  consistencyLoading: false,
  readabilityPanelOpen: false,
  povPanelOpen: false,
  coreferencePanelOpen: false,
  characterVoicePanelOpen: false,

  setActiveChapterId: (id) => set({ activeChapterId: id }),
  setActiveVolumeId: (id) => set({ activeVolumeId: id }),
  setSaveStatus: (saveStatus) =>
    set({ saveStatus, lastSavedAt: saveStatus === "saved" ? new Date() : undefined }),
  setEditor: (editor) => set({ editor }),
  setIsDragging: (isDragging) => set({ isDragging }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  toggleContextPanel: () => set((s) => ({ contextPanelOpen: !s.contextPanelOpen })),
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
  setSessionActive: (sessionActive) => set({ sessionActive }),
  toggleGenerationPanel: () => set((s) => ({ generationPanelOpen: !s.generationPanelOpen })),
  toggleExtractionPanel: () =>
    set((s) => ({
      extractionPanelOpen: !s.extractionPanelOpen,
      generationPanelOpen: s.extractionPanelOpen ? s.generationPanelOpen : false,
    })),

  toggleBetaReaderPanel: () => set(toggleBetaReaderPanel),
  setBetaReaderResult: (betaReaderResult) => set({ betaReaderResult }),
  setBetaReaderLoading: (betaReaderLoading) => set({ betaReaderLoading }),
  toggleSentimentPanel: () => set(toggleSentimentPanel),
  setSentimentResult: (sentimentResult) => set({ sentimentResult }),
  setSentimentLoading: (sentimentLoading) => set({ sentimentLoading }),
  toggleConsistencyPanel: () => set(toggleConsistencyPanel),
  setConsistencyResult: (consistencyResult) => set({ consistencyResult }),
  setConsistencyLoading: (consistencyLoading) => set({ consistencyLoading }),
  toggleReadabilityPanel: () => set(toggleReadabilityPanel),
  togglePovPanel: () => set(togglePovPanel),
  toggleCoreferencePanel: () => set(toggleCoreferencePanel),
  toggleCharacterVoicePanel: () => set(toggleCharacterVoicePanel),
}));
