import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AdaptiveSnapshotHistory } from "@/components/studio/settings/_components/AdaptiveSnapshotHistory";
import type { AdaptiveSnapshotsResponse } from "@/types";

// Mock next-intl — returns the key string so assertions are locale-independent.
vi.mock("next-intl", () => ({
  useTranslations: (ns: string) => (key: string) => (ns === "aiAssist" ? key : `${ns}.${key}`),
}));

// Mock the data hook — component tests stay decoupled from the transport layer.
const mockUseAdaptiveSnapshots = vi.fn();
vi.mock("@/lib/hooks/useAdaptiveSnapshots", () => ({
  useAdaptiveSnapshots: (...args: unknown[]) => mockUseAdaptiveSnapshots(...args),
}));

function snapshot(
  created_at: string,
  overrides: Partial<AdaptiveSnapshotsResponse["items"][number]> = {},
): AdaptiveSnapshotsResponse["items"][number] {
  return {
    invocation_id: `inv-${created_at}`,
    novel_id: null,
    intent: "chapter_writing",
    mode: null,
    created_at,
    source_summary: null,
    weights: null,
    ...overrides,
  };
}

describe("AdaptiveSnapshotHistory", () => {
  it("renders the empty state when there are no items", () => {
    mockUseAdaptiveSnapshots.mockReturnValue({
      data: { project_id: "proj-1", items: [] },
      isLoading: false,
      error: null,
    });
    render(<AdaptiveSnapshotHistory projectId="proj-1" />);
    expect(screen.getByText("historyEmpty")).toBeInTheDocument();
  });

  it("renders the loading state", () => {
    mockUseAdaptiveSnapshots.mockReturnValue({ data: undefined, isLoading: true, error: null });
    render(<AdaptiveSnapshotHistory projectId="proj-1" />);
    expect(screen.getByText("adaptive.loading")).toBeInTheDocument();
  });

  it("renders snapshots newest-first regardless of input order", () => {
    mockUseAdaptiveSnapshots.mockReturnValue({
      data: {
        project_id: "proj-1",
        // Oldest deliberately first — component must sort by created_at desc.
        items: [
          snapshot("2026-07-20T10:00:00Z", { intent: "oldest-intent" }),
          snapshot("2026-07-22T12:00:00Z", { intent: "newest-intent" }),
        ],
      },
      isLoading: false,
      error: null,
    });
    render(<AdaptiveSnapshotHistory projectId="proj-1" />);
    const intents = screen.getAllByTestId("snapshot-intent").map((el) => el.textContent);
    expect(intents).toEqual(["newest-intent", "oldest-intent"]);
  });

  it("renders active weights and the source labels that shaped the snapshot", () => {
    mockUseAdaptiveSnapshots.mockReturnValue({
      data: {
        project_id: "proj-1",
        items: [
          snapshot("2026-07-22T12:00:00Z", {
            intent: "dialogue_coach",
            mode: "refine",
            source_summary: { preference: "values brevity", voice_profiles: "warm tone" },
            weights: {
              preference: 0.5,
              voice_fidelity: 0.9,
              style_constraints: 1.0,
              avoidance: 1.0,
            },
          }),
        ],
      },
      isLoading: false,
      error: null,
    });
    render(<AdaptiveSnapshotHistory projectId="proj-1" />);
    // Weight values rendered for each of the four weights (1.00 appears twice:
    // style_constraints and avoidance are both 1.0 — use getAllByText).
    expect(screen.getByText("0.50")).toBeInTheDocument();
    expect(screen.getByText("0.90")).toBeInTheDocument();
    expect(screen.getAllByText("1.00")).toHaveLength(2);
    // Active source keys surfaced as chips (exact match — avoids colliding with
    // the weight label "adaptive.weight.preference" which also contains "preference").
    expect(screen.getByText("preference")).toBeInTheDocument();
    expect(screen.getByText("voice_profiles")).toBeInTheDocument();
  });

  it("falls back to created_at for the React key when invocation_id is null", () => {
    mockUseAdaptiveSnapshots.mockReturnValue({
      data: {
        project_id: "proj-1",
        items: [{ ...snapshot("2026-07-22T12:00:00Z"), invocation_id: null, intent: "null-id" }],
      },
      isLoading: false,
      error: null,
    });
    // No console error about missing keys → renders without throwing.
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(<AdaptiveSnapshotHistory projectId="proj-1" />);
    expect(screen.getByText("null-id")).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalledWith(expect.stringContaining('unique "key"'));
    spy.mockRestore();
  });
});
