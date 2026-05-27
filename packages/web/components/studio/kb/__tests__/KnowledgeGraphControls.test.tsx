/**
 * KnowledgeGraphControls tests — layout selector, filter, and search.
 *
 * Tests:
 * 1. Renders stats bar with node/edge counts
 * 2. Shows loading text when isLoading
 * 3. Renders search input
 * 4. Renders layout selector buttons
 * 5. Renders entity type filter buttons
 * 6. Calls onLayoutChange when layout clicked
 * 7. Calls onSearchQueryChange on input change
 * 8. Calls onSearchSubmit on Enter key
 * 9. Shows clear button when search query is non-empty
 * 10. Calls onSearchClear when clear clicked
 * 11. Calls onEntityTypeFilterChange when filter toggled
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KnowledgeGraphControls } from "@/components/studio/kb/KnowledgeGraphControls";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/components/studio/kb/constants", () => ({
  ENTITY_TYPES: ["character", "location", "faction"],
}));

vi.mock("@/components/studio/kb/graph-styles", () => ({
  ENTITY_TYPE_COLORS: {
    character: "hsl(0, 70%, 50%)",
    location: "hsl(200, 70%, 50%)",
    faction: "hsl(120, 70%, 50%)",
  },
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const defaultProps = {
  layout: "cose" as const,
  onLayoutChange: vi.fn(),
  entityTypeFilter: new Set<string>(),
  onEntityTypeFilterChange: vi.fn(),
  searchQuery: "",
  onSearchQueryChange: vi.fn(),
  onSearchSubmit: vi.fn(),
  onSearchClear: vi.fn(),
  isLoading: false,
  nodeCount: 10,
  edgeCount: 5,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KnowledgeGraphControls", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders stats bar with node and edge counts", () => {
    render(<KnowledgeGraphControls {...defaultProps} />);

    expect(screen.getByText(/10 nodes/)).toBeDefined();
    expect(screen.getByText(/5 edges/)).toBeDefined();
  });

  it("shows loading text when isLoading", () => {
    render(<KnowledgeGraphControls {...defaultProps} isLoading />);

    expect(screen.getByText("graph.loading")).toBeDefined();
  });

  it("renders search input", () => {
    render(<KnowledgeGraphControls {...defaultProps} />);

    expect(screen.getByPlaceholderText("graph.searchPlaceholder")).toBeDefined();
  });

  it("renders layout selector buttons", () => {
    render(<KnowledgeGraphControls {...defaultProps} />);

    expect(screen.getByText("graph.forceLayout")).toBeDefined();
    expect(screen.getByText("graph.hierarchicalLayout")).toBeDefined();
    expect(screen.getByText("graph.concentricLayout")).toBeDefined();
  });

  it("renders entity type filter buttons", () => {
    render(<KnowledgeGraphControls {...defaultProps} />);

    expect(screen.getByText("character")).toBeDefined();
    expect(screen.getByText("location")).toBeDefined();
    expect(screen.getByText("faction")).toBeDefined();
  });

  it("calls onLayoutChange when layout button clicked", () => {
    const onLayoutChange = vi.fn();
    render(<KnowledgeGraphControls {...defaultProps} onLayoutChange={onLayoutChange} />);

    fireEvent.click(screen.getByText("graph.hierarchicalLayout"));
    expect(onLayoutChange).toHaveBeenCalledWith("dagre");
  });

  it("calls onSearchQueryChange on input change", () => {
    const onSearchQueryChange = vi.fn();
    render(<KnowledgeGraphControls {...defaultProps} onSearchQueryChange={onSearchQueryChange} />);

    const input = screen.getByPlaceholderText("graph.searchPlaceholder");
    fireEvent.change(input, { target: { value: "Anna" } });

    expect(onSearchQueryChange).toHaveBeenCalledWith("Anna");
  });

  it("calls onSearchSubmit on Enter key", () => {
    const onSearchSubmit = vi.fn();
    render(<KnowledgeGraphControls {...defaultProps} onSearchSubmit={onSearchSubmit} />);

    const input = screen.getByPlaceholderText("graph.searchPlaceholder");
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onSearchSubmit).toHaveBeenCalled();
  });

  it("shows clear button when search query is non-empty", () => {
    render(<KnowledgeGraphControls {...defaultProps} searchQuery="Anna" />);

    expect(screen.getByLabelText("Clear search")).toBeDefined();
  });

  it("does not show clear button when search query is empty", () => {
    render(<KnowledgeGraphControls {...defaultProps} searchQuery="" />);

    expect(screen.queryByLabelText("Clear search")).toBeNull();
  });

  it("calls onSearchClear when clear button clicked", () => {
    const onSearchClear = vi.fn();
    render(
      <KnowledgeGraphControls {...defaultProps} searchQuery="Anna" onSearchClear={onSearchClear} />,
    );

    fireEvent.click(screen.getByLabelText("Clear search"));
    expect(onSearchClear).toHaveBeenCalled();
  });

  it("calls onEntityTypeFilterChange when entity type toggled", () => {
    const onEntityTypeFilterChange = vi.fn();
    render(
      <KnowledgeGraphControls
        {...defaultProps}
        onEntityTypeFilterChange={onEntityTypeFilterChange}
      />,
    );

    fireEvent.click(screen.getByText("character"));
    expect(onEntityTypeFilterChange).toHaveBeenCalled();

    // Verify the filter adds the character type
    const filterArg = onEntityTypeFilterChange.mock.calls[0][0] as Set<string>;
    expect(filterArg.has("character")).toBe(true);
  });

  it("highlights active layout button", () => {
    render(<KnowledgeGraphControls {...defaultProps} layout="cose" />);

    const coseButton = screen.getByText("graph.forceLayout").closest("button");
    expect(coseButton?.className).toContain("bg-primary");
  });

  it("renders singular form for single node/edge", () => {
    render(<KnowledgeGraphControls {...defaultProps} nodeCount={1} edgeCount={1} />);

    expect(screen.getByText(/1 node/)).toBeDefined();
    expect(screen.getByText(/1 edge/)).toBeDefined();
  });
});
