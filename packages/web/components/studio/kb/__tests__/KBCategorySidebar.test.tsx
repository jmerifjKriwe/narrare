/**
 * KBCategorySidebar tests — entity type tabs with count badges.
 *
 * Tests:
 * 1. Renders KB title header
 * 2. Renders "All" tab with total count
 * 3. Renders per-entity-type tabs
 * 4. Highlights active type tab
 * 5. Calls onTypeChange when type tab clicked
 * 6. Shows analyze button when onAnalyze provided
 * 7. Shows consistency check button when onConsistencyCheck provided
 * 8. Shows graph button when onShowGraph provided
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KBCategorySidebar } from "@/components/studio/kb/KBCategorySidebar";
import type { KBEntityType } from "@/lib/api/kb";

// ---------------------------------------------------------------------------
// Test wrapper
// ---------------------------------------------------------------------------

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/lib/hooks/useKB", () => ({
  useKBEntries: (_novelId: string, params?: { entity_type?: string }) => {
    if (params?.entity_type === "character") {
      return { data: { total: 5, items: [] } };
    }
    return { data: { total: 12, items: [] } };
  },
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const defaultProps = {
  novelId: "novel-1",
  activeType: null as KBEntityType | null,
  onTypeChange: vi.fn(),
  onAnalyze: vi.fn(),
  onConsistencyCheck: vi.fn(),
  onShowGraph: vi.fn(),
  showGraph: false,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KBCategorySidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders KB title header", () => {
    renderWithProviders(<KBCategorySidebar {...defaultProps} />);

    expect(screen.getByText("kb.title")).toBeDefined();
  });

  it("renders All tab with total count", () => {
    renderWithProviders(<KBCategorySidebar {...defaultProps} />);

    expect(screen.getByText("kb.allTypes")).toBeDefined();
    // "12" appears in multiple count badges — verify at least one exists
    const countElements = screen.getAllByText("12");
    expect(countElements.length).toBeGreaterThanOrEqual(1);
  });

  it("renders per-entity-type tabs", () => {
    renderWithProviders(<KBCategorySidebar {...defaultProps} />);

    expect(screen.getByText("kb.characters")).toBeDefined();
    expect(screen.getByText("kb.locations")).toBeDefined();
    expect(screen.getByText("kb.factions")).toBeDefined();
  });

  it("highlights active type tab", () => {
    renderWithProviders(
      <KBCategorySidebar {...defaultProps} activeType={"character" as KBEntityType} />,
    );

    // Active tab should have the bg-primary class
    const characterTab = screen.getByText("kb.characters").closest("button");
    expect(characterTab?.className).toContain("bg-primary");
  });

  it("calls onTypeChange(null) when All tab clicked", () => {
    const onTypeChange = vi.fn();
    renderWithProviders(<KBCategorySidebar {...defaultProps} onTypeChange={onTypeChange} />);

    fireEvent.click(screen.getByText("kb.allTypes"));
    expect(onTypeChange).toHaveBeenCalledWith(null);
  });

  it("calls onTypeChange with type when type tab clicked", () => {
    const onTypeChange = vi.fn();
    renderWithProviders(<KBCategorySidebar {...defaultProps} onTypeChange={onTypeChange} />);

    fireEvent.click(screen.getByText("kb.characters"));
    expect(onTypeChange).toHaveBeenCalledWith("character");
  });

  it("shows analyze button when onAnalyze provided", () => {
    renderWithProviders(<KBCategorySidebar {...defaultProps} />);

    expect(screen.getByText("worldbuilding.analyzeButton")).toBeDefined();
  });

  it("does not show analyze button when onAnalyze not provided", () => {
    renderWithProviders(<KBCategorySidebar {...defaultProps} onAnalyze={undefined} />);

    expect(screen.queryByText("worldbuilding.analyzeButton")).toBeNull();
  });

  it("shows consistency check button when onConsistencyCheck provided", () => {
    renderWithProviders(<KBCategorySidebar {...defaultProps} />);

    expect(screen.getByText("consistency.checkButton")).toBeDefined();
  });

  it("shows graph button when onShowGraph provided", () => {
    renderWithProviders(<KBCategorySidebar {...defaultProps} />);

    expect(screen.getByText("graph.title")).toBeDefined();
  });

  it("does not show graph button when onShowGraph not provided", () => {
    renderWithProviders(<KBCategorySidebar {...defaultProps} onShowGraph={undefined} />);

    expect(screen.queryByText("graph.title")).toBeNull();
  });

  it("calls onAnalyze when analyze button clicked", () => {
    const onAnalyze = vi.fn();
    renderWithProviders(<KBCategorySidebar {...defaultProps} onAnalyze={onAnalyze} />);

    fireEvent.click(screen.getByText("worldbuilding.analyzeButton"));
    expect(onAnalyze).toHaveBeenCalled();
  });

  it("calls onConsistencyCheck when check button clicked", () => {
    const onConsistencyCheck = vi.fn();
    renderWithProviders(
      <KBCategorySidebar {...defaultProps} onConsistencyCheck={onConsistencyCheck} />,
    );

    fireEvent.click(screen.getByText("consistency.checkButton"));
    expect(onConsistencyCheck).toHaveBeenCalled();
  });
});
