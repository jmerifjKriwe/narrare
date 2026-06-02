import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TimelineEventList } from "@/components/studio/planning/timeline/TimelineEventList";

// Mock next-intl
vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
  useLocale: () => "en",
}));

// Mock hooks at module level (hoisted)
vi.mock("@/lib/hooks/useTimeline", () => ({
  useTimelineEvents: () => ({
    data: [],
    isLoading: false,
    error: null,
  }),
  useCreateTimelineEvent: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteTimelineEvent: () => ({ mutate: vi.fn(), isPending: false }),
  useSSEExtraction: () => ({
    isExtracting: false,
    extractedEvents: [],
    extractError: null,
    startExtraction: vi.fn(),
    reset: vi.fn(),
  }),
  useConfirmExtractedEvent: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
  useTimelineExtraction: () => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    data: undefined,
    reset: vi.fn(),
  }),
  useUpdateTimelineEvent: () => ({
    mutate: vi.fn(),
    isPending: false,
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
  useTimelineEvent: () => ({
    data: null,
    isLoading: false,
    error: null,
  }),
  useCharacterAges: () => ({
    data: null,
    isLoading: false,
    error: null,
  }),
}));

describe("TimelineEventList", () => {
  it("renders event list with add event button", () => {
    render(<TimelineEventList novelId="novel-1" />);
    expect(screen.getByText("addEvent")).toBeDefined();
  });

  it("shows empty state when no events", () => {
    render(<TimelineEventList novelId="novel-1" />);
    expect(screen.getByText("noEvents")).toBeDefined();
  });

  it("renders filter controls", () => {
    render(<TimelineEventList novelId="novel-1" />);
    expect(screen.getByLabelText("filterByType")).toBeDefined();
    expect(screen.getByLabelText("filterBySource")).toBeDefined();
  });

  it("shows add event button", () => {
    render(<TimelineEventList novelId="novel-1" />);
    expect(screen.getByText("addEvent")).toBeDefined();
  });
});
