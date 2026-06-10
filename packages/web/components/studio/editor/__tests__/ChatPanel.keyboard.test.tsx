/**
 * ChatPanel tests — Keyboard shortcuts (Ctrl+Enter + Escape).
 *
 * Tests:
 * 1. Ctrl+Enter sends message
 * 2. Plain Enter does NOT send
 * 3. Shift+Enter does NOT send
 * 4. Cmd+Enter sends message (Mac)
 * 5. Escape when streaming calls cancelStream
 * 6. Escape when idle calls onClose
 * 7. Other keys don't trigger send or close
 *
 * Uses a mock for useChat to control streaming state.
 * Separated from general ChatPanel tests to avoid mocking conflicts.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ChatPanel } from "@/components/studio/editor/ChatPanel";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockSendMessage = vi.fn();
const mockCancelStream = vi.fn();
const mockClearConversation = vi.fn();
let mockIsStreaming = false;

vi.mock("@/lib/hooks/useChat", () => ({
  useChat: () => ({
    messages: [],
    isStreaming: mockIsStreaming,
    conversationId: null,
    error: null,
    sendMessage: mockSendMessage,
    clearConversation: mockClearConversation,
    cancelStream: mockCancelStream,
    chatEndRef: { current: null },
  }),
}));

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => {
    const translations: Record<string, string> = {
      "chatPanel.title": "Writing Chat",
      "chatPanel.connected": "Connected",
      "chatPanel.disconnected": "Disconnected",
      "chatPanel.newConversation": "Ask anything",
      "chatPanel.streaming": "Thinking...",
      "chatPanel.inputPlaceholder": "Ask...",
      "chatPanel.send": "Send",
      "chatPanel.sendHint": "Ctrl+Enter to send",
      "chatPanel.errorConnecting": "Connection error",
      "chatPanel.clearConversation": "Clear",
      "sessionPanel.close": "Close",
      "sessionPanel.aiDraftBadge": "AI Draft",
      "aiActions.addToDraft": "Add to draft",
      "sessionPanel.addedToDraft": "Added",
    };
    return translations[key] || key;
  },
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const defaultProps = {
  projectId: "project-1",
  onClose: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ChatPanel — keyboard shortcuts", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsStreaming = false;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // -- Send tests --

  it("sends message on Ctrl+Enter", () => {
    render(<ChatPanel {...defaultProps} />);

    const input = screen.getByPlaceholderText("Ask...");
    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.keyDown(input, { key: "Enter", ctrlKey: true });

    expect(mockSendMessage).toHaveBeenCalledWith("Hello");
  });

  it("sends message on Cmd+Enter (Mac)", () => {
    render(<ChatPanel {...defaultProps} />);

    const input = screen.getByPlaceholderText("Ask...");
    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.keyDown(input, { key: "Enter", metaKey: true });

    expect(mockSendMessage).toHaveBeenCalledWith("Hello");
  });

  it("does NOT send on plain Enter", () => {
    render(<ChatPanel {...defaultProps} />);

    const input = screen.getByPlaceholderText("Ask...");
    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(mockSendMessage).not.toHaveBeenCalled();
  });

  it("does NOT send on Shift+Enter", () => {
    render(<ChatPanel {...defaultProps} />);

    const input = screen.getByPlaceholderText("Ask...");
    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.keyDown(input, { key: "Enter", shiftKey: true });

    expect(mockSendMessage).not.toHaveBeenCalled();
  });

  it("does NOT send on other keys", () => {
    render(<ChatPanel {...defaultProps} />);

    const input = screen.getByPlaceholderText("Ask...");
    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.keyDown(input, { key: " " });
    fireEvent.keyDown(input, { key: "x" });

    expect(mockSendMessage).not.toHaveBeenCalled();
  });

  // -- Escape tests --

  it("calls cancelStream on Escape when streaming", () => {
    mockIsStreaming = true;
    render(<ChatPanel {...defaultProps} />);

    fireEvent.keyDown(window, { key: "Escape" });

    expect(mockCancelStream).toHaveBeenCalledTimes(1);
  });

  it("calls onClose on Escape when NOT streaming", () => {
    const onClose = vi.fn();
    render(<ChatPanel {...defaultProps} onClose={onClose} />);

    fireEvent.keyDown(window, { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does NOT call cancelStream or onClose on non-Escape keys", () => {
    const onClose = vi.fn();
    mockIsStreaming = true;
    render(<ChatPanel {...defaultProps} onClose={onClose} />);

    fireEvent.keyDown(window, { key: "Enter" });
    fireEvent.keyDown(window, { key: " " });

    expect(mockCancelStream).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("shows sendHint text", () => {
    render(<ChatPanel {...defaultProps} />);

    expect(screen.getByText("Ctrl+Enter to send")).toBeDefined();
  });
});
