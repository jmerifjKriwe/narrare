import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
});
