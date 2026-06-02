/**
 * KBAssistedCreationPanel tests — Session actions.
 *
 * Tests the panel's session-level actions:
 * - Abandon flow (confirm dialog, confirm, cancelling confirm)
 * - Complete & Save flow
 * - Cancel button
 * - Abandoning pending state
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { KBAssistedCreationPanel } from "@/components/studio/kb/KBAssistedCreationPanel";

// ---------------------------------------------------------------------------
// Mocks — hook layer
// ---------------------------------------------------------------------------

const mockHooks = {
  createSession: {
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null as Error | null,
  },
  session: {
    data: null as Record<string, unknown> | null,
    isLoading: false,
  },
  completeSession: {
    mutate: vi.fn(),
    isPending: false,
  },
  abandonSession: {
    mutate: vi.fn(),
    isPending: false,
  },
  answerField: {
    mutate: vi.fn(),
  },
  suggestField: {
    mutate: vi.fn(),
    isPending: false,
  },
  interview: {
    mutate: vi.fn(),
    isPending: false,
  },
  enhance: {
    mutate: vi.fn(),
    isPending: false,
  },
};

vi.mock("@/lib/hooks/useKBSessions", () => ({
  useCreateKBSession: () => mockHooks.createSession,
  useKBSession: () => mockHooks.session,
  useAnswerField: () => mockHooks.answerField,
  useCompleteKBSession: () => mockHooks.completeSession,
  useAbandonKBSession: () => mockHooks.abandonSession,
  useKBSessionSuggest: () => mockHooks.suggestField,
  useKBSessionInterview: () => mockHooks.interview,
  useKBSessionEnhance: () => mockHooks.enhance,
}));

vi.mock("@/components/studio/kb/KBInterviewView", () => ({
  KBInterviewView: ({
    onBack,
    onRequestQuestion,
    onSubmitAnswer,
  }: {
    onBack: () => void;
    onRequestQuestion: (signal?: AbortSignal) => Promise<unknown>;
    onSubmitAnswer: (fieldKey: string, answer: string) => Promise<void>;
  }) => (
    <div data-testid="interview-view">
      <span>kb.interviewMode</span>
      <button type="button" data-testid="interview-back" onClick={onBack}>
        Back
      </button>
      <button
        type="button"
        data-testid="interview-request-question"
        onClick={() => onRequestQuestion()}
      >
        Request Question
      </button>
      <button
        type="button"
        data-testid="interview-submit-answer"
        onClick={() => onSubmitAnswer("name", "Anna")}
      >
        Submit Answer
      </button>
    </div>
  ),
}));

vi.mock("@/components/studio/kb/KBEnhanceReview", () => ({
  KBEnhanceReview: ({
    onBack,
    onRequestEnhance,
    onApplySelected,
  }: {
    onBack: () => void;
    onRequestEnhance: () => Promise<unknown>;
    onApplySelected: () => void;
  }) => (
    <div data-testid="enhance-view">
      <span>kb.enhanceReview</span>
      <button type="button" data-testid="enhance-back" onClick={onBack}>
        Back
      </button>
      <button type="button" data-testid="enhance-request" onClick={() => onRequestEnhance()}>
        Request Enhance
      </button>
      <button type="button" data-testid="enhance-apply" onClick={onApplySelected}>
        Apply Selected
      </button>
    </div>
  ),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockField = (overrides: Record<string, unknown> = {}) => ({
  field_key: "name",
  label: "Name",
  field_type: "text" as const,
  required: true,
  source: "user" as const,
  user_value: undefined as string | undefined,
  ai_suggested_value: undefined as string | undefined,
  ai_reasoning: undefined as string | undefined,
  final_value: undefined as string | undefined,
  ...overrides,
});

const mockSessionData = {
  id: "session-1",
  novel_id: "novel-1",
  user_id: "user-1",
  entity_type: "character",
  status: "active",
  fields: [
    mockField({ user_value: "Test Character", final_value: "Test Character" }),
    mockField({
      field_key: "description",
      label: "Description",
      required: false,
    }),
    mockField({
      field_key: "background",
      label: "Background",
      required: false,
    }),
  ],
  context_entries: [],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const defaultProps = {
  novelId: "novel-1",
  entityType: "character" as const,
  onComplete: vi.fn(),
  onCancel: vi.fn(),
};

// ---------------------------------------------------------------------------
// Test helpers
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
// Tests — Session Actions
// ---------------------------------------------------------------------------

describe("KBAssistedCreationPanel — Session Actions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockHooks.createSession = {
      mutate: vi.fn(
        (_entityType: string, options?: { onSuccess?: (s: typeof mockSessionData) => void }) => {
          options?.onSuccess?.(mockSessionData);
        },
      ),
      isPending: false,
      isError: false,
      error: null,
    };
    mockHooks.session = { data: mockSessionData, isLoading: false };
    mockHooks.completeSession = { mutate: vi.fn(), isPending: false };
    mockHooks.abandonSession = { mutate: vi.fn(), isPending: false };
    mockHooks.answerField = { mutate: vi.fn() };
    mockHooks.suggestField = { mutate: vi.fn(), isPending: false };
    mockHooks.interview = { mutate: vi.fn(), isPending: false };
    mockHooks.enhance = { mutate: vi.fn(), isPending: false };
  });

  afterEach(() => {
    cleanup();
  });

  it("'Abandon' button shows confirm dialog on first click", async () => {
    renderWithProviders(<KBAssistedCreationPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("kb.abandon")).toBeDefined();
    });

    fireEvent.click(screen.getByText("kb.abandon"));

    // ConfirmDialog renders with title and confirm action label
    expect(screen.getByText("kb.interview.cancelConfirmTitle")).toBeDefined();
    expect(screen.getByText("kb.interview.cancelConfirmAction")).toBeDefined();
  });

  it("'Cancel' in abandon confirm returns to normal state", async () => {
    renderWithProviders(<KBAssistedCreationPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("kb.abandon")).toBeDefined();
    });

    fireEvent.click(screen.getByText("kb.abandon"));
    expect(screen.getByText("kb.interview.cancelConfirmTitle")).toBeDefined();

    // Cancel button in confirm dialog uses common.cancel → renders as "cancel"
    const cancelButtons = screen.getAllByText("cancel");
    const dialogCancel = cancelButtons.find(
      (btn) => btn.closest('[class*="absolute"]') !== null || btn.closest("button") !== null,
    );
    if (dialogCancel) {
      fireEvent.click(dialogCancel);
    }

    await waitFor(() => {
      expect(screen.queryByText("kb.interview.cancelConfirmTitle")).toBeNull();
    });
  });

  it("confirmed abandon calls onCancel", async () => {
    const onCancel = vi.fn();
    mockHooks.abandonSession = {
      mutate: vi.fn((_args: unknown, options?: { onSuccess?: () => void }) => {
        options?.onSuccess?.();
      }),
      isPending: false,
    };

    renderWithProviders(<KBAssistedCreationPanel {...defaultProps} onCancel={onCancel} />);

    await waitFor(() => {
      expect(screen.getByText("kb.abandon")).toBeDefined();
    });

    fireEvent.click(screen.getByText("kb.abandon"));
    expect(screen.getByText("kb.interview.cancelConfirmTitle")).toBeDefined();

    // Confirm button uses the confirmLabel: kb.interview.cancelConfirmAction
    fireEvent.click(screen.getByText("kb.interview.cancelConfirmAction"));

    await waitFor(() => {
      expect(onCancel).toHaveBeenCalledTimes(1);
    });
  });

  it("'Complete & Save' completes session", async () => {
    const onComplete = vi.fn();
    const testEntryId = "kb-entry-test-123";
    mockHooks.completeSession = {
      mutate: vi.fn(
        (_args: unknown, options?: { onSuccess?: (data: { entry_id: string }) => void }) => {
          options?.onSuccess?.({ entry_id: testEntryId });
        },
      ),
      isPending: false,
    };

    renderWithProviders(<KBAssistedCreationPanel {...defaultProps} onComplete={onComplete} />);

    await waitFor(() => {
      expect(screen.getByText("kb.completeAndSave")).toBeDefined();
    });

    const nameInput = screen.getByLabelText("kb.entry_name") as HTMLInputElement;
    fireEvent.change(nameInput, { target: { value: "Test Character Name" } });

    fireEvent.click(screen.getByText("kb.completeAndSave"));

    await waitFor(() => {
      expect(onComplete).toHaveBeenCalledTimes(1);
      expect(onComplete).toHaveBeenCalledWith(testEntryId);
    });
  });

  it("'Complete & Save' is disabled when no fields filled", async () => {
    mockHooks.session = {
      data: {
        ...mockSessionData,
        fields: [mockField()],
      },
      isLoading: false,
    };

    renderWithProviders(<KBAssistedCreationPanel {...defaultProps} />);

    await waitFor(() => {
      const completeButton = screen.getByText("kb.completeAndSave").closest("button");
      expect(completeButton?.disabled).toBe(true);
    });
  });

  it("handles cancel by calling onCancel", async () => {
    const onCancel = vi.fn();
    renderWithProviders(<KBAssistedCreationPanel {...defaultProps} onCancel={onCancel} />);

    await waitFor(() => {
      expect(screen.getByText("kb.aiAssistedCreation")).toBeDefined();
    });

    const cancelButtons = screen.getAllByText("kb.cancel");
    const footerCancel = cancelButtons[cancelButtons.length - 1];
    fireEvent.click(footerCancel);

    expect(onCancel).toHaveBeenCalled();
  });

  it("shows confirm dialog when abandon is clicked", async () => {
    renderWithProviders(<KBAssistedCreationPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("kb.abandon")).toBeDefined();
    });

    fireEvent.click(screen.getByText("kb.abandon"));

    // ConfirmDialog opens with title and confirm action
    await waitFor(() => {
      expect(screen.getByText("kb.interview.cancelConfirmTitle")).toBeDefined();
    });
    expect(screen.getByText("kb.interview.cancelConfirmAction")).toBeDefined();
  });
});
