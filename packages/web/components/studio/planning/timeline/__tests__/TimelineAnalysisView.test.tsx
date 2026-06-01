import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TimelineAnalysisView } from "@/components/studio/planning/timeline/TimelineAnalysisView";

// Mock next-intl
vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
  useLocale: () => "en",
}));

// Default mock — returns null data (empty state)
const mockRefetch = vi.fn();
let mockAnalysisData: unknown = null;
let mockIsLoading = false;
let mockError: Error | null = null;

vi.mock("@/lib/hooks/useTimeline", () => ({
  useTimelineAnalysis: () => ({
    data: mockAnalysisData,
    isLoading: mockIsLoading,
    error: mockError,
    refetch: mockRefetch,
  }),
}));

describe("TimelineAnalysisView", () => {
  it("renders with no analysis data", () => {
    mockAnalysisData = null;
    mockIsLoading = false;
    mockError = null;

    render(<TimelineAnalysisView novelId="novel-1" />);
    expect(screen.getByText("noAnalysis")).toBeDefined();
  });

  it("shows loading state", () => {
    mockAnalysisData = null;
    mockIsLoading = true;
    mockError = null;

    render(<TimelineAnalysisView novelId="novel-1" />);
    expect(screen.getByText("runningAnalysis")).toBeDefined();
  });

  it("shows error state", () => {
    mockAnalysisData = null;
    mockIsLoading = false;
    mockError = new Error("Failed");

    render(<TimelineAnalysisView novelId="novel-1" />);
    expect(screen.getByText("errorAnalysis")).toBeDefined();
  });

  it("renders analysis results with conflicts and gaps", () => {
    mockAnalysisData = {
      timeline_events: [
        {
          event_name: "The Council of Elrond",
          description: "A council to decide the fate of the Ring.",
          timestamp: "Year 3018, October",
          chapter_reference: "Chapter 2",
          characters_involved: ["Frodo", "Gandalf"],
          location: "Rivendell",
          causes: ["The discovery of the Ring"],
          consequences: ["The Fellowship is formed"],
        },
      ],
      temporal_conflicts: ["Timeline conflict detected"],
      coverage_gaps: ["Gap between chapters"],
      overall_assessment: "Mostly consistent.",
    };
    mockIsLoading = false;
    mockError = null;

    render(<TimelineAnalysisView novelId="novel-1" />);
    expect(screen.getByText("The Council of Elrond")).toBeDefined();
    expect(screen.getByText("Timeline conflict detected")).toBeDefined();
    expect(screen.getByText("Gap between chapters")).toBeDefined();
    expect(screen.getByText("Mostly consistent.")).toBeDefined();
  });
});
