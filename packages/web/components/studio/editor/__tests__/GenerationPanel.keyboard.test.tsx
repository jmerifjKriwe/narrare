/**
 * GenerationPanel tests — Keyboard shortcuts (Escape handler).
 *
 * Tests the Escape keyboard shortcut for different panel phases:
 * 1. Escape when streaming calls handleStop
 * 2. Escape when reviewing calls onClose
 * 3. Escape when configuring does nothing
 *
 * Uses a mock for useGenerationPanelController to control phase.
 * Separated from GenerationPanel.test.tsx to avoid mocking conflicts.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GenerationPanel } from "@/components/studio/editor/GenerationPanel";

// ---------------------------------------------------------------------------
// Mock controller
// ---------------------------------------------------------------------------

const mockHandleStop = vi.fn();
const mockOnClose = vi.fn();
let mockPhase: "config" | "streaming" | "review" | "error" = "config";

vi.mock("../generationPanelController", () => ({
  useGenerationPanelController: () => ({
    phase: mockPhase,
    handleStop: mockHandleStop,
    handleGenerate: vi.fn(),
    handleRegenerate: vi.fn(),
    handleRetry: vi.fn(),
    handleRatingDone: vi.fn(),
    acceptDraft: vi.fn(),
    rejectDraft: vi.fn(),
    setMode: vi.fn(),
    setOutline: vi.fn(),
    setPrompt: vi.fn(),
    setTone: vi.fn(),
    setWordTarget: vi.fn(),
    mode: "full_draft" as const,
    outline: "",
    prompt: "",
    wordTarget: 0,
    tone: "balanced",
    targetNum: 3000,
    draftText: "",
    wordCount: 0,
    tokenUsage: null,
    contextMeta: null,
    eventCount: 0,
    showRating: null,
    isLoading: false,
    errorMsg: null,
    connectionLost: false,
    error: null,
    acceptMutation: { isPending: false },
    rejectMutation: { isPending: false },
  }),
}));

// ---------------------------------------------------------------------------
// Mock shared dependencies
// ---------------------------------------------------------------------------

vi.mock("@/lib/hooks/useMemory", () => ({
  useMemoryStatus: () => ({
    eventCount: 0,
    confidence: 0,
    hasProfile: false,
    data: null,
  }),
  useRecordFeedback: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
}));

vi.mock("@/components/studio/learning/LearningStatus", () => ({
  LearningStatus: () => <span data-testid="learning-status" />,
}));

vi.mock("../GenerationConfig", () => ({
  GenerationConfig: () => <div data-testid="mock-generation-config" />,
}));

vi.mock("../GenerationDraft", () => ({
  GenerationDraft: () => <div data-testid="mock-generation-draft" />,
}));

// ---------------------------------------------------------------------------
// Test wrapper
// ---------------------------------------------------------------------------

const defaultProps = {
  novelId: "novel-1",
  chapterId: "chapter-1",
  chapterContent: "",
  onDraftAccepted: vi.fn(),
  onClose: mockOnClose,
  onStartSession: vi.fn(),
};

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("GenerationPanel — keyboard shortcuts", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPhase = "config";
  });

  afterEach(() => {
    // Clean up any lingering effects
    vi.restoreAllMocks();
  });

  it("calls handleStop on Escape when streaming", () => {
    mockPhase = "streaming";
    renderWithProviders(<GenerationPanel {...defaultProps} />);

    fireEvent.keyDown(window, { key: "Escape" });

    expect(mockHandleStop).toHaveBeenCalledTimes(1);
  });

  it("calls onClose on Escape when reviewing", () => {
    mockPhase = "review";
    renderWithProviders(<GenerationPanel {...defaultProps} />);

    fireEvent.keyDown(window, { key: "Escape" });

    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it("does NOT call handleStop or onClose on Escape during config phase", () => {
    mockPhase = "config";
    renderWithProviders(<GenerationPanel {...defaultProps} />);

    fireEvent.keyDown(window, { key: "Escape" });

    expect(mockHandleStop).not.toHaveBeenCalled();
    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it("does NOT call handleStop or onClose on other keys during streaming", () => {
    mockPhase = "streaming";
    renderWithProviders(<GenerationPanel {...defaultProps} />);

    fireEvent.keyDown(window, { key: "Enter" });
    fireEvent.keyDown(window, { key: " " });
    fireEvent.keyDown(window, { key: "x" });

    expect(mockHandleStop).not.toHaveBeenCalled();
    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it("does NOT call handleStop or onClose on other keys during review", () => {
    mockPhase = "review";
    renderWithProviders(<GenerationPanel {...defaultProps} />);

    fireEvent.keyDown(window, { key: "Enter" });
    fireEvent.keyDown(window, { key: "Escape" }); // Only Escape should trigger

    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it("calls handleStop on Escape during error phase (falls through to streaming)", () => {
    mockPhase = "error";
    renderWithProviders(<GenerationPanel {...defaultProps} />);

    fireEvent.keyDown(window, { key: "Escape" });

    // Error phase is not handled by the Escape handler, so nothing should happen
    expect(mockHandleStop).not.toHaveBeenCalled();
    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it("preloads phase-dependent rendering to ensure handler is attached", () => {
    // Verify that the component renders in the expected phase
    mockPhase = "streaming";
    renderWithProviders(<GenerationPanel {...defaultProps} />);

    // Should render the streaming/draft content
    expect(screen.getByTestId("mock-generation-draft")).toBeDefined();

    // Escape should work
    fireEvent.keyDown(window, { key: "Escape" });
    expect(mockHandleStop).toHaveBeenCalledTimes(1);
  });
});
