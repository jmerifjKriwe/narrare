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

// Mutation mock state
const mockMutate = vi.fn();
let mockIsPending = false;
let mockIsError = false;
const mockCreateMutate = vi.fn();
let mockCreateIsPending = false;

vi.mock("@/lib/hooks/useTimeline", () => ({
  useTimelineExtraction: () => ({
    mutate: mockMutate,
    isPending: mockIsPending,
    isError: mockIsError,
    data: undefined,
    reset: vi.fn(),
  }),
  useCreateTimelineEvent: () => ({
    mutate: mockCreateMutate,
    isPending: mockCreateIsPending,
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
    mockIsPending = false;
    mockIsError = false;
    mockCreateIsPending = false;
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

  it("triggers extraction mutation on extract click", async () => {
    render(<TimelineExtractionReview novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText("Chapter 1")).toBeDefined();
    });

    // Select a chapter
    fireEvent.click(screen.getByText("Chapter 1"));

    // Click extract
    fireEvent.click(screen.getByText("extractButton"));

    expect(mockMutate).toHaveBeenCalledWith(["ch-1"], expect.any(Object));
  });

  it("shows loading state while extracting", async () => {
    mockIsPending = true;
    render(<TimelineExtractionReview novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText("Chapter 1")).toBeDefined();
    });

    // Select and extract
    fireEvent.click(screen.getByText("Chapter 1"));
    fireEvent.click(screen.getByText("extracting"));

    expect(screen.getByText("extracting")).toBeDefined();
  });

  it("shows error state when extraction fails", async () => {
    mockIsError = true;
    render(<TimelineExtractionReview novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText("errorExtract")).toBeDefined();
    });
  });

  it("shows empty state when no extractions found", () => {
    render(<TimelineExtractionReview novelId="novel-1" />);
    expect(screen.getByText("noExtractions")).toBeDefined();
  });

  it("renders extracted events with accept/reject buttons", async () => {
    // Simulate extraction success via onSuccess callback
    mockMutate.mockImplementation((_chapterIds, options) => {
      options?.onSuccess?.(mockExtractedEvents);
    });

    render(<TimelineExtractionReview novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText("Chapter 1")).toBeDefined();
    });

    // Select and extract
    fireEvent.click(screen.getByText("Chapter 1"));
    fireEvent.click(screen.getByText("extractButton"));

    await waitFor(() => {
      // Check extracted events are rendered — use getAllByText since
      // "three days later" appears in both the expression title and context
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

  it("accepts an extracted event and creates timeline event", async () => {
    mockMutate.mockImplementation((_chapterIds, options) => {
      options?.onSuccess?.(mockExtractedEvents);
    });

    render(<TimelineExtractionReview novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText("Chapter 1")).toBeDefined();
    });

    fireEvent.click(screen.getByText("Chapter 1"));
    fireEvent.click(screen.getByText("extractButton"));

    await waitFor(() => {
      expect(screen.getAllByText("accept").length).toBe(2);
    });

    // Accept first event
    const acceptButtons = screen.getAllByText("accept");
    fireEvent.click(acceptButtons[0]);

    expect(mockCreateMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        event_name: "Arrival at the castle",
        source: "extracted",
      }),
    );
  });

  it("rejects an extracted event", async () => {
    mockMutate.mockImplementation((_chapterIds, options) => {
      options?.onSuccess?.(mockExtractedEvents);
    });

    render(<TimelineExtractionReview novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText("Chapter 1")).toBeDefined();
    });

    fireEvent.click(screen.getByText("Chapter 1"));
    fireEvent.click(screen.getByText("extractButton"));

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
