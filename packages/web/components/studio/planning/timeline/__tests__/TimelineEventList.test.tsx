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
