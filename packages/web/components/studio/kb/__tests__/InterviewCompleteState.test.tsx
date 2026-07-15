/**
 * InterviewCompleteState tests — completion screen with Q&A history toggle.
 *
 * Tests:
 * - Renders the "show history" toggle button
 * - History timeline is NOT visible until toggled
 * - Clicking the toggle reveals the Q&A pairs from the interview
 * - Toggling again hides the history
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { InterviewCompleteState } from "@/components/studio/kb/InterviewCompleteState";
import type { KBCreationField } from "@/lib/api/kb-sessions";
import type { InterviewQAEntry } from "@/lib/hooks/use-interview-history";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const fields: KBCreationField[] = [
  {
    field_key: "name",
    label: "Name",
    field_type: "text",
    required: true,
    source: "user",
  },
];

const history: InterviewQAEntry[] = [
  {
    question: "What is this character's name?",
    answer: "Anna Schmidt",
    fieldKey: "name",
  },
];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("InterviewCompleteState — History access", () => {
  it("renders the show-history toggle button", () => {
    render(
      <InterviewCompleteState
        onRequestMoreQuestions={vi.fn()}
        onBack={vi.fn()}
        history={history}
        fields={fields}
      />,
    );

    expect(screen.getByText("kb.showInterviewHistory")).toBeDefined();
  });

  it("does not show Q&A pairs before the history is toggled", () => {
    render(
      <InterviewCompleteState
        onRequestMoreQuestions={vi.fn()}
        onBack={vi.fn()}
        history={history}
        fields={fields}
      />,
    );

    expect(screen.queryByText("What is this character's name?")).toBeNull();
    expect(screen.queryByText("Anna Schmidt")).toBeNull();
  });

  it("reveals the Q&A history when the toggle is clicked", () => {
    render(
      <InterviewCompleteState
        onRequestMoreQuestions={vi.fn()}
        onBack={vi.fn()}
        history={history}
        fields={fields}
      />,
    );

    fireEvent.click(screen.getByText("kb.showInterviewHistory"));

    expect(screen.getByText("What is this character's name?")).toBeDefined();
    expect(screen.getByText("Anna Schmidt")).toBeDefined();
  });

  it("hides the history when toggled a second time", () => {
    render(
      <InterviewCompleteState
        onRequestMoreQuestions={vi.fn()}
        onBack={vi.fn()}
        history={history}
        fields={fields}
      />,
    );

    const toggle = screen.getByText("kb.showInterviewHistory");
    fireEvent.click(toggle); // show
    expect(screen.getByText("Anna Schmidt")).toBeDefined();

    fireEvent.click(screen.getByText("kb.hideInterviewHistory")); // hide
    expect(screen.queryByText("Anna Schmidt")).toBeNull();
  });
});
