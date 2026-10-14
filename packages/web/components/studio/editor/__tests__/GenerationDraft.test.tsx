import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GenerationDraft } from "@/components/studio/editor/GenerationDraft";

describe("GenerationDraft", () => {
  const defaultProps = {
    phase: "streaming" as const,
    draftText: "",
    wordCount: 0,
    targetNum: 1000,
    tokenUsage: null,
    isAcceptPending: false,
    isRejectPending: false,
    onStop: vi.fn(),
    onAccept: vi.fn(),
    onReject: vi.fn(),
    onRegenerate: vi.fn(),
  };

  it("renders AI draft badge", () => {
    render(<GenerationDraft {...defaultProps} />);
    expect(screen.getByText("generationPanel.aiDraftBadge")).toBeDefined();
  });

  it("shows stop button in streaming phase", () => {
    render(<GenerationDraft {...defaultProps} phase="streaming" />);
    expect(screen.getByText("aiActions.stop")).toBeDefined();
  });

  it("shows waiting for text when draftText is empty", () => {
    render(<GenerationDraft {...defaultProps} />);
    expect(screen.getByText("generationPanel.waitingForText")).toBeDefined();
  });

  it("shows draft text when provided", () => {
    render(<GenerationDraft {...defaultProps} draftText="Once upon a time..." />);
    expect(screen.getByText("Once upon a time...")).toBeDefined();
  });

  it("shows review buttons in review phase", () => {
    render(<GenerationDraft {...defaultProps} phase="review" />);
    expect(screen.getByText("aiActions.accept")).toBeDefined();
    expect(screen.getByText("aiActions.reject")).toBeDefined();
    expect(screen.getByText("aiActions.retry")).toBeDefined();
  });

  it("does not show stop button in review phase", () => {
    render(<GenerationDraft {...defaultProps} phase="review" />);
    expect(screen.queryByText("aiActions.stop")).toBeNull();
  });

  it("calls onStop when stop is clicked", () => {
    const onStop = vi.fn();
    render(<GenerationDraft {...defaultProps} onStop={onStop} />);
    fireEvent.click(screen.getByText("aiActions.stop"));
    expect(onStop).toHaveBeenCalledOnce();
  });

  it("calls onAccept when accept is clicked", () => {
    const onAccept = vi.fn();
    // Non-empty draft: Accept is disabled while the draft is empty (M06).
    render(
      <GenerationDraft
        {...defaultProps}
        phase="review"
        draftText="The harbour bell rang twice."
        onAccept={onAccept}
      />,
    );
    fireEvent.click(screen.getByText("aiActions.accept"));
    expect(onAccept).toHaveBeenCalledOnce();
  });

  it("calls onReject when reject is clicked", () => {
    const onReject = vi.fn();
    render(<GenerationDraft {...defaultProps} phase="review" onReject={onReject} />);
    fireEvent.click(screen.getByText("aiActions.reject"));
    expect(onReject).toHaveBeenCalledOnce();
  });

  it("calls onRegenerate when regenerate is clicked", () => {
    const onRegenerate = vi.fn();
    render(<GenerationDraft {...defaultProps} phase="review" onRegenerate={onRegenerate} />);
    fireEvent.click(screen.getByText("aiActions.retry"));
    expect(onRegenerate).toHaveBeenCalledOnce();
  });

  it("disables accept button when isAcceptPending", () => {
    render(<GenerationDraft {...defaultProps} phase="review" isAcceptPending={true} />);
    const button = screen.getByText("aiActions.accept").closest("button");
    expect(button).not.toBeNull();
    expect(button!.disabled).toBe(true);
  });

  it("shows word count progress", () => {
    render(<GenerationDraft {...defaultProps} wordCount={500} targetNum={1000} />);
    expect(screen.getByText("generationPanel.wordCountProgress")).toBeDefined();
  });

  it("disables Accept when the draft is empty (M06)", () => {
    render(<GenerationDraft {...defaultProps} phase="review" draftText="" wordCount={0} />);
    const button = screen.getByText("aiActions.accept").closest("button");
    expect(button).not.toBeNull();
    expect(button!.disabled).toBe(true);
  });

  it("keeps Accept enabled for a non-empty draft (M06)", () => {
    render(
      <GenerationDraft
        {...defaultProps}
        phase="review"
        draftText="The harbour bell rang twice before dawn."
        wordCount={7}
      />,
    );
    const button = screen.getByText("aiActions.accept").closest("button");
    expect(button).not.toBeNull();
    expect(button!.disabled).toBe(false);
  });
});
