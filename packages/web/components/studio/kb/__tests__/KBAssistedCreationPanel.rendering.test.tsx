/**
 * KBAssistedCreationPanel tests — Rendering & state display.
 *
 * Tests the panel's visual states:
 * - Loading state during session creation
 * - Field list after successful creation
 * - Session status badge
 * - Error state on creation failure
 * - Progress bar display
 * - Entity type icon rendering
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { KBAssistedCreationPanel } from "@/components/studio/kb/KBAssistedCreationPanel";

// ---------------------------------------------------------------------------
// Mocks — hook layer
// ---------------------------------------------------------------------------

// Create mutable state objects that the mock will reference.
// We update these before each test to control hook behavior.
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

// Also mock sub-components to isolate panel logic
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
// Tests — Rendering & State
// ---------------------------------------------------------------------------

describe("KBAssistedCreationPanel — Rendering & State", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset mock state to default (loading → will resolve to session data)
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

  it("shows loading state while creating session", () => {
    // Make session loading (no data yet, create not called)
    mockHooks.session = { data: null, isLoading: true };
    // Keep create as pending
    mockHooks.createSession = {
      mutate: vi.fn(),
      isPending: true,
      isError: false,
      error: null,
    };

    renderWithProviders(<KBAssistedCreationPanel {...defaultProps} />);

    // Should show the loading state with creating session text
    expect(screen.getByText("kb.sessionCreating")).toBeDefined();
  });

  it("shows field list after session created", async () => {
    renderWithProviders(<KBAssistedCreationPanel {...defaultProps} />);

    // Should show the field list with AI-Assisted Creation title
    await waitFor(() => {
      expect(screen.getByText("kb.aiAssistedCreation")).toBeDefined();
    });

    // Should show entity type
    await waitFor(() => {
      expect(screen.getByText("kb.characters")).toBeDefined();
    });
  });

  it("shows session status badge", async () => {
    renderWithProviders(<KBAssistedCreationPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("kb.statusActive")).toBeDefined();
    });
  });

  it("shows 'Complete & Save' button after session loaded", async () => {
    renderWithProviders(<KBAssistedCreationPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("kb.completeAndSave")).toBeDefined();
    });
  });

  it("shows error state on creation failure", async () => {
    mockHooks.createSession = {
      mutate: vi.fn(),
      isPending: false,
      isError: true,
      error: new Error("Failed to create session"),
    };
    mockHooks.session = { data: null, isLoading: false };

    renderWithProviders(<KBAssistedCreationPanel {...defaultProps} />);

    await waitFor(() => {
      // Error is mapped via mapSSEError → AIErrorResponse with German fallback
      expect(
        screen.getByText("Verbindung verloren. Prüfe deine Internetverbindung."),
      ).toBeDefined();
    });

    // Cancel button should be visible in error state
    expect(screen.getByText("kb.cancel")).toBeDefined();
  });

  it("'Cancel' button in error state calls onCancel", async () => {
    const onCancel = vi.fn();
    mockHooks.createSession = {
      mutate: vi.fn(),
      isPending: false,
      isError: true,
      error: new Error("Creation failed"),
    };
    mockHooks.session = { data: null, isLoading: false };

    renderWithProviders(<KBAssistedCreationPanel {...defaultProps} onCancel={onCancel} />);

    await waitFor(() => {
      expect(
        screen.getByText("Verbindung verloren. Prüfe deine Internetverbindung."),
      ).toBeDefined();
    });

    fireEvent.click(screen.getByText("kb.cancel"));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("shows progress bar in field list view", async () => {
    renderWithProviders(<KBAssistedCreationPanel {...defaultProps} />);

    await waitFor(() => {
      // Progress text appears in both header and field list
      const progressTexts = screen.getAllByText("kb.sessionProgress");
      expect(progressTexts.length).toBeGreaterThan(0);
    });

    // Progress bar should render (purple progress div)
    const barElements = document.querySelectorAll(".bg-purple-500");
    expect(barElements.length).toBeGreaterThan(0);
  });

  it("renders entity icon for different entity types", async () => {
    renderWithProviders(<KBAssistedCreationPanel {...defaultProps} entityType="location" />);

    await waitFor(() => {
      expect(screen.getByText("kb.aiAssistedCreation")).toBeDefined();
    });

    await waitFor(() => {
      expect(screen.getByText("kb.locations")).toBeDefined();
    });
  });
});
