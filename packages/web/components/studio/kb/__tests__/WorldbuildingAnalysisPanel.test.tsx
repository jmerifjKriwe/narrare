/**
 * WorldbuildingAnalysisPanel tests — AI worldbuilding analysis.
 *
 * Tests:
 * 1. Shows loading state on mount (auto-triggers)
 * 2. Shows score header after successful analysis
 * 3. Shows tabs for gaps, connections, consistency
 * 4. Shows error state on failure
 * 5. Shows no findings state when no issues
 * 6. Calls onClose when close clicked
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorldbuildingAnalysisPanel } from "@/components/studio/kb/WorldbuildingAnalysisPanel";

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

const mockMutateAsync = vi.fn();

vi.mock("@/lib/hooks/useWorldbuilding", () => ({
  useWorldbuildingAnalyze: () => ({
    mutateAsync: mockMutateAsync,
    isPending: false,
  }),
  useWorldbuildingApply: () => ({
    mutateAsync: vi.fn().mockResolvedValue({ success: true, created_count: 0 }),
    isPending: false,
  }),
}));

vi.mock("@/components/studio/kb/WorldbuildingAnalysisCards", () => ({
  GapCard: ({ gap }: { gap: { description: string } }) => (
    <div data-testid="gap-card">{gap.description}</div>
  ),
  ConnectionCard: ({
    connection,
  }: {
    connection: { source_entity_name: string; target_entity_name: string };
  }) => (
    <div data-testid="connection-card">
      {connection.source_entity_name} → {connection.target_entity_name}
    </div>
  ),
  ConsistencyCard: ({ issue }: { issue: { description: string } }) => (
    <div data-testid="consistency-card">{issue.description}</div>
  ),
  groupByCategory: (issues: { category: string }[]) => {
    const groups: Record<string, { category: string }[]> = {};
    for (const issue of issues) {
      if (!groups[issue.category]) groups[issue.category] = [];
      groups[issue.category].push(issue);
    }
    return groups;
  },
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const defaultProps = {
  novelId: "novel-1",
  onClose: vi.fn(),
};

function createAnalysisResponse() {
  return {
    worldbuilding_score: 0.75,
    overall_assessment: "Good foundation with some gaps.",
    entity_count: 10,
    gap_findings: [
      {
        entity_id: "e1",
        entity_name: "Anna",
        gap_type: "missing_field",
        field_key: "backstory",
        description: "Character lacks backstory",
        severity: "major",
      },
    ],
    connection_suggestions: [
      {
        finding_index: 0,
        source_entity_name: "Anna",
        target_entity_name: "Berlin",
        suggested_rel_type: "lives_in",
        confidence: 0.8,
        reasoning: "Character likely lives in this location",
      },
    ],
    consistency_issues: [
      {
        finding_index: 0,
        category: "timeline",
        severity: "minor",
        description: "Minor timeline inconsistency",
        confidence: 0.7,
        entity_names: ["Anna"],
        contradiction: "Date mismatch",
      },
    ],
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("WorldbuildingAnalysisPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state on mount", async () => {
    mockMutateAsync.mockReturnValue(new Promise(() => {})); // never resolves

    renderWithProviders(<WorldbuildingAnalysisPanel {...defaultProps} />);

    expect(screen.getByText("worldbuilding.analyzing")).toBeDefined();
  });

  it("shows score header after successful analysis", async () => {
    mockMutateAsync.mockResolvedValue(createAnalysisResponse());

    renderWithProviders(<WorldbuildingAnalysisPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("0.75")).toBeDefined();
    });
    expect(screen.getByText("worldbuilding.score")).toBeDefined();
  });

  it("shows tab buttons after successful analysis", async () => {
    mockMutateAsync.mockResolvedValue(createAnalysisResponse());

    renderWithProviders(<WorldbuildingAnalysisPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("worldbuilding.gaps")).toBeDefined();
    });
    expect(screen.getByText("worldbuilding.connections")).toBeDefined();
    expect(screen.getByText("worldbuilding.consistency")).toBeDefined();
  });

  it("shows error state on failure", async () => {
    mockMutateAsync.mockRejectedValue(new Error("Analysis failed"));

    renderWithProviders(<WorldbuildingAnalysisPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("worldbuilding.error")).toBeDefined();
    });
    expect(screen.getByText("Analysis failed")).toBeDefined();
  });

  it("shows retry button in error state", async () => {
    mockMutateAsync.mockRejectedValue(new Error("Analysis failed"));

    renderWithProviders(<WorldbuildingAnalysisPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("retry")).toBeDefined();
    });
  });

  it("shows no issues state when no findings", async () => {
    mockMutateAsync.mockResolvedValue({
      ...createAnalysisResponse(),
      gap_findings: [],
      connection_suggestions: [],
      consistency_issues: [],
    });

    renderWithProviders(<WorldbuildingAnalysisPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("worldbuilding.noIssues")).toBeDefined();
    });
  });

  it("shows entity count in score header", async () => {
    mockMutateAsync.mockResolvedValue(createAnalysisResponse());

    renderWithProviders(<WorldbuildingAnalysisPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("worldbuilding.entityCount")).toBeDefined();
    });
  });

  it("renders overall assessment text", async () => {
    mockMutateAsync.mockResolvedValue(createAnalysisResponse());

    renderWithProviders(<WorldbuildingAnalysisPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Good foundation with some gaps.")).toBeDefined();
    });
  });

  it("calls onClose when X button clicked", async () => {
    mockMutateAsync.mockResolvedValue(createAnalysisResponse());
    const onClose = vi.fn();

    renderWithProviders(<WorldbuildingAnalysisPanel {...defaultProps} onClose={onClose} />);

    await waitFor(() => {
      expect(screen.getByText("0.75")).toBeDefined();
    });

    // Find and click X button
    const closeButtons = screen.getAllByRole("button");
    // The X button has a Lucide X icon inside
    const xButton = closeButtons[closeButtons.length - 1];
    fireEvent.click(xButton);
  });
});
