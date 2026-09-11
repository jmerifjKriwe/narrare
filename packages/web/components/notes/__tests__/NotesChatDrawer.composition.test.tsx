/**
 * NotesChatDrawer composition tests — the REAL ChatPanel is mounted (NOT
 * stubbed, unlike NotesChatDrawer.test.tsx) to prove the Escape wiring
 * end-to-end after the P-DRAWER onClose dedupe:
 *
 * - Escape dismissal has exactly ONE owner: ChatPanel's window listener
 *   (cancel-while-streaming, close-otherwise). The drawer itself adds NO
 *   second listener — historically both fired `onClose` on Escape (double
 *   close, masked by the stubbed-ChatPanel drawer tests).
 * - Streaming keeps the drawer's Escape semantics identical to the
 *   standalone studio ChatPanel: first Escape cancels the stream, the
 *   drawer stays open; a second Escape (idle) closes it.
 *
 * useChat is mocked (same pattern as ChatPanel.keyboard.test.tsx) so the
 * streaming state is controllable without SSE/network; next-intl uses the
 * centralized setupTests mock (keys verbatim — no banner text assertions
 * here, those live in the stubbed file).
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Note } from "@/types";
import { NotesChatDrawer } from "../NotesChatDrawer";

const mockCancelStream = vi.fn();
let mockIsStreaming = false;

vi.mock("@/lib/hooks/useChat", () => ({
  useChat: () => ({
    messages: [],
    isStreaming: mockIsStreaming,
    conversationId: null,
    error: null,
    isError: false,
    sendMessage: vi.fn(),
    clearConversation: vi.fn(),
    cancelStream: mockCancelStream,
    retry: vi.fn(),
    chatEndRef: { current: null },
  }),
}));

const note: Note = {
  id: "n1",
  title: "Twist",
  content: "The aunt did it",
  note_type: "idea",
  tags: [],
  novel_id: null,
  series_id: null,
  created_at: "2026-08-21T00:00:00Z",
  updated_at: "2026-08-21T00:00:00Z",
};

describe("NotesChatDrawer × ChatPanel — Escape ownership (composition)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsStreaming = false;
  });

  it("fires onClose exactly once on Escape when idle (no double close)", () => {
    const onClose = vi.fn();
    render(<NotesChatDrawer open onClose={onClose} note={note} />);
    // Sanity: the REAL ChatPanel is mounted (its input renders), not a stub.
    expect(screen.getByPlaceholderText("chatPanel.inputPlaceholder")).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("Escape while streaming cancels the stream and keeps the drawer open", () => {
    const onClose = vi.fn();
    mockIsStreaming = true;
    render(<NotesChatDrawer open onClose={onClose} note={note} />);

    fireEvent.keyDown(window, { key: "Escape" });

    expect(mockCancelStream).toHaveBeenCalledTimes(1);
    expect(onClose).not.toHaveBeenCalled();
    // The drawer stays open (banner still rendered) — cancel-first, matching
    // the standalone ChatPanel Escape semantics.
    expect(screen.getByTestId("note-chat-banner")).toBeInTheDocument();
  });

  it("a second Escape after the stream was cancelled closes the drawer", () => {
    const onClose = vi.fn();
    mockIsStreaming = true;
    const { rerender } = render(<NotesChatDrawer open onClose={onClose} note={note} />);

    fireEvent.keyDown(window, { key: "Escape" }); // cancels the stream
    expect(onClose).not.toHaveBeenCalled();

    mockIsStreaming = false;
    rerender(<NotesChatDrawer open onClose={onClose} note={note} />);
    fireEvent.keyDown(window, { key: "Escape" }); // idle → close

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
