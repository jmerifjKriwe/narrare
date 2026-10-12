import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Editor } from "@tiptap/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EditorToolbar } from "./EditorToolbar";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

// Child triggers pull from useEditorStore; stub them so the toolbar's own
// onClickCapture opener-tracking is what we exercise.
vi.mock("../analysis/BetaReaderTrigger", () => ({
  BetaReaderTrigger: () => <div data-testid="beta-reader-trigger" />,
}));
vi.mock("../analysis/SentimentTrigger", () => ({
  SentimentTrigger: () => <div data-testid="sentiment-trigger" />,
}));
vi.mock("../analysis/ConsistencyTrigger", () => ({
  ConsistencyTrigger: () => <div data-testid="consistency-trigger" />,
}));
vi.mock("../analysis/ReadabilityTrigger", () => ({
  ReadabilityTrigger: () => <div data-testid="readability-trigger" />,
}));
vi.mock("../analysis/POVTrigger", () => ({
  POVTrigger: () => <div data-testid="pov-trigger" />,
}));
vi.mock("../analysis/CoreferenceTrigger", () => ({
  CoreferenceTrigger: () => <div data-testid="coreference-trigger" />,
}));
vi.mock("../analysis/CharacterVoiceTrigger", () => ({
  CharacterVoiceTrigger: () => <div data-testid="character-voice-trigger" />,
}));
vi.mock("../analysis/VoiceCheckTrigger", () => ({
  VoiceCheckTrigger: ({ onClick }: { onClick?: () => void }) => (
    <button type="button" aria-label="voiceCheck.trigger" onClick={onClick} />
  ),
}));
vi.mock("../analysis/DialogueCoachTrigger", () => ({
  DialogueCoachTrigger: () => <div data-testid="dialogue-coach-trigger" />,
}));
vi.mock("./AdaptiveStatusIndicator", () => ({
  AdaptiveStatusIndicator: () => <div data-testid="adaptive-status-indicator" />,
}));
vi.mock("../editor/GhostTextConfig", () => ({
  GhostTextConfig: () => <div data-testid="ghost-text-config" />,
}));

// Minimal editor stub: only isActive() is read at render; click handlers here
// go through the mocked props, not the editor.
const editorStub = { isActive: () => false } as unknown as Editor;

const baseProps = {
  editor: editorStub,
  activeRightPanel: null,
  extractionPanelOpen: false,
  toggleRightPanel: vi.fn(),
  toggleExtractionPanel: vi.fn(),
  openNameGenerator: vi.fn(),
  onRightPanelOpenerChange: vi.fn(),
  novelId: "novel-1",
  // Continue-writing (extend) wiring (audit B08) — handlers come from
  // EditorView's useContinueStream; individual tests override as needed.
  onExtend: vi.fn(),
  onExtendStop: vi.fn(),
  isExtendStreaming: false,
};

describe("EditorToolbar opener tracking", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("records the opener button when the click lands on an SVG icon", () => {
    const onRightPanelOpenerChange = vi.fn();
    render(<EditorToolbar {...baseProps} onRightPanelOpenerChange={onRightPanelOpenerChange} />);

    const generateButton = screen.getByRole("button", { name: "editor.generate" });
    const icon = generateButton.querySelector("svg");
    expect(icon).not.toBeNull();

    // lucide icons render as SVGElement (not HTMLElement). Clicking the icon
    // must still resolve to its enclosing button for focus-return tracking.
    fireEvent.click(icon as SVGElement);

    expect(onRightPanelOpenerChange).toHaveBeenCalledTimes(1);
    expect(onRightPanelOpenerChange).toHaveBeenCalledWith(generateButton);
  });
});

// ---------------------------------------------------------------------------
// Editor chain stub — supports the formatting buttons (bold/italic/heading/
// blockquote) which call editor.chain().focus().toggleX().run(). Each chain
// method returns the chain so it composes; only `run` is the terminal effect.
// ---------------------------------------------------------------------------

function makeChainEditor(active: Record<string, boolean> = {}) {
  // Build incrementally so each method can close over and return `chain`.
  const chain: Record<string, ReturnType<typeof vi.fn>> = {};
  chain.focus = vi.fn(() => chain);
  chain.toggleBold = vi.fn(() => chain);
  chain.toggleItalic = vi.fn(() => chain);
  chain.toggleHeading = vi.fn(() => chain);
  chain.toggleBlockquote = vi.fn(() => chain);
  chain.run = vi.fn();
  const editor = {
    isActive: (name: string, attrs?: { level?: number }) => {
      if (name === "heading") return !!active[`heading${attrs?.level ?? ""}`];
      return !!active[name];
    },
    chain: () => chain,
  } as unknown as Editor;
  return { editor, chain };
}

