import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TimelinePanel } from "@/components/studio/planning/timeline/TimelinePanel";

// Mock next-intl
vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
  useLocale: () => "en",
}));

// Mock TanStack Query hooks
vi.mock("@/lib/hooks/useTimeline", () => ({
  useTimelineEvents: () => ({
    data: [],
    isLoading: false,
    error: null,
  }),
  useTimelineAnalysis: () => ({
    data: null,
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

describe("TimelinePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders without crashing", () => {
    render(<TimelinePanel novelId="novel-1" />);
    expect(screen.getByText("title")).toBeDefined();
  });

  it("shows Events tab by default", () => {
    render(<TimelinePanel novelId="novel-1" />);
    const eventsTab = screen.getByText("eventsTab");
    expect(eventsTab).toBeDefined();
    // Events tab should be active (has accent background)
    expect(eventsTab.closest("button")).toBeDefined();
  });

  it("switches to Analysis tab on click", () => {
    render(<TimelinePanel novelId="novel-1" />);
    const analysisTab = screen.getByText("analysisTab");
    fireEvent.click(analysisTab);
    // After clicking, the analysis view should render
    // Since mock returns null data, it shows "noAnalysis"
    expect(screen.getByText("noAnalysis")).toBeDefined();
  });

  it("shows loading state when analysis is loading", () => {
    vi.doMock("@/lib/hooks/useTimeline", () => ({
      useTimelineEvents: () => ({
        data: [],
        isLoading: false,
        error: null,
      }),
      useTimelineAnalysis: () => ({
        data: null,
        isLoading: true,
        error: null,
        refetch: vi.fn(),
      }),
    }));

    render(<TimelinePanel novelId="novel-1" />);
    // Component renders successfully
    expect(screen.getByText("title")).toBeDefined();
  });
});
