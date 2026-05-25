/**
 * KBAssistedCreationPanel tests — View navigation.
 *
 * Tests switching between views:
 * - Interview view (Start Interview button)
 * - Enhance view (Enhance All button)
 * - Back navigation from interview/enhance to field list
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
// Tests — View Navigation
// ---------------------------------------------------------------------------

describe("KBAssistedCreationPanel — View Navigation", () => {
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

  it("'Start Interview' switches to interview view", async () => {
    renderWithProviders(<KBAssistedCreationPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("kb.aiAssistedCreation")).toBeDefined();
    });

    const interviewButtons = screen.getAllByText("kb.startInterview");
    fireEvent.click(interviewButtons[0]);

    await waitFor(() => {
      expect(screen.getByTestId("interview-view")).toBeDefined();
    });
  });

  it("footer 'Start Interview' switches to interview view", async () => {
    renderWithProviders(<KBAssistedCreationPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("kb.aiAssistedCreation")).toBeDefined();
    });

    const interviewButtons = screen.getAllByText("kb.startInterview");
    fireEvent.click(interviewButtons[interviewButtons.length - 1]);

    await waitFor(() => {
      expect(screen.getByTestId("interview-view")).toBeDefined();
    });
  });

  it("'Enhance All' switches to enhance view", async () => {
    renderWithProviders(<KBAssistedCreationPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("kb.aiAssistedCreation")).toBeDefined();
    });

    const enhanceButtons = screen.getAllByText("kb.enhanceAll");
    fireEvent.click(enhanceButtons[0]);

    await waitFor(() => {
      expect(screen.getByTestId("enhance-view")).toBeDefined();
    });
  });

  it("'Back' from interview returns to field list", async () => {
    renderWithProviders(<KBAssistedCreationPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("kb.aiAssistedCreation")).toBeDefined();
    });

    const interviewButtons = screen.getAllByText("kb.startInterview");
    fireEvent.click(interviewButtons[0]);

    await waitFor(() => {
      expect(screen.getByTestId("interview-view")).toBeDefined();
    });

    fireEvent.click(screen.getByTestId("interview-back"));

    await waitFor(() => {
      expect(screen.getByText("kb.aiAssistedCreation")).toBeDefined();
    });
  });

  it("'Back' from enhance returns to field list", async () => {
    renderWithProviders(<KBAssistedCreationPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("kb.aiAssistedCreation")).toBeDefined();
    });

    const enhanceButtons = screen.getAllByText("kb.enhanceAll");
    fireEvent.click(enhanceButtons[enhanceButtons.length - 1]);

    await waitFor(() => {
      expect(screen.getByTestId("enhance-view")).toBeDefined();
    });

    fireEvent.click(screen.getByTestId("enhance-back"));

    await waitFor(() => {
      expect(screen.getByText("kb.aiAssistedCreation")).toBeDefined();
    });
  });
});
