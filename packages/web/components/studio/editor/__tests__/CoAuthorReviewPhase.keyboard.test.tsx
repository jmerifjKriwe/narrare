/**
 * CoAuthorReviewPhase tests — Keyboard shortcut (Ctrl/Cmd+Enter).
 *
 * Tests the apply shortcut for the Co-Author review phase (CR-AUFG-07-13).
 * Escape → close is handled by the parent CoAuthorPanel, so only the
 * Ctrl/Cmd+Enter → apply shortcut is tested here.
 *
 * The component is rendered directly (not through CoAuthorPanel) to avoid
 * the parent's mock that replaces CoAuthorReviewPhase with a stub.
 */

import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CoAuthorReviewPhase } from "@/components/studio/editor/_components/CoAuthorReviewPhase";
import type { ChangeDetail } from "@/lib/api/coauthor";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockChanges: ChangeDetail[] = [
  {
    id: "change-1",
    change_type: "word_choice",
    original_text: "old text",
    revised_text: "new text",
    index: 0,
  },
];

const defaultProps = {
  changes: mockChanges,
  acceptance: {},
  reasoning: "Overall reasoning",
  onToggleChange: vi.fn(),
  onAcceptAll: vi.fn(),
  onRejectAll: vi.fn(),
  onApply: vi.fn(),
  submitting: false,
  onClose: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CoAuthorReviewPhase — keyboard shortcuts", () => {
  it("calls onApply on Ctrl+Enter (CR-AUFG-07-13)", () => {
    const onApply = vi.fn();
    render(<CoAuthorReviewPhase {...defaultProps} onApply={onApply} />);

    fireEvent.keyDown(window, { key: "Enter", ctrlKey: true });

    expect(onApply).toHaveBeenCalledTimes(1);
  });

  it("calls onApply on Cmd+Enter (Mac)", () => {
    const onApply = vi.fn();
    render(<CoAuthorReviewPhase {...defaultProps} onApply={onApply} />);

    fireEvent.keyDown(window, { key: "Enter", metaKey: true });

    expect(onApply).toHaveBeenCalledTimes(1);
  });

  it("does NOT call onApply when submitting", () => {
    const onApply = vi.fn();
    render(<CoAuthorReviewPhase {...defaultProps} onApply={onApply} submitting={true} />);

    fireEvent.keyDown(window, { key: "Enter", ctrlKey: true });

    expect(onApply).not.toHaveBeenCalled();
  });

  it("does NOT call onApply on plain Enter (without modifier)", () => {
    const onApply = vi.fn();
    render(<CoAuthorReviewPhase {...defaultProps} onApply={onApply} />);

    fireEvent.keyDown(window, { key: "Enter" });

    expect(onApply).not.toHaveBeenCalled();
  });
});
