import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RatingPrompt } from "@/components/studio/editor/RatingPrompt";

describe("RatingPrompt", () => {
  const defaultProps = {
    action: "accept" as const,
    onSubmit: vi.fn(),
    onDismiss: vi.fn(),
  };

  it("renders rating prompt text", () => {
    render(<RatingPrompt {...defaultProps} />);
    expect(screen.getByText("aiActions.rating")).toBeDefined();
  });

  it("renders 5 star buttons", () => {
    render(<RatingPrompt {...defaultProps} />);
    const stars = screen.getAllByRole("button", { name: /[1-5]/ });
    expect(stars).toHaveLength(5);
  });

  it("calls onSubmit with rating when submit is clicked after selecting stars", () => {
    const onSubmit = vi.fn();
    render(<RatingPrompt {...defaultProps} onSubmit={onSubmit} />);

    // Click star 4
    fireEvent.click(screen.getByRole("button", { name: "4" }));
    // Click submit
    fireEvent.click(screen.getByText("aiActions.submitRating"));

    expect(onSubmit).toHaveBeenCalledWith({ rating: 4, reason: undefined });
  });

  it("disables submit when no stars selected", () => {
    render(<RatingPrompt {...defaultProps} />);
    const submitBtn = screen.getByText("aiActions.submitRating").closest("button");
    expect(submitBtn!.disabled).toBe(true);
  });

  it("calls onDismiss when skip is clicked", () => {
    const onDismiss = vi.fn();
    render(<RatingPrompt {...defaultProps} onDismiss={onDismiss} />);
    fireEvent.click(screen.getByText("aiActions.skipRating"));
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it("shows reject reason textarea for reject action", () => {
    render(<RatingPrompt {...defaultProps} action="reject" />);
    expect(screen.getByPlaceholderText("aiActions.rejectReason")).toBeDefined();
  });

  it("does not show reject reason textarea for accept action", () => {
    render(<RatingPrompt {...defaultProps} action="accept" />);
    expect(screen.queryByPlaceholderText("aiActions.rejectReason")).toBeNull();
  });

  it("shows submitted confirmation after submit", () => {
    render(<RatingPrompt {...defaultProps} />);
    fireEvent.click(screen.getByRole("button", { name: "5" }));
    fireEvent.click(screen.getByText("aiActions.submitRating"));
    expect(screen.getByText("aiActions.ratingSubmitted")).toBeDefined();
  });
});
