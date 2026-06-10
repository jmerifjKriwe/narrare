/**
 * Rendering tests for KBSessionFieldList.
 *
 * Covers: all field rendering, progress text/bar, "Suggest AI" button visibility,
 * source badges, AI suggestion display, empty state.
 */

import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { KBSessionFieldList } from "@/components/studio/kb/KBSessionFieldList";
import type { KBCreationSession } from "@/lib/api/kb-sessions";
import { defaultProps, mockSession } from "./setup";

describe("KBSessionFieldList — rendering", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders all fields grouped by status", () => {
    render(<KBSessionFieldList {...defaultProps} />);

    expect(screen.getByText("Name")).toBeDefined();
    expect(screen.getByText("Description")).toBeDefined();
    expect(screen.getByText("Background")).toBeDefined();
    expect(screen.getByText("Affiliation")).toBeDefined();
  });

  it("shows progress text", () => {
    render(<KBSessionFieldList {...defaultProps} />);

    expect(screen.getByText("kb.sessionProgress")).toBeDefined();
  });

  it("shows progress bar", () => {
    const { container } = render(<KBSessionFieldList {...defaultProps} />);

    const bars = container.querySelectorAll(".rounded-full");
    expect(bars.length).toBeGreaterThanOrEqual(1);
  });

  it("shows 'Suggest AI' button on empty fields", () => {
    render(<KBSessionFieldList {...defaultProps} />);

    const suggestButtons = screen.getAllByText("kb.suggestAI");
    expect(suggestButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("does not show 'Suggest AI' on fields that already have values", () => {
    const singleEmptySession: KBCreationSession = {
      ...mockSession,
      fields: [
        {
          field_key: "name",
          label: "Name",
          field_type: "text",
          required: true,
          source: "user",
          user_value: "Anna",
          ai_suggested_value: undefined,
          ai_reasoning: undefined,
          final_value: "Anna",
        },
        {
          field_key: "description",
          label: "Description",
          field_type: "text",
          required: false,
          source: "user",
          user_value: "A character",
          ai_suggested_value: undefined,
          ai_reasoning: undefined,
          final_value: "A character",
        },
      ],
    };

    render(<KBSessionFieldList {...defaultProps} session={singleEmptySession} />);

    expect(screen.queryByText("kb.suggestAI")).toBeNull();
  });

  it("shows source badges for filled fields", () => {
    render(<KBSessionFieldList {...defaultProps} />);

    expect(screen.getByText("kb.source_ai")).toBeDefined();
  });

  it("shows AI suggestion with accept/reject buttons", () => {
    render(<KBSessionFieldList {...defaultProps} />);

    expect(screen.getByText("aiActions.reject")).toBeDefined();
    expect(screen.getByText("aiActions.accept")).toBeDefined();
    expect(screen.getByText("A historian from a small town.")).toBeDefined();
  });

  it("shows ai_reasoning for AI suggestions", () => {
    render(<KBSessionFieldList {...defaultProps} />);

    expect(screen.getByText("Common background archetype.")).toBeDefined();
  });

  it("renders empty state when no fields", () => {
    const emptySessionNoFields: KBCreationSession = {
      ...mockSession,
      fields: [],
    };

    render(<KBSessionFieldList {...defaultProps} session={emptySessionNoFields} />);

    expect(screen.getByText("kb.sessionProgress")).toBeDefined();
  });
});
