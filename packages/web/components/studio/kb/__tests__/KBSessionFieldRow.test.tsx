/**
 * KBSessionFieldRow tests — field row with AI suggest lifecycle (CR-AUFG-07-07).
 *
 * Tests prove:
 * 1. Visible cancel control during suggesting state (§16.2 cancel_ui)
 * 2. Clicking cancel invokes onCancelSuggest (cancel path)
 * 3. Structured error rendering uses i18n key from AIErrorResponse (§16.5)
 * 4. Suggest button disabled while suggesting (loading state)
 * 5. Suggest triggers onSuggest with field key
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KBSessionFieldRow } from "@/components/studio/kb/KBSessionFieldRow";
import type { KBCreationField } from "@/lib/api/kb-sessions";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const emptyField: KBCreationField = {
  field_key: "description",
  label: "Description",
  field_type: "text",
  required: false,
  source: "user",
  user_value: undefined,
  ai_suggested_value: undefined,
  ai_reasoning: undefined,
  final_value: undefined,
};

const structuredError: AIErrorResponse = {
  kind: "http",
  status: 401,
  i18nKey: "aiActions.errorApiKey",
  userMessage: "Your API key is invalid.",
  retryable: false,
  cause: new Error("401"),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KBSessionFieldRow — AI suggest lifecycle (CR-AUFG-07-07)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows visible cancel control when suggesting (§16.2 cancel_ui)", () => {
    render(
      <KBSessionFieldRow
        field={emptyField}
        isEmpty
        suggestingFieldKey="description"
        onCancelSuggest={vi.fn()}
        onSuggest={vi.fn()}
        onAnswer={vi.fn()}
        onAcceptSuggestion={vi.fn()}
        onRejectSuggestion={vi.fn()}
      />,
    );

    // Cancel button must be visible with localized label
    expect(screen.getByText("aiActions.stop")).toBeDefined();
  });

  it("does not show cancel control when not suggesting", () => {
    render(
      <KBSessionFieldRow
        field={emptyField}
        isEmpty
        suggestingFieldKey={null}
        onCancelSuggest={vi.fn()}
        onSuggest={vi.fn()}
        onAnswer={vi.fn()}
        onAcceptSuggestion={vi.fn()}
        onRejectSuggestion={vi.fn()}
      />,
    );

    // No stop button when idle
    expect(screen.queryByText("aiActions.stop")).toBeNull();
    // Suggest button shows default label
    expect(screen.getByText("kb.suggestAI")).toBeDefined();
  });

  it("clicking cancel invokes onCancelSuggest (cancel path)", () => {
    const onCancelSuggest = vi.fn();

    render(
      <KBSessionFieldRow
        field={emptyField}
        isEmpty
        suggestingFieldKey="description"
        onCancelSuggest={onCancelSuggest}
        onSuggest={vi.fn()}
        onAnswer={vi.fn()}
        onAcceptSuggestion={vi.fn()}
        onRejectSuggestion={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText("aiActions.stop"));
    expect(onCancelSuggest).toHaveBeenCalledTimes(1);
  });

  it("renders structured error via i18n key from AIErrorResponse (§16.5)", () => {
    render(
      <KBSessionFieldRow
        field={emptyField}
        isEmpty
        suggestingFieldKey={null}
        suggestionError={structuredError}
        suggestionErrorFieldKey="description"
        onCancelSuggest={vi.fn()}
        onSuggest={vi.fn()}
        onAnswer={vi.fn()}
        onAcceptSuggestion={vi.fn()}
        onRejectSuggestion={vi.fn()}
      />,
    );

    // The alert must render the i18n key from the structured AIErrorResponse,
    // never raw exception text (§16.5, RULE-16).
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toBe("aiActions.errorApiKey");
  });

  it("does not render error for a different field key", () => {
    render(
      <KBSessionFieldRow
        field={emptyField}
        isEmpty
        suggestingFieldKey={null}
        suggestionError={structuredError}
        suggestionErrorFieldKey="other_field"
        onCancelSuggest={vi.fn()}
        onSuggest={vi.fn()}
        onAnswer={vi.fn()}
        onAcceptSuggestion={vi.fn()}
        onRejectSuggestion={vi.fn()}
      />,
    );

    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("disables suggest button while suggesting (loading state)", () => {
    render(
      <KBSessionFieldRow
        field={emptyField}
        isEmpty
        suggestingFieldKey="description"
        onCancelSuggest={vi.fn()}
        onSuggest={vi.fn()}
        onAnswer={vi.fn()}
        onAcceptSuggestion={vi.fn()}
        onRejectSuggestion={vi.fn()}
      />,
    );

    // The suggest button should show "generating" text and be disabled
    const generatingText = screen.getByText("aiActions.generating");
    const suggestButton = generatingText.closest("button");
    expect(suggestButton?.disabled).toBe(true);
  });

  it("triggers onSuggest with field key when suggest button clicked", () => {
    const onSuggest = vi.fn();

    render(
      <KBSessionFieldRow
        field={emptyField}
        isEmpty
        onSuggest={onSuggest}
        onAnswer={vi.fn()}
        onAcceptSuggestion={vi.fn()}
        onRejectSuggestion={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText("kb.suggestAI"));
    expect(onSuggest).toHaveBeenCalledWith("description");
  });
});
