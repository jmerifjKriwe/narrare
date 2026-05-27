/**
 * WorldbuildingAnalysisCards tests — GapCard, ConnectionCard, ConsistencyCard.
 *
 * Tests:
 * 1. GapCard renders severity badge and description
 * 2. GapCard renders entity name when present
 * 3. GapCard renders gap type
 * 4. ConnectionCard renders source → target names
 * 5. ConnectionCard shows confidence percentage
 * 6. ConnectionCard shows selected state
 * 7. ConnectionCard calls onToggle when clicked
 * 8. ConsistencyCard renders severity and confidence
 * 9. ConsistencyCard renders contradiction
 * 10. ConsistencyCard renders suggested resolution
 * 11. groupByCategory groups issues correctly
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  ConnectionCard,
  ConsistencyCard,
  GapCard,
  groupByCategory,
} from "@/components/studio/kb/WorldbuildingAnalysisCards";
import type { ConnectionSuggestion, ConsistencyIssue, GapFinding } from "@/lib/api/worldbuilding";

// ---------------------------------------------------------------------------
// Mock t function (matches setupTests mock)
// ---------------------------------------------------------------------------

const t = (key: string) => key;

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function createGap(overrides: Partial<GapFinding> = {}): GapFinding {
  return {
    entity_id: "e1",
    entity_name: "Anna",
    entity_type: "character",
    gap_type: "missing_field",
    field_key: "backstory",
    description: "Character lacks backstory details",
    related_entity_type: null,
    story_relevance: 5,
    severity: "major",
    ...overrides,
  } as GapFinding;
}

function createConnection(overrides: Partial<ConnectionSuggestion> = {}): ConnectionSuggestion {
  return {
    finding_index: 0,
    source_entity_id: "entity-1",
    source_entity_name: "Anna",
    source_entity_type: "character",
    target_entity_id: "entity-2",
    target_entity_name: "Berlin",
    target_entity_type: "location",
    suggested_rel_type: "lives_in",
    inverse_rel_type: null,
    reasoning: "Character likely lives here",
    confidence: 0.85,
    story_relevance: 8,
    ...overrides,
  } as ConnectionSuggestion;
}

function createConsistencyIssue(overrides: Partial<ConsistencyIssue> = {}): ConsistencyIssue {
  return {
    finding_index: 0,
    category: "timeline",
    entity_ids: ["entity-1", "entity-2"],
    entity_names: ["Anna", "Johann"],
    description: "Timeline inconsistency detected",
    contradiction: "Events happen in wrong order",
    suggested_resolution: "Reorder events in chapter 3",
    severity: "critical",
    confidence: 0.9,
    ...overrides,
  } as ConsistencyIssue;
}

// ---------------------------------------------------------------------------
// Tests — GapCard
// ---------------------------------------------------------------------------

describe("GapCard", () => {
  it("renders severity badge", () => {
    render(<GapCard gap={createGap()} t={t} />);

    expect(screen.getByText("major")).toBeDefined();
  });

  it("renders description", () => {
    render(<GapCard gap={createGap()} t={t} />);

    expect(screen.getByText("Character lacks backstory details")).toBeDefined();
  });

  it("renders entity name when present", () => {
    render(<GapCard gap={createGap()} t={t} />);

    expect(screen.getByText("Anna")).toBeDefined();
  });

  it("renders gap type formatted", () => {
    render(<GapCard gap={createGap()} t={t} />);

    expect(screen.getByText("missing field")).toBeDefined();
  });

  it("renders without entity name when absent", () => {
    render(<GapCard gap={createGap({ entity_name: undefined })} t={t} />);

    expect(screen.queryByText("Anna")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Tests — ConnectionCard
// ---------------------------------------------------------------------------

describe("ConnectionCard", () => {
  it("renders source and target names", () => {
    render(
      <ConnectionCard
        connection={createConnection()}
        isSelected={false}
        onToggle={vi.fn()}
        t={t}
      />,
    );

    expect(screen.getByText("Anna")).toBeDefined();
    expect(screen.getByText("Berlin")).toBeDefined();
  });

  it("shows confidence percentage", () => {
    render(
      <ConnectionCard
        connection={createConnection()}
        isSelected={false}
        onToggle={vi.fn()}
        t={t}
      />,
    );

    // Confidence text is split across elements: "85% worldbuilding.confidence"
    const confidenceEl = screen.getByText(/worldbuilding\.confidence/);
    expect(confidenceEl).toBeDefined();
    expect(confidenceEl.textContent).toContain("85%");
  });

  it("shows suggested relationship type", () => {
    render(
      <ConnectionCard
        connection={createConnection()}
        isSelected={false}
        onToggle={vi.fn()}
        t={t}
      />,
    );

    expect(screen.getByText("lives_in")).toBeDefined();
  });

  it("calls onToggle when clicked", () => {
    const onToggle = vi.fn();
    render(
      <ConnectionCard
        connection={createConnection()}
        isSelected={false}
        onToggle={onToggle}
        t={t}
      />,
    );

    fireEvent.click(screen.getByText("Anna").closest("button")!);
    expect(onToggle).toHaveBeenCalled();
  });

  it("shows selected state styling", () => {
    render(<ConnectionCard connection={createConnection()} isSelected onToggle={vi.fn()} t={t} />);

    expect(screen.getByText("kb.willApply")).toBeDefined();
  });

  it("shows reasoning when present", () => {
    render(
      <ConnectionCard
        connection={createConnection()}
        isSelected={false}
        onToggle={vi.fn()}
        t={t}
      />,
    );

    expect(screen.getByText("Character likely lives here")).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// Tests — ConsistencyCard
// ---------------------------------------------------------------------------

describe("ConsistencyCard", () => {
  it("renders severity badge", () => {
    render(<ConsistencyCard issue={createConsistencyIssue()} t={t} />);

    expect(screen.getByText("critical")).toBeDefined();
  });

  it("renders description", () => {
    render(<ConsistencyCard issue={createConsistencyIssue()} t={t} />);

    expect(screen.getByText("Timeline inconsistency detected")).toBeDefined();
  });

  it("renders contradiction", () => {
    render(<ConsistencyCard issue={createConsistencyIssue()} t={t} />);

    // The label is rendered as "worldbuilding.contradiction:" (with colon in same span)
    const label = screen.getByText(/worldbuilding\.contradiction/);
    expect(label).toBeDefined();
    expect(screen.getByText("Events happen in wrong order")).toBeDefined();
  });

  it("renders suggested resolution", () => {
    render(<ConsistencyCard issue={createConsistencyIssue()} t={t} />);

    // The label is rendered as "worldbuilding.resolution:" (with colon in same span)
    const label = screen.getByText(/worldbuilding\.resolution/);
    expect(label).toBeDefined();
    expect(screen.getByText("Reorder events in chapter 3")).toBeDefined();
  });

  it("shows confidence percentage", () => {
    render(<ConsistencyCard issue={createConsistencyIssue()} t={t} />);

    // Confidence text is in same element: "90% worldbuilding.confidence"
    const el = screen.getByText(/worldbuilding\.confidence/);
    expect(el.textContent).toContain("90%");
  });

  it("shows entity count", () => {
    render(<ConsistencyCard issue={createConsistencyIssue()} t={t} />);

    const el = screen.getByText(/worldbuilding\.entities/);
    expect(el.textContent).toContain("2");
  });
});

// ---------------------------------------------------------------------------
// Tests — groupByCategory
// ---------------------------------------------------------------------------

describe("groupByCategory", () => {
  it("groups issues by category", () => {
    const issues = [
      createConsistencyIssue({ category: "timeline" }),
      createConsistencyIssue({ category: "timeline", finding_index: 1 }),
      createConsistencyIssue({ category: "character", finding_index: 2 }),
    ];

    const result = groupByCategory(issues);

    expect(result.timeline).toHaveLength(2);
    expect(result.character).toHaveLength(1);
  });

  it("returns empty object for empty array", () => {
    const result = groupByCategory([]);
    expect(Object.keys(result)).toHaveLength(0);
  });
});
