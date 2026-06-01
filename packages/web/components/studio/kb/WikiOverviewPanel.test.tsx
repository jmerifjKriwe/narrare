import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { WikiIndexResponse, WikiSummaryListResponse } from "@/lib/api/wiki";
import { WikiOverviewPanel } from "./WikiOverviewPanel";

// --- Mock hooks ---

const mockRefreshMutate = vi.fn();
const mockMarkStaleMutate = vi.fn();

vi.mock("@/lib/hooks/useWiki", () => ({
  useWikiIndex: () => wikiIndexResult,
  useWikiSummaries: () => wikiSummariesResult,
  useWikiRefresh: () => ({
    mutate: mockRefreshMutate,
    isPending: false,
    isError: false,
  }),
  useWikiMarkStale: () => ({
    mutate: mockMarkStaleMutate,
    isPending: false,
    isError: false,
  }),
}));

let wikiIndexResult: { data: WikiIndexResponse | undefined; isLoading: boolean; isError: boolean };
let wikiSummariesResult: {
  data: WikiSummaryListResponse | { items: never[]; total: number };
  isLoading: boolean;
  isError: boolean;
};

const mockIndex: WikiIndexResponse = {
  novel_id: "novel-1",
  total_summaries: 20,
  fresh_count: 12,
  stale_count: 3,
  pending_count: 5,
  last_generated_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
};

const mockSummaries: WikiSummaryListResponse = {
  items: [
    {
      id: "ws-1",
      novel_id: "novel-1",
      entity_id: "John Smith",
      narrative_summary: "A brave hero who fights for justice and freedom.",
      role_in_story: "Protagonist",
      key_attributes: ["brave", "determined"],
      relationships: null,
      chapter_references: null,
      character_arc: "From farm boy to legendary warrior",
      status: "fresh",
      version: 3,
      generated_at: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
      refreshed_at: null,
    },
    {
      id: "ws-2",
      novel_id: "novel-1",
      entity_id: "Castle Black",
      narrative_summary: "An ancient fortress guarding the northern border.",
      role_in_story: "Key Location",
      key_attributes: null,
      relationships: null,
      chapter_references: null,
      character_arc: null,
      status: "stale",
      version: 1,
      generated_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
      refreshed_at: null,
    },
    {
      id: "ws-3",
      novel_id: "novel-1",
      entity_id: "The Dark Forest",
      narrative_summary: "",
      role_in_story: null,
      key_attributes: null,
      relationships: null,
      chapter_references: null,
      character_arc: null,
      status: "pending",
      version: 0,
      generated_at: null,
      refreshed_at: null,
    },
  ],
  total: 3,
};

beforeEach(() => {
  vi.clearAllMocks();

  wikiIndexResult = {
    data: mockIndex,
    isLoading: false,
    isError: false,
  };

  wikiSummariesResult = {
    data: mockSummaries,
    isLoading: false,
    isError: false,
  };
});

describe("WikiOverviewPanel", () => {
  it("renders without crashing", () => {
    const onClose = vi.fn();
    render(<WikiOverviewPanel novelId="novel-1" onClose={onClose} />);
    expect(screen.getByText("kb.wiki.overviewTitle")).toBeInTheDocument();
  });

  it("shows index stats (fresh/stale/pending counts)", () => {
    render(<WikiOverviewPanel novelId="novel-1" onClose={vi.fn()} />);
    expect(screen.getByText(/kb\.wiki\.fresh/)).toBeInTheDocument();
    expect(screen.getByText(/12/)).toBeInTheDocument(); // fresh count
    expect(screen.getByText(/3/)).toBeInTheDocument(); // stale count
    expect(screen.getByText(/5/)).toBeInTheDocument(); // pending count
  });

  it("shows entity summaries list", () => {
    render(<WikiOverviewPanel novelId="novel-1" onClose={vi.fn()} />);
    expect(screen.getByText("John Smith")).toBeInTheDocument();
    expect(screen.getByText("Castle Black")).toBeInTheDocument();
    expect(screen.getByText("The Dark Forest")).toBeInTheDocument();
  });

  it("refresh button works", async () => {
    render(<WikiOverviewPanel novelId="novel-1" onClose={vi.fn()} />);
    const refreshButtons = screen.getAllByRole("button", { name: /kb\.wiki\.(refresh|generate)/ });
    // At least one refresh button per entity
    expect(refreshButtons.length).toBeGreaterThanOrEqual(3);
    await userEvent.click(refreshButtons[0]);
    expect(mockRefreshMutate).toHaveBeenCalled();
  });

  it("mark all stale button works", async () => {
    render(<WikiOverviewPanel novelId="novel-1" onClose={vi.fn()} />);
    const markStaleButton = screen.getByRole("button", { name: /kb\.wiki\.markAllStale/ });
    await userEvent.click(markStaleButton);
    expect(mockMarkStaleMutate).toHaveBeenCalled();
  });

  it("handles loading state", () => {
    wikiIndexResult = {
      data: undefined,
      isLoading: true,
      isError: false,
    };
    render(<WikiOverviewPanel novelId="novel-1" onClose={vi.fn()} />);
    expect(screen.getByText("kb.wiki.loading")).toBeInTheDocument();
  });

  it("handles empty state", () => {
    wikiSummariesResult = {
      data: { items: [], total: 0 },
      isLoading: false,
      isError: false,
    };
    render(<WikiOverviewPanel novelId="novel-1" onClose={vi.fn()} />);
    expect(screen.getByText("kb.wiki.noSummaries")).toBeInTheDocument();
  });

  it("handles error state", () => {
    wikiIndexResult = {
      data: undefined,
      isLoading: false,
      isError: true,
    };
    render(<WikiOverviewPanel novelId="novel-1" onClose={vi.fn()} />);
    expect(screen.getByText("kb.wiki.loadError")).toBeInTheDocument();
  });

  it("calls onClose when close button is clicked", async () => {
    const onClose = vi.fn();
    render(<WikiOverviewPanel novelId="novel-1" onClose={onClose} />);
    const closeButtons = screen.getAllByRole("button", { name: "kb.wiki.close" });
    await userEvent.click(closeButtons[0]);
    expect(onClose).toHaveBeenCalled();
  });
});
