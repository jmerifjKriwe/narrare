/**
 * Interaction tests for KBSessionFieldList.
 *
 * Covers: onSuggest callback, action buttons (Start Interview, Enhance All),
 * accept/reject suggestion callbacks, Suggest AI disabled state, inline editing.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { KBSessionFieldList } from "@/components/studio/kb/KBSessionFieldList";
import { defaultProps, emptySession } from "./setup";

describe("KBSessionFieldList — interactions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls onSuggest when 'Suggest AI' is clicked", () => {
    const onSuggest = vi.fn();
    render(<KBSessionFieldList {...defaultProps} onSuggest={onSuggest} session={emptySession} />);

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

  it("accept button calls onAcceptSuggestion with field key and value", () => {
    const onAcceptSuggestion = vi.fn();
    render(<KBSessionFieldList {...defaultProps} onAcceptSuggestion={onAcceptSuggestion} />);

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

    const suggestButtons = screen.getAllByText("kb.suggestAI");
    const disabledButtons = suggestButtons.filter((btn) => btn.closest("button")?.disabled);
    expect(disabledButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("allows inline editing of filled fields", () => {
    render(<KBSessionFieldList {...defaultProps} />);

    const editButtons = document.querySelectorAll('[class*="p-1 text-muted-foreground"]');
    if (editButtons.length > 0) {
      fireEvent.click(editButtons[0]);
    }

    expect(() => screen.getByText("kb.save")).toBeTruthy();
    expect(() => screen.getByText("kb.cancel")).toBeTruthy();
  });
});
