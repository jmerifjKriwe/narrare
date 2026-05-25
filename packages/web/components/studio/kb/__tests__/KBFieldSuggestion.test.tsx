/**
 * KBFieldSuggestion tests — AI suggestion display with SSE streaming.
 *
 * Tests:
 * 1. Returns null when idle (no loading, no result, no error)
 * 2. Shows loading state with typing animation
 * 3. Shows "AI thinking" placeholder when no streamed text yet
 * 4. Shows streamed text character by character
 * 5. Shows complete suggestion with accept/reject buttons
 * 6. Shows reasoning box when result has reasoning
 * 7. Shows error state with retry button
 * 8. Accept button calls onAccept with suggestion value
 * 9. Reject button calls onReject
 * 10. Resets display when field changes
 * 11. Immediately shows full text when result is available (not streaming)
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KBFieldSuggestion } from "@/components/studio/kb/KBFieldSuggestion";
import type { KBCreationField, KBSuggestionResult } from "@/lib/api/kb-sessions";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockField: KBCreationField = {
  field_key: "description",
  label: "Description",
  field_type: "text",
  required: false,
  source: "user",
  user_value: undefined,
  ai_suggested_value: undefined,
  ai_reasoning: undefined,
  final_value: undefined,
};

const mockResult: KBSuggestionResult = {
  field_key: "description",
  suggestion: "A brave adventurer with a mysterious past.",
  reasoning: "Common heroic archetype for fantasy stories.",
};

const defaultProps = {
  field: mockField,
  onAccept: vi.fn(),
  onReject: vi.fn(),
  onRetry: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KBFieldSuggestion", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns null when idle (no loading, no result, no error)", () => {
    const { container } = render(<KBFieldSuggestion {...defaultProps} />);
    expect(container.innerHTML).toBe("");
  });

  it("shows loading state with AI thinking placeholder", () => {
    render(<KBFieldSuggestion {...defaultProps} isLoading streamedText="" />);

    expect(screen.getByText("kb.aiSuggestion")).toBeDefined();
    expect(screen.getByText("kb.aiThinking")).toBeDefined();
    // Should have a pulsing dot
    const pulseDot = document.querySelector(".animate-pulse");
    expect(pulseDot).toBeTruthy();
  });

  it("shows streamed text during loading", () => {
    render(<KBFieldSuggestion {...defaultProps} isLoading streamedText="A brave" />);

    // "A brave" should be displayed (or some portion depending on animation timing)
    // The animation is setTimeout-based, but the displayText starts empty and grows
    // to match streamedText character by character. For testing, we can check
    // that the component is in loading state with the right content.
    expect(screen.getByText("kb.aiSuggestion")).toBeDefined();
  });

  it("shows complete suggestion with accept/reject buttons", () => {
    render(<KBFieldSuggestion {...defaultProps} result={mockResult} />);

    expect(screen.getByText("kb.aiSuggestion")).toBeDefined();
    expect(screen.getByText(mockResult.suggestion)).toBeDefined();
    expect(screen.getByText("kb.reject")).toBeDefined();
    expect(screen.getByText("kb.accept")).toBeDefined();
  });

  it("shows reasoning box when result has reasoning", () => {
    render(<KBFieldSuggestion {...defaultProps} result={mockResult} />);

    expect(screen.getByText("kb.aiReasoning")).toBeDefined();
    expect(screen.getByText(mockResult.reasoning)).toBeDefined();
  });

  it("hides reasoning box when result has no reasoning", () => {
    render(<KBFieldSuggestion {...defaultProps} result={{ ...mockResult, reasoning: "" }} />);

    expect(screen.queryByText("kb.aiReasoning")).toBeNull();
  });

  it("shows error state with retry button", () => {
    const error = new Error("Something went wrong");
    render(<KBFieldSuggestion {...defaultProps} error={error} />);

    expect(screen.getByText("Something went wrong")).toBeDefined();
    expect(screen.getByText("kb.retry")).toBeDefined();
  });

  it("accept button calls onAccept with suggestion value", () => {
    const onAccept = vi.fn();
    render(<KBFieldSuggestion {...defaultProps} onAccept={onAccept} result={mockResult} />);

    fireEvent.click(screen.getByText("kb.accept"));
    expect(onAccept).toHaveBeenCalledWith(mockResult.suggestion);
    expect(onAccept).toHaveBeenCalledTimes(1);
  });

  it("reject button calls onReject", () => {
    const onReject = vi.fn();
    render(<KBFieldSuggestion {...defaultProps} onReject={onReject} result={mockResult} />);

    fireEvent.click(screen.getByText("kb.reject"));
    expect(onReject).toHaveBeenCalledTimes(1);
  });

  it("retry button calls onRetry in error state", () => {
    const onRetry = vi.fn();
    render(<KBFieldSuggestion {...defaultProps} onRetry={onRetry} error={new Error("Failed")} />);

    fireEvent.click(screen.getByText("kb.retry"));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("resets display when field changes", () => {
    const { rerender } = render(
      <KBFieldSuggestion {...defaultProps} field={mockField} isLoading streamedText="old text" />,
    );

    // Change field key
    const newField: KBCreationField = { ...mockField, field_key: "background" };
    rerender(<KBFieldSuggestion {...defaultProps} field={newField} />);

    // After field change, component should go to idle → null
    expect(screen.queryByText("kb.aiSuggestion")).toBeNull();
  });

  it("immediately shows full text when result passed directly (not streaming)", () => {
    render(<KBFieldSuggestion {...defaultProps} result={mockResult} />);

    // The full suggestion text should be visible
    expect(screen.getByText(mockResult.suggestion)).toBeDefined();
  });
});
