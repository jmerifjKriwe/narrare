/**
 * InterviewHistory tests — Q&A review timeline with keyword search.
 *
 * Tests the history presentation component:
 * - Renders all Q&A pairs (question, answer, field badge)
 * - Search filters pairs by keyword in question or answer
 * - Search is case-insensitive
 * - Empty state when no pairs match the search
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { InterviewHistory } from "@/components/studio/kb/InterviewHistory";
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
  {
    field_key: "description",
    label: "Description",
    field_type: "text",
    required: false,
    source: "user",
  },
];

const entries: InterviewQAEntry[] = [
  {
    question: "What is this character's name?",
    answer: "Anna Schmidt",
    fieldKey: "name",
  },
  {
    question: "Describe the character's appearance.",
    answer: "Tall with dark hair",
    fieldKey: "description",
  },
];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("InterviewHistory — Rendering", () => {
  it("renders all Q&A pairs with question, answer, and field badge", () => {
    render(<InterviewHistory entries={entries} fields={fields} />);

    // Questions rendered (muted)
    expect(screen.getByText("What is this character's name?")).toBeDefined();
    expect(screen.getByText("Describe the character's appearance.")).toBeDefined();

    // Answers rendered (foreground)
    expect(screen.getByText("Anna Schmidt")).toBeDefined();
    expect(screen.getByText("Tall with dark hair")).toBeDefined();

    // Field labels rendered as badges (resolved from fields prop)
    expect(screen.getByText("Name")).toBeDefined();
    expect(screen.getByText("Description")).toBeDefined();
  });

  it("falls back to field key when label is missing", () => {
    const entryWithUnknownField: InterviewQAEntry[] = [
      {
        question: "Some question?",
        answer: "Some answer",
        fieldKey: "unknown_field",
      },
    ];

    render(<InterviewHistory entries={entryWithUnknownField} fields={fields} />);

    // Unknown field key shown verbatim as the badge
    expect(screen.getByText("unknown_field")).toBeDefined();
  });
});

describe("InterviewHistory — Search", () => {
  it("filters pairs by keyword in the question", () => {
    render(<InterviewHistory entries={entries} fields={fields} />);

    const search = screen.getByPlaceholderText("kb.interviewHistorySearch");
    fireEvent.change(search, { target: { value: "appearance" } });

    expect(screen.getByText("Describe the character's appearance.")).toBeDefined();
    expect(screen.queryByText("What is this character's name?")).toBeNull();
  });

  it("filters pairs by keyword in the answer", () => {
    render(<InterviewHistory entries={entries} fields={fields} />);

    const search = screen.getByPlaceholderText("kb.interviewHistorySearch");
    fireEvent.change(search, { target: { value: "Anna" } });

    expect(screen.getByText("Anna Schmidt")).toBeDefined();
    expect(screen.queryByText("Tall with dark hair")).toBeNull();
  });

  it("search is case-insensitive", () => {
    render(<InterviewHistory entries={entries} fields={fields} />);

    const search = screen.getByPlaceholderText("kb.interviewHistorySearch");
    fireEvent.change(search, { target: { value: "ANNA" } });

    expect(screen.getByText("Anna Schmidt")).toBeDefined();
    expect(screen.queryByText("Tall with dark hair")).toBeNull();
  });

  it("shows empty state when no pairs match the search", () => {
    render(<InterviewHistory entries={entries} fields={fields} />);

    const search = screen.getByPlaceholderText("kb.interviewHistorySearch");
    fireEvent.change(search, { target: { value: "nonexistent-term-xyz" } });

    expect(screen.getByText("kb.interviewHistoryEmpty")).toBeDefined();
    expect(screen.queryByText("Anna Schmidt")).toBeNull();
  });

  it("shows all pairs again after clearing the search", () => {
    render(<InterviewHistory entries={entries} fields={fields} />);

    const search = screen.getByPlaceholderText("kb.interviewHistorySearch");
    fireEvent.change(search, { target: { value: "Anna" } });
    expect(screen.queryByText("Tall with dark hair")).toBeNull();

    fireEvent.change(search, { target: { value: "" } });
    expect(screen.getByText("Tall with dark hair")).toBeDefined();
  });
});
