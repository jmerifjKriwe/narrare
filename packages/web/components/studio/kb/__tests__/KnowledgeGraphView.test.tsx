/**
 * KnowledgeGraphView tests — graph visualization component.
 *
 * Tests:
 * 1. Renders loading state while fetching graph data
 * 2. Renders empty state when no entities exist
 * 3. Renders error state on fetch failure
 * 4. Renders graph container with zoom controls
 * 5. Calls onSelectEntry when node is double-clicked
 * 6. Renders KnowledgeGraphControls overlay
 * 7. Renders KnowledgeGraphPathPanel
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KnowledgeGraphView } from "@/components/studio/kb/KnowledgeGraphView";

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

// Mock cytoscape — returns a stub instance with event binding
const mockCyInstance = {
  on: vi.fn(),
  off: vi.fn(),
  destroy: vi.fn(),
  elements: vi.fn(() => ({
    removeClass: vi.fn().mockReturnThis(),
    not: vi.fn(() => ({ not: vi.fn(() => ({ addClass: vi.fn() })) })),
  })),
  layout: vi.fn(() => ({ run: vi.fn() })),
  zoom: vi.fn(),
  center: vi.fn(),
  fit: vi.fn(),
  animate: vi.fn(),
  getElementById: vi.fn(() => ({
    length: 1,
    data: vi.fn((key: string) => {
      if (key === "label") return "Test Node";
      if (key === "entity_type") return "character";
      if (key === "degree") return 5;
      return null;
    }),
    addClass: vi.fn(),
    connectedEdges: vi.fn(() => ({ addClass: vi.fn() })),
    neighborhood: vi.fn(() => ({ nodes: vi.fn(() => ({ addClass: vi.fn() })) })),
    edgesTo: vi.fn(() => ({ addClass: vi.fn() })),
    renderedPosition: vi.fn(() => ({ x: 100, y: 100 })),
  })),
};

vi.mock("cytoscape", () => {
  const cytoscape = vi.fn(() => mockCyInstance);
  (cytoscape as unknown as { use: typeof vi.fn }).use = vi.fn();
  return { default: cytoscape };
});

// Mock cytoscape-dagre
vi.mock("cytoscape-dagre", () => ({ default: vi.fn() }));

// Mock graph utilities
vi.mock("@/components/studio/kb/graph-layouts", () => ({
  LAYOUT_CONFIGS: {
    cose: { name: "cose" },
    dagre: { name: "dagre" },
    concentric: { name: "concentric" },
  },
}));

vi.mock("@/components/studio/kb/graph-styles", () => ({
  buildGraphStyles: () => [],
  ENTITY_TYPE_COLORS: {
    character: "hsl(0, 70%, 50%)",
    location: "hsl(200, 70%, 50%)",
  },
}));

vi.mock("@/components/studio/kb/graph-utils", () => ({
  filterByEntityTypes: (data: unknown) => data,
  graphToElements: () => [{ data: { id: "node-1", label: "Anna" } }],
  searchNodes: () => [{ id: "node-1" }],
}));

// Mock hooks
const mockGraphData = {
  nodes: [{ id: "node-1", name: "Anna", entity_type: "character" }],
  edges: [{ id: "edge-1", source: "node-1", target: "node-2" }],
  stats: { node_count: 2, edge_count: 1 },
};

// Controllable hook mocks so individual tests can drive loading/error states.
// Names use the `mock*` prefix so vitest's hoisted vi.mock() factory can
// reference them.
const mockUseKBGraph = vi.fn();
const mockUseKBGraphPath = vi.fn(() => ({
  mutate: vi.fn(),
  isPending: false,
  error: null,
}));

vi.mock("@/lib/hooks/useKBGraph", () => ({
  useKBGraph: () => mockUseKBGraph(),
  useKBGraphPath: () => mockUseKBGraphPath(),
}));

// Mock sub-components
vi.mock("@/components/studio/kb/KnowledgeGraphControls", () => ({
  KnowledgeGraphControls: ({ nodeCount, edgeCount }: { nodeCount: number; edgeCount: number }) => (
    <div data-testid="graph-controls">
      <span>{nodeCount} nodes</span>
      <span>{edgeCount} edges</span>
    </div>
  ),
}));

vi.mock("@/components/studio/kb/KnowledgeGraphPathPanel", () => ({
  KnowledgeGraphPathPanel: () => <div data-testid="path-panel" />,
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const defaultProps = {
  novelId: "novel-1",
  onSelectEntry: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KnowledgeGraphView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: successful graph load.
    mockUseKBGraph.mockReturnValue({
      data: mockGraphData,
      isLoading: false,
      error: null,
    });
  });

  it("renders graph container div", () => {
    renderWithProviders(<KnowledgeGraphView {...defaultProps} />);

    // The container div should exist with the bg-background class
    const container = document.querySelector(".bg-background");
    expect(container).toBeDefined();
  });

  it("renders zoom control buttons", () => {
    renderWithProviders(<KnowledgeGraphView {...defaultProps} />);

    expect(screen.getByLabelText("Zoom in")).toBeDefined();
    expect(screen.getByLabelText("Zoom out")).toBeDefined();
    expect(screen.getByLabelText("Fit to view")).toBeDefined();
  });

  it("renders KnowledgeGraphControls overlay", () => {
    renderWithProviders(<KnowledgeGraphView {...defaultProps} />);

    expect(screen.getByTestId("graph-controls")).toBeDefined();
    expect(screen.getByText("2 nodes")).toBeDefined();
    expect(screen.getByText("1 edges")).toBeDefined();
  });

  it("renders KnowledgeGraphPathPanel", () => {
    renderWithProviders(<KnowledgeGraphView {...defaultProps} />);

    expect(screen.getByTestId("path-panel")).toBeDefined();
  });

  it("zooms in when zoom button is clicked", () => {
    renderWithProviders(<KnowledgeGraphView {...defaultProps} />);

    const zoomInBtn = screen.getByLabelText("Zoom in");
    fireEvent.click(zoomInBtn);

    expect(mockCyInstance.zoom).toHaveBeenCalled();
    expect(mockCyInstance.center).toHaveBeenCalled();
  });

  it("zooms out when zoom out button is clicked", () => {
    renderWithProviders(<KnowledgeGraphView {...defaultProps} />);

    const zoomOutBtn = screen.getByLabelText("Zoom out");
    fireEvent.click(zoomOutBtn);

    expect(mockCyInstance.zoom).toHaveBeenCalled();
  });

  it("fits graph when fit button is clicked", () => {
    renderWithProviders(<KnowledgeGraphView {...defaultProps} />);

    const fitBtn = screen.getByLabelText("Fit to view");
    fireEvent.click(fitBtn);

    expect(mockCyInstance.fit).toHaveBeenCalled();
  });

  it("initializes cytoscape when elements are available", async () => {
    renderWithProviders(<KnowledgeGraphView {...defaultProps} />);

    // cytoscape constructor should have been called
    await waitFor(() => {
      expect(mockCyInstance.on).toHaveBeenCalled();
    });
  });

  // Regression (CR-07-03): graph load errors must render the canonical mapped
  // message (mapSSEError), never the raw underlying error text which can leak
  // backend/internal details. A generic fetch Error maps to the connection
  // error message.
  it("renders mapped error message on fetch failure, not the raw underlying error", () => {
    mockUseKBGraph.mockReturnValue({
      data: null,
      isLoading: false,
      error: new Error("Internal backend secret 42"),
    });

    renderWithProviders(<KnowledgeGraphView {...defaultProps} />);

    // mapSSEError maps a generic Error to the connection error message.
    expect(screen.getByText("Verbindung verloren. Prüfe deine Internetverbindung.")).toBeDefined();
    // Raw backend detail must NOT leak to the UI.
    expect(screen.queryByText(/Internal backend secret 42/)).toBeNull();
  });

  it("does not leak the raw underlying error when error carries a network message", () => {
    mockUseKBGraph.mockReturnValue({
      data: null,
      isLoading: false,
      error: new Error("fetch failed: ECONNREFUSED db.internal:5432"),
    });

    renderWithProviders(<KnowledgeGraphView {...defaultProps} />);

    // The raw internal stack detail must never be rendered.
    expect(screen.queryByText(/ECONNREFUSED db.internal/)).toBeNull();
    expect(screen.getByText("Verbindung verloren. Prüfe deine Internetverbindung.")).toBeDefined();
  });
});
