/**
 * AIRating component tests (CR-AUFG-07-24).
 *
 * Verifies the accessible rating control:
 *   - radiogroup role with 5 radio options + privacy notice (idle)
 *   - onSubmit receives {rating, reason}
 *   - onSkip fires on skip click
 *   - loading disables controls + shows submitting text
 *   - success shows confirmation
 *   - error shows error message + retry
 *   - skipped shows compact dismissal
 *
 * i18n: the global setupTests.ts mock returns the translation key verbatim,
 * so assertions match on the key strings (e.g. "aiActions.submitRating").
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AIRatingViewModel } from "@/lib/ai-rating/contracts";
import { AIRating } from "../AIRating";

const vm: AIRatingViewModel = {
  sourceType: "co_author_change",
  sourceId: "change-1",
  projectId: "proj-1",
  intent: "rewrite",
  suggestionText: "A revised sentence.",
  action: "accept",
  chapterId: "ch-1",
  genre: null,
  mode: null,
};

afterEach(() => {
  cleanup();
});

describe("AIRating", () => {
  it("renders a radiogroup with 5 options and the privacy notice", () => {
    render(
      <AIRating
        viewModel={vm}
        state="idle"
        onSubmit={vi.fn()}
        onSkip={vi.fn()}
        onRetry={vi.fn()}
      />,
    );
    expect(screen.getByRole("radiogroup")).toBeTruthy();
    expect(screen.getAllByRole("radio")).toHaveLength(5);
    expect(screen.getByText("aiActions.ratingPrivacyNotice")).toBeTruthy();
  });

  it("calls onSubmit with the selected scale value and optional reason", () => {
    const onSubmit = vi.fn();
    render(
      <AIRating
        viewModel={vm}
        state="idle"
        onSubmit={onSubmit}
        onSkip={vi.fn()}
        onRetry={vi.fn()}
      />,
    );
    fireEvent.click(screen.getAllByRole("radio")[3]); // value 4
    fireEvent.change(screen.getByPlaceholderText("aiActions.ratingReasonPlaceholder"), {
      target: { value: "good tone" },
    });
    fireEvent.click(screen.getByRole("button", { name: "aiActions.submitRating" }));
    expect(onSubmit).toHaveBeenCalledWith({ rating: 4, reason: "good tone" });
  });

  it("calls onSkip when the skip button is clicked", () => {
    const onSkip = vi.fn();
    render(
      <AIRating viewModel={vm} state="idle" onSubmit={vi.fn()} onSkip={onSkip} onRetry={vi.fn()} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "aiActions.skipRating" }));
    expect(onSkip).toHaveBeenCalledOnce();
  });

  it("shows a submitting indicator and disables controls while state is loading", () => {
    render(
      <AIRating
        viewModel={vm}
        state="loading"
        onSubmit={vi.fn()}
        onSkip={vi.fn()}
        onRetry={vi.fn()}
      />,
    );
    expect(screen.getByText("aiActions.ratingSubmitting")).toBeTruthy();
    expect(screen.getByRole("button", { name: "aiActions.submitRating" })).toBeDisabled();
  });

  it("shows a success confirmation when state is success", () => {
    render(
      <AIRating
        viewModel={vm}
        state="success"
        onSubmit={vi.fn()}
        onSkip={vi.fn()}
        onRetry={vi.fn()}
      />,
    );
    expect(screen.getByText("aiActions.ratingSubmitted")).toBeTruthy();
  });

  it("shows an error message and a retry button when state is error", () => {
    const onRetry = vi.fn();
    render(
      <AIRating
        viewModel={vm}
        state="error"
        onSubmit={vi.fn()}
        onSkip={vi.fn()}
        onRetry={onRetry}
      />,
    );
    expect(screen.getByText("aiActions.ratingError")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "aiActions.ratingRetry" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("renders the skipped confirmation without rating controls", () => {
    const { container } = render(
      <AIRating
        viewModel={vm}
        state="skipped"
        onSubmit={vi.fn()}
        onSkip={vi.fn()}
        onRetry={vi.fn()}
      />,
    );
    // Skipped state shows a small confirmation only — no rating controls
    expect(container.querySelector("input[type='radio']")).toBeNull();
    expect(screen.getByText("aiActions.ratingSkipped")).toBeTruthy();
  });

  it("disables the submit button until a rating is selected", () => {
    render(
      <AIRating
        viewModel={vm}
        state="idle"
        onSubmit={vi.fn()}
        onSkip={vi.fn()}
        onRetry={vi.fn()}
      />,
    );
    const submitButton = screen.getByRole("button", { name: "aiActions.submitRating" });
    expect(submitButton).toBeDisabled();
    fireEvent.click(screen.getAllByRole("radio")[1]); // value 2
    expect(submitButton).not.toBeDisabled();
  });

  it("keeps radio name unique per source so multiple ratings don't collide", () => {
    const vmA = { ...vm, sourceId: "a" };
    const vmB = { ...vm, sourceId: "b" };
    const { unmount } = render(
      <AIRating
        viewModel={vmA}
        state="idle"
        onSubmit={vi.fn()}
        onSkip={vi.fn()}
        onRetry={vi.fn()}
      />,
    );
    const nameA = screen.getAllByRole("radio")[0].getAttribute("name");
    unmount();
    render(
      <AIRating
        viewModel={vmB}
        state="idle"
        onSubmit={vi.fn()}
        onSkip={vi.fn()}
        onRetry={vi.fn()}
      />,
    );
    const nameB = screen.getAllByRole("radio")[0].getAttribute("name");
    expect(nameA).not.toBe(nameB);
  });
});
