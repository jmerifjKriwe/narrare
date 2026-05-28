import type { Editor } from "@tiptap/react";
import { create } from "zustand";
import type {
  BetaReaderResponse,
  ConsistencyResponse,
  SentimentOverview,
} from "@/lib/api/analysis";
import type { ChapterSummary, SaveStatus } from "@/types";

interface EditorState {
  // Active chapter (UI state: which tab is selected — data fetched via TanStack Query)
  activeChapterId: string | null;

  // Active volume filter (null = "All")
  activeVolumeId: string | null;

  // Save state
  saveStatus: SaveStatus;
  lastSavedAt: Date | null;

  // UI toggles
  sidebarOpen: boolean;
  contextPanelOpen: boolean;
  focusMode: boolean;
  storyboardOpen: boolean;

  // Editor reference — set by EditorSurface, read by CommandPalette
  editor: Editor | null;

  // Drag state — true while a block drag is in progress
  isDragging: boolean;

  // Generation state
  isGenerating: boolean;
  activeRequestId: string | null;
  generationMode: string | null;
  draftText: string;
  sessionActive: boolean;
  generationPanelOpen: boolean;

  // Extraction state
  extractionPanelOpen: boolean;

  // Beta reader analysis state
  betaReaderPanelOpen: boolean;
  betaReaderResult: BetaReaderResponse | null;
  betaReaderLoading: boolean;

  // Sentiment analysis state
  sentimentPanelOpen: boolean;
  sentimentResult: SentimentOverview[] | null;
  sentimentLoading: boolean;

  // Consistency checker state
  consistencyPanelOpen: boolean;
  consistencyResult: ConsistencyResponse | null;
  consistencyLoading: boolean;

  // Actions
  setActiveChapterId: (id: string | null) => void;
  setActiveVolumeId: (id: string | null) => void;
  setSaveStatus: (status: SaveStatus) => void;
  setEditor: (editor: Editor | null) => void;
  setIsDragging: (dragging: boolean) => void;
  toggleSidebar: () => void;
  toggleContextPanel: () => void;
  toggleFocusMode: () => void;
  toggleStoryboard: () => void;
  updateChapterWordCount: (
    chapterId: string,
    wordCount: number,
    chapters: ChapterSummary[],
  ) => ChapterSummary[];
  setGenerating: (value: boolean) => void;
  setActiveRequestId: (id: string | null) => void;
  setGenerationMode: (mode: string | null) => void;
  setDraftText: (text: string) => void;
  setSessionActive: (value: boolean) => void;
  toggleGenerationPanel: () => void;
  toggleExtractionPanel: () => void;
  toggleBetaReaderPanel: () => void;
  setBetaReaderResult: (result: BetaReaderResponse | null) => void;
  setBetaReaderLoading: (loading: boolean) => void;
  toggleSentimentPanel: () => void;
  setSentimentResult: (result: SentimentOverview[] | null) => void;
  setSentimentLoading: (loading: boolean) => void;
  toggleConsistencyPanel: () => void;
  setConsistencyResult: (result: ConsistencyResponse | null) => void;
  setConsistencyLoading: (loading: boolean) => void;
}

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

  setActiveChapterId: (id) => set({ activeChapterId: id }),

  setActiveVolumeId: (id) => set({ activeVolumeId: id }),

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

  toggleStoryboard: () => set((s) => ({ storyboardOpen: !s.storyboardOpen })),

  /**
   * Pure function: returns new chapters array with updated word count.
   * Caller is responsible for syncing back to TanStack Query cache.
   */
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
      // Close generation panel when opening extraction panel
      generationPanelOpen: s.extractionPanelOpen ? s.generationPanelOpen : false,
    })),

  toggleBetaReaderPanel: () =>
    set((s) => ({
      betaReaderPanelOpen: !s.betaReaderPanelOpen,
      // Close other right panels when opening beta reader panel
      contextPanelOpen: s.betaReaderPanelOpen ? s.contextPanelOpen : false,
      generationPanelOpen: s.betaReaderPanelOpen ? s.generationPanelOpen : false,
      sentimentPanelOpen: s.betaReaderPanelOpen ? s.sentimentPanelOpen : false,
      consistencyPanelOpen: s.betaReaderPanelOpen ? s.consistencyPanelOpen : false,
    })),

  setBetaReaderResult: (betaReaderResult) => set({ betaReaderResult }),

  setBetaReaderLoading: (betaReaderLoading) => set({ betaReaderLoading }),

  toggleSentimentPanel: () =>
    set((s) => ({
      sentimentPanelOpen: !s.sentimentPanelOpen,
      // Close other right panels when opening sentiment panel
      contextPanelOpen: s.sentimentPanelOpen ? s.contextPanelOpen : false,
      generationPanelOpen: s.sentimentPanelOpen ? s.generationPanelOpen : false,
      betaReaderPanelOpen: s.sentimentPanelOpen ? s.betaReaderPanelOpen : false,
      consistencyPanelOpen: s.sentimentPanelOpen ? s.consistencyPanelOpen : false,
    })),

  setSentimentResult: (sentimentResult) => set({ sentimentResult }),

  setSentimentLoading: (sentimentLoading) => set({ sentimentLoading }),

  toggleConsistencyPanel: () =>
    set((s) => ({
      consistencyPanelOpen: !s.consistencyPanelOpen,
      // Close other right panels when opening consistency panel
      contextPanelOpen: s.consistencyPanelOpen ? s.contextPanelOpen : false,
      generationPanelOpen: s.consistencyPanelOpen ? s.generationPanelOpen : false,
      betaReaderPanelOpen: s.consistencyPanelOpen ? s.betaReaderPanelOpen : false,
      sentimentPanelOpen: s.consistencyPanelOpen ? s.sentimentPanelOpen : false,
    })),

  setConsistencyResult: (consistencyResult) => set({ consistencyResult }),

  setConsistencyLoading: (consistencyLoading) => set({ consistencyLoading }),
}));
