/**
 * AnalyticsCostsPanel tests — STATS-002 (Task 14). Controlled useAnalyticsCosts
 * result (hook itself is msw-tested), local next-intl mock (global shape +
 * `t.has` + deterministic `useFormatter().number`), recharts stubs per the
 * SentimentChart test pattern.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CostMonthReport } from "@/lib/api/analytics";
import { AnalyticsCostsPanel } from "./AnalyticsCostsPanel";

vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => {
    const dict: Record<string, Record<string, string>> = {
      "analytics.costs": { unpriced: "{count} unpriced", exportCsv: "Export CSV" },
      "analytics.costs.intent": { draft: "Draft" },
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

const mockUseAnalyticsCosts = vi.fn();

vi.mock("@/lib/hooks/useAnalyticsCosts", () => ({
  useAnalyticsCosts: (month: string) => mockUseAnalyticsCosts(month),
}));

const mockDownloadCostsCsv = vi.fn();

vi.mock("@/lib/api/analytics", () => ({
  analyticsApi: {
    downloadCostsCsv: (month: string) => mockDownloadCostsCsv(month),
  },
}));

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  BarChart: ({ children, data }: { children: ReactNode; data: unknown[] }) => (
    <div data-testid="costs-trend-chart" data-points={data.length}>
      {children}
    </div>
  ),
  Bar: () => <div data-testid="costs-trend-bar" />,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
}));

const REPORT: CostMonthReport = {
  month: "2026-10",
  totals: { calls: 1234, tokens_in: 500000, tokens_out: 250000, cost_usd: 12.5, unpriced_calls: 0 },
  by_intent: [
    { intent: "draft", calls: 10, cost_usd: 8.25, unpriced_calls: 0 },
    { intent: "custom_intent", calls: 4, cost_usd: 4.25, unpriced_calls: 1 },
  ],
  by_model: [
    { provider: "openai", model_id: "gpt-5", calls: 14, cost_usd: 12.5, unpriced_calls: 1 },
  ],
  trend: ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"].map((month, i) => ({
    month,
    cost_usd: i + 1,
  })),
};

function resolved(report: CostMonthReport) {
  return { data: report, isPending: false, isError: false, refetch: vi.fn() };
}

// Current/previous month, computed the same client-local way as the component.
const monthKey = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
const now = new Date();
const CURRENT = monthKey(now);
const PREV = monthKey(new Date(now.getFullYear(), now.getMonth() - 1, 1));

describe("AnalyticsCostsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAnalyticsCosts.mockImplementation(() => resolved(REPORT));
    mockDownloadCostsCsv.mockResolvedValue(undefined);
  });

  it("defaults to the current month; next is clamped (disabled), prev enabled", async () => {
    render(<AnalyticsCostsPanel />);

    expect(await screen.findByTestId("costs-month-label")).toHaveTextContent(CURRENT);
    expect(mockUseAnalyticsCosts).toHaveBeenCalledWith(CURRENT);
    expect(screen.getByRole("button", { name: "nextMonth" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "prevMonth" })).toBeEnabled();
  });

  it("prev/next buttons shift the queried month", async () => {
    const user = userEvent.setup();
    render(<AnalyticsCostsPanel />);
    await screen.findByTestId("costs-month-label");

    await user.click(screen.getByRole("button", { name: "prevMonth" }));
    expect(mockUseAnalyticsCosts).toHaveBeenLastCalledWith(PREV);
    expect(screen.getByTestId("costs-month-label")).toHaveTextContent(PREV);

    await user.click(screen.getByRole("button", { name: "nextMonth" }));
    expect(mockUseAnalyticsCosts).toHaveBeenLastCalledWith(CURRENT);
  });

  it("renders formatted totals; unpriced badge appears iff unpriced_calls > 0", async () => {
    const { rerender } = render(<AnalyticsCostsPanel />);

    expect((await screen.findAllByText("$12.50")).length).toBeGreaterThan(0); // totals + model row
    expect(screen.getByText("1,234")).toBeInTheDocument(); // calls
    expect(screen.getByText("500,000")).toBeInTheDocument(); // tokens_in
    expect(screen.queryByTestId("costs-unpriced-badge")).not.toBeInTheDocument();

    mockUseAnalyticsCosts.mockImplementation(() =>
      resolved({ ...REPORT, totals: { ...REPORT.totals, unpriced_calls: 2 } }),
    );
    rerender(<AnalyticsCostsPanel />);

    expect(await screen.findByTestId("costs-unpriced-badge")).toHaveTextContent("2 unpriced");
  });

  it("renders breakdown tables (raw-key intent fallback) and the six-month trend", async () => {
    render(<AnalyticsCostsPanel />);

    expect(await screen.findByText("Draft")).toBeInTheDocument(); // translated intent
    expect(screen.getByText("custom_intent")).toBeInTheDocument(); // untranslated → raw key
    expect(screen.getByText("openai / gpt-5")).toBeInTheDocument(); // provider / model_id
    expect(screen.getByTestId("costs-trend-chart")).toHaveAttribute("data-points", "6");
    expect(screen.getByTestId("costs-trend-bar")).toBeInTheDocument();
  });

  it("handles pending, error (retry refetches), and empty states", async () => {
    const user = userEvent.setup();
    const refetch = vi.fn();
    mockUseAnalyticsCosts.mockImplementation(() => ({ isPending: true, refetch }));
    const { rerender } = render(<AnalyticsCostsPanel />);

    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");

    mockUseAnalyticsCosts.mockImplementation(() => ({ isError: true, refetch }));
    rerender(<AnalyticsCostsPanel />);
    expect(await screen.findByRole("alert")).toHaveTextContent("error");
    await user.click(screen.getByRole("button", { name: "retry" }));
    expect(refetch).toHaveBeenCalledOnce();

    mockUseAnalyticsCosts.mockImplementation(() =>
      resolved({ ...REPORT, totals: { ...REPORT.totals, calls: 0 } }),
    );
    rerender(<AnalyticsCostsPanel />);
    expect(await screen.findByText("empty")).toBeInTheDocument();
    expect(screen.queryByTestId("costs-trend-chart")).not.toBeInTheDocument();
  });

  describe("CSV export", () => {
    it("renders the export button in the header", async () => {
      render(<AnalyticsCostsPanel />);

      expect(await screen.findByRole("button", { name: "Export CSV" })).toBeInTheDocument();
    });

    it("exports the currently selected month", async () => {
      const user = userEvent.setup();
      render(<AnalyticsCostsPanel />);
      await screen.findByTestId("costs-month-label");

      await user.click(screen.getByRole("button", { name: "Export CSV" }));

      expect(mockDownloadCostsCsv).toHaveBeenCalledOnce();
      expect(mockDownloadCostsCsv).toHaveBeenLastCalledWith(CURRENT);
    });

    it("re-exports after month navigation (tracks the new selection)", async () => {
      const user = userEvent.setup();
      render(<AnalyticsCostsPanel />);
      await screen.findByTestId("costs-month-label");

      await user.click(screen.getByRole("button", { name: "prevMonth" }));
      await user.click(screen.getByRole("button", { name: "Export CSV" }));

      expect(mockDownloadCostsCsv).toHaveBeenLastCalledWith(PREV);
    });

    it("is disabled while the download is in flight, then re-enabled", async () => {
      let resolveDownload!: () => void;
      mockDownloadCostsCsv.mockImplementation(
        () =>
          new Promise<void>((resolve) => {
            resolveDownload = resolve;
          }),
      );
      const user = userEvent.setup();
      render(<AnalyticsCostsPanel />);
      await screen.findByTestId("costs-month-label");

      const exportButton = screen.getByRole("button", { name: "Export CSV" });
      await user.click(exportButton);
      expect(exportButton).toBeDisabled();

      resolveDownload();
      await waitFor(() => expect(exportButton).toBeEnabled());
      expect(mockDownloadCostsCsv).toHaveBeenCalledOnce();
    });

    it("logs a failed export and re-enables the button", async () => {
      const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
      mockDownloadCostsCsv.mockRejectedValue(new Error("HTTP 500"));
      const user = userEvent.setup();
      render(<AnalyticsCostsPanel />);
      await screen.findByTestId("costs-month-label");

      const exportButton = screen.getByRole("button", { name: "Export CSV" });
      await user.click(exportButton);

      await waitFor(() => expect(exportButton).toBeEnabled());
      expect(consoleError).toHaveBeenCalledOnce();
      consoleError.mockRestore();
    });
  });
});
