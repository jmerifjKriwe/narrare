import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TimelineExtractionReview } from "@/components/studio/planning/timeline/TimelineExtractionReview";
import type { ExtractedEvent } from "@/types/timeline";

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
const mockExtractedEvents: ExtractedEvent[] = [
  {
    id: "ext-1",
    expression: "three days later",
    event_name: "Arrival at the castle",
    timestamp_raw: "Day 4",
    chapter_reference: "Chapter 2",
    character_names: ["Aragorn", "Legolas"],
    location_name: "Minas Tirith",
    confidence: 0.8,
    context: "...three days later they arrived at the castle gates.",
  },
  {
    id: "ext-2",
    expression: "that summer",
    event_name: "The great feast",
    timestamp_raw: "Summer, Year 2",
    chapter_reference: "Chapter 3",
    character_names: ["Frodo"],
    location_name: "The Shire",
    confidence: 0.6,
    context: "That summer they held a great feast in the meadow.",
  },
];

// SSE extraction hook mock state
let mockIsExtracting = false;
let mockExtractedEventsState: ExtractedEvent[] = [];
let mockExtractError: { userMessage: string } | null = null;
const mockStartExtraction = vi.fn();
const mockResetExtraction = vi.fn();
const mockCancelExtraction = vi.fn();

// Confirm mutation mock state
const mockConfirmMutate = vi.fn();
let mockConfirmIsPending = false;

vi.mock("@/lib/hooks/useTimeline", () => ({
  useSSEExtraction: () => ({
    isExtracting: mockIsExtracting,
    extractedEvents: mockExtractedEventsState,
    extractError: mockExtractError,
    startExtraction: mockStartExtraction,
    cancelExtraction: mockCancelExtraction,
    reset: mockResetExtraction,
  }),
  useConfirmExtractedEvent: () => ({
    mutate: mockConfirmMutate,
    isPending: mockConfirmIsPending,
  }),
}));

// Mock chapters API
vi.mock("@/lib/api/client", () => ({
  chaptersApi: {
    list: vi.fn().mockResolvedValue([
      { id: "ch-1", title: "Chapter 1" },
      { id: "ch-2", title: "Chapter 2" },
      { id: "ch-3", title: "Chapter 3" },
    ]),
  },
}));

