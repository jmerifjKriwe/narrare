import { describe, expect, it, vi } from "vitest";
import { builtInCommands } from "@/components/studio/editor/commands";

/** Factory that creates a fresh CommandContext with all spies. */
function createContext() {
  return {
    toggleSidebar: vi.fn(),
    toggleFocusMode: vi.fn(),
    toggleContextPanel: vi.fn(),
    toggleStoryboard: vi.fn(),
    saveChapter: vi.fn(),
    startGeneration: vi.fn(),
    stopGeneration: vi.fn(),
    acceptDraft: vi.fn(),
    rejectDraft: vi.fn(),
    createChapter: vi.fn(),
    toggleGenerationPanel: vi.fn(),
    startExtend: vi.fn(),
    startRewrite: vi.fn(),
  };
}

/** Default CommandState for testing. */
const defaultState = {
  isGenerating: false,
  hasDraft: false,
  hasPendingAnnotation: false,
  hasSelection: false,
  selectionLength: 0,
};

describe("builtInCommands", () => {
  it("has all expected format commands", () => {
    const formatCommands = builtInCommands.filter((c) => c.category === "format");
    expect(formatCommands.map((c) => c.id)).toEqual([
      "bold",
      "italic",
      "heading1",
      "heading2",
      "heading3",
      "sceneBreak",
    ]);
  });

  it("has all expected editor commands", () => {
    const editorCommands = builtInCommands.filter((c) => c.category === "editor");
    expect(editorCommands.map((c) => c.id)).toEqual([
      "toggleSidebar",
      "toggleFocusMode",
      "togglePanel",
      "toggleStoryboard",
      "save",
    ]);
  });

  it("has all expected generation commands", () => {
    const genCommands = builtInCommands.filter((c) => c.category === "generation");
    expect(genCommands.map((c) => c.id)).toEqual([
      "generate-chapter",
      "generate-outline",
      "auto-continue",
      "start-session",
      "stop-generation",
      "accept-draft",
      "reject-draft",
      "continue-writing",
      "continue-writing-short",
      "continue-writing-long",
      "rewrite-selection",
    ]);
  });

  it("each command has required fields", () => {
    for (const command of builtInCommands) {
      expect(command.id).toBeDefined();
      expect(command.label).toBeDefined();
      expect(command.category).toMatch(/^(format|editor|generation)$/);
      expect(typeof command.action).toBe("function");
    }
  });

  it("generation commands are only visible when not generating and no draft", () => {
    const startCommands = builtInCommands.filter(
      (c) =>
        c.category === "generation" &&
        c.isVisible &&
        !c.id.includes("stop") &&
        !c.id.includes("draft") &&
        !c.id.includes("rewrite"),
    );
    for (const cmd of startCommands) {
      expect(cmd.isVisible!({ ...defaultState, isGenerating: false, hasDraft: false })).toBe(true);
      expect(cmd.isVisible!({ ...defaultState, isGenerating: true })).toBe(false);
      expect(cmd.isVisible!({ ...defaultState, isGenerating: false, hasDraft: true })).toBe(false);
    }
  });

  it("stop-generation is only visible while generating", () => {
    const stopCmd = builtInCommands.find((c) => c.id === "stop-generation")!;
    expect(stopCmd.isVisible!({ ...defaultState, isGenerating: true })).toBe(true);
    expect(stopCmd.isVisible!({ ...defaultState })).toBe(false);
    expect(stopCmd.isVisible!({ ...defaultState, hasDraft: true })).toBe(false);
  });

  it("accept-draft and reject-draft are only visible when draft exists", () => {
    const acceptCmd = builtInCommands.find((c) => c.id === "accept-draft")!;
    const rejectCmd = builtInCommands.find((c) => c.id === "reject-draft")!;
    expect(acceptCmd.isVisible!({ ...defaultState, hasDraft: true })).toBe(true);
    expect(acceptCmd.isVisible!({ ...defaultState })).toBe(false);
    expect(rejectCmd.isVisible!({ ...defaultState, hasDraft: true })).toBe(true);
    expect(rejectCmd.isVisible!({ ...defaultState })).toBe(false);
  });

  it("format commands call editor actions", () => {
    const editor = {
      chain: () => ({
        focus: () => ({
          toggleBold: () => ({ run: vi.fn() }),
          toggleItalic: () => ({ run: vi.fn() }),
          toggleHeading: () => ({ run: vi.fn() }),
        }),
      }),
      commands: {
        insertContent: vi.fn(),
      },
    };

    const boldCmd = builtInCommands.find((c) => c.id === "bold")!;
    const runSpy = vi.fn();
    editor.chain = () => ({
      focus: () => ({
        toggleBold: () => ({ run: runSpy }),
        toggleItalic: () => ({ run: vi.fn() }),
        toggleHeading: () => ({ run: vi.fn() }),
      }),
    });
    boldCmd.action(editor as never, {} as never);
    expect(runSpy).toHaveBeenCalled();
  });

  it("heading commands call toggleHeading with correct levels", () => {
    const runH1 = vi.fn();
    const runH2 = vi.fn();
    const runH3 = vi.fn();
    const mockHeading = vi.fn((opts: { level: number }) => {
      if (opts.level === 1) return { run: runH1 };
      if (opts.level === 2) return { run: runH2 };
      if (opts.level === 3) return { run: runH3 };
      return { run: vi.fn() };
    });
    const editor = {
      chain: () => ({
        focus: () => ({
          toggleBold: () => ({ run: vi.fn() }),
          toggleItalic: () => ({ run: vi.fn() }),
          toggleHeading: mockHeading,
        }),
      }),
    };

    builtInCommands.find((c) => c.id === "heading1")!.action(editor as never, {} as never);
    expect(runH1).toHaveBeenCalled();
    builtInCommands.find((c) => c.id === "heading2")!.action(editor as never, {} as never);
    expect(runH2).toHaveBeenCalled();
    builtInCommands.find((c) => c.id === "heading3")!.action(editor as never, {} as never);
    expect(runH3).toHaveBeenCalled();
  });

  it("italic command calls toggleItalic", () => {
    const runItalic = vi.fn();
    const editor = {
      chain: () => ({
        focus: () => ({
          toggleItalic: () => ({ run: runItalic }),
        }),
      }),
    };
    builtInCommands.find((c) => c.id === "italic")!.action(editor as never, {} as never);
    expect(runItalic).toHaveBeenCalled();
  });

  it("editor commands call context callbacks", () => {
    const context = createContext();

    const sidebarCmd = builtInCommands.find((c) => c.id === "toggleSidebar")!;
    sidebarCmd.action({} as never, context);
    expect(context.toggleSidebar).toHaveBeenCalled();

    const focusCmd = builtInCommands.find((c) => c.id === "toggleFocusMode")!;
    focusCmd.action({} as never, context);
    expect(context.toggleFocusMode).toHaveBeenCalled();

    const panelCmd = builtInCommands.find((c) => c.id === "togglePanel")!;
    panelCmd.action({} as never, context);
    expect(context.toggleContextPanel).toHaveBeenCalled();
  });

  it("save command calls saveChapter", () => {
    const context = createContext();
    const saveCmd = builtInCommands.find((c) => c.id === "save")!;
    saveCmd.action({} as never, context);
    expect(context.saveChapter).toHaveBeenCalled();
  });

  it("generation commands call startGeneration with correct mode", () => {
    const context = createContext();

    const chapterCmd = builtInCommands.find((c) => c.id === "generate-chapter")!;
    chapterCmd.action({} as never, context);
    expect(context.startGeneration).toHaveBeenCalledWith("full_draft");

    const outlineCmd = builtInCommands.find((c) => c.id === "generate-outline")!;
    outlineCmd.action({} as never, context);
    expect(context.startGeneration).toHaveBeenCalledWith("scene_by_scene");

    const sessionCmd = builtInCommands.find((c) => c.id === "start-session")!;
    sessionCmd.action({} as never, context);
    expect(context.startGeneration).toHaveBeenCalledWith("interactive_session");

    const autoCmd = builtInCommands.find((c) => c.id === "auto-continue")!;
    autoCmd.action({} as never, context);
    expect(context.startGeneration).toHaveBeenCalledWith("interview_assisted");
  });

  it("stop/accept/reject commands call their context callbacks", () => {
    const context = createContext();

    const stopCmd = builtInCommands.find((c) => c.id === "stop-generation")!;
    stopCmd.action({} as never, context);
    expect(context.stopGeneration).toHaveBeenCalled();

    const acceptCmd = builtInCommands.find((c) => c.id === "accept-draft")!;
    acceptCmd.action({} as never, context);
    expect(context.acceptDraft).toHaveBeenCalled();

    const rejectCmd = builtInCommands.find((c) => c.id === "reject-draft")!;
    rejectCmd.action({} as never, context);
    expect(context.rejectDraft).toHaveBeenCalled();
  });

  it("sceneBreak command calls insertContent", () => {
    const editor = { commands: { insertContent: vi.fn() } };
    const sceneBreakCmd = builtInCommands.find((c) => c.id === "sceneBreak")!;
    sceneBreakCmd.action(editor as never, {} as never);
    expect(editor.commands.insertContent).toHaveBeenCalledWith({ type: "sceneBreak" });
  });

  it("continue-writing commands call startExtend with correct length", () => {
    const context = createContext();

    const continueCmd = builtInCommands.find((c) => c.id === "continue-writing")!;
    continueCmd.action({} as never, context);
    expect(context.startExtend).toHaveBeenCalledWith("medium");

    const shortCmd = builtInCommands.find((c) => c.id === "continue-writing-short")!;
    shortCmd.action({} as never, context);
    expect(context.startExtend).toHaveBeenCalledWith("short");

    const longCmd = builtInCommands.find((c) => c.id === "continue-writing-long")!;
    longCmd.action({} as never, context);
    expect(context.startExtend).toHaveBeenCalledWith("long");
  });

  it("continue-writing commands are hidden when annotation is pending", () => {
    const continueCmd = builtInCommands.find((c) => c.id === "continue-writing")!;
    expect(continueCmd.isVisible!({ ...defaultState })).toBe(true);
    expect(continueCmd.isVisible!({ ...defaultState, hasPendingAnnotation: true })).toBe(false);
    expect(continueCmd.isVisible!({ ...defaultState, isGenerating: true })).toBe(false);
  });

  it("rewrite-selection is only visible with valid selection length", () => {
    const rewriteCmd = builtInCommands.find((c) => c.id === "rewrite-selection")!;
    expect(
      rewriteCmd.isVisible!({ ...defaultState, hasSelection: true, selectionLength: 100 }),
    ).toBe(true);
    expect(
      rewriteCmd.isVisible!({ ...defaultState, hasSelection: false, selectionLength: 0 }),
    ).toBe(false);
    expect(
      rewriteCmd.isVisible!({ ...defaultState, hasSelection: true, selectionLength: 30 }),
    ).toBe(false);
    expect(
      rewriteCmd.isVisible!({ ...defaultState, hasSelection: true, selectionLength: 2500 }),
    ).toBe(false);
    expect(
      rewriteCmd.isVisible!({ ...defaultState, hasSelection: true, selectionLength: 50 }),
    ).toBe(true);
    expect(
      rewriteCmd.isVisible!({ ...defaultState, hasSelection: true, selectionLength: 2000 }),
    ).toBe(true);
  });
});
