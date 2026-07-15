/**
 * ChatPanel tests — Actionable error rendering (CR-AUFG-07-25 regression).
 *
 * Regression: ChatPanel previously rendered a generic
 * `chatPanel.errorConnecting` constant ("Verbindungsfehler") for every error,
 * discarding the structured AIErrorResponse computed by useChat. It now
 * renders `error.userMessage` and a retry button when `error.retryable`.
 *
 * Tests:
 * 1. Non-retryable 401 error renders the actionable "API-Schlüssel" message,
 *    NOT the generic "Verbindungsfehler", and shows NO retry button.
 * 2. Retryable error (e.g. rate limit) renders a retry button.
 * 3. Clicking the retry button calls `retry`.
 * 4. No error renders nothing.
 *
 * Uses a mock for useChat to control the error state. Separated from the
 * keyboard tests to avoid mocking conflicts.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ChatPanel } from "@/components/studio/editor/ChatPanel";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation.types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockRetry = vi.fn();
let mockError: AIErrorResponse | null = null;
let mockIsError = false;

vi.mock("@/lib/hooks/useChat", () => ({
  useChat: () => ({
    messages: [],
    isStreaming: false,
    conversationId: null,
    error: mockError,
    isError: mockIsError,
    sendMessage: vi.fn(),
    clearConversation: vi.fn(),
    cancelStream: vi.fn(),
    retry: mockRetry,
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
      "chatPanel.errorConnecting": "Verbindungsfehler",
      "chatPanel.clearConversation": "Clear",
      "sessionPanel.close": "Close",
      "sessionPanel.aiDraftBadge": "AI Draft",
      "aiActions.addToDraft": "Add to draft",
      "aiActions.retry": "Erneut versuchen",
      "sessionPanel.addedToDraft": "Added",
    };
    return translations[key] || key;
  },
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const API_KEY_ERROR: AIErrorResponse = {
  kind: "http",
  status: 401,
  i18nKey: "aiActions.errorApiKey",
  userMessage: "Dein API-Schlüssel ist ungültig. Überprüfe deine KI-Einstellungen.",
  retryable: false,
  cause: new Error("401 Unauthorized"),
};

const RATE_LIMIT_ERROR: AIErrorResponse = {
  kind: "http",
  status: 429,
  i18nKey: "aiActions.errorRateLimit",
  userMessage: "Du hast zu viele Anfragen gesendet. Warte einen Moment.",
  retryable: true,
  cause: new Error("429 Too Many Requests"),
};

const defaultProps = {
  projectId: "project-1",
  onClose: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ChatPanel — actionable error rendering", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockError = null;
    mockIsError = false;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the actionable API-key message (not the generic constant) on a 401", () => {
    mockError = API_KEY_ERROR;
    mockIsError = true;

    render(<ChatPanel {...defaultProps} />);

    // The structured, actionable message appears...
    expect(
      screen.getByText("Dein API-Schlüssel ist ungültig. Überprüfe deine KI-Einstellungen."),
    ).toBeDefined();
    // ...and the discarded generic constant does NOT.
    expect(screen.queryByText("Verbindungsfehler")).toBeNull();
  });

  it("does NOT show a retry button for a non-retryable error", () => {
    mockError = API_KEY_ERROR;
    mockIsError = true;

    render(<ChatPanel {...defaultProps} />);

    expect(screen.queryByText("Erneut versuchen")).toBeNull();
  });

  it("shows a retry button for a retryable error", () => {
    mockError = RATE_LIMIT_ERROR;
    mockIsError = true;

    render(<ChatPanel {...defaultProps} />);

    expect(screen.getByText("Erneut versuchen")).toBeDefined();
  });

  it("calls retry when the retry button is clicked", () => {
    mockError = RATE_LIMIT_ERROR;
    mockIsError = true;

    render(<ChatPanel {...defaultProps} />);

    fireEvent.click(screen.getByText("Erneut versuchen"));

    expect(mockRetry).toHaveBeenCalledTimes(1);
  });

  it("renders no error UI when there is no error", () => {
    render(<ChatPanel {...defaultProps} />);

    expect(screen.queryByText("Verbindungsfehler")).toBeNull();
    expect(screen.queryByText("Erneut versuchen")).toBeNull();
    expect(
      screen.queryByText("Dein API-Schlüssel ist ungültig. Überprüfe deine KI-Einstellungen."),
    ).toBeNull();
  });
});
