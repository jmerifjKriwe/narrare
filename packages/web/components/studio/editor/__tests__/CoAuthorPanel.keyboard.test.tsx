/**
 * CoAuthorPanel tests — Keyboard shortcuts (Escape handler).
 *
 * Tests:
 * 1. Escape calls handleCancel (closes panel)
 * 2. Other keys do NOT call handleCancel
 *
 * Uses a mock for useCoAuthorPanel to avoid complex hook dependencies.
 * Separated from general CoAuthorPanel tests to avoid mocking conflicts.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CoAuthorPanel } from "@/components/studio/editor/CoAuthorPanel";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockHandleCancel = vi.fn();

vi.mock("../_components/useCoAuthorPanel", () => ({
  useCoAuthorPanel: () => ({
    phase: "focus",
    selectedFocus: [],
    streamedText: "",
    changes: [],
    acceptance: {},
    submitting: false,
    errorMsg: null,
    phaseLabel: null,
    t: (key: string) => {
      const translations: Record<string, string> = {
        "coAuthor.title": "Co-Author",
        "coAuthor.close": "Close",
        "coAuthor.errorGeneric": "An error occurred",
      };
      return translations[key] || key;
    },
    toggleFocus: vi.fn(),
    handleStart: vi.fn(),
    handleAcceptAll: vi.fn(),
    handleRejectAll: vi.fn(),
    handleToggleChange: vi.fn(),
    handleApply: vi.fn(),
    handleCancel: mockHandleCancel,
    handleStop: vi.fn(),
    handleRetry: vi.fn(),
  }),
}));

vi.mock("../_components/CoAuthorFocusSelector", () => ({
  CoAuthorFocusSelector: () => <div data-testid="mock-focus-selector" />,
}));

vi.mock("../_components/CoAuthorStreamingPhase", () => ({
  CoAuthorStreamingPhase: () => <div data-testid="mock-streaming-phase" />,
}));

vi.mock("../_components/CoAuthorReviewPhase", () => ({
  CoAuthorReviewPhase: () => <div data-testid="mock-review-phase" />,
}));

vi.mock("../_components/CoAuthorDonePhase", () => ({
  CoAuthorDonePhase: () => <div data-testid="mock-done-phase" />,
}));

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const defaultProps = {
  novelId: "novel-1",
  chapterId: "chapter-1",
  selectionText: "selected text",
  onAccept: vi.fn(),
  onClose: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CoAuthorPanel — keyboard shortcuts", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls handleCancel on Escape", () => {
    render(<CoAuthorPanel {...defaultProps} />);

    fireEvent.keyDown(window, { key: "Escape" });

    expect(mockHandleCancel).toHaveBeenCalledTimes(1);
  });

  it("does NOT call handleCancel on other keys", () => {
    render(<CoAuthorPanel {...defaultProps} />);

    fireEvent.keyDown(window, { key: "Enter" });
    fireEvent.keyDown(window, { key: " " });
    fireEvent.keyDown(window, { key: "x" });

    expect(mockHandleCancel).not.toHaveBeenCalled();
  });

  it("renders focus selector in initial phase", () => {
    render(<CoAuthorPanel {...defaultProps} />);

    expect(screen.getByTestId("mock-focus-selector")).toBeDefined();
  });
});
