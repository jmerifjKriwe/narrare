import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Mock the hooks before importing the component
const mockUsePreferences = vi.fn();
const mockUseResetPreferences = vi.fn();
const mockUseTriggerAnalysis = vi.fn();

vi.mock("@/lib/hooks/useMemory", () => ({
  usePreferences: () => mockUsePreferences(),
  useResetPreferences: () => mockUseResetPreferences(),
  useTriggerAnalysis: () => mockUseTriggerAnalysis(),
}));

// AdaptiveDashboard (now mounted inside LearningTab) uses real TanStack Query
// hooks. Stub them here so the dashboard renders without a QueryClientProvider.
// The dashboard itself is covered by AdaptiveDashboard.test.tsx (MSW + provider).
vi.mock("@/lib/hooks/useAdaptiveContext", () => ({
  useAdaptiveContext: () => ({
    data: {
      project_id: "novel-1",
      enabled: false,
      weights: { preference: 0, voice_fidelity: 0, style_constraints: 0, avoidance: 0 },
      sources: {
        preference_text: "",
        voice_profiles_text: "",
        style_constraints_text: "",
        avoidance_patterns_text: "",
      },
      has_any_signal: false,
    },
    isLoading: false,
    error: null,
  }),
  useToggleAdaptive: () => ({ mutate: vi.fn(), isPending: false }),
  useSetAdaptiveWeights: () => ({ mutate: vi.fn(), isPending: false }),
  adaptiveKeys: {
    all: ["adaptive-context"],
    context: (id: string) => ["adaptive-context", id],
    snapshots: (id: string) => ["adaptive-context", id, "snapshots"],
  },
}));

// Must import after mock
import { LearningTab } from "@/components/studio/settings/LearningTab";

describe("LearningTab", () => {
  const defaultHookReturn = {
    data: null,
    isLoading: false,
    error: null,
  };

  const defaultResetReturn = {
    mutate: vi.fn(),
    isPending: false,
    error: null,
  };

  const defaultAnalysisReturn = {
    mutate: vi.fn(),
    isPending: false,
    error: null,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockUsePreferences.mockReturnValue(defaultHookReturn);
    mockUseResetPreferences.mockReturnValue(defaultResetReturn);
    mockUseTriggerAnalysis.mockReturnValue(defaultAnalysisReturn);
  });

  it("shows loading state", () => {
    mockUsePreferences.mockReturnValue({ ...defaultHookReturn, isLoading: true });
    render(<LearningTab novelId="novel-1" />);
    expect(screen.getByText("learning.loading")).toBeDefined();
  });

  it("shows title and description", () => {
    render(<LearningTab novelId="novel-1" />);
    expect(screen.getByText("learning.title")).toBeDefined();
    expect(screen.getByText("learning.description")).toBeDefined();
  });

  it("shows no data state when no profile", () => {
    render(<LearningTab novelId="novel-1" />);
    expect(screen.getByText("learning.noData")).toBeDefined();
  });

  it("shows profile when data exists", () => {
    mockUsePreferences.mockReturnValue({
      ...defaultHookReturn,
      data: {
        user_id: "u1",
        project_id: "p1",
        event_count: 10,
        confidence: 0.5,
        style: { tone: "dramatic" },
        content: {},
        constraints: [],
        last_updated: "2026-05-21T00:00:00Z",
      },
    });
    render(<LearningTab novelId="novel-1" />);
    expect(screen.getByText("learning.stylePatterns")).toBeDefined();
  });

  it("shows analyze button", () => {
    render(<LearningTab novelId="novel-1" />);
    expect(screen.getByText("learning.analyze")).toBeDefined();
  });

  it("shows min events hint when < 5 events", () => {
    mockUsePreferences.mockReturnValue({
      ...defaultHookReturn,
      data: {
        user_id: "u1",
        project_id: "p1",
        event_count: 3,
        confidence: 0,
        style: {},
        content: {},
        constraints: [],
        last_updated: "2026-05-21T00:00:00Z",
      },
    });
    render(<LearningTab novelId="novel-1" />);
    expect(screen.getByText("learning.minEventsHint")).toBeDefined();
  });

  it("shows reset button", () => {
    render(<LearningTab novelId="novel-1" />);
    expect(screen.getByText("learning.reset")).toBeDefined();
  });

  it("shows reset confirmation when reset is clicked", () => {
    render(<LearningTab novelId="novel-1" />);
    fireEvent.click(screen.getByText("learning.reset"));
    expect(screen.getByText("learning.resetConfirm")).toBeDefined();
  });

  it("calls reset mutation on confirm", () => {
    const mutate = vi.fn();
    mockUseResetPreferences.mockReturnValue({ ...defaultResetReturn, mutate });
    render(<LearningTab novelId="novel-1" />);
    fireEvent.click(screen.getByText("learning.reset"));
    fireEvent.click(screen.getByText("learning.confirmReset"));
    expect(mutate).toHaveBeenCalledOnce();
  });

  // Regression (CR-07-03): errors must render the canonical mapped message
  // (mapSSEError), never the raw underlying error text which can leak backend
  // details.

  it("renders mapped error message on profile fetch failure, not the raw underlying error", () => {
    mockUsePreferences.mockReturnValue({
      ...defaultHookReturn,
      error: new Error("profile fetch secret 99"),
    });
    render(<LearningTab novelId="novel-1" />);

    // mapSSEError maps a generic Error to the connection error message.
    expect(screen.getByText("Verbindung verloren. Prüfe deine Internetverbindung.")).toBeDefined();
    expect(screen.queryByText(/profile fetch secret 99/)).toBeNull();
  });

  it("renders mapped error message on analysis failure, not the raw underlying error", () => {
    mockUseTriggerAnalysis.mockReturnValue({
      ...defaultAnalysisReturn,
      error: new Error("LLM analysis boom secret"),
    });
    render(<LearningTab novelId="novel-1" />);

    // The canonical mapped message renders (network error → connection msg).
    expect(screen.getByText("Verbindung verloren. Prüfe deine Internetverbindung.")).toBeDefined();
    expect(screen.queryByText(/LLM analysis boom secret/)).toBeNull();
  });

  it("shows a retry control on analysis failure that re-triggers analysis", () => {
    const mutate = vi.fn();
    mockUseTriggerAnalysis.mockReturnValue({
      ...defaultAnalysisReturn,
      mutate,
      // Generic Error → network kind → connectionLostRetry label is shown.
      error: new Error("analysis failed"),
    });
    render(<LearningTab novelId="novel-1" />);

    fireEvent.click(screen.getByText("aiActions.connectionLostRetry"));
    expect(mutate).toHaveBeenCalledOnce();
  });

  it("shows a connection-lost indication on analysis network error", () => {
    mockUseTriggerAnalysis.mockReturnValue({
      ...defaultAnalysisReturn,
      error: new Error("network down"),
    });
    render(<LearningTab novelId="novel-1" />);

    // Connection-lost is indicated by the connectionLostRetry control.
    expect(screen.getByText("aiActions.connectionLostRetry")).toBeDefined();
  });
});