describe("TimelineExtractionReview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsExtracting = false;
    mockExtractedEventsState = [];
    mockExtractError = null;
    mockConfirmIsPending = false;
  });

  it("renders extraction review with title", async () => {
    render(<TimelineExtractionReview novelId="novel-1" />);
    expect(screen.getByText("extractTitle")).toBeDefined();
  });

  it("shows chapter selection after loading chapters", async () => {
    render(<TimelineExtractionReview novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText("Chapter 1")).toBeDefined();
      expect(screen.getByText("Chapter 2")).toBeDefined();
      expect(screen.getByText("Chapter 3")).toBeDefined();
    });
  });

  it("disables extract button when no chapters are selected", async () => {
    render(<TimelineExtractionReview novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText("Chapter 1")).toBeDefined();
    });

    const extractButton = screen.getByText("extractButton");
    expect(extractButton.closest("button")?.disabled).toBe(true);
  });

  it("enables extract button when chapters are selected", async () => {
    render(<TimelineExtractionReview novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText("Chapter 1")).toBeDefined();
    });

    fireEvent.click(screen.getByText("Chapter 1"));
    const extractButton = screen.getByText("extractButton");
    expect(extractButton.closest("button")?.disabled).toBe(false);
  });

  it("triggers SSE extraction on extract click", async () => {
    render(<TimelineExtractionReview novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText("Chapter 1")).toBeDefined();
    });

    // Select a chapter
    fireEvent.click(screen.getByText("Chapter 1"));

    // Click extract
    fireEvent.click(screen.getByText("extractButton"));

    expect(mockStartExtraction).toHaveBeenCalledWith(["ch-1"]);
  });

  it("shows loading state while extracting", async () => {
    mockIsExtracting = true;
    render(<TimelineExtractionReview novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText("extracting")).toBeDefined();
    });
  });

  it("shows a visible stop button while extracting (CR-AUFG-07-09 §16.2)", async () => {
    mockIsExtracting = true;
    render(<TimelineExtractionReview novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText("extracting")).toBeDefined();
    });

    // The cancel button is visible during extraction
    const stopButton = screen.getByTestId("timeline-extract-stop");
    expect(stopButton).toBeDefined();
  });

  it("calls cancelExtraction when stop button is clicked during extraction", async () => {
    mockIsExtracting = true;
    render(<TimelineExtractionReview novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByTestId("timeline-extract-stop")).toBeDefined();
    });

    fireEvent.click(screen.getByTestId("timeline-extract-stop"));

    expect(mockCancelExtraction).toHaveBeenCalledTimes(1);
  });

  it("does NOT show a stop button when not extracting", async () => {
    mockIsExtracting = false;
    render(<TimelineExtractionReview novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText("Chapter 1")).toBeDefined();
    });

    expect(screen.queryByTestId("timeline-extract-stop")).toBeNull();
  });

  it("shows spinner when extracting with no events yet", async () => {
    mockIsExtracting = true;
    mockExtractedEventsState = [];
    render(<TimelineExtractionReview novelId="novel-1" />);

    // Should show the spinner (Loader2 is in the DOM)
    await waitFor(() => {
      expect(screen.getByText("extracting")).toBeDefined();
    });
  });

  it("shows extraction count during SSE streaming", async () => {
    mockIsExtracting = true;
    mockExtractedEventsState = [mockExtractedEvents[0]];
    render(<TimelineExtractionReview novelId="novel-1" />);

    // The extractedCount key uses {count} parameter
    await waitFor(() => {
      expect(screen.getByText("extractedCount")).toBeDefined();
    });
  });

  it("shows error state when extraction fails", async () => {
    mockExtractError = { userMessage: "Failed to extract temporal expressions." };
    render(<TimelineExtractionReview novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText("Failed to extract temporal expressions.")).toBeDefined();
    });
  });

  it("shows empty state when no extractions found", () => {
    render(<TimelineExtractionReview novelId="novel-1" />);
    expect(screen.getByText("noExtractions")).toBeDefined();
  });

  it("renders extracted events with accept/reject buttons", async () => {
    // Populate extracted events directly (simulates SSE progressive arrival)
    mockExtractedEventsState = mockExtractedEvents;
    render(<TimelineExtractionReview novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText(/Chapter 1/)).toBeDefined();
    });

    // Check extracted events are rendered
    await waitFor(() => {
      expect(screen.getAllByText(/three days later/).length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(/Arrival at the castle/)).toBeDefined();
      expect(screen.getByText("Aragorn")).toBeDefined();
      expect(screen.getByText("Legolas")).toBeDefined();
    });

    // Accept/reject buttons should be visible
    const acceptButtons = screen.getAllByText("accept");
    const rejectButtons = screen.getAllByText("reject");
    expect(acceptButtons.length).toBe(2);
    expect(rejectButtons.length).toBe(2);
  });

  it("accepts an extracted event via confirm endpoint", async () => {
    mockExtractedEventsState = mockExtractedEvents;
    render(<TimelineExtractionReview novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText(/Chapter 1/)).toBeDefined();
    });

    await waitFor(() => {
      expect(screen.getAllByText("accept").length).toBe(2);
    });

    // Accept first event
    const acceptButtons = screen.getAllByText("accept");
    fireEvent.click(acceptButtons[0]);

    // Should call confirm mutation with the full ExtractedEvent
    expect(mockConfirmMutate).toHaveBeenCalledWith(mockExtractedEvents[0]);
  });

  it("rejects an extracted event", async () => {
    mockExtractedEventsState = mockExtractedEvents;
    render(<TimelineExtractionReview novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText(/Chapter 1/)).toBeDefined();
    });

    await waitFor(() => {
      expect(screen.getAllByText("reject").length).toBe(2);
    });

    // Reject first event
    const rejectButtons = screen.getAllByText("reject");
    fireEvent.click(rejectButtons[0]);

    // Should show "rejected" label
    await waitFor(() => {
      expect(screen.getByText("rejected")).toBeDefined();
    });
  });

  it("shows onClose button when onClose is provided", () => {
    const onClose = vi.fn();
    render(<TimelineExtractionReview novelId="novel-1" onClose={onClose} />);

    const closeButton = screen.getByLabelText("close");
    expect(closeButton).toBeDefined();

    fireEvent.click(closeButton);
    expect(onClose).toHaveBeenCalledOnce();
  });
});
