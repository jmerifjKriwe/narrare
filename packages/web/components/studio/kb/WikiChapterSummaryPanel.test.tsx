import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { WikiChapterSummaryResponse } from "@/lib/api/wiki";
import { WikiChapterSummaryPanel } from "./WikiChapterSummaryPanel";

// --- Mock hooks ---

let chapterSummaryResult: {
  data: WikiChapterSummaryResponse | null | undefined;
  isLoading: boolean;
  isError: boolean;
};

vi.mock("@/lib/hooks/useWiki", () => ({
  useWikiChapterSummary: () => chapterSummaryResult,
}));

const mockChapterSummary: WikiChapterSummaryResponse = {
  id: "wcs-1",
  chapter_id: "chapter-1",
  narrative_summary:
    "In this chapter, the protagonist discovers a hidden passage beneath the castle.",
  key_events: [
    "Discovery of hidden passage",
    "Confrontation with the guard",
    "Escape through tunnels",
  ],
  entities_involved: [
    { name: "John Smith", entity_id: "ent-1" },
    { name: "Castle Black", entity_id: "ent-2" },
  ],
  themes: ["Betrayal", "Redemption"],
  emotional_arc: "Rising tension → Climax",
  status: "fresh",
  version: 2,
  generated_at: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
};

beforeEach(() => {
  vi.clearAllMocks();
  chapterSummaryResult = {
    data: mockChapterSummary,
    isLoading: false,
    isError: false,
  };
});

describe("WikiChapterSummaryPanel", () => {
  it("renders chapter summary", () => {
    render(<WikiChapterSummaryPanel novelId="novel-1" chapterId="chapter-1" />);
    expect(screen.getByText("kb.wiki.chapterWiki")).toBeInTheDocument();
  });

  it("shows all fields (narrative, events, entities, themes) when expanded", async () => {
    render(<WikiChapterSummaryPanel novelId="novel-1" chapterId="chapter-1" />);

    // Click to expand
    const headerButton = screen.getByRole("button");
    await userEvent.click(headerButton);

    expect(screen.getByText("kb.wiki.narrativeSummary")).toBeInTheDocument();
    expect(screen.getByText("kb.wiki.keyEvents")).toBeInTheDocument();
    expect(screen.getByText("kb.wiki.entitiesInvolved")).toBeInTheDocument();
    expect(screen.getByText("kb.wiki.themes")).toBeInTheDocument();
    expect(screen.getByText("kb.wiki.emotionalArc")).toBeInTheDocument();

    // Check narrative content
    expect(screen.getByText(/In this chapter, the protagonist discovers/)).toBeInTheDocument();

    // Check event content
    expect(screen.getByText("Discovery of hidden passage")).toBeInTheDocument();
    expect(screen.getByText("Confrontation with the guard")).toBeInTheDocument();

    // Check entity badges
    expect(screen.getByText("John Smith")).toBeInTheDocument();
    expect(screen.getByText("Castle Black")).toBeInTheDocument();

    // Check theme tags
    expect(screen.getByText("Betrayal")).toBeInTheDocument();
    expect(screen.getByText("Redemption")).toBeInTheDocument();

    // Check emotional arc
    expect(screen.getByText("Rising tension → Climax")).toBeInTheDocument();
  });

  it("handles no-summary state", () => {
    chapterSummaryResult = {
      data: null,
      isLoading: false,
      isError: false,
    };
    render(<WikiChapterSummaryPanel novelId="novel-1" chapterId="chapter-1" />);
    expect(screen.getByText("kb.wiki.noSummaryYet")).toBeInTheDocument();
  });

  it("starts collapsed", () => {
    render(<WikiChapterSummaryPanel novelId="novel-1" chapterId="chapter-1" />);
    // Header is visible but content is not
    expect(screen.getByText("kb.wiki.chapterWiki")).toBeInTheDocument();
    // Narrative summary content should NOT be visible when collapsed
    expect(screen.queryByText("kb.wiki.narrativeSummary")).not.toBeInTheDocument();
  });

  it("toggles expanded/collapsed", async () => {
    render(<WikiChapterSummaryPanel novelId="novel-1" chapterId="chapter-1" />);

    // Starts collapsed
    expect(screen.queryByText("kb.wiki.narrativeSummary")).not.toBeInTheDocument();

    // Expand
    const headerButton = screen.getByRole("button");
    await userEvent.click(headerButton);
    expect(screen.getByText("kb.wiki.narrativeSummary")).toBeInTheDocument();

    // Collapse
    await userEvent.click(headerButton);
    expect(screen.queryByText("kb.wiki.narrativeSummary")).not.toBeInTheDocument();
  });

  it("handles loading state", () => {
    chapterSummaryResult = {
      data: undefined,
      isLoading: true,
      isError: false,
    };
    render(<WikiChapterSummaryPanel novelId="novel-1" chapterId="chapter-1" />);
    expect(screen.getByText("kb.wiki.loading")).toBeInTheDocument();
  });

  it("handles error state", () => {
    chapterSummaryResult = {
      data: undefined,
      isLoading: false,
      isError: true,
    };
    render(<WikiChapterSummaryPanel novelId="novel-1" chapterId="chapter-1" />);
    expect(screen.getByText("kb.wiki.loadError")).toBeInTheDocument();
  });
});
