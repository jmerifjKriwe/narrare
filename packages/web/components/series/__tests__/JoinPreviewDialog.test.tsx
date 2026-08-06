/**
 * JoinPreviewDialog component tests (Spec 1, Slice 4, Task 4.8).
 *
 * The dialog is a CONTROLLED, presentational component that renders a fetched
 * JoinPreview (per-entry treatment list) and asks the user to confirm applying
 * the join. It owns no data fetching — the parent (AddNovelToSeries) drives the
 * join hooks and passes state in via props, mirroring the ConfirmDialog pattern.
 *
 * Covers: open/closed, loading, error, treatments render, canon_empty vs
 * canon_nonempty explanation, confirm/cancel callbacks, applying-disabled.
 *
 * Conventions (mirrors SeriesWorkspace.test.tsx): the centralized setupTests.ts
 * mock returns i18n KEY STRINGS verbatim, so assertions check for keys. motion/react
 * is neutralized globally, so AnimatePresence mounts children immediately.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { JoinPreviewDialog } from "@/components/series/JoinPreviewDialog";
import type { JoinPreview } from "@/types";

const canonEmptyFixture: JoinPreview = {
  series_id: "series-1",
  novel_id: "novel-1",
  canon_empty: true,
  treatments: [
    {
      entry_id: "e-1",
      slug: "holden",
      entity_type: "character",
      current_scope: "novel",
      target_scope: "novel",
      reason_code: "entity_default_overlay",
      reason: "Entity type 'character' defaults to Novel-Overlay (Policy iii)",
    },
    {
      entry_id: "e-2",
      slug: "rocinante",
      entity_type: "system",
      current_scope: "novel",
      target_scope: "series",
      reason_code: "entity_default_canon",
      reason: "Entity type 'system' defaults to Canon (Policy iii)",
    },
  ],
};

const defaultProps = {
  open: true,
  onOpenChange: vi.fn(),
  novelTitle: "Leviathan Wakes",
  preview: canonEmptyFixture,
  isLoading: false,
  isError: false,
  isApplying: false,
  applyError: false,
  onConfirm: vi.fn(),
};

describe("JoinPreviewDialog", () => {
  it("renders nothing when closed", () => {
    render(<JoinPreviewDialog {...defaultProps} open={false} />);
    expect(screen.queryByTestId("join-preview-dialog")).toBeNull();
  });

  it("shows a loading state while the preview is loading", () => {
    render(<JoinPreviewDialog {...defaultProps} preview={null} isLoading={true} />);
    expect(screen.getByTestId("join-preview-loading")).toBeDefined();
    expect(screen.queryByTestId("join-treatment")).toBeNull();
  });

  it("shows an error state when the preview fails", () => {
    render(<JoinPreviewDialog {...defaultProps} preview={null} isError={true} />);
    expect(screen.getByTestId("join-preview-error")).toBeDefined();
  });

  it("renders one row per treatment", () => {
    render(<JoinPreviewDialog {...defaultProps} />);
    expect(screen.getAllByTestId("join-treatment")).toHaveLength(2);
  });

  it("renders each treatment's slug, entity type, target and reason", () => {
    render(<JoinPreviewDialog {...defaultProps} />);
    expect(screen.getByText("holden")).toBeDefined();
    expect(screen.getByText("rocinante")).toBeDefined();
    // entity type labels reuse the shared kb.<type>s keys (C3 fix) — the i18n
    // mock returns keys verbatim.
    expect(screen.getByText("kb.characters")).toBeDefined();
    expect(screen.getByText("kb.systems")).toBeDefined();
    // target labels: series-scope → Series-Canon, novel-scope → Novel-Overlay
    expect(screen.getByText("series.join.targetSeries")).toBeDefined();
    expect(screen.getByText("series.join.targetNovel")).toBeDefined();
    // reasons resolve from the stable reason_code (C3 fix), not free-text.
    expect(screen.getByText("series.join.reason.entity_default_overlay")).toBeDefined();
    expect(screen.getByText("series.join.reason.entity_default_canon")).toBeDefined();
  });

  it("shows the canon_empty explanation when the series canon is empty", () => {
    render(<JoinPreviewDialog {...defaultProps} />);
    expect(screen.getByTestId("join-preview-explanation").textContent).toContain(
      "series.join.explanation.canon_empty",
    );
  });

  it("shows the canon_nonempty explanation when the series canon is non-empty", () => {
    const nonEmpty: JoinPreview = { ...canonEmptyFixture, canon_empty: false };
    render(<JoinPreviewDialog {...defaultProps} preview={nonEmpty} />);
    expect(screen.getByTestId("join-preview-explanation").textContent).toContain(
      "series.join.explanation.canon_nonempty",
    );
  });

  it("calls onConfirm when the confirm button is clicked", () => {
    const onConfirm = vi.fn();
    render(<JoinPreviewDialog {...defaultProps} onConfirm={onConfirm} />);
    fireEvent.click(screen.getByTestId("join-preview-confirm"));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("disables the confirm button and shows applying state while applying", () => {
    render(<JoinPreviewDialog {...defaultProps} isApplying={true} />);
    const confirm = screen.getByTestId("join-preview-confirm") as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);
  });

  it("calls onOpenChange(false) when the cancel button is clicked", () => {
    const onOpenChange = vi.fn();
    render(<JoinPreviewDialog {...defaultProps} onOpenChange={onOpenChange} />);
    fireEvent.click(screen.getByTestId("join-preview-cancel"));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("shows a friendly message when there are no treatments to preview", () => {
    const empty: JoinPreview = { ...canonEmptyFixture, treatments: [] };
    render(<JoinPreviewDialog {...defaultProps} preview={empty} />);
    const emptyState = screen.getByTestId("join-preview-empty");
    expect(emptyState.textContent).toContain("series.join.noTreatments");
    // No treatment rows rendered — the bordered box only holds the message.
    expect(screen.queryAllByTestId("join-treatment")).toHaveLength(0);
  });

  it("does not close while a join is applying — cancel is a no-op", () => {
    const onOpenChange = vi.fn();
    render(<JoinPreviewDialog {...defaultProps} isApplying={true} onOpenChange={onOpenChange} />);
    fireEvent.click(screen.getByTestId("join-preview-cancel"));
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  it("does not close while a join is applying — backdrop click is a no-op", () => {
    const onOpenChange = vi.fn();
    render(<JoinPreviewDialog {...defaultProps} isApplying={true} onOpenChange={onOpenChange} />);
    // The backdrop is the overlay's first child div (aria-hidden).
    const backdrop = document.querySelector('[aria-hidden="true"]') as HTMLElement;
    fireEvent.click(backdrop);
    expect(onOpenChange).not.toHaveBeenCalled();
  });
});
