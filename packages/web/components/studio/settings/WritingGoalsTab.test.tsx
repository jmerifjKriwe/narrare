import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WritingGoalsTab } from "./WritingGoalsTab";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------
// Note: next-intl is mocked globally in setupTests.ts

vi.mock("@/lib/api/client", () => ({
  chaptersApi: {
    list: vi.fn().mockResolvedValue([
      { id: "ch-1", novel_id: "novel-1", word_count: 1500 },
      { id: "ch-2", novel_id: "novel-1", word_count: 2500 },
    ]),
  },
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function renderWithProviders(ui: React.ReactElement) {
  return render(<QueryClientProvider client={createQueryClient()}>{ui}</QueryClientProvider>);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("WritingGoalsTab", () => {
  describe("rendering", () => {
    it("renders title and description", async () => {
      renderWithProviders(<WritingGoalsTab novelId="novel-1" />);

      await waitFor(() => {
        expect(screen.getByText("settings.writing.title")).toBeInTheDocument();
        expect(screen.getByText("settings.writing.description")).toBeInTheDocument();
      });
    });

    it("renders daily goal input", async () => {
      renderWithProviders(<WritingGoalsTab novelId="novel-1" />);

      await waitFor(() => {
        expect(screen.getByText("settings.writing.dailyGoalDescription")).toBeInTheDocument();
        expect(screen.getByText("settings.writing.wordsPerDay")).toBeInTheDocument();
      });
    });

    it("renders project progress section", async () => {
      renderWithProviders(<WritingGoalsTab novelId="novel-1" />);

      await waitFor(() => {
        expect(screen.getByText("settings.writing.projectProgress")).toBeInTheDocument();
        expect(screen.getByText("settings.writing.projectProgressDescription")).toBeInTheDocument();
      });
    });

    it("shows word count and percentage", async () => {
      renderWithProviders(<WritingGoalsTab novelId="novel-1" />);

      await waitFor(() => {
        // 1500 + 2500 = 4000 words — toLocaleString() varies by Node.js locale
        expect(screen.getByText(/4[.,]000/)).toBeInTheDocument();
      });
    });
  });
});
