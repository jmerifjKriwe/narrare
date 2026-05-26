/**
 * FeedbackCard tests — renders feedback items with correct styling.
 *
 * Tests:
 * 1. Renders feedback item with severity badge and category
 * 2. Renders strength item with green tint
 * 3. Renders question item with blue tint
 * 4. Collapsible excerpt shows/hides on click
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  FeedbackCard,
  feedbackCardItem,
  questionCardItem,
  strengthCardItem,
} from "@/components/studio/analysis/FeedbackCard";
import type { BetaFeedbackItem, BetaReaderQuestion, BetaReaderStrength } from "@/lib/api/analysis";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) => {
    if (params) {
      return Object.entries(params).reduce((str, [k, v]) => str.replace(`{${k}}`, String(v)), key);
    }
    return key;
  },
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockFeedback: BetaFeedbackItem = {
  category: "plot",
  severity: "critical",
  location: "Paragraph 3",
  title: "Plot hole: Inconsistent timeline",
  description: "The character references an event that has not happened yet.",
  suggestion: "Remove the reference or add a flashback scene earlier.",
  text_excerpt: "She remembered the battle of Helm's Deep...",
};

const mockStrength: BetaReaderStrength = {
  category: "character",
  title: "Strong character voice",
  description: "The protagonist has a distinctive and consistent voice.",
  text_excerpt: "I never did like mornings, not even as a child.",
};

const mockQuestion: BetaReaderQuestion = {
  category: "prose",
  location: "Paragraph 5",
  question: "Who is speaking in this paragraph?",
  context: "The dialogue tag is missing, making it unclear.",
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("FeedbackCard", () => {
  it("renders feedback item with severity badge and category", () => {
    render(<FeedbackCard item={feedbackCardItem(mockFeedback)} />);

    expect(screen.getByText("severity.critical")).toBeDefined();
    expect(screen.getByText("categories.plot")).toBeDefined();
    expect(screen.getByText("Plot hole: Inconsistent timeline")).toBeDefined();
    expect(
      screen.getByText("The character references an event that has not happened yet."),
    ).toBeDefined();
    expect(screen.getByText("suggestion")).toBeDefined();
    expect(
      screen.getByText("Remove the reference or add a flashback scene earlier."),
    ).toBeDefined();
    expect(screen.getByText("Paragraph 3")).toBeDefined();
  });

  it("renders strength item with green tint", () => {
    render(<FeedbackCard item={strengthCardItem(mockStrength)} />);

    expect(screen.getByText("Strong character voice")).toBeDefined();
    expect(
      screen.getByText("The protagonist has a distinctive and consistent voice."),
    ).toBeDefined();
    expect(screen.getByText("categories.character")).toBeDefined();
    // No severity badge for strengths
    expect(screen.queryByText("severity.critical")).toBeNull();
    expect(screen.queryByText("severity.moderate")).toBeNull();
  });

  it("renders question item with blue tint", () => {
    render(<FeedbackCard item={questionCardItem(mockQuestion)} />);

    expect(screen.getByText("Who is speaking in this paragraph?")).toBeDefined();
    expect(screen.getByText("The dialogue tag is missing, making it unclear.")).toBeDefined();
    expect(screen.getByText("categories.prose")).toBeDefined();
    expect(screen.getByText("Paragraph 5")).toBeDefined();
  });

  it("collapsible excerpt shows/hides on click", () => {
    render(<FeedbackCard item={feedbackCardItem(mockFeedback)} />);

    // Excerpt not visible initially
    expect(screen.queryByText(/She remembered the battle/)).toBeNull();

    // Click to show
    const toggleButton = screen.getByText("excerpt.show");
    fireEvent.click(toggleButton);

    // Excerpt now visible
    expect(screen.getByText(/She remembered the battle/)).toBeDefined();

    // Click to hide
    const hideButton = screen.getByText("excerpt.hide");
    fireEvent.click(hideButton);

    // Excerpt hidden again
    expect(screen.queryByText(/She remembered the battle/)).toBeNull();
  });
});