describe("EditorToolbar rendering", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when the editor is null", () => {
    const { container } = render(<EditorToolbar {...baseProps} editor={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the editor is destroyed (B08 carry-forward)", () => {
    // After a remount the store can still hold the previous (destroyed)
    // instance while the next one is being created. The toolbar must not
    // offer any buttons — in particular Continue — in that window.
    const { editor } = makeChainEditor();
    const destroyed = { ...editor, isDestroyed: true } as unknown as Editor;
    const { container } = render(<EditorToolbar {...baseProps} editor={destroyed} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the formatting buttons when an editor is present", () => {
    const { editor } = makeChainEditor();
    render(<EditorToolbar {...baseProps} editor={editor} />);

    expect(screen.getByRole("button", { name: "editor.bold" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "editor.italic" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "editor.heading2" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "editor.heading3" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "editor.blockquote" })).toBeInTheDocument();
  });
});

describe("EditorToolbar active state propagation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("marks the generate button pressed when the generation panel is active", () => {
    const { editor } = makeChainEditor();
    render(<EditorToolbar {...baseProps} editor={editor} activeRightPanel="generation" />);

    expect(screen.getByRole("button", { name: "editor.generate" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("marks the extract button pressed when the extraction panel is open", () => {
    const { editor } = makeChainEditor();
    render(<EditorToolbar {...baseProps} editor={editor} extractionPanelOpen />);

    expect(screen.getByRole("button", { name: "kb.extract" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("reflects active editor marks on the formatting buttons", () => {
    const { editor } = makeChainEditor({ bold: true, heading2: true });
    render(<EditorToolbar {...baseProps} editor={editor} />);

    expect(screen.getByRole("button", { name: "editor.bold" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "editor.heading2" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    // Italic is inactive.
    expect(screen.getByRole("button", { name: "editor.italic" })).not.toHaveAttribute(
      "aria-pressed",
    );
  });
});

describe("EditorToolbar interactions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("runs the bold toggle chain when the bold button is clicked", () => {
    const { editor, chain } = makeChainEditor();
    render(<EditorToolbar {...baseProps} editor={editor} />);

    fireEvent.click(screen.getByRole("button", { name: "editor.bold" }));

    expect(chain.focus).toHaveBeenCalledTimes(1);
    expect(chain.toggleBold).toHaveBeenCalledTimes(1);
    expect(chain.run).toHaveBeenCalledTimes(1);
  });

  it("runs the heading toggle chain with level 2 for the H2 button", () => {
    const { editor, chain } = makeChainEditor();
    render(<EditorToolbar {...baseProps} editor={editor} />);

    fireEvent.click(screen.getByRole("button", { name: "editor.heading2" }));

    expect(chain.toggleHeading).toHaveBeenCalledWith({ level: 2 });
    expect(chain.run).toHaveBeenCalled();
  });

  it("opens the generation panel via toggleRightPanel when generate is clicked", () => {
    const toggleRightPanel = vi.fn();
    const { editor } = makeChainEditor();
    render(<EditorToolbar {...baseProps} editor={editor} toggleRightPanel={toggleRightPanel} />);

    fireEvent.click(screen.getByRole("button", { name: "editor.generate" }));

    expect(toggleRightPanel).toHaveBeenCalledWith("generation", "toolbar");
  });

  it("toggles the extraction panel when the extract button is clicked", () => {
    const toggleExtractionPanel = vi.fn();
    const { editor } = makeChainEditor();
    render(
      <EditorToolbar
        {...baseProps}
        editor={editor}
        toggleExtractionPanel={toggleExtractionPanel}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "kb.extract" }));

    expect(toggleExtractionPanel).toHaveBeenCalledTimes(1);
  });

  it("opens the name generator when its button is clicked", () => {
    const openNameGenerator = vi.fn();
    const { editor } = makeChainEditor();
    render(<EditorToolbar {...baseProps} editor={editor} openNameGenerator={openNameGenerator} />);

    fireEvent.click(screen.getByRole("button", { name: "editor.nameGenerator" }));

    expect(openNameGenerator).toHaveBeenCalledTimes(1);
  });

  it("renders the Continue button and forwards the default length (B08)", async () => {
    const onExtend = vi.fn();
    const user = userEvent.setup();
    render(
      <EditorToolbar
        {...baseProps}
        onExtend={onExtend}
        onExtendStop={vi.fn()}
        isExtendStreaming={false}
      />,
    );

    await user.click(screen.getByRole("button", { name: "annotation.continueWriting" }));

    expect(onExtend).toHaveBeenCalledTimes(1);
    expect(onExtend).toHaveBeenCalledWith("medium");
  });

  it("opens the voice-check panel via toggleRightPanel when VoiceCheck is clicked", () => {
    const toggleRightPanel = vi.fn();
    const { editor } = makeChainEditor();
    render(
      <EditorToolbar
        {...baseProps}
        editor={editor}
        toggleRightPanel={toggleRightPanel}
        onRightPanelOpenerChange={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "voiceCheck.trigger" }));

    expect(toggleRightPanel).toHaveBeenCalledWith("voice_check", "toolbar");
  });
});
