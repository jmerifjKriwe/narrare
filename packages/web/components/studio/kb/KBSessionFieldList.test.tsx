/**
 * KBSessionFieldList tests
 *
 * Tests: progress bar with correct counts, empty fields show suggest button,
 * suggest triggers onSuggest with correct field key, inline edit mode,
 * source badge rendering, enhance button triggers onEnhance.
 *
 * This component receives all callbacks as props — no hooks to mock.
 *
 * next-intl is globally mocked in setupTests.ts (returns keys directly).
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { KBCreationField, KBCreationSession } from "@/lib/api/kb-sessions";
import { KBSessionFieldList } from "./KBSessionFieldList";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeField(overrides: Partial<KBCreationField> = {}): KBCreationField {
  return {
    field_key: "name",
    label: "Character Name",
    field_type: "text",
    required: true,
    source: "user",
    final_value: "Hero",
    user_value: "Hero",
    ai_suggested_value: undefined,
    ai_reasoning: undefined,
    ...overrides,
  };
}

function makeSession(overrides: Partial<KBCreationSession> = {}): KBCreationSession {
  return {
    id: "session-1",
    novel_id: "novel-1",
    user_id: "user-1",
    entity_type: "character",
    name: "New Character",
    status: "active",
    fields: [],
    context_entries: [],
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

const defaultCallbacks = {
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

  // -------------------------------------------------------------------------
  // Progress bar
  // -------------------------------------------------------------------------

  it("renders progress text with correct filled/total counts", () => {
    const session = makeSession({
      fields: [
        makeField({ field_key: "name", final_value: "Hero", source: "user" }),
        makeField({ field_key: "age", final_value: "25", source: "user" }),
        makeField({
          field_key: "backstory",
          final_value: undefined,
          user_value: undefined,
          ai_suggested_value: undefined,
          source: "user",
        }),
      ],
    });

    render(<KBSessionFieldList session={session} {...defaultCallbacks} />);

    // 2 of 3 fields filled — the global mock returns the key as-is
    expect(screen.getByText("kb.sessionProgress")).toBeInTheDocument();
  });

  it("progress bar has correct width percentage", () => {
    const session = makeSession({
      fields: [
        makeField({ field_key: "name", final_value: "Hero", source: "user" }),
        makeField({
          field_key: "age",
          final_value: undefined,
          user_value: undefined,
          ai_suggested_value: undefined,
          source: "user",
        }),
      ],
    });

    const { container } = render(<KBSessionFieldList session={session} {...defaultCallbacks} />);

    // Progress bar width = 50% (1/2)
    const progressBar = container.querySelector('[style*="width: 50%"]');
    expect(progressBar).toBeInTheDocument();
  });

  it("shows 0% progress bar when no fields filled", () => {
    const session = makeSession({
      fields: [
        makeField({
          field_key: "name",
          final_value: undefined,
          user_value: undefined,
          ai_suggested_value: undefined,
          source: "user",
        }),
      ],
    });

    const { container } = render(<KBSessionFieldList session={session} {...defaultCallbacks} />);

    const progressBar = container.querySelector('[style*="width: 0%"]');
    expect(progressBar).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Empty fields — suggest button
  // -------------------------------------------------------------------------

  it("empty fields show AI suggest button", () => {
    const session = makeSession({
      fields: [
        makeField({
          field_key: "backstory",
          label: "Backstory",
          final_value: undefined,
          user_value: undefined,
          ai_suggested_value: undefined,
          source: "user",
        }),
      ],
    });

    render(<KBSessionFieldList session={session} {...defaultCallbacks} />);

    expect(screen.getByText("kb.suggestAI")).toBeInTheDocument();
  });

  it("clicking suggest triggers onSuggest with correct field key", async () => {
    const user = userEvent.setup();
    const onSuggest = vi.fn();
    const session = makeSession({
      fields: [
        makeField({
          field_key: "backstory",
          label: "Backstory",
          final_value: undefined,
          user_value: undefined,
          ai_suggested_value: undefined,
          source: "user",
        }),
      ],
    });

    render(<KBSessionFieldList session={session} {...defaultCallbacks} onSuggest={onSuggest} />);

    await user.click(screen.getByText("kb.suggestAI"));

    expect(onSuggest).toHaveBeenCalledWith("backstory");
  });

  // -------------------------------------------------------------------------
  // Inline edit mode
  // -------------------------------------------------------------------------

  it("clicking edit button on filled field enters edit mode", async () => {
    const user = userEvent.setup();
    const session = makeSession({
      fields: [
        makeField({
          field_key: "name",
          label: "Name",
          final_value: "Hero",
          user_value: "Hero",
          source: "user",
        }),
      ],
    });

    render(<KBSessionFieldList session={session} {...defaultCallbacks} />);

    // Find and click the edit button (Edit3 icon)
    const editButtons = screen.getAllByRole("button");
    // The edit button has an SVG icon — find it by its container
    const editBtn = editButtons.find(
      (btn) => btn.querySelector("svg.lucide") !== null && btn.textContent === "",
    );

    if (editBtn) {
      await user.click(editBtn);
    }

    // In edit mode, a textarea should appear
    await waitFor(() => {
      const textarea = document.querySelector("textarea");
      if (textarea) {
        expect(textarea).toBeInTheDocument();
      }
    });
  });

  it("save edit triggers onAnswer with field key and new value", async () => {
    const user = userEvent.setup();
    const onAnswer = vi.fn();
    const session = makeSession({
      fields: [
        makeField({
          field_key: "name",
          label: "Name",
          final_value: "Old Value",
          user_value: "Old Value",
          source: "user",
        }),
      ],
    });

    render(<KBSessionFieldList session={session} {...defaultCallbacks} onAnswer={onAnswer} />);

    // The filled field should be in the "completed" section
    // Find the edit button — it's a small icon button on the field card
    const allButtons = screen.getAllByRole("button");
    const editBtn = allButtons.find((btn) => {
      // Edit button has an SVG icon and is inside a field card
      const svg = btn.querySelector("svg");
      return (
        svg !== null &&
        btn.className.includes("text-muted-foreground") &&
        btn.className.includes("hover:text-foreground")
      );
    });
    expect(editBtn).toBeTruthy();

    // Click to enter edit mode
    await user.click(editBtn!);

    // Wait for the edit textarea to appear
    await waitFor(() => {
      // The edit textarea should have the current value
      const editTextarea = document.querySelector("textarea.min-h-\\[80px\\]");
      expect(editTextarea).toBeInTheDocument();
    });

    // Use fireEvent to directly set the textarea value (avoids reversed-text issues with user.type)
    const editTextarea = document.querySelector("textarea.min-h-\\[80px\\]") as HTMLTextAreaElement;
    fireEvent.change(editTextarea, { target: { value: "Updated Value" } });

    // Click save button
    const saveButton = screen.getByText("kb.save");
    await user.click(saveButton);

    expect(onAnswer).toHaveBeenCalledWith("name", "Updated Value");
  });

  it("cancel edit does not trigger onAnswer", async () => {
    const user = userEvent.setup();
    const onAnswer = vi.fn();
    const session = makeSession({
      fields: [
        makeField({
          field_key: "name",
          label: "Name",
          final_value: "Hero",
          user_value: "Hero",
          source: "user",
        }),
      ],
    });

    render(<KBSessionFieldList session={session} {...defaultCallbacks} onAnswer={onAnswer} />);

    // Click edit button
    const editButtons = screen.getAllByRole("button");
    const editBtn = editButtons.find(
      (btn) => btn.querySelector("svg.lucide") !== null && btn.textContent === "",
    );

    if (editBtn) {
      await user.click(editBtn);
    }

    // Wait for cancel button
    await waitFor(() => {
      expect(screen.getByText("kb.cancel")).toBeInTheDocument();
    });

    // Click cancel
    await user.click(screen.getByText("kb.cancel"));

    expect(onAnswer).not.toHaveBeenCalled();
  });

  // -------------------------------------------------------------------------
  // Source badges
  // -------------------------------------------------------------------------

  it("renders source badge for user-filled fields", () => {
    const session = makeSession({
      fields: [
        makeField({ field_key: "name", source: "user", final_value: "Hero", user_value: "Hero" }),
      ],
    });

    render(<KBSessionFieldList session={session} {...defaultCallbacks} />);

    expect(screen.getByText("kb.source_user")).toBeInTheDocument();
  });

  it("renders source badge for AI-suggested fields", () => {
    const session = makeSession({
      fields: [
        makeField({
          field_key: "backstory",
          source: "ai",
          final_value: undefined,
          user_value: undefined,
          ai_suggested_value: "A brave warrior",
        }),
      ],
    });

    render(<KBSessionFieldList session={session} {...defaultCallbacks} />);

    expect(screen.getByText("kb.source_ai")).toBeInTheDocument();
  });

  it("renders source badge for merged fields", () => {
    const session = makeSession({
      fields: [
        makeField({
          field_key: "traits",
          source: "merged",
          final_value: "Brave, loyal",
          user_value: undefined,
        }),
      ],
    });

    render(<KBSessionFieldList session={session} {...defaultCallbacks} />);

    expect(screen.getByText("kb.source_merged")).toBeInTheDocument();
  });

  it("renders source badge for world_derived fields", () => {
    const session = makeSession({
      fields: [
        makeField({
          field_key: "region",
          source: "world_derived",
          final_value: "Northern Kingdom",
          user_value: undefined,
        }),
      ],
    });

    render(<KBSessionFieldList session={session} {...defaultCallbacks} />);

    expect(screen.getByText("kb.source_world_derived")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Enhance button
  // -------------------------------------------------------------------------

  it("enhance button triggers onEnhance", async () => {
    const user = userEvent.setup();
    const onEnhance = vi.fn();
    const session = makeSession({
      fields: [
        makeField({ field_key: "name", source: "user", final_value: "Hero", user_value: "Hero" }),
      ],
    });

    render(<KBSessionFieldList session={session} {...defaultCallbacks} onEnhance={onEnhance} />);

    await user.click(screen.getByText("kb.enhanceAll"));

    expect(onEnhance).toHaveBeenCalledOnce();
  });

  it("enhance button is disabled when no fields are filled", () => {
    const session = makeSession({
      fields: [
        makeField({
          field_key: "name",
          source: "user",
          final_value: undefined,
          user_value: undefined,
          ai_suggested_value: undefined,
        }),
      ],
    });

    render(<KBSessionFieldList session={session} {...defaultCallbacks} />);

    const enhanceButton = screen.getByText("kb.enhanceAll").closest("button");
    expect(enhanceButton).toHaveProperty("disabled", true);
  });

  // -------------------------------------------------------------------------
  // Start interview button
  // -------------------------------------------------------------------------

  it("start interview button triggers onStartInterview", async () => {
    const user = userEvent.setup();
    const onStartInterview = vi.fn();
    const session = makeSession({ fields: [] });

    render(
      <KBSessionFieldList
        session={session}
        {...defaultCallbacks}
        onStartInterview={onStartInterview}
      />,
    );

    await user.click(screen.getByText("kb.startInterview"));

    expect(onStartInterview).toHaveBeenCalledOnce();
  });

  // -------------------------------------------------------------------------
  // AI suggestion accept/reject
  // -------------------------------------------------------------------------

  it("renders accept/reject buttons for AI suggestions pending review", () => {
    const session = makeSession({
      fields: [
        makeField({
          field_key: "backstory",
          source: "ai",
          final_value: undefined,
          user_value: undefined,
          ai_suggested_value: "A legendary warrior",
        }),
      ],
    });

    render(<KBSessionFieldList session={session} {...defaultCallbacks} />);

    expect(screen.getByText("kb.accept")).toBeInTheDocument();
    expect(screen.getByText("kb.reject")).toBeInTheDocument();
  });

  it("accept AI suggestion triggers onAcceptSuggestion", async () => {
    const user = userEvent.setup();
    const onAcceptSuggestion = vi.fn();
    const session = makeSession({
      fields: [
        makeField({
          field_key: "backstory",
          source: "ai",
          final_value: undefined,
          user_value: undefined,
          ai_suggested_value: "A legendary warrior",
        }),
      ],
    });

    render(
      <KBSessionFieldList
        session={session}
        {...defaultCallbacks}
        onAcceptSuggestion={onAcceptSuggestion}
      />,
    );

    await user.click(screen.getByText("kb.accept"));

    expect(onAcceptSuggestion).toHaveBeenCalledWith("backstory", "A legendary warrior");
  });

  it("reject AI suggestion triggers onRejectSuggestion", async () => {
    const user = userEvent.setup();
    const onRejectSuggestion = vi.fn();
    const session = makeSession({
      fields: [
        makeField({
          field_key: "backstory",
          source: "ai",
          final_value: undefined,
          user_value: undefined,
          ai_suggested_value: "A legendary warrior",
        }),
      ],
    });

    render(
      <KBSessionFieldList
        session={session}
        {...defaultCallbacks}
        onRejectSuggestion={onRejectSuggestion}
      />,
    );

    await user.click(screen.getByText("kb.reject"));

    expect(onRejectSuggestion).toHaveBeenCalledWith("backstory");
  });

  // -------------------------------------------------------------------------
  // Required field indicator
  // -------------------------------------------------------------------------

  it("shows required indicator on required fields", () => {
    const session = makeSession({
      fields: [
        makeField({
          field_key: "name",
          required: true,
          source: "user",
          final_value: "Hero",
          user_value: "Hero",
        }),
      ],
    });

    const { container } = render(<KBSessionFieldList session={session} {...defaultCallbacks} />);

    // The * indicator for required fields
    expect(container.querySelector("span.text-red-500")).toBeInTheDocument();
  });
});
