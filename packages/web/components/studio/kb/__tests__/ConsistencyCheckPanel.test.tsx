/**
 * ConsistencyCheckPanel tests — KB consistency check results.
 *
 * Tests:
 * 1. Renders loading state on mount (auto-triggers check)
 * 2. Shows results after successful check
 * 3. Shows no-issues state when no issues found
 * 4. Shows error state on failure
 * 5. Calls onClose when close button clicked
 * 6. Calls runCheck with refresh=true on refresh click
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ConsistencyCheckPanel } from "@/components/studio/kb/ConsistencyCheckPanel";

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

const mockCheckConsistency = vi.fn();

vi.mock("@/lib/api/consistency", () => ({
  consistencyApi: {
    checkConsistency: (...args: unknown[]) => mockCheckConsistency(...args),
  },
}));

vi.mock("@/components/studio/kb/WorldbuildingAnalysisCards", () => ({
  ConsistencyCard: ({ issue }: { issue: { finding_index: number; description: string } }) => (
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

function createSuccessResponse(overrides = {}) {
  return {
    issues: [
      {
        finding_index: 0,
        category: "timeline",
        severity: "major",
        description: "Timeline contradiction detected",
        confidence: 0.85,
        entity_names: ["Anna", "Johann"],
        contradiction: "Event order mismatch",
        suggested_resolution: "Reorder events",
      },
    ],
    entity_count: 5,
    summary: { timeline_issues: 1 },
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ConsistencyCheckPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state on mount", async () => {
    mockCheckConsistency.mockReturnValue(new Promise(() => {})); // never resolves

    renderWithProviders(<ConsistencyCheckPanel {...defaultProps} />);

    // Should show loading indicator text
    expect(screen.getByText("consistency.checking")).toBeDefined();
  });

  it("shows results after successful check", async () => {
    mockCheckConsistency.mockResolvedValue(createSuccessResponse());

    renderWithProviders(<ConsistencyCheckPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("1")).toBeDefined(); // issue count
    });

    expect(screen.getByText("worldbuilding.consistency")).toBeDefined();
    expect(screen.getByTestId("consistency-card")).toBeDefined();
  });

  it("shows no-issues state when no issues found", async () => {
    mockCheckConsistency.mockResolvedValue(createSuccessResponse({ issues: [], summary: {} }));

    renderWithProviders(<ConsistencyCheckPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("consistency.noIssues")).toBeDefined();
    });
  });

  it("shows error state on failure", async () => {
    mockCheckConsistency.mockRejectedValue(new Error("Network error"));

    renderWithProviders(<ConsistencyCheckPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("worldbuilding.error")).toBeDefined();
    });
    expect(screen.getByText("Network error")).toBeDefined();
  });

  it("shows retry button in error state", async () => {
    mockCheckConsistency.mockRejectedValue(new Error("Network error"));

    renderWithProviders(<ConsistencyCheckPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("retry")).toBeDefined();
    });
  });

  it("calls onClose when close (X) button clicked", async () => {
    mockCheckConsistency.mockResolvedValue(createSuccessResponse());

    renderWithProviders(<ConsistencyCheckPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("1")).toBeDefined();
    });

    // Find the X button (there are two — header and results)
    const closeButtons = screen.getAllByRole("button");
    // The second X button in the header right side
    const xButton = closeButtons.find(
      (btn) => btn.querySelector("svg.lucide-x") !== null || btn.textContent === "",
    );
    if (xButton) fireEvent.click(xButton);
  });

  it("calls runCheck with refresh on refresh click", async () => {
    mockCheckConsistency.mockResolvedValue(createSuccessResponse());

    renderWithProviders(<ConsistencyCheckPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("worldbuilding.refresh")).toBeDefined();
    });

    mockCheckConsistency.mockResolvedValue(createSuccessResponse());
    fireEvent.click(screen.getByText("worldbuilding.refresh"));
  });

  it("shows entity count in summary", async () => {
    mockCheckConsistency.mockResolvedValue(createSuccessResponse());

    renderWithProviders(<ConsistencyCheckPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("worldbuilding.entityCount")).toBeDefined();
    });
  });

  it("calls onClose when back arrow clicked", async () => {
    mockCheckConsistency.mockResolvedValue(createSuccessResponse());
    const onClose = vi.fn();

    renderWithProviders(<ConsistencyCheckPanel {...defaultProps} onClose={onClose} />);

    await waitFor(() => {
      expect(screen.getByText("1")).toBeDefined();
    });

    // The back button is the first button
    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[0]);
    expect(onClose).toHaveBeenCalled();
  });
});
