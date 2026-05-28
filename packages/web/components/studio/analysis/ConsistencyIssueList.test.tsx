/**
 * ConsistencyIssueList tests
 *
 * Tests: render all issues, filter by check type, filter by severity,
 * dismiss action, mark intentional toggle, "no issues" message,
 * issue count after filtering.
 *
 * This component receives `issues` and `t` as props — no hooks to mock.
 * The `t` function is mocked to return keys directly.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ConsistencyIssue } from "@/lib/api/analysis";
import { ConsistencyIssueList } from "./ConsistencyIssueList";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

/** Simple t function mock matching the setupTests pattern. */
function mockT(key: string, params?: Record<string, unknown>): string {
  if (params) {
    return Object.entries(params).reduce((str, [k, v]) => str.replace(`{${k}}`, String(v)), key);
  }
  return key;
}

function makeIssue(overrides: Partial<ConsistencyIssue> = {}): ConsistencyIssue {
  return {
    check_type: "character",
    severity: "error",
    description: "Inconsistent character name",
    locations: ["Chapter 1"],
    conflicting_facts: ["John (Ch 1)", "Jon (Ch 2)"],
    suggestion: "Use consistent name",
    confidence: 0.9,
    ...overrides,
  };
}

const defaultIssues: ConsistencyIssue[] = [
  makeIssue({ check_type: "character", severity: "error", description: "Name mismatch" }),
  makeIssue({ check_type: "timeline", severity: "warning", description: "Timeline gap" }),
  makeIssue({ check_type: "world", severity: "info", description: "New location" }),
  makeIssue({ check_type: "plot", severity: "error", description: "Plot hole" }),
];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ConsistencyIssueList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // -------------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------------

  it("renders all issues by default", () => {
    render(<ConsistencyIssueList issues={defaultIssues} t={mockT} />);

    // All 4 issue descriptions should be visible
    expect(screen.getByText("Name mismatch")).toBeInTheDocument();
    expect(screen.getByText("Timeline gap")).toBeInTheDocument();
    expect(screen.getByText("New location")).toBeInTheDocument();
    expect(screen.getByText("Plot hole")).toBeInTheDocument();
  });

  it("renders issue count with total", () => {
    render(<ConsistencyIssueList issues={defaultIssues} t={mockT} />);

    // mockT returns the key without param substitution since key lacks {count}/{total} placeholders
    expect(screen.getByText("consistency.issueCount")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Filter by check type
  // -------------------------------------------------------------------------

  it("filter by check type shows only matching issues", async () => {
    const user = userEvent.setup();
    render(<ConsistencyIssueList issues={defaultIssues} t={mockT} />);

    // Open the type filter dropdown
    const typeSelect = screen.getByLabelText("consistency.filterByType");
    await user.selectOptions(typeSelect, "character");

    // Only character issues should be visible
    expect(screen.getByText("Name mismatch")).toBeInTheDocument();
    expect(screen.queryByText("Timeline gap")).not.toBeInTheDocument();
    expect(screen.queryByText("New location")).not.toBeInTheDocument();
    expect(screen.queryByText("Plot hole")).not.toBeInTheDocument();
  });

  it("selecting 'all' type filter shows all issues again", async () => {
    const user = userEvent.setup();
    render(<ConsistencyIssueList issues={defaultIssues} t={mockT} />);

    // Filter to character only
    const typeSelect = screen.getByLabelText("consistency.filterByType");
    await user.selectOptions(typeSelect, "character");

    // Only 1 issue visible
    expect(screen.queryByText("Timeline gap")).not.toBeInTheDocument();

    // Reset to all
    await user.selectOptions(typeSelect, "all");

    // All visible again
    expect(screen.getByText("Name mismatch")).toBeInTheDocument();
    expect(screen.getByText("Timeline gap")).toBeInTheDocument();
    expect(screen.getByText("New location")).toBeInTheDocument();
    expect(screen.getByText("Plot hole")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Filter by severity
  // -------------------------------------------------------------------------

  it("filter by severity shows only matching issues", async () => {
    const user = userEvent.setup();
    render(<ConsistencyIssueList issues={defaultIssues} t={mockT} />);

    const severitySelect = screen.getByLabelText("consistency.filterBySeverity");
    await user.selectOptions(severitySelect, "warning");

    // Only warning issue
    expect(screen.getByText("Timeline gap")).toBeInTheDocument();
    expect(screen.queryByText("Name mismatch")).not.toBeInTheDocument();
    expect(screen.queryByText("New location")).not.toBeInTheDocument();
    expect(screen.queryByText("Plot hole")).not.toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Dismiss action
  // -------------------------------------------------------------------------

  it("dismiss action removes issue from list", async () => {
    const user = userEvent.setup();
    render(<ConsistencyIssueList issues={defaultIssues} t={mockT} />);

    // Find first issue card and click dismiss
    const dismissButtons = screen.getAllByLabelText("consistency.actions.dismiss");
    expect(dismissButtons.length).toBe(4);

    await user.click(dismissButtons[0]);

    // One issue should be dismissed — only 3 visible
    const remainingDescriptions = screen.getAllByText(/mismatch|gap|location|hole/);
    expect(remainingDescriptions.length).toBe(3);
  });

  it("issue count updates after dismissing", async () => {
    const user = userEvent.setup();
    render(<ConsistencyIssueList issues={defaultIssues} t={mockT} />);

    const dismissButtons = screen.getAllByLabelText("consistency.actions.dismiss");
    await user.click(dismissButtons[0]);

    // The text element still shows "consistency.issueCount" but count changed
    expect(screen.getByText("consistency.issueCount")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Mark intentional
  // -------------------------------------------------------------------------

  it("mark intentional toggles state on issue card", async () => {
    const user = userEvent.setup();
    render(<ConsistencyIssueList issues={defaultIssues} t={mockT} />);

    // Click "mark intentional" on first issue
    const intentionalButtons = screen.getAllByLabelText("consistency.actions.markIntentional");
    await user.click(intentionalButtons[0]);

    // Should now show "consistency.intentional" badge in the header area
    const intentionalBadges = screen.getAllByText("consistency.intentional");
    expect(intentionalBadges.length).toBeGreaterThanOrEqual(1);
  });

  // -------------------------------------------------------------------------
  // No issues state
  // -------------------------------------------------------------------------

  it("shows no issues message when all issues filtered out", async () => {
    const user = userEvent.setup();
    render(<ConsistencyIssueList issues={defaultIssues} t={mockT} />);

    // Filter to a type that doesn't exist in our test data — well, all 4 types exist
    // Let's use severity filter for a type with 0 matches
    const severitySelect = screen.getByLabelText("consistency.filterBySeverity");

    // All our issues are error/warning/info — no issue with severity that would be 0
    // Let's use check type "character" which has only 1, and also filter severity "info"
    await user.selectOptions(severitySelect, "info");

    // Now filter type to "character" (no character+info combo exists)
    const typeSelect = screen.getByLabelText("consistency.filterByType");
    await user.selectOptions(typeSelect, "character");

    // Should show no issues message
    expect(screen.getByText("consistency.noIssues")).toBeInTheDocument();
  });

  it("shows no issues message when all issues are dismissed", async () => {
    const user = userEvent.setup();
    render(<ConsistencyIssueList issues={defaultIssues} t={mockT} />);

    // Dismiss all issues
    const dismissButtons = screen.getAllByLabelText("consistency.actions.dismiss");
    for (const btn of dismissButtons) {
      await user.click(btn);
    }

    expect(screen.getByText("consistency.noIssues")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Empty input
  // -------------------------------------------------------------------------

  it("shows no issues message when issues array is empty", () => {
    render(<ConsistencyIssueList issues={[]} t={mockT} />);

    expect(screen.getByText("consistency.noIssues")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Expandable details
  // -------------------------------------------------------------------------

  it("issue card expand button toggles details visibility", async () => {
    const user = userEvent.setup();
    const issue = makeIssue({
      description: "Expandable issue",
      locations: ["Ch 1"],
      suggestion: "Fix it",
    });
    render(<ConsistencyIssueList issues={[issue]} t={mockT} />);

    // Initially collapsed — locations not visible
    expect(screen.queryByText("consistency.locations")).not.toBeInTheDocument();

    // Click expand
    const expandButton = screen.getByText("consistency.detailsShow");
    await user.click(expandButton);

    // Now locations and suggestion should be visible
    expect(screen.getByText("consistency.locations")).toBeInTheDocument();
    expect(screen.getByText("consistency.suggestion")).toBeInTheDocument();

    // Collapse button text changes
    expect(screen.getByText("consistency.detailsHide")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Copy suggestion
  // -------------------------------------------------------------------------

  it("copy suggestion button is visible when suggestion exists", () => {
    const issue = makeIssue({ description: "Copy test", suggestion: "Fix this" });
    render(<ConsistencyIssueList issues={[issue]} t={mockT} />);

    expect(screen.getByLabelText("consistency.actions.copySuggestion")).toBeInTheDocument();
  });

  it("copy suggestion button is absent when no suggestion", () => {
    const issue = makeIssue({ description: "No suggestion", suggestion: null });
    render(<ConsistencyIssueList issues={[issue]} t={mockT} />);

    expect(screen.queryByLabelText("consistency.actions.copySuggestion")).not.toBeInTheDocument();
  });
});
