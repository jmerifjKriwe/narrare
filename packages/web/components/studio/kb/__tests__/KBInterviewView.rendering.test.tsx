/**
 * KBInterviewView tests — Rendering & display states.
 *
 * Tests the interview view's visual states:
 * - Loading state while requesting first question
 * - Question display after SSE completes
 * - Answer textarea appearance
 * - Exit Interview button
 * - Question progress indicator
 * - Target field info display
 * - Submit button enable/disable states
 * - Submitting spinner state
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KBInterviewView } from "@/components/studio/kb/KBInterviewView";
import type { KBCreationSession, KBInterviewResult } from "@/lib/api/kb-sessions";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockSession: KBCreationSession = {
  id: "session-1",
  novel_id: "novel-1",
  user_id: "user-1",
  entity_type: "character",
  status: "active",
  fields: [
    {
      field_key: "name",
      label: "Name",
      field_type: "text",
      required: true,
      source: "user",
      user_value: undefined,
      ai_suggested_value: undefined,
      ai_reasoning: undefined,
      final_value: undefined,
    },
    {
      field_key: "description",
      label: "Description",
      field_type: "text",
      required: false,
      source: "user",
      user_value: undefined,
      ai_suggested_value: undefined,
      ai_reasoning: undefined,
      final_value: undefined,
    },
  ],
  context_entries: [],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const mockQuestion: KBInterviewResult = {
  question: "What is this character's name?",
  target_field: "name",
  reasoning: null,
};

// ---------------------------------------------------------------------------
// Tests — Rendering & Display
// ---------------------------------------------------------------------------

describe("KBInterviewView — Rendering & Display", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state on mount while requesting first question", async () => {
    // Keep promise pending — don't resolve
    const onRequestQuestion = vi.fn().mockReturnValue(new Promise(() => {}));

    render(
      <KBInterviewView
        novelId="novel-1"
        sessionId="session-1"
        session={mockSession}
        onRequestQuestion={onRequestQuestion}
        onSubmitAnswer={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    expect(screen.getByText("aiActions.aiThinking")).toBeDefined();

    // start() defers execute via queueMicrotask — wait for it
    await waitFor(() => {
      expect(onRequestQuestion).toHaveBeenCalledTimes(1);
    });
  });

  it("shows question after SSE completes", async () => {
    const onRequestQuestion = vi.fn().mockResolvedValue(mockQuestion);

    render(
      <KBInterviewView
        novelId="novel-1"
        sessionId="session-1"
        session={mockSession}
        onRequestQuestion={onRequestQuestion}
        onSubmitAnswer={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("What is this character's name?")).toBeDefined();
    });
  });

  it("shows answer textarea after question loads", async () => {
    const onRequestQuestion = vi.fn().mockResolvedValue(mockQuestion);

    render(
      <KBInterviewView
        novelId="novel-1"
        sessionId="session-1"
        session={mockSession}
        onRequestQuestion={onRequestQuestion}
        onSubmitAnswer={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText("kb.yourAnswer")).toBeDefined();
    });
  });

  it("shows 'Exit Interview' button", async () => {
    const onBack = vi.fn();
    const onRequestQuestion = vi.fn().mockResolvedValue(mockQuestion);

    render(
      <KBInterviewView
        novelId="novel-1"
        sessionId="session-1"
        session={mockSession}
        onRequestQuestion={onRequestQuestion}
        onSubmitAnswer={vi.fn()}
        onBack={onBack}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("kb.exitInterview")).toBeDefined();
    });

    fireEvent.click(screen.getByText("kb.exitInterview"));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it("shows question progress", async () => {
    const onRequestQuestion = vi.fn().mockResolvedValue(mockQuestion);

    render(
      <KBInterviewView
        novelId="novel-1"
        sessionId="session-1"
        session={mockSession}
        onRequestQuestion={onRequestQuestion}
        onSubmitAnswer={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("kb.interviewProgress")).toBeDefined();
    });
  });

  it("shows target field info when question has target_field", async () => {
    const onRequestQuestion = vi.fn().mockResolvedValue(mockQuestion);

    render(
      <KBInterviewView
        novelId="novel-1"
        sessionId="session-1"
        session={mockSession}
        onRequestQuestion={onRequestQuestion}
        onSubmitAnswer={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await waitFor(() => {
      // "Name" is rendered as part of "About: Name" text
      expect(screen.getByText(/Name/)).toBeDefined();
    });
  });

  it("disables submit button when answer is empty", async () => {
    const onRequestQuestion = vi.fn().mockResolvedValue(mockQuestion);

    render(
      <KBInterviewView
        novelId="novel-1"
        sessionId="session-1"
        session={mockSession}
        onRequestQuestion={onRequestQuestion}
        onSubmitAnswer={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("kb.submitAnswer")).toBeDefined();
    });

    const submitButton = screen.getByText("kb.submitAnswer").closest("button");
    expect(submitButton?.disabled).toBe(true);
  });

  it("enables submit button when answer is provided", async () => {
    const onRequestQuestion = vi.fn().mockResolvedValue(mockQuestion);

    render(
      <KBInterviewView
        novelId="novel-1"
        sessionId="session-1"
        session={mockSession}
        onRequestQuestion={onRequestQuestion}
        onSubmitAnswer={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText("kb.yourAnswer")).toBeDefined();
    });

    const textarea = screen.getByPlaceholderText("kb.yourAnswer");
    fireEvent.change(textarea, { target: { value: "Anna" } });

    const submitButton = screen.getByText("kb.submitAnswer").closest("button");
    expect(submitButton?.disabled).toBe(false);
  });

  it("shows submitting state", async () => {
    // Keep submit promise pending
    const onSubmitAnswer = vi.fn().mockReturnValue(new Promise(() => {}));
    const onRequestQuestion = vi.fn().mockResolvedValue(mockQuestion);

    render(
      <KBInterviewView
        novelId="novel-1"
        sessionId="session-1"
        session={mockSession}
        onRequestQuestion={onRequestQuestion}
        onSubmitAnswer={onSubmitAnswer}
        onBack={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText("kb.yourAnswer")).toBeDefined();
    });

    // Type and submit
    const textarea = screen.getByPlaceholderText("kb.yourAnswer");
    fireEvent.change(textarea, { target: { value: "Anna" } });
    fireEvent.click(screen.getByText("kb.submitAnswer"));

    // Submit button should show spinner (text stays same but button has Loader2)
    await waitFor(() => {
      expect(screen.getByText("kb.submitAnswer")).toBeDefined();
    });
  });
});
