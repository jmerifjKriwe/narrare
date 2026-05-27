/**
 * KnowledgeGraphPathPanel tests — shortest path result display.
 *
 * Tests:
 * 1. Returns null when no result, not loading, and no error
 * 2. Shows loading text when isLoading
 * 3. Shows error message when error provided
 * 4. Shows path with entity names when result has path
 * 5. Shows "no path" message when result has no path
 * 6. Shows hop count for found path
 * 7. Calls onClose when close button clicked
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KnowledgeGraphPathPanel } from "@/components/studio/kb/KnowledgeGraphPathPanel";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const defaultProps = {
  pathResult: null as {
    path: string[] | null;
    length: number | null;
    entity_names: string[] | null;
  } | null,
  isLoading: false,
  error: null as string | null,
  onClose: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KnowledgeGraphPathPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns null when no result, not loading, and no error", () => {
    const { container } = render(<KnowledgeGraphPathPanel {...defaultProps} />);

    expect(container.innerHTML).toBe("");
  });

  it("shows loading text when isLoading", () => {
    render(<KnowledgeGraphPathPanel {...defaultProps} isLoading />);

    expect(screen.getByText("graph.loading")).toBeDefined();
    expect(screen.getByText("graph.findPath")).toBeDefined();
  });

  it("shows error message when error provided", () => {
    render(<KnowledgeGraphPathPanel {...defaultProps} error="Path finding failed" />);

    expect(screen.getByText("Path finding failed")).toBeDefined();
  });

  it("shows path with entity names when result has path", () => {
    render(
      <KnowledgeGraphPathPanel
        {...defaultProps}
        pathResult={{
          path: ["node-1", "node-2", "node-3"],
          length: 2,
          entity_names: ["Anna", "Johann", "Berlin"],
        }}
      />,
    );

    expect(screen.getByText("Anna")).toBeDefined();
    expect(screen.getByText("Johann")).toBeDefined();
    expect(screen.getByText("Berlin")).toBeDefined();
  });

  it("shows hop count for found path", () => {
    render(
      <KnowledgeGraphPathPanel
        {...defaultProps}
        pathResult={{
          path: ["node-1", "node-2", "node-3"],
          length: 2,
          entity_names: ["Anna", "Johann", "Berlin"],
        }}
      />,
    );

    expect(screen.getByText(/2 hops/)).toBeDefined();
  });

  it("shows singular hop for length 1", () => {
    render(
      <KnowledgeGraphPathPanel
        {...defaultProps}
        pathResult={{
          path: ["node-1", "node-2"],
          length: 1,
          entity_names: ["Anna", "Berlin"],
        }}
      />,
    );

    expect(screen.getByText(/1 hop/)).toBeDefined();
  });

  it("shows no path message when result has null path", () => {
    render(
      <KnowledgeGraphPathPanel
        {...defaultProps}
        pathResult={{
          path: null,
          length: null,
          entity_names: null,
        }}
      />,
    );

    expect(screen.getByText("graph.noPath")).toBeDefined();
  });

  it("calls onClose when close button clicked", () => {
    const onClose = vi.fn();
    render(<KnowledgeGraphPathPanel {...defaultProps} isLoading onClose={onClose} />);

    fireEvent.click(screen.getByLabelText("Close path panel"));
    expect(onClose).toHaveBeenCalled();
  });

  it("renders find path title", () => {
    render(<KnowledgeGraphPathPanel {...defaultProps} isLoading />);

    expect(screen.getByText("graph.findPath")).toBeDefined();
  });
});
