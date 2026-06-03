import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TimelineEventForm } from "@/components/studio/planning/timeline/TimelineEventForm";

// Mock next-intl
vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
  useLocale: () => "en",
}));

// Mock hooks
const mockCreateMutation = { mutate: vi.fn(), isPending: false };
const mockUpdateMutation = { mutate: vi.fn(), isPending: false };

vi.mock("@/lib/hooks/useTimeline", () => ({
  useCreateTimelineEvent: () => mockCreateMutation,
  useUpdateTimelineEvent: () => mockUpdateMutation,
  useTimelineEvents: () => ({
    data: [],
    isLoading: false,
    error: null,
  }),
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

describe("TimelineEventForm", () => {
  it("renders create form", () => {
    const onClose = vi.fn();
    render(<TimelineEventForm novelId="novel-1" eventId={null} onClose={onClose} />);
    expect(screen.getByText("addEvent")).toBeDefined();
    expect(screen.getByLabelText("eventName *")).toBeDefined();
  });

  it("renders edit form when eventId is provided", () => {
    const onClose = vi.fn();
    render(<TimelineEventForm novelId="novel-1" eventId="evt-1" onClose={onClose} />);
    expect(screen.getByText("editEvent")).toBeDefined();
  });

  it("validates required fields", () => {
    const onClose = vi.fn();
    render(<TimelineEventForm novelId="novel-1" eventId={null} onClose={onClose} />);
    const submitButton = screen.getByText("create");
    fireEvent.click(submitButton);
    // Should show validation error
    expect(screen.getByText("eventNameRequired")).toBeDefined();
  });

  it("calls onClose when cancel is clicked", () => {
    const onClose = vi.fn();
    render(<TimelineEventForm novelId="novel-1" eventId={null} onClose={onClose} />);
    const cancelButton = screen.getByText("cancel");
    fireEvent.click(cancelButton);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("renders all form fields", () => {
    const onClose = vi.fn();
    render(<TimelineEventForm novelId="novel-1" eventId={null} onClose={onClose} />);
    expect(screen.getByLabelText("description")).toBeDefined();
    expect(screen.getByLabelText("eventType")).toBeDefined();
    expect(screen.getByLabelText("timestamp")).toBeDefined();
    expect(screen.getByLabelText("temporalOrder")).toBeDefined();
    expect(screen.getByLabelText("causes")).toBeDefined();
    expect(screen.getByLabelText("consequences")).toBeDefined();
  });
});
