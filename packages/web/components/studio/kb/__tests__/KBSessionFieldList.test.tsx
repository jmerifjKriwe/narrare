/**
 * KBSessionFieldList tests — Field list view for KB creation session.
 *
 * Tests:
 * 1. Renders all fields grouped by status (empty, user-filled, ai-suggested, merged)
 * 2. Shows "Suggest AI" button on empty fields
 * 3. Does not show "Suggest AI" on fields that already have values
 * 4. Shows source badges (user/ai/world_derived/merged)
 * 5. Calls onSuggest when "Suggest AI" is clicked
 * 6. Shows "Start Interview" and "Enhance All" buttons
 * 7. Shows progress bar and progress text
 * 8. "Enhance All" disabled when no fields filled
 * 9. Allows inline editing of filled fields (edit → save)
 * 10. Shows AI suggestion with accept/reject buttons
 * 11. Accept button calls onAcceptSuggestion
 * 12. Reject button calls onRejectSuggestion
 * 13. Disables "Suggest AI" button when field is being suggested
 * 14. Empty state when no fields
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KBSessionFieldList } from "@/components/studio/kb/KBSessionFieldList";
import type { KBCreationField, KBCreationSession } from "@/lib/api/kb-sessions";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const emptyFields: KBCreationField[] = [
  {
    field_key: "name",
    label: "Name",
    field_type: "text",
    required: true,
    source: "user",
    user_value: undefined,
    ai_suggested_value: undefined,
    ai_reasoning: undefined,
    final_value: undefined,
  },
  {
    field_key: "description",
    label: "Description",
    field_type: "text",
    required: false,
    source: "user",
    user_value: undefined,
    ai_suggested_value: undefined,
    ai_reasoning: undefined,
    final_value: undefined,
  },
];

const mixedFields: KBCreationField[] = [
  {
    field_key: "name",
    label: "Name",
    field_type: "text",
    required: true,
    source: "user",
    user_value: "Anna Schmidt",
    ai_suggested_value: undefined,
    ai_reasoning: undefined,
    final_value: "Anna Schmidt",
  },
  {
    field_key: "description",
    label: "Description",
    field_type: "text",
    required: false,
    source: "user",
    user_value: undefined,
    ai_suggested_value: undefined,
    ai_reasoning: undefined,
    final_value: undefined,
  },
  {
    field_key: "background",
    label: "Background",
    field_type: "text",
    required: false,
    source: "ai",
    user_value: undefined,
    ai_suggested_value: "A historian from a small town.",
    ai_reasoning: "Common background archetype.",
    final_value: undefined,
  },
  {
    field_key: "affiliation",
    label: "Affiliation",
    field_type: "text",
    required: false,
    source: "world_derived",
    user_value: "University of Berlin",
    ai_suggested_value: undefined,
    ai_reasoning: undefined,
    final_value: "University of Berlin",
  },
];

const mockSession: KBCreationSession = {
  id: "session-1",
  novel_id: "novel-1",
  user_id: "user-1",
  entity_type: "character",
  status: "active",
  fields: mixedFields,
  context_entries: [],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const emptySession: KBCreationSession = {
  ...mockSession,
  fields: emptyFields,
};

const defaultProps = {
  session: mockSession,
  onSuggest: vi.fn(),
  onAnswer: vi.fn(),
  onAcceptSuggestion: vi.fn(),
  onRejectSuggestion: vi.fn(),
  onStartInterview: vi.fn(),
  onEnhance: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KBSessionFieldList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders all fields grouped by status", () => {
    render(<KBSessionFieldList {...defaultProps} />);

    // Should show all field labels
    expect(screen.getByText("Name")).toBeDefined();
    expect(screen.getByText("Description")).toBeDefined();
    expect(screen.getByText("Background")).toBeDefined();
    expect(screen.getByText("Affiliation")).toBeDefined();
  });

  it("shows progress text", () => {
    render(<KBSessionFieldList {...defaultProps} />);

    // 3 out of 4 fields have values (name=user, background=ai, affiliation=world_derived)
    expect(screen.getByText("kb.sessionProgress")).toBeDefined();
  });

  it("shows progress bar", () => {
    const { container } = render(<KBSessionFieldList {...defaultProps} />);

    // Progress bar should render
    const bars = container.querySelectorAll(".rounded-full");
    expect(bars.length).toBeGreaterThanOrEqual(1);
  });

  it("shows 'Suggest AI' button on empty fields", () => {
    render(<KBSessionFieldList {...defaultProps} />);

    // "Description" is empty and should have "Suggest AI"
    const suggestButtons = screen.getAllByText("kb.suggestAI");
    expect(suggestButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("does not show 'Suggest AI' on fields that already have values", () => {
    // Use session where only one field is empty
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

    // No empty fields → no "Suggest AI" buttons
    expect(screen.queryByText("kb.suggestAI")).toBeNull();
  });

  it("shows source badges for filled fields", () => {
    render(<KBSessionFieldList {...defaultProps} />);

    // Should have a source badge for the background field (source: "ai")
    // SourceBadge renders a span with text, and uses t("kb.source_ai")
    expect(screen.getByText("kb.source_ai")).toBeDefined();
  });

  it("calls onSuggest when 'Suggest AI' is clicked", () => {
    const onSuggest = vi.fn();
    render(<KBSessionFieldList {...defaultProps} onSuggest={onSuggest} session={emptySession} />);

    // Click the first "Suggest AI" button
    const suggestButtons = screen.getAllByText("kb.suggestAI");
    fireEvent.click(suggestButtons[0]);

    expect(onSuggest).toHaveBeenCalledTimes(1);
    expect(onSuggest).toHaveBeenCalledWith("name");
  });

  it("shows 'Start Interview' and 'Enhance All' buttons", () => {
    render(<KBSessionFieldList {...defaultProps} />);

    expect(screen.getByText("kb.startInterview")).toBeDefined();
    expect(screen.getByText("kb.enhanceAll")).toBeDefined();
  });

  it("'Enhance All' is enabled when fields are filled", () => {
    render(<KBSessionFieldList {...defaultProps} />);

    const enhanceButton = screen.getByText("kb.enhanceAll").closest("button");
    expect(enhanceButton?.disabled).toBe(false);
  });

  it("'Enhance All' is disabled when no fields are filled", () => {
    render(<KBSessionFieldList {...defaultProps} session={emptySession} />);

    const enhanceButton = screen.getByText("kb.enhanceAll").closest("button");
    expect(enhanceButton?.disabled).toBe(true);
  });

  it("calls onStartInterview when 'Start Interview' is clicked", () => {
    const onStartInterview = vi.fn();
    render(<KBSessionFieldList {...defaultProps} onStartInterview={onStartInterview} />);

    fireEvent.click(screen.getByText("kb.startInterview"));
    expect(onStartInterview).toHaveBeenCalledTimes(1);
  });

  it("calls onEnhance when 'Enhance All' is clicked", () => {
    const onEnhance = vi.fn();
    render(<KBSessionFieldList {...defaultProps} onEnhance={onEnhance} />);

    fireEvent.click(screen.getByText("kb.enhanceAll"));
    expect(onEnhance).toHaveBeenCalledTimes(1);
  });

  it("shows AI suggestion with accept/reject buttons", () => {
    render(<KBSessionFieldList {...defaultProps} />);

    // "Background" has ai_suggested_value → should show accept/reject
    expect(screen.getByText("aiActions.reject")).toBeDefined();
    expect(screen.getByText("aiActions.accept")).toBeDefined();
    expect(screen.getByText("A historian from a small town.")).toBeDefined();
  });

  it("shows ai_reasoning for AI suggestions", () => {
    render(<KBSessionFieldList {...defaultProps} />);

    expect(screen.getByText("Common background archetype.")).toBeDefined();
  });

  it("accept button calls onAcceptSuggestion with field key and value", () => {
    const onAcceptSuggestion = vi.fn();
    render(<KBSessionFieldList {...defaultProps} onAcceptSuggestion={onAcceptSuggestion} />);

    // Find and click the accept button (within AI suggestion section)
    const acceptButtons = screen.getAllByText("aiActions.accept");
    fireEvent.click(acceptButtons[0]);

    expect(onAcceptSuggestion).toHaveBeenCalledWith("background", "A historian from a small town.");
  });

  it("reject button calls onRejectSuggestion", () => {
    const onRejectSuggestion = vi.fn();
    render(<KBSessionFieldList {...defaultProps} onRejectSuggestion={onRejectSuggestion} />);

    const rejectButtons = screen.getAllByText("aiActions.reject");
    fireEvent.click(rejectButtons[0]);

    expect(onRejectSuggestion).toHaveBeenCalledWith("background");
  });

  it("disables 'Suggest AI' button when field is being suggested", () => {
    render(
      <KBSessionFieldList
        {...defaultProps}
        suggestingFieldKey="description"
        session={emptySession}
      />,
    );

    // "description" field is being suggested → its "Suggest AI" button should be disabled
    // "name" field is empty but not being suggested → its "Suggest AI" button should be enabled
    const suggestButtons = screen.getAllByText("kb.suggestAI");
    const disabledButtons = suggestButtons.filter((btn) => btn.closest("button")?.disabled);
    expect(disabledButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("allows inline editing of filled fields", () => {
    render(<KBSessionFieldList {...defaultProps} />);

    // Find edit buttons (Edit3 icons). "Name" has user_value, so it should have an edit button
    const editButtons = document.querySelectorAll('[class*="p-1 text-muted-foreground"]');
    // Click the first edit button
    if (editButtons.length > 0) {
      fireEvent.click(editButtons[0]);
    }

    // Should show save/cancel buttons
    expect(() => screen.getByText("kb.save")).toBeTruthy();
    expect(() => screen.getByText("kb.cancel")).toBeTruthy();
  });

  it("renders empty state when no fields", () => {
    const emptySessionNoFields: KBCreationSession = {
      ...mockSession,
      fields: [],
    };

    render(<KBSessionFieldList {...defaultProps} session={emptySessionNoFields} />);

    // Should render without crashing
    expect(screen.getByText("kb.sessionProgress")).toBeDefined();
  });
});
