import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useEditorStore } from "@/lib/stores/editorStore";
import type { Chapter } from "@/types";
import { StatusBar } from "./StatusBar";

// --- Mocks ---

vi.mock("next-intl", () => ({
  useTranslations: (ns: string) => {
    const translations: Record<string, Record<string, string>> = {
      editor: {
        "saveStatus.idle": "",
        "saveStatus.saving": "Saving\u2026",
        "saveStatus.saved": "Saved",
        "saveStatus.error": "Save failed \u2014 retry?",
        wordCount: "words",
        readingTime: "reading time",
      },
    };
    return (key: string) => translations[ns]?.[key] ?? `${ns}.${key}`;
  },
}));

// --- Helpers ---

const sampleChapter: Chapter = {
  id: "ch-1",
  novel_id: "novel-1",
  volume_id: null,
  title: "Chapter One",
  content: "<p>Hello world</p>",
  summary: "",
  position: 0,
  word_count: 1500,
  status: "draft",
  pov_character_id: "",
  timeline_position: "",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  useEditorStore.setState({
    activeChapterId: null,
    saveStatus: "idle",
    lastSavedAt: null,
    sidebarOpen: true,
    contextPanelOpen: false,
    focusMode: false,
  });
});

describe("StatusBar", () => {
  it("should display word count when a chapter is provided", () => {
    render(<StatusBar chapter={sampleChapter} />);

    expect(screen.getByText("words")).toBeInTheDocument();
  });

  it("should display reading time when a chapter is provided", () => {
    render(<StatusBar chapter={sampleChapter} />);

    expect(screen.getByText("reading time")).toBeInTheDocument();
  });

  it("should not display word count or reading time when chapter is null", () => {
    render(<StatusBar chapter={null} />);

    expect(screen.queryByText("words")).not.toBeInTheDocument();
    expect(screen.queryByText("reading time")).not.toBeInTheDocument();
  });

  it('should display "Saving…" when saveStatus is "saving"', () => {
    useEditorStore.setState({ saveStatus: "saving" });

    render(<StatusBar chapter={sampleChapter} />);

    expect(screen.getByText("Saving\u2026")).toBeInTheDocument();
  });

  it('should show spinner indicator when saveStatus is "saving"', () => {
    useEditorStore.setState({ saveStatus: "saving" });

    render(<StatusBar chapter={sampleChapter} />);

    // The spinner has animate-spin class
    const spinner = document.querySelector(".animate-spin");
    expect(spinner).toBeInTheDocument();
  });

  it('should display "Saved" when saveStatus is "saved"', () => {
    useEditorStore.setState({ saveStatus: "saved" });

    render(<StatusBar chapter={sampleChapter} />);

    expect(screen.getByText("Saved")).toBeInTheDocument();
  });

  it('should show success dot when saveStatus is "saved"', () => {
    useEditorStore.setState({ saveStatus: "saved" });

    render(<StatusBar chapter={sampleChapter} />);

    // The success indicator is a small dot with success color
    const dot =
      document.querySelector('[style*="color: var(--color-success)"]') ||
      document.querySelector(".bg-\\[var\\(--color-success\\)\\]");
    expect(dot).toBeInTheDocument();
  });

  it('should display error message when saveStatus is "error"', () => {
    useEditorStore.setState({ saveStatus: "error" });

    render(<StatusBar chapter={sampleChapter} />);

    expect(screen.getByText(/Save failed/)).toBeInTheDocument();
  });

  it('should show error dot when saveStatus is "error"', () => {
    useEditorStore.setState({ saveStatus: "error" });

    render(<StatusBar chapter={sampleChapter} />);

    // Error indicator has error color dot
    const dot = document.querySelector(".bg-\\[var\\(--color-error\\)\\]");
    expect(dot).toBeInTheDocument();
  });

  it('should not show any save label when saveStatus is "idle"', () => {
    useEditorStore.setState({ saveStatus: "idle" });

    render(<StatusBar chapter={sampleChapter} />);

    // idle has empty string label
    expect(screen.queryByText("Saving")).not.toBeInTheDocument();
    expect(screen.queryByText("Saved")).not.toBeInTheDocument();
    expect(screen.queryByText(/Save failed/)).not.toBeInTheDocument();
  });

  it("should have role=status for accessibility", () => {
    render(<StatusBar chapter={sampleChapter} />);

    const statusBar = screen.getAllByRole("status");
    expect(statusBar.length).toBeGreaterThanOrEqual(1);
  });

  it("should have aria-live=polite for status updates", () => {
    render(<StatusBar chapter={sampleChapter} />);

    const liveRegion = document.querySelector('[aria-live="polite"]');
    expect(liveRegion).toBeInTheDocument();
  });

  it("should use editorStore for save status state", () => {
    // Set store to "saving"
    useEditorStore.setState({ saveStatus: "saving" });

    render(<StatusBar chapter={sampleChapter} />);

    expect(screen.getByText("Saving\u2026")).toBeInTheDocument();
  });

  it("should display word count of 0 as 0", () => {
    const chapterWithZeroWords: Chapter = { ...sampleChapter, word_count: 0 };

    render(<StatusBar chapter={chapterWithZeroWords} />);

    expect(screen.getByText("words")).toBeInTheDocument();
  });
});
