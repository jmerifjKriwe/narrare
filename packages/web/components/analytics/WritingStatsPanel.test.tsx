/**
 * WritingStatsPanel tests — STATS-001 (Task E7). Controlled useAnalyticsWriting
 * + useNovels results (hooks themselves are msw-tested in their own suites),
 * local next-intl mock (global shape + deterministic useFormatter().number),
 * recharts stubs per the AnalyticsCostsPanel/SentimentChart test pattern.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { WritingReport } from "@/lib/hooks/useAnalyticsWriting";
import { WritingStatsPanel } from "./WritingStatsPanel";

vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => {
    const dict: Record<string, Record<string, string>> = {
      "analytics.writing": {
        title: "Writing",
        novelLabel: "Novel",
        novelAll: "All novels",
        today: "Words today",
        streakCurrent: "Current streak",
        streakLongest: "Longest streak",
        streakDays: "{count} days",
        totalWords: "Total words",
        chart: "Daily words — last 90 days",
        goalTitle: "Writing goal",
        goalOf: "{current} of {target} words ({percent}%)",
        empty: "No writing activity recorded yet.",
        error: "Failed to load writing statistics.",
        retry: "Retry",
      },
    };
    const messages = dict[namespace] ?? {};
    const t = (key: string, params?: Record<string, unknown>) => {
      let str = messages[key] ?? key;
      if (params) {
        for (const [k, v] of Object.entries(params)) str = str.replace(`{${k}}`, String(v));
      }
      return str;
    };
    t.has = (key: string) => key in messages;
    return t;
  },
  useFormatter: () => ({
    number: (value: number, opts?: Intl.NumberFormatOptions) =>
      new Intl.NumberFormat("en-US", opts).format(value),
  }),
}));

const mockUseAnalyticsWriting = vi.fn();

vi.mock("@/lib/hooks/useAnalyticsWriting", () => ({
  useAnalyticsWriting: (novelId?: string | null) => mockUseAnalyticsWriting(novelId),
}));

const mockUseNovels = vi.fn();

vi.mock("@/lib/hooks/useNovels", () => ({
  useNovels: () => mockUseNovels(),
}));

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  BarChart: ({ children, data }: { children: ReactNode; data: unknown[] }) => (
    <div data-testid="writing-daily-chart" data-points={data.length}>
      {children}
    </div>
  ),
  Bar: () => <div data-testid="writing-daily-bar" />,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
}));

/** 90 zero-filled UTC days ending today — the backend contract shape. */
const DAILIES = Array.from({ length: 90 }, (_, i) => {
  const day = new Date(Date.UTC(2026, 9, 8) - (89 - i) * 86_400_000);
  return { date: day.toISOString().slice(0, 10), words: (i % 7) + 1 };
});

const REPORT: WritingReport = {
  dailies: DAILIES,
  streaks: { current: 4, longest: 12 },
  today_words: 350,
  total_words: 48211,
  goal: null,
};

const GOAL: NonNullable<WritingReport["goal"]> = {
  target_words: 80000,
  current_words: 48211,
  progress_pct: 60.3,
};

function resolved(report: WritingReport, error: unknown = null) {
  return { data: report, isPending: false, isError: error !== null, error, refetch: vi.fn() };
}

const NOVELS = [
  { id: "novel-1", title: "Alpha" },
  { id: "novel-2", title: "Beta" },
];

