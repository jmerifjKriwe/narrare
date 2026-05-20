import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SyncStatusBadge } from "@/components/studio/planning/SyncStatusBadge";
import type { SyncStatus } from "@/types";

/**
 * Unit tests for SyncStatusBadge component.
 *
 * The next-intl mock in setupTests.ts returns the key path as text,
 * so t("storyboard.status.on_track") → "storyboard.status.on_track".
 * This lets us verify the correct key is used without real translations.
 */

const STATUS_STYLES: Record<SyncStatus, string> = {
  empty: "bg-gray-100 text-gray-500",
  planned: "bg-blue-100 text-blue-600",
  on_track: "bg-green-100 text-green-600",
  deviated: "bg-yellow-100 text-yellow-600",
  completed: "bg-emerald-100 text-emerald-600",
};

const statuses: SyncStatus[] = ["empty", "planned", "on_track", "deviated", "completed"];

describe("SyncStatusBadge", () => {
  it.each(statuses)("renders correct color class for status=%s", (status) => {
    const { container } = render(<SyncStatusBadge status={status} />);
    const span = container.querySelector("span.inline-flex");
    expect(span).toBeDefined();
    expect(span?.className).toContain(STATUS_STYLES[status].split(" ")[0]);
  });

  it.each(statuses)("renders status label text for status=%s", (status) => {
    render(<SyncStatusBadge status={status} />);
    // The mock returns the key path as text
    expect(screen.getByText(`storyboard.status.${status}`)).toBeDefined();
  });

  it("applies custom className", () => {
    const { container } = render(<SyncStatusBadge status="on_track" className="self-start" />);
    const span = container.querySelector("span.inline-flex");
    expect(span?.className).toContain("self-start");
  });

  it("renders the status dot", () => {
    const { container } = render(<SyncStatusBadge status="planned" />);
    const dot = container.querySelector("span.w-1\\.5");
    expect(dot).toBeDefined();
  });
});
