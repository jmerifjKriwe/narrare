/**
 * ConsistencyResults tests — dismiss filtering and toggle (CR-AUFG-07-26).
 *
 * Uses the REAL ConsistencyCard (no mock) for genuine integration coverage.
 * The useDismissedFindings hook is mocked to control the dismissed set.
 *
 * Tests:
 * 1. Renders all issues when none are dismissed
 * 2. Hides dismissed issues by default
 * 3. Shows the toggle button when dismissed issues exist
 * 4. Does not show the toggle when nothing is dismissed
 * 5. Reveals dismissed issues when toggle is clicked
 * 6. Calls dismiss when the card dismiss button is clicked
 * 7. Calls undismiss when the dismissed card restore button is clicked
 * 8. Shows dismissed badge on revealed dismissed cards
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// --- Mock useDismissedFindings hook ---

const mockDismiss = vi.fn();
const mockUndismiss = vi.fn();
let dismissedSet: Set<string> = new Set();

vi.mock("@/lib/hooks/useDismissedFindings", () => ({
  useDismissedFindings: () => ({
    dismissedFingerprints: dismissedSet,
    dismiss: mockDismiss,
    undismiss: mockUndismiss,
    isLoading: false,
  }),
}));

import { ConsistencyResults } from "@/components/studio/kb/ConsistencyResults";
import type { ConsistencyCheckResponse } from "@/lib/api/consistency";
import { consistencyFingerprint } from "@/lib/api/consistency";
import type { ConsistencyIssue } from "@/lib/api/worldbuilding";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function createIssue(overrides: Partial<ConsistencyIssue> = {}): ConsistencyIssue {
  return {
    finding_index: 0,
    category: "timeline",
    entity_ids: ["e1", "e2"],
    entity_names: ["Anna", "Johann"],
    description: "Timeline mismatch",
    contradiction: "wrong order",
    suggested_resolution: null,
    severity: "major",
    confidence: 0.8,
    ...overrides,
  } as ConsistencyIssue;
}

const issue0 = createIssue({ finding_index: 0 });
const issue1 = createIssue({
  finding_index: 1,
  entity_ids: ["e3"],
  entity_names: ["Berlin"],
  description: "Location error",
  severity: "minor",
});

const fp0 = consistencyFingerprint(issue0); // "Timeline mismatch::Anna,Johann"

function createResult(overrides: Partial<ConsistencyCheckResponse> = {}): ConsistencyCheckResponse {
  return {
    novel_id: "novel-1",
    entity_count: 2,
    issues: [issue0, issue1],
    summary: { timeline: 2 },
    checked_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ConsistencyResults — dismiss filtering", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    dismissedSet = new Set();
  });

  it("renders all issues when none are dismissed", () => {
    render(<ConsistencyResults novelId="novel-1" result={createResult()} />);

    expect(screen.getByText("Timeline mismatch")).toBeDefined();
    expect(screen.getByText("Location error")).toBeDefined();
  });

  it("hides dismissed issues by default", () => {
    dismissedSet = new Set([fp0]);

    render(<ConsistencyResults novelId="novel-1" result={createResult()} />);

    expect(screen.queryByText("Timeline mismatch")).toBeNull();
    expect(screen.getByText("Location error")).toBeDefined();
  });

  it("shows the toggle button when dismissed issues exist", () => {
    dismissedSet = new Set([fp0]);

    render(<ConsistencyResults novelId="novel-1" result={createResult()} />);

    expect(screen.getByText(/kb\.showDismissed/)).toBeDefined();
  });

  it("does not show the toggle button when nothing is dismissed", () => {
    render(<ConsistencyResults novelId="novel-1" result={createResult()} />);

    expect(screen.queryByText(/kb\.showDismissed/)).toBeNull();
    expect(screen.queryByText(/kb\.hideDismissed/)).toBeNull();
  });

  it("reveals dismissed issues when toggle is clicked", () => {
    dismissedSet = new Set([fp0]);

    render(<ConsistencyResults novelId="novel-1" result={createResult()} />);

    // Initially hidden
    expect(screen.queryByText("Timeline mismatch")).toBeNull();

    // Click toggle to show dismissed
    fireEvent.click(screen.getByText(/kb\.showDismissed/));

    // Now both visible
    expect(screen.getByText("Timeline mismatch")).toBeDefined();
    expect(screen.getByText("Location error")).toBeDefined();

    // Button text switches to "hide"
    expect(screen.getByText(/kb\.hideDismissed/)).toBeDefined();
  });

  it("calls dismiss with the real fingerprint when dismiss button clicked", () => {
    render(<ConsistencyResults novelId="novel-1" result={createResult()} />);

    // Both cards have dismiss buttons; click the first (issue 0)
    const dismissButtons = screen.getAllByLabelText(/kb\.dismissFinding/);
    fireEvent.click(dismissButtons[0]);

    expect(mockDismiss).toHaveBeenCalledOnce();
    expect(mockDismiss).toHaveBeenCalledWith(fp0);
  });

  it("calls undismiss with the real fingerprint when restore button clicked", () => {
    dismissedSet = new Set([fp0]);

    render(<ConsistencyResults novelId="novel-1" result={createResult()} />);

    // Reveal dismissed issues
    fireEvent.click(screen.getByText(/kb\.showDismissed/));

    // The dismissed card now shows a restore (undismiss) button
    fireEvent.click(screen.getByLabelText(/kb\.undismiss/));

    expect(mockUndismiss).toHaveBeenCalledOnce();
    expect(mockUndismiss).toHaveBeenCalledWith(fp0);
  });

  it("shows dismissed badge on revealed dismissed cards", () => {
    dismissedSet = new Set([fp0]);

    render(<ConsistencyResults novelId="novel-1" result={createResult()} />);

    // Badge not shown when dismissed issues are hidden
    expect(screen.queryByText(/kb\.dismissedBadge/)).toBeNull();

    fireEvent.click(screen.getByText(/kb\.showDismissed/));

    // Badge now shown on the revealed dismissed card
    expect(screen.getByText(/kb\.dismissedBadge/)).toBeDefined();
  });
});
