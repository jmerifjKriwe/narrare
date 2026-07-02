import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EditorRightPanelSlot } from "./EditorRightPanelSlot";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock("../editor/MetadataSidebar", () => ({
  MetadataSidebar: () => <div data-testid="metadata-sidebar" />,
}));
vi.mock("../kb/WikiChapterSummaryPanel", () => ({
  WikiChapterSummaryPanel: () => <div />,
}));
vi.mock("../analysis/ReadabilityPanel", () => ({
  ReadabilityPanel: ({ onClose }: { onClose: () => void }) => (
    <section data-testid="readability-panel">
      <button type="button" onClick={onClose}>
        close
      </button>
    </section>
  ),
}));
vi.mock("../editor/SessionPanel", () => ({
  SessionPanel: () => <section data-testid="session-panel" />,
}));
vi.mock("../editor/GenerationPanel", () => ({
  GenerationPanel: () => <section data-testid="generation-panel" />,
}));
vi.mock("../analysis/BetaReaderPanel", () => ({
  BetaReaderPanel: () => <section data-testid="beta-reader-panel" />,
}));
vi.mock("../analysis/POVPanel", () => ({
  POVPanel: () => <section data-testid="pov-panel" />,
}));
vi.mock("../analysis/CoreferencePanel", () => ({
  CoreferencePanel: () => <section data-testid="coreference-panel" />,
}));
vi.mock("../analysis/CharacterVoicePanel", () => ({
  CharacterVoicePanel: () => <section data-testid="character-voice-panel" />,
}));
vi.mock("../analysis/VoiceCheckPanel", () => ({
  VoiceCheckPanel: () => <section data-testid="voice-check-panel" />,
}));
vi.mock("../analysis/SentimentPanel", () => ({
  SentimentPanel: () => <section data-testid="sentiment-panel" />,
}));
vi.mock("../analysis/ConsistencyPanel", () => ({
  ConsistencyPanel: () => <section data-testid="consistency-panel" />,
}));

const baseProps = {
  novelId: "novel-1",
  activeChapterId: "chapter-1",
  content: "<p>text</p>",
  chapter: undefined,
  chapters: [],
  sessionStartWordCount: 0,
  volumeStats: undefined,
  wordCount: 10,
  charCount: 50,
  paragraphCount: 1,
  sessionMode: "interactive_session" as const,
  handleSessionClose: vi.fn(),
  handleDraftAccepted: vi.fn(),
  handleStartSession: vi.fn(),
  closePanel: vi.fn(),
};

describe("EditorRightPanelSlot", () => {
  it("renders exactly the active panel occupant", () => {
    render(<EditorRightPanelSlot {...baseProps} activePanel="readability" />);
    expect(screen.getAllByTestId("readability-panel")).toHaveLength(1);
    expect(screen.queryByTestId("metadata-sidebar")).not.toBeInTheDocument();
  });

  it("renders no right slot when active panel is null", () => {
    render(<EditorRightPanelSlot {...baseProps} activePanel={null} />);
    expect(screen.queryByRole("region")).not.toBeInTheDocument();
  });

  it("closes active panel on Escape", () => {
    const closePanel = vi.fn();
    render(<EditorRightPanelSlot {...baseProps} activePanel="metadata" closePanel={closePanel} />);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(closePanel).toHaveBeenCalledWith("metadata");
  });

  it("returns focus to the invoking element on Escape when available", () => {
    const returnFocusTo = document.createElement("button");
    document.body.append(returnFocusTo);
    render(
      <EditorRightPanelSlot {...baseProps} activePanel="metadata" returnFocusTo={returnFocusTo} />,
    );

    fireEvent.keyDown(window, { key: "Escape" });

    expect(document.activeElement).toBe(returnFocusTo);
    returnFocusTo.remove();
  });

  it("returns focus to the opener when the panel closes", () => {
    const opener = document.createElement("button");
    opener.textContent = "open";
    document.body.appendChild(opener);
    // No side effect on closePanel AND opener is not pre-focused, so the
    // activeElement assertion can only pass via the slot's own returnFocusTo
    // focus-return on Escape (a deleted returnFocusTo.focus() fails this).
    const closePanel = vi.fn();

    render(
      <EditorRightPanelSlot
        {...baseProps}
        activePanel="metadata"
        closePanel={closePanel}
        returnFocusTo={opener}
      />,
    );

    // Move focus off the opener so the assertion isolates the slot's behavior.
    document.body.focus();

    fireEvent.keyDown(window, { key: "Escape" });

    expect(closePanel).toHaveBeenCalledWith("metadata");
    expect(document.activeElement).toBe(opener);
    opener.remove();
  });

  it("announces panel shell state in a polite status region", () => {
    render(<EditorRightPanelSlot {...baseProps} activePanel="metadata" />);

    expect(screen.getByRole("status")).toHaveTextContent("shell.panelOpened");
  });

  it("announces panel close in the status region when the active panel is cleared", () => {
    const { rerender } = render(<EditorRightPanelSlot {...baseProps} activePanel="metadata" />);
    expect(screen.getByRole("status")).toHaveTextContent("shell.panelOpened");

    rerender(<EditorRightPanelSlot {...baseProps} activePanel={null} />);

    expect(screen.getByRole("status")).toHaveTextContent("shell.panelClosed");
  });

  it("uses one responsive shell for desktop and mobile panel layouts", () => {
    render(<EditorRightPanelSlot {...baseProps} activePanel="metadata" />);

    const panel = screen.getByTestId("editor-right-panel");
    expect(panel.className).toContain("fixed");
    expect(panel.className).toContain("lg:static");
    expect(panel.className).toContain("lg:w-96");
    expect(panel.className).toContain("lg:flex");
    expect(screen.queryByTestId("editor-right-panel-mobile")).not.toBeInTheDocument();
    expect(screen.queryByTestId("editor-right-panel-desktop")).not.toBeInTheDocument();
  });
});
