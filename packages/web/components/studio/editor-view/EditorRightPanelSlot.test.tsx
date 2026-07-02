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
    expect(screen.getAllByTestId("readability-panel")).toHaveLength(2);
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

  it("keeps a mobile drawer representation for the active panel", () => {
    render(<EditorRightPanelSlot {...baseProps} activePanel="metadata" />);

    expect(screen.getByTestId("editor-right-panel-mobile").className).toContain("lg:hidden");
    expect(screen.getByTestId("editor-right-panel-desktop").className).toContain("lg:flex");
  });
});
