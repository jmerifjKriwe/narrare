import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TimelineConsistencyPanel } from "@/components/studio/planning/timeline/TimelineConsistencyPanel";
import type { TemporalConsistency } from "@/types/timeline";

// Mock next-intl
vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) => {
    if (params) {
      return Object.entries(params).reduce((acc, [k, v]) => acc.replace(`{${k}}`, String(v)), key);
    }
    return key;
  },
  useLocale: () => "en",
}));

// Mock data
const mockConsistencyData: TemporalConsistency = {
  issues: [
    {
      severity: "error",
      rule_id: "ordering_violation",
      event_ids: ["evt-1", "evt-2"],
      description: "The battle is listed before the arrival, but the arrival causes the battle.",
      suggestion: "Swap temporal_order.",
      source: "deterministic",
    },
    {
      severity: "warning",
      rule_id: "duplicate_events",
      event_ids: ["evt-3", "evt-4"],
      description: "Both events have same timestamp and chapter.",
      suggestion: "Review and merge.",
      source: "deterministic",
    },
    {
      severity: "info",
      rule_id: "gap_detected",
      event_ids: ["evt-5"],
      description: "A gap of 5 years between events.",
      suggestion: "Consider adding bridging events.",
      source: "llm",
    },
  ],
  deterministic_pass: false,
  overall_assessment: "2 warnings found",
};

const mockRefetch = vi.fn();
let mockConsistency: TemporalConsistency | null = null;
let mockIsLoading = false;
let mockError: Error | null = null;

vi.mock("@/lib/hooks/useTimeline", () => ({
  useTimelineConsistency: () => ({
    data: mockConsistency,
    isLoading: mockIsLoading,
    error: mockError,
    refetch: mockRefetch,
  }),
}));

describe("TimelineConsistencyPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockConsistency = null;
    mockIsLoading = false;
    mockError = null;
  });

  it("renders with no consistency data (empty state)", () => {
    mockConsistency = null;
    render(<TimelineConsistencyPanel novelId="novel-1" />);
    expect(screen.getByText("noIssues")).toBeDefined();
  });

  it("shows loading state", () => {
    mockIsLoading = true;
    render(<TimelineConsistencyPanel novelId="novel-1" />);
    expect(screen.getByText("checking")).toBeDefined();
  });

  it("shows error state", () => {
    mockError = new Error("Failed");
    render(<TimelineConsistencyPanel novelId="novel-1" />);
    expect(screen.getByText("errorConsistency")).toBeDefined();
  });

  it("shows recheck button in error state", () => {
    mockError = new Error("Failed");
    render(<TimelineConsistencyPanel novelId="novel-1" />);

    const recheckButtons = screen.getAllByText("recheck");
    fireEvent.click(recheckButtons[0]);
    expect(mockRefetch).toHaveBeenCalledOnce();
  });

  it("shows no issues when consistency has no issues", () => {
    mockConsistency = {
      issues: [],
      deterministic_pass: true,
      overall_assessment: "All clear",
    };
    render(<TimelineConsistencyPanel novelId="novel-1" />);
    // Two instances of noIssues: the assessment + the fallback empty state
    const noIssuesTexts = screen.getAllByText("noIssues");
    expect(noIssuesTexts.length).toBeGreaterThanOrEqual(1);
  });

  it("shows issues grouped by severity (errors first)", () => {
    mockConsistency = mockConsistencyData;
    render(<TimelineConsistencyPanel novelId="novel-1" />);

    // Error issue
    expect(screen.getByText("error")).toBeDefined();
    expect(screen.getByText(/battle is listed before/)).toBeDefined();

    // Warning issue
    expect(screen.getByText("warning")).toBeDefined();
    expect(screen.getByText(/same timestamp and chapter/)).toBeDefined();

    // Info issue
    expect(screen.getByText("info")).toBeDefined();
    expect(screen.getByText(/gap of 5 years/)).toBeDefined();
  });

  it("shows error count and warning count in header", () => {
    mockConsistency = mockConsistencyData;
    render(<TimelineConsistencyPanel novelId="novel-1" />);

    // The mock useTranslations returns keys, not interpolated strings.
    // Both hasErrors and hasWarnings are rendered in the same <span>.
    const headerSpan = screen.getByText("hasErrors", { exact: false });
    expect(headerSpan.textContent).toContain("hasErrors");
    expect(headerSpan.textContent).toContain("hasWarnings");
  });

  it("shows rule ID and source badge for each issue", () => {
    mockConsistency = mockConsistencyData;
    render(<TimelineConsistencyPanel novelId="novel-1" />);

    // Rule IDs
    expect(screen.getByText(/ordering_violation/)).toBeDefined();
    expect(screen.getByText(/duplicate_events/)).toBeDefined();

    // Source badges
    expect(screen.getAllByText("sourceDeterministic").length).toBe(2);
    expect(screen.getByText("sourceLlm")).toBeDefined();
  });

  it("shows suggestion for each issue", () => {
    mockConsistency = mockConsistencyData;
    render(<TimelineConsistencyPanel novelId="novel-1" />);

    // Suggestions
    expect(screen.getByText(/Swap temporal_order/)).toBeDefined();
    expect(screen.getByText(/Review and merge/)).toBeDefined();
    expect(screen.getByText(/Consider adding bridging events/)).toBeDefined();
  });

  it("shows affected event IDs for each issue", () => {
    mockConsistency = mockConsistencyData;
    render(<TimelineConsistencyPanel novelId="novel-1" />);

    // Event IDs displayed as pills
    expect(screen.getByText("evt-1")).toBeDefined();
    expect(screen.getByText("evt-2")).toBeDefined();
    expect(screen.getByText("evt-3")).toBeDefined();
  });

  it("recheck button triggers refetch", () => {
    mockConsistency = mockConsistencyData;
    render(<TimelineConsistencyPanel novelId="novel-1" />);

    const recheckButtons = screen.getAllByText("recheck");
    // Last one is the re-check button at bottom
    fireEvent.click(recheckButtons[recheckButtons.length - 1]);
    expect(mockRefetch).toHaveBeenCalledOnce();
  });

  it("handles empty issues array", () => {
    mockConsistency = {
      issues: [],
      deterministic_pass: true,
      overall_assessment: "No issues",
    };
    render(<TimelineConsistencyPanel novelId="novel-1" />);

    // Should not show any issue cards
    expect(screen.queryByText("affectedEvents")).toBeNull();
  });
});
