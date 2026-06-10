/**
 * RewriteSuggestionModal tests — Keyboard shortcuts for rewrite suggestions.
 *
 * Tests the keyboard shortcut handler (KEYBOARD-001):
 * 1. Ctrl+Y calls onAccept
 * 2. Ctrl+N calls onReject
 * 3. Escape when streaming calls onNewSuggestions
 * 4. Escape when NOT streaming calls onReject
 * 5. Cmd+Y (Mac) also calls onAccept
 */

import { fireEvent, render } from "@testing-library/react";
import { useTranslations } from "next-intl";
import { describe, expect, it, vi } from "vitest";
import { RewriteSuggestionModal } from "../RewriteSuggestionModal";
import type { AISuggestion } from "../TipTapEditorController";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockSuggestion: AISuggestion = {
  original: "The old text that needs rewriting.",
  suggestions: ["The new improved text version one.", "The new improved text version two."],
  labels: ["Concise", "Descriptive"],
  position: { from: 0, to: 35 },
};

// ---------------------------------------------------------------------------
// Tests — Keyboard Shortcuts
// ---------------------------------------------------------------------------

describe("RewriteSuggestionModal", () => {
  const t = useTranslations("studio");

  const defaultProps = {
    aiSuggestion: mockSuggestion,
    selectedSuggestion: 0,
    onSelectedSuggestionChange: vi.fn(),
    rejectionReason: "",
    onRejectionReasonChange: vi.fn(),
    showRejectionInput: false,
    isRewriteStreaming: false,
    rewriteError: null,
    onReject: vi.fn(),
    onInsertAsNew: vi.fn(),
    onNewSuggestions: vi.fn(),
    onAccept: vi.fn(),
    t,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("keyboard shortcuts", () => {
    it("calls onAccept on Ctrl+Y", () => {
      const onAccept = vi.fn();
      render(<RewriteSuggestionModal {...defaultProps} onAccept={onAccept} />);

      fireEvent.keyDown(window, { key: "y", ctrlKey: true });

      expect(onAccept).toHaveBeenCalledTimes(1);
    });

    it("calls onAccept on Cmd+Y (Mac)", () => {
      const onAccept = vi.fn();
      render(<RewriteSuggestionModal {...defaultProps} onAccept={onAccept} />);

      fireEvent.keyDown(window, { key: "y", metaKey: true });

      expect(onAccept).toHaveBeenCalledTimes(1);
    });

    it("calls onReject on Ctrl+N", () => {
      const onReject = vi.fn();
      render(<RewriteSuggestionModal {...defaultProps} onReject={onReject} />);

      fireEvent.keyDown(window, { key: "n", ctrlKey: true });

      expect(onReject).toHaveBeenCalledTimes(1);
    });

    it("calls onReject on Escape when NOT streaming", () => {
      const onReject = vi.fn();
      render(
        <RewriteSuggestionModal {...defaultProps} isRewriteStreaming={false} onReject={onReject} />,
      );

      fireEvent.keyDown(window, { key: "Escape" });

      expect(onReject).toHaveBeenCalledTimes(1);
    });

    it("calls onNewSuggestions on Escape when streaming", () => {
      const onNewSuggestions = vi.fn();
      render(
        <RewriteSuggestionModal
          {...defaultProps}
          isRewriteStreaming={true}
          onNewSuggestions={onNewSuggestions}
        />,
      );

      fireEvent.keyDown(window, { key: "Escape" });

      expect(onNewSuggestions).toHaveBeenCalledTimes(1);
      // Should NOT call onReject when streaming
      expect(defaultProps.onReject).not.toHaveBeenCalled();
    });

    it("does NOT call any handler on other keys", () => {
      const onAccept = vi.fn();
      const onReject = vi.fn();
      const onNewSuggestions = vi.fn();
      render(
        <RewriteSuggestionModal
          {...defaultProps}
          onAccept={onAccept}
          onReject={onReject}
          onNewSuggestions={onNewSuggestions}
        />,
      );

      fireEvent.keyDown(window, { key: "a" });
      fireEvent.keyDown(window, { key: "Enter" });
      fireEvent.keyDown(window, { key: " " });

      expect(onAccept).not.toHaveBeenCalled();
      expect(onReject).not.toHaveBeenCalled();
      expect(onNewSuggestions).not.toHaveBeenCalled();
    });

    it("calls onReject on Escape when streaming completes (transitions)", () => {
      // Simulate the lifecycle: first streaming (Escape → onNewSuggestions),
      // then streaming completes (Escape → onReject)
      const onReject = vi.fn();
      const onNewSuggestions = vi.fn();
      const { rerender } = render(
        <RewriteSuggestionModal
          {...defaultProps}
          isRewriteStreaming={true}
          onReject={onReject}
          onNewSuggestions={onNewSuggestions}
        />,
      );

      fireEvent.keyDown(window, { key: "Escape" });
      expect(onNewSuggestions).toHaveBeenCalledTimes(1);
      expect(onReject).not.toHaveBeenCalled();

      // Now streaming completes
      vi.clearAllMocks();
      rerender(
        <RewriteSuggestionModal
          {...defaultProps}
          isRewriteStreaming={false}
          onReject={onReject}
          onNewSuggestions={onNewSuggestions}
        />,
      );

      fireEvent.keyDown(window, { key: "Escape" });
      expect(onReject).toHaveBeenCalledTimes(1);
    });
  });
});
