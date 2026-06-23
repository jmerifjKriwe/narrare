/**
 * SessionPanel tests — interactive session chat UI.
 *
 * Tests:
 * 1. Renders chat input
 * 2. Sends message on submit
 * 3. Displays chat messages
 * 4. Shows AI response stream
 * 5. Handles connection error
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SessionPanel } from "@/components/studio/editor/SessionPanel";

// ---------------------------------------------------------------------------
// Test wrapper
// ---------------------------------------------------------------------------

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
// Mocks
// ---------------------------------------------------------------------------

// Mock scrollIntoView for jsdom
Element.prototype.scrollIntoView = vi.fn();

// Override global next-intl mock to include .raw() for interview greetings
vi.mock("next-intl", () => ({
  useTranslations: () => {
    const fn = (key: string, params?: Record<string, unknown>) => {
      if (params) {
        return Object.entries(params).reduce(
          (str, [k, v]) => str.replace(`{${k}}`, String(v)),
          key,
        );
      }
      return key;
    };
    fn.raw = (key: string) => {
      if (key === "sessionPanel.interviewGreetings") {
        return ["Hello! Let's begin.", "Welcome to the interview."];
      }
      return [];
    };
    return fn;
  },
  useLocale: () => "en",
  useNow: () => new Date("2024-01-01"),
  useTimeZone: () => "UTC",
}));

const mockSocketConnect = vi.fn();
const mockSocketClose = vi.fn();
const mockSocketSend = vi.fn();

let capturedOnMessage: ((msg: Record<string, unknown>) => void) | null = null;

function dispatchSessionMessage(message: Record<string, unknown>): void {
  if (!capturedOnMessage) {
    throw new Error("Session socket message handler was not captured");
  }
  act(() => {
    capturedOnMessage?.(message);
  });
}

vi.mock("@/lib/api/generation", () => ({
  WritingSessionSocket: class MockWritingSessionSocket {
    constructor(_chapterId: string, onMessage: (msg: Record<string, unknown>) => void) {
      capturedOnMessage = onMessage;
    }
    connect = mockSocketConnect;
    close = mockSocketClose;
    send = mockSocketSend;
  },
}));

vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({ user: { id: "test-user-id", email: "test@example.com" } }),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const defaultProps = {
  chapterId: "chapter-1",
  novelId: "novel-1",
  mode: "interactive_session" as const,
  onClose: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SessionPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    capturedOnMessage = null;
  });

  it("renders chat input", () => {
    renderWithProviders(<SessionPanel {...defaultProps} />);
    expect(screen.getByPlaceholderText("sessionPanel.inputPlaceholder")).toBeDefined();
  });

  it("sends message on submit button click", async () => {
    renderWithProviders(<SessionPanel {...defaultProps} />);

    const input = screen.getByPlaceholderText("sessionPanel.inputPlaceholder");
    fireEvent.change(input, { target: { value: "Hello AI" } });
    fireEvent.click(screen.getByRole("button", { name: "sessionPanel.send" }));

    // The user message should appear in chat
    await waitFor(() => {
      expect(screen.getByText("Hello AI")).toBeDefined();
    });

    // Socket.send should have been called with the user direction
    expect(mockSocketSend).toHaveBeenCalledWith({
      type: "user_direction",
      content: "Hello AI",
    });
  });

  it("displays chat messages from WebSocket", async () => {
    renderWithProviders(<SessionPanel {...defaultProps} />);

    // Simulate receiving a greeting message from WebSocket
    await waitFor(() => {
      expect(capturedOnMessage).not.toBeNull();
    });

    dispatchSessionMessage({
      type: "greeting",
      message: "Hello! I'm your writing assistant.",
    });

    await waitFor(() => {
      expect(screen.getByText("Hello! I'm your writing assistant.")).toBeDefined();
    });
  });

  it("shows AI response stream", async () => {
    renderWithProviders(<SessionPanel {...defaultProps} />);

    await waitFor(() => {
      expect(capturedOnMessage).not.toBeNull();
    });

    // Simulate streaming text chunks
    dispatchSessionMessage({
      type: "text_chunk",
      text: "The castle loomed",
    });

    await waitFor(() => {
      expect(screen.getByText(/The castle loomed/)).toBeDefined();
    });

    // Complete the text
    dispatchSessionMessage({
      type: "text_done",
    });
  });

  it("handles connection error via error message type", async () => {
    renderWithProviders(<SessionPanel {...defaultProps} />);

    await waitFor(() => {
      expect(capturedOnMessage).not.toBeNull();
    });

    // Simulate error message from server
    dispatchSessionMessage({
      type: "error",
      message: "Connection failed",
    });

    await waitFor(() => {
      expect(screen.getByText("Connection failed")).toBeDefined();
    });
  });

  it("renders send button", () => {
    renderWithProviders(<SessionPanel {...defaultProps} />);
    expect(screen.getByRole("button", { name: "sessionPanel.send" })).toBeDefined();
  });

  it("renders close button", () => {
    renderWithProviders(<SessionPanel {...defaultProps} />);
    expect(screen.getByRole("button", { name: "sessionPanel.close" })).toBeDefined();
  });

  it("displays end session button", () => {
    renderWithProviders(<SessionPanel {...defaultProps} />);
    expect(screen.getByText("sessionPanel.endSession")).toBeDefined();
  });

  it("sends stop_generation when the stop button is clicked", async () => {
    renderWithProviders(<SessionPanel {...defaultProps} />);

    await waitFor(() => {
      expect(capturedOnMessage).not.toBeNull();
    });

    dispatchSessionMessage({ type: "text_chunk", text: "A partial stream" });

    await waitFor(() => {
      expect(screen.getByText("stop")).toBeDefined();
    });

    fireEvent.click(screen.getByText("stop"));

    expect(mockSocketSend).toHaveBeenCalledWith({ type: "stop_generation" });
  });

  it("sends stop_generation when Escape is pressed during streaming", async () => {
    renderWithProviders(<SessionPanel {...defaultProps} />);

    await waitFor(() => {
      expect(capturedOnMessage).not.toBeNull();
    });

    dispatchSessionMessage({ type: "text_chunk", text: "A partial stream" });

    await waitFor(() => {
      expect(screen.getByText("stop")).toBeDefined();
    });

    fireEvent.keyDown(window, { key: "Escape" });

    expect(mockSocketSend).toHaveBeenCalledWith({ type: "stop_generation" });
  });

  it("renders server-confirmed stopped prose from generation_stopped", async () => {
    renderWithProviders(<SessionPanel {...defaultProps} />);

    await waitFor(() => {
      expect(capturedOnMessage).not.toBeNull();
    });

    dispatchSessionMessage({
      type: "generation_stopped",
      invocation_id: "inv-1",
      partial_prose: "The server preserved this partial prose.",
      sequence: 4,
      reason: "user_stop",
    });

    await waitFor(() => {
      expect(screen.getByText("The server preserved this partial prose.")).toBeDefined();
    });
  });

  it("preserves local prose and sends recover_session from failed recovery banner retry", async () => {
    renderWithProviders(<SessionPanel {...defaultProps} />);

    await waitFor(() => {
      expect(capturedOnMessage).not.toBeNull();
    });

    dispatchSessionMessage({ type: "greeting", session_id: "session-1", message: "Ready" });
    dispatchSessionMessage({ type: "text_chunk", text: "Unsaved local prose" });
    dispatchSessionMessage({ type: "connection_lost", reason: "idle_timeout" });
    dispatchSessionMessage({ type: "recovery_failed", reason: "session_expired" });

    await waitFor(() => {
      expect(screen.getByText("sessionPanel.preserveLocalCopy")).toBeDefined();
      expect(screen.getByText("Unsaved local prose")).toBeDefined();
    });

    fireEvent.click(screen.getByRole("button", { name: "aiActions.connectionLostRetry" }));

    expect(mockSocketSend).toHaveBeenCalledWith({
      type: "recover_session",
      session_id: "session-1",
    });
  });
});
