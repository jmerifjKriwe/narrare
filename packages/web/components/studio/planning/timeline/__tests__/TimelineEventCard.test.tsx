import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TimelineEventCard } from "@/components/studio/planning/timeline/TimelineEventCard";
import type { TimelineEvent } from "@/types/timeline";

// Mock next-intl
vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
  useLocale: () => "en",
}));

// Mock delete hook
const mockDeleteMutation = { mutate: vi.fn(), isPending: false };
vi.mock("@/lib/hooks/useTimeline", () => ({
  useDeleteTimelineEvent: () => mockDeleteMutation,
}));

const baseEvent: TimelineEvent = {
  id: "evt-1",
  novel_id: "novel-1",
  event_name: "The Battle of Helm's Deep",
  description: "A great battle at the fortress.",
  event_type: "battle",
  timestamp_raw: "Year of the Dragon, Spring",
  timestamp_normalized: "3001-03-15",
  temporal_order: 5,
  chapter_id: "ch-1",
  character_refs: [{ id: "char-1", name: "Aragorn" }],
  location_ref: { id: "loc-1", name: "Helm's Deep" },
  causes: "Saruman's army advances",
  consequences: "Rohan is saved",
  source: "manual",
  confidence: null,
  is_confirmed: true,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

describe("TimelineEventCard", () => {
  it("renders event with all fields", () => {
    render(<TimelineEventCard event={baseEvent} novelId="novel-1" onEdit={vi.fn()} />);
    expect(screen.getByText("The Battle of Helm's Deep")).toBeDefined();
    expect(screen.getByText("Aragorn")).toBeDefined();
    // Location is rendered with emoji prefix — check it exists in the document
    const locationElements = screen.getAllByText(/Helm's Deep/);
    expect(locationElements.length).toBeGreaterThanOrEqual(1);
  });

  it("shows source badge correctly for manual events", () => {
    render(<TimelineEventCard event={baseEvent} novelId="novel-1" onEdit={vi.fn()} />);
    expect(screen.getByText("manual")).toBeDefined();
  });

  it("shows source badge for AI analysis events", () => {
    const aiEvent = { ...baseEvent, source: "ai_analysis" as const, confidence: 0.85 };
    render(<TimelineEventCard event={aiEvent} novelId="novel-1" onEdit={vi.fn()} />);
    expect(screen.getByText("aiAnalysis")).toBeDefined();
  });

  it("shows confirmed indicator for extracted events", () => {
    const extractedEvent = { ...baseEvent, source: "extracted" as const, is_confirmed: false };
    render(<TimelineEventCard event={extractedEvent} novelId="novel-1" onEdit={vi.fn()} />);
    expect(screen.getByText("unconfirmed")).toBeDefined();
  });

  it("calls onEdit when edit button is clicked", () => {
    const onEdit = vi.fn();
    render(<TimelineEventCard event={baseEvent} novelId="novel-1" onEdit={onEdit} />);
    const editButton = screen.getByLabelText("editEvent");
    editButton.click();
    expect(onEdit).toHaveBeenCalledOnce();
  });

  it("shows confidence bar for AI events", () => {
    const aiEvent = { ...baseEvent, source: "ai_analysis" as const, confidence: 0.85 };
    render(<TimelineEventCard event={aiEvent} novelId="novel-1" onEdit={vi.fn()} />);
    expect(screen.getByText("85%")).toBeDefined();
  });
});
