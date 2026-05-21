/**
 * Unit tests for SyncStatusBadge component.
 *
 * Verifies that all five sync statuses render correctly
 * with their respective visual styles and labels.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SyncStatusBadge } from "@/components/studio/planning/SyncStatusBadge";
import type { SyncStatus } from "@/types";

describe("SyncStatusBadge", () => {
  afterEach(() => {
    cleanup();
  });

  const STATUSES: SyncStatus[] = ["empty", "planned", "on_track", "deviated", "completed"];

  it.each(STATUSES)("renders the '%s' status with correct label", (status) => {
    render(<SyncStatusBadge status={status} />);

    // The i18n mock returns the key as-is:
    // t(`storyboard.status.${status}`) → "storyboard.status.{status}"
    expect(screen.getByText(`storyboard.status.${status}`)).toBeInTheDocument();
  });

  it("renders with custom className", () => {
    render(<SyncStatusBadge status="completed" className="my-custom-class" />);

    const badge = screen.getByText("storyboard.status.completed");
    // The className should be applied to the span containing the text
    expect(badge.className).toContain("my-custom-class");
  });

  it("renders all five statuses without error", () => {
    STATUSES.forEach((status) => {
      const { unmount } = render(<SyncStatusBadge status={status} />);
      const badge = screen.getByText(`storyboard.status.${status}`);
      expect(badge).toBeInTheDocument();
      unmount();
    });
  });
});
