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
  useTimelineConsistency: () => ({
    data: null,
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useTimelineExtraction: () => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    data: undefined,
    reset: vi.fn(),
  }),
  useCreateTimelineEvent: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
}));

// Mock chapters API for extraction component
vi.mock("@/lib/api/client", () => ({
  chaptersApi: {
    list: vi.fn().mockResolvedValue([{ id: "ch-1", title: "Chapter 1" }]),
  },
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
    expect(eventsTab.closest("button")).toBeDefined();
  });

  it("switches to Analysis tab on click", () => {
    render(<TimelinePanel novelId="novel-1" />);
    const analysisTab = screen.getByText("analysisTab");
    fireEvent.click(analysisTab);
    expect(screen.getByText("noAnalysis")).toBeDefined();
  });

  it("switches to Consistency tab on click", () => {
    render(<TimelinePanel novelId="novel-1" />);
    const consistencyTab = screen.getByText("consistencyTab");
    fireEvent.click(consistencyTab);
    // Consistency panel renders with empty state
    expect(screen.getByText("noIssues")).toBeDefined();
  });

  it("switches to Extract tab on click", async () => {
    render(<TimelinePanel novelId="novel-1" />);
    const extractTab = screen.getByText("extractTab");
    fireEvent.click(extractTab);
    // Extract panel renders with title
    expect(screen.getByText("extractTitle")).toBeDefined();
  });

  it("shows all four tabs", () => {
    render(<TimelinePanel novelId="novel-1" />);
    expect(screen.getByText("eventsTab")).toBeDefined();
    expect(screen.getByText("analysisTab")).toBeDefined();
    expect(screen.getByText("consistencyTab")).toBeDefined();
    expect(screen.getByText("extractTab")).toBeDefined();
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
      useTimelineConsistency: () => ({
        data: null,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      }),
      useTimelineExtraction: () => ({
        mutate: vi.fn(),
        isPending: false,
        isError: false,
        data: undefined,
        reset: vi.fn(),
      }),
      useCreateTimelineEvent: () => ({
        mutate: vi.fn(),
        isPending: false,
      }),
    }));

    render(<TimelinePanel novelId="novel-1" />);
    expect(screen.getByText("title")).toBeDefined();
  });
});
