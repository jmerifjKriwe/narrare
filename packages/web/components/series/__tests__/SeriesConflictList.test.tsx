/**
 * SeriesConflictList component tests (Spec 4 Task 4).
 *
 * Pure presentational component — no hooks to mock. Verifies the empty
 * (no-conflicts) state, the severity badges (error vs warning), and that each
 * conflict renders the Canon statement, the chapter excerpt, and the
 * explanation.
 *
 * Conventions: setupTests.ts returns i18n KEY STRINGS verbatim.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SeriesConflictList } from "@/components/series/SeriesConflictList";
import type { CanonConflict } from "@/types";

function makeConflict(overrides: Partial<CanonConflict> = {}): CanonConflict {
  return {
    canon_entry_slug: "character-elara-eye-color",
    canon_entry_name: "Elara — Eye Color",
    chapter_text_excerpt: "Elara's blue eyes glinted.",
    canon_statement: "Elara has green eyes.",
    explanation: "Canon fixes Elara's eyes as green; the chapter says blue.",
    severity: "error",
    ...overrides,
  };
}

describe("SeriesConflictList", () => {
  it("renders the positive no-conflicts state when the list is empty", () => {
    render(<SeriesConflictList conflicts={[]} />);
    expect(screen.getByTestId("series-conflicts-empty").textContent).toContain(
      "series.drift.noConflicts",
    );
    expect(screen.queryByTestId("series-conflict-item")).toBeNull();
  });

  it("renders the agent summary when provided", () => {
    render(<SeriesConflictList conflicts={[]} summary="Band II is clean." />);
    expect(screen.getByText("Band II is clean.")).toBeDefined();
  });

  it("renders one item per conflict with its severity badge", () => {
    const conflicts = [
      makeConflict({ severity: "error", canon_entry_name: "Elara — Eye Color" }),
      makeConflict({
        severity: "warning",
        canon_entry_slug: "world-magic-rules",
        canon_entry_name: "Magic Rules",
      }),
    ];
    render(<SeriesConflictList conflicts={conflicts} />);

    const items = screen.getAllByTestId("series-conflict-item");
    expect(items).toHaveLength(2);
    expect(screen.getByTestId("series-conflict-severity-error").textContent).toContain(
      "series.drift.severity.error",
    );
    expect(screen.getByTestId("series-conflict-severity-warning").textContent).toContain(
      "series.drift.severity.warning",
    );
  });

  it("renders the canon statement, the chapter excerpt, and the explanation", () => {
    render(<SeriesConflictList conflicts={[makeConflict()]} />);
    const item = screen.getByTestId("series-conflict-item");
    expect(item.textContent).toContain("Elara has green eyes.");
    expect(item.textContent).toContain("Elara's blue eyes glinted.");
    expect(item.textContent).toContain("Canon fixes Elara's eyes as green; the chapter says blue.");
  });
});
