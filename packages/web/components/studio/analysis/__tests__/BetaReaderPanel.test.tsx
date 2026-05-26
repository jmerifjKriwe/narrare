/**
 * BetaReaderPanel tests — analysis results panel with tabs.
 *
 * Tests:
 * 1. Shows loading state on mount
 * 2. Shows results with all 4 tabs after successful analysis
 * 3. Switches between tabs
 * 4. Shows error state with retry button
 * 5. Shows empty state for tabs with no items
 * 6. Renders score bars in overall tab
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BetaReaderPanel } from "@/components/studio/analysis/BetaReaderPanel";
import type { BetaReaderResponse } from "@/lib/api/analysis";
import { useBetaReaderAnalyze, useBetaReaderDeepDive } from "@/lib/hooks/useBetaReader";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) => {
    if (params) {
      return Object.entries(params).reduce((str, [k, v]) => str.replace(`{${k}}`, String(v)), key);
    }
    return key;
  },
}));

vi.mock("@/lib/hooks/useBetaReader", () => ({
  useBetaReaderAnalyze: vi.fn(),
  useBetaReaderDeepDive: vi.fn(),
}));

vi.mock("@/lib/stores/editorStore", () => ({
  useEditorStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({
      setBetaReaderResult: vi.fn(),
      setBetaReaderLoading: vi.fn(),
    }),
}));

// Mock recharts to avoid rendering issues in jsdom
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="radar-chart">{children}</div>
  ),
  RadarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PolarGrid: () => <div />,
  PolarAngleAxis: () => <div />,
  PolarRadiusAxis: () => <div />,
  Radar: () => <div />,
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockResponse: BetaReaderResponse = {
  novel_id: "novel-1",
  chapter_ids: ["chapter-1"],
  total_word_count: 3000,
  strengths: [
    {
      category: "character",
      title: "Strong character voice",
      description: "Distinct and consistent voice.",
      text_excerpt: null,
    },
  ],
  feedback: [
    {
      category: "plot",
      severity: "critical",
      location: "Paragraph 3",
      title: "Plot hole detected",
      description: "Timeline inconsistency.",
      suggestion: "Add flashback.",
      text_excerpt: null,
    },
    {
      category: "prose",
      severity: "minor",
      location: null,
      title: "Minor wording issue",
      description: "Could be clearer.",
      suggestion: null,
      text_excerpt: null,
    },
  ],
  questions: [
    {
      category: "prose",
      location: "Paragraph 5",
      question: "Who is speaking?",
      context: "Missing dialogue tag.",
    },
  ],
  overall: {
    summary: "A solid chapter with strong characters but some plot issues.",
    reader_engagement: 7,
    emotional_impact: 6,
    pacing_score: 8,
    prose_quality: 7,
    plot_progression: 5,
    character_development: 8,
  },
  analyzed_at: "2026-05-26T12:00:00Z",
  cache_key: "abc123",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <BetaReaderPanel novelId="novel-1" chapterIds={["chapter-1"]} onClose={vi.fn()} />
    </QueryClientProvider>,
  );
}

function setupLoadingState() {
  const mockMutateAsync = vi.fn().mockReturnValue(new Promise(() => {})); // never resolves = loading
  (useBetaReaderAnalyze as ReturnType<typeof vi.fn>).mockReturnValue({
    mutateAsync: mockMutateAsync,
    isPending: true,
  });
  (useBetaReaderDeepDive as ReturnType<typeof vi.fn>).mockReturnValue({
    mutateAsync: vi.fn(),
    isPending: false,
  });
  return { mockMutateAsync };
}

function setupResultsState() {
  const mockMutateAsync = vi.fn().mockResolvedValue(mockResponse);
  (useBetaReaderAnalyze as ReturnType<typeof vi.fn>).mockReturnValue({
    mutateAsync: mockMutateAsync,
    isPending: false,
  });
  (useBetaReaderDeepDive as ReturnType<typeof vi.fn>).mockReturnValue({
    mutateAsync: vi.fn(),
    isPending: false,
  });
  return { mockMutateAsync };
}

function setupErrorState() {
  const mockMutateAsync = vi.fn().mockRejectedValue(new Error("Server error"));
  (useBetaReaderAnalyze as ReturnType<typeof vi.fn>).mockReturnValue({
    mutateAsync: mockMutateAsync,
    isPending: false,
  });
  (useBetaReaderDeepDive as ReturnType<typeof vi.fn>).mockReturnValue({
    mutateAsync: vi.fn(),
    isPending: false,
  });
  return { mockMutateAsync };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("BetaReaderPanel", () => {
  it("shows loading state on mount", () => {
    setupLoadingState();
    renderPanel();

    expect(screen.getByText("loading")).toBeDefined();
    expect(screen.getByText("loadingSubtext")).toBeDefined();
  });

  it("shows results with all 4 tabs after successful analysis", async () => {
    setupResultsState();
    renderPanel();

    await waitFor(() => {
      expect(screen.getByText("tabs.strengths")).toBeDefined();
    });

    expect(screen.getByText("tabs.issues")).toBeDefined();
    expect(screen.getByText("tabs.questions")).toBeDefined();
    expect(screen.getByText("tabs.overall")).toBeDefined();
  });

  it("switches between tabs and shows content", async () => {
    setupResultsState();
    renderPanel();

    await waitFor(() => {
      expect(screen.getByText("tabs.strengths")).toBeDefined();
    });

    // Default tab is strengths — shows strength card
    expect(screen.getByText("Strong character voice")).toBeDefined();

    // Switch to issues tab
    fireEvent.click(screen.getByText("tabs.issues"));
    expect(screen.getByText("Plot hole detected")).toBeDefined();

    // Switch to questions tab
    fireEvent.click(screen.getByText("tabs.questions"));
    expect(screen.getByText("Who is speaking?")).toBeDefined();

    // Switch to overall tab
    fireEvent.click(screen.getByText("tabs.overall"));
    expect(screen.getByText("overall.summary")).toBeDefined();
  });

  it("shows error state with retry button", async () => {
    setupErrorState();
    renderPanel();

    await waitFor(() => {
      expect(screen.getByText("error")).toBeDefined();
    });

    expect(screen.getByText("Server error")).toBeDefined();
    expect(screen.getByText("retry")).toBeDefined();
  });

  it("shows empty state for tabs with no items", async () => {
    const emptyResponse = {
      ...mockResponse,
      strengths: [],
      feedback: [],
      questions: [],
    };
    const mockMutateAsync = vi.fn().mockResolvedValue(emptyResponse);
    (useBetaReaderAnalyze as ReturnType<typeof vi.fn>).mockReturnValue({
      mutateAsync: mockMutateAsync,
      isPending: false,
    });
    (useBetaReaderDeepDive as ReturnType<typeof vi.fn>).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    });

    renderPanel();

    await waitFor(() => {
      expect(screen.getByText("empty.issues")).toBeDefined();
    });
  });

  it("renders score bars in overall tab", async () => {
    setupResultsState();
    renderPanel();

    await waitFor(() => {
      expect(screen.getByText("tabs.overall")).toBeDefined();
    });

    // Switch to overall tab
    fireEvent.click(screen.getByText("tabs.overall"));

    // Should show summary
    expect(
      screen.getByText("A solid chapter with strong characters but some plot issues."),
    ).toBeDefined();

    // Should show score labels
    expect(screen.getByText("overall.engagement")).toBeDefined();
    expect(screen.getByText("overall.emotionalImpact")).toBeDefined();
    expect(screen.getByText("overall.pacing")).toBeDefined();
    expect(screen.getByText("overall.proseQuality")).toBeDefined();
    expect(screen.getByText("overall.plotProgression")).toBeDefined();
    expect(screen.getByText("overall.characterDev")).toBeDefined();

    // Should show score values
    const score7Elements = screen.getAllByText("7/10");
    expect(score7Elements.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("5/10")).toBeDefined();
  });
});
