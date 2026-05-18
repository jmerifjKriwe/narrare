import { describe, expect, it } from "vitest";
import { useEditorStore } from "@/lib/stores/editorStore";

describe("editorStore", () => {
  beforeEach(() => {
    // Reset to initial state
    useEditorStore.setState({
      activeChapterId: null,
      activeVolumeId: null,
      saveStatus: "idle",
      lastSavedAt: null,
      sidebarOpen: true,
      contextPanelOpen: false,
      focusMode: false,
      editor: null,
      isDragging: false,
      isGenerating: false,
      activeRequestId: null,
      generationMode: null,
      draftText: "",
      sessionActive: false,
      generationPanelOpen: false,
    });
  });

  it("sets active chapter id", () => {
    useEditorStore.getState().setActiveChapterId("ch-1");
    expect(useEditorStore.getState().activeChapterId).toBe("ch-1");
  });

  it("sets active volume id", () => {
    useEditorStore.getState().setActiveVolumeId("vol-1");
    expect(useEditorStore.getState().activeVolumeId).toBe("vol-1");
  });

  it("sets save status and updates lastSavedAt on save", () => {
    useEditorStore.getState().setSaveStatus("saved");
    expect(useEditorStore.getState().saveStatus).toBe("saved");
    expect(useEditorStore.getState().lastSavedAt).toBeInstanceOf(Date);

    useEditorStore.getState().setSaveStatus("idle");
    expect(useEditorStore.getState().saveStatus).toBe("idle");
  });

  it("sets editor reference", () => {
    const fakeEditor = { isFake: true } as never;
    useEditorStore.getState().setEditor(fakeEditor);
    expect(useEditorStore.getState().editor).toBe(fakeEditor);
  });

  it("sets dragging state", () => {
    useEditorStore.getState().setIsDragging(true);
    expect(useEditorStore.getState().isDragging).toBe(true);
  });

  it("toggles sidebar", () => {
    expect(useEditorStore.getState().sidebarOpen).toBe(true);
    useEditorStore.getState().toggleSidebar();
    expect(useEditorStore.getState().sidebarOpen).toBe(false);
    useEditorStore.getState().toggleSidebar();
    expect(useEditorStore.getState().sidebarOpen).toBe(true);
  });

  it("toggles context panel", () => {
    expect(useEditorStore.getState().contextPanelOpen).toBe(false);
    useEditorStore.getState().toggleContextPanel();
    expect(useEditorStore.getState().contextPanelOpen).toBe(true);
  });

  it("toggles focus mode and manages sidebar", () => {
    useEditorStore.getState().toggleFocusMode();
    expect(useEditorStore.getState().focusMode).toBe(true);
    // Sidebar is hidden when entering focus mode
    expect(useEditorStore.getState().sidebarOpen).toBe(false);

    useEditorStore.getState().toggleFocusMode();
    expect(useEditorStore.getState().focusMode).toBe(false);
    // Sidebar restored when exiting focus mode
    expect(useEditorStore.getState().sidebarOpen).toBe(true);
  });

  it("sets generating state", () => {
    useEditorStore.getState().setGenerating(true);
    expect(useEditorStore.getState().isGenerating).toBe(true);
  });

  it("sets active request id", () => {
    useEditorStore.getState().setActiveRequestId("req-1");
    expect(useEditorStore.getState().activeRequestId).toBe("req-1");
  });

  it("sets generation mode", () => {
    useEditorStore.getState().setGenerationMode("full_draft");
    expect(useEditorStore.getState().generationMode).toBe("full_draft");
  });

  it("sets draft text", () => {
    useEditorStore.getState().setDraftText("Hello world");
    expect(useEditorStore.getState().draftText).toBe("Hello world");
  });

  it("sets session active", () => {
    useEditorStore.getState().setSessionActive(true);
    expect(useEditorStore.getState().sessionActive).toBe(true);
  });

  it("toggles generation panel", () => {
    expect(useEditorStore.getState().generationPanelOpen).toBe(false);
    useEditorStore.getState().toggleGenerationPanel();
    expect(useEditorStore.getState().generationPanelOpen).toBe(true);
  });

  it("updateChapterWordCount is a pure function", () => {
    const chapters = [
      { id: "c1", word_count: 100, title: "Ch1" },
      { id: "c2", word_count: 200, title: "Ch2" },
    ] as never[];
    const updated = useEditorStore.getState().updateChapterWordCount("c1", 150, chapters);
    expect(updated[0].word_count).toBe(150);
    expect(updated[1].word_count).toBe(200);
    // Original unchanged
    expect(chapters[0].word_count).toBe(100);
  });
});