describe("WritingStatsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAnalyticsWriting.mockImplementation(() => resolved(REPORT));
    mockUseNovels.mockReturnValue({ data: NOVELS });
  });

  it("renders today's words, streaks and total from the report", async () => {
    render(<WritingStatsPanel />);

    expect(await screen.findByText("Words today")).toBeInTheDocument();
    expect(screen.getByText("350")).toBeInTheDocument();
    expect(screen.getByText("Current streak")).toBeInTheDocument();
    expect(screen.getByText("4 days")).toBeInTheDocument();
    expect(screen.getByText("Longest streak")).toBeInTheDocument();
    expect(screen.getByText("12 days")).toBeInTheDocument();
    expect(screen.getByText("Total words")).toBeInTheDocument();
    expect(screen.getByText("48,211")).toBeInTheDocument();
  });

  it("feeds the 90-day daily series to the bar chart", async () => {
    render(<WritingStatsPanel />);

    expect(await screen.findByTestId("writing-daily-chart")).toHaveAttribute("data-points", "90");
    expect(screen.getByTestId("writing-daily-bar")).toBeInTheDocument();
  });

  it("defaults the novel scope to all novels; the selector switches the hook param", async () => {
    const user = userEvent.setup();
    render(<WritingStatsPanel />);

    await screen.findByText("Words today");
    expect(mockUseAnalyticsWriting).toHaveBeenLastCalledWith(null);

    await user.selectOptions(screen.getByLabelText("Novel"), "novel-2");
    expect(mockUseAnalyticsWriting).toHaveBeenLastCalledWith("novel-2");

    await user.selectOptions(screen.getByLabelText("Novel"), "");
    expect(mockUseAnalyticsWriting).toHaveBeenLastCalledWith(null);
  });

  describe("goal progress bar", () => {
    it("is absent when the report carries no goal (all-novels / no target)", async () => {
      render(<WritingStatsPanel />);

      await screen.findByText("Words today");
      expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    });

    it("renders percentage + current/target when a novel goal is set", async () => {
      mockUseAnalyticsWriting.mockImplementation(() => resolved({ ...REPORT, goal: GOAL }));
      render(<WritingStatsPanel />);

      const bar = await screen.findByRole("progressbar");
      expect(bar).toHaveAttribute("aria-valuenow", "60.3");
      expect(screen.getByText("48,211 of 80,000 words (60.3%)")).toBeInTheDocument();
    });
  });

  it("shows the empty state (no events at all) instead of cards and chart", async () => {
    mockUseAnalyticsWriting.mockImplementation(() =>
      resolved({
        dailies: DAILIES.map((day) => ({ ...day, words: 0 })),
        streaks: { current: 0, longest: 0 },
        today_words: 0,
        total_words: 0,
        goal: null,
      }),
    );
    render(<WritingStatsPanel />);

    expect(await screen.findByText("No writing activity recorded yet.")).toBeInTheDocument();
    expect(screen.queryByTestId("writing-daily-chart")).not.toBeInTheDocument();
    expect(screen.queryByText("Words today")).not.toBeInTheDocument();
  });

  it("handles pending and error (retry refetches) states", async () => {
    const user = userEvent.setup();
    const refetch = vi.fn();
    mockUseAnalyticsWriting.mockImplementation(() => ({ isPending: true, refetch }));
    const { rerender } = render(<WritingStatsPanel />);

    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");

    mockUseAnalyticsWriting.mockImplementation(() => ({ isError: true, refetch }));
    rerender(<WritingStatsPanel />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Failed to load writing statistics.",
    );
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(refetch).toHaveBeenCalledOnce();
  });

  it("shows the loading selector state while the novels list resolves", async () => {
    mockUseNovels.mockReturnValue({ data: undefined });
    render(<WritingStatsPanel />);

    await screen.findByText("Words today");
    expect(screen.getByLabelText("Novel")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "All novels" })).toBeInTheDocument();
    expect(screen.getByTestId("writing-daily-chart")).toHaveAttribute("data-points", "90");
  });

  it("keeps the previous report mounted while a novel switch refetches", async () => {
    // keepPreviousData contract (hook-level, mirrored in the panel's UX):
    // during the switch the query is NOT pending and data stays defined.
    const user = userEvent.setup();
    mockUseAnalyticsWriting.mockImplementation((novelId?: string | null) =>
      resolved(novelId ? { ...REPORT, goal: GOAL } : REPORT),
    );
    render(<WritingStatsPanel />);
    await screen.findByText("Words today");

    await user.selectOptions(screen.getByLabelText("Novel"), "novel-2");
    await waitFor(() =>
      expect(screen.getByText("48,211 of 80,000 words (60.3%)")).toBeInTheDocument(),
    );
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
