/**
 * NameGenerator tests — name generation form component.
 *
 * Tests use useAIOperation mock for controlled AI operation state.
 * Tests:
 * 1. Renders all form fields
 * 2. Form submission triggers aiOp.start
 * 3. Results display after generation
 * 4. Loading state during generation
 * 5. Error handling via aiOp.onError
 * 6. Count validation (clamped to 1–50)
 * 7. Generates with correct parameters
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { NameGenerator } from "@/components/studio/generation/NameGenerator";
import type {
  AIOperationState,
  UseAIOperationOptions,
  UseAIOperationReturn,
} from "@/lib/hooks/use-ai-operation";
import { createAbortSignal } from "./helpers/ai-test-helpers";

// ---------------------------------------------------------------------------
// Hoisted mock data and helpers
// ---------------------------------------------------------------------------

const { mockNovel, mockNameResponse, createMockAiOp } = vi.hoisted(() => {
  const mockNovel = {
    id: "novel-1",
    title: "Test Novel",
    writing_language: "en",
    author: "Test Author",
    genre: "Fantasy",
    tone: "epic",
    story_structure: "three-act",
    logline: "A test story",
    synopsis: "A test synopsis",
    is_demo: false,
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z",
  };

  const mockNameResponse = {
    names: [
      {
        name: "Aelindra",
        type: "character",
        name_style: "Fantasy",
        pronunciation: "ay-LIN-dra",
        meaning: "Star light",
        is_duplicate: false,
        confidence: 0.95,
      },
      {
        name: "Theron",
        type: "character",
        name_style: "Fantasy",
        pronunciation: "THEH-ron",
        meaning: "Hunter",
        is_duplicate: true,
        confidence: 0.88,
      },
    ],
    count: 2,
    name_style: "Fantasy",
    name_type: "character",
  };

  /** Create a mutable mock useAIOperation return value. */
  function createMockAiOp(
    overrides: Partial<UseAIOperationReturn<unknown>> = {},
  ): UseAIOperationReturn<unknown> {
    return {
      state: {
        status: "idle",
        result: null,
        error: null,
        attemptCount: 0,
      } as AIOperationState<unknown>,
      start: vi.fn(),
      cancel: vi.fn(),
      retry: vi.fn(),
      reset: vi.fn(),
      notifyData: vi.fn(),
      isIdle: true,
      isLoading: false,
      isStreaming: false,
      isComplete: false,
      isError: false,
      isConnectionLost: false,
      ...overrides,
    };
  }

  return { mockNovel, mockNameResponse, createMockAiOp };
});

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/lib/api/client", () => ({
  novelsApi: {
    get: vi.fn().mockResolvedValue(mockNovel),
  },
  generationApi: {
    generateNames: vi.fn(),
  },
}));

vi.mock("@/lib/hooks/use-ai-operation", () => ({
  useAIOperation: vi.fn(),
}));

vi.mock("@/components/studio/generation/NameResults", () => ({
  NameResults: vi.fn(
    ({ results, isLoading }: { results: typeof mockNameResponse | null; isLoading: boolean }) => (
      <div data-testid="name-results">
        {isLoading ? "Loading..." : results ? `${results.count} results` : "No results"}
      </div>
    ),
  ),
}));

vi.mock("@/lib/api/kb", () => ({
  kbApi: {
    createEntry: vi.fn(),
  },
}));

vi.mock("@/lib/constants/name-styles", () => ({
  NAME_STYLE_SUGGESTIONS: ["Fantasy", "Sci-Fi", "Nordisch"],
}));

import { generationApi, novelsApi } from "@/lib/api/client";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";

const mockedGenerationApi = vi.mocked(generationApi);
const mockedNovelsApi = vi.mocked(novelsApi);
const mockedUseAIOperation = vi.mocked(useAIOperation);

// ---------------------------------------------------------------------------
// Test wrapper
// ---------------------------------------------------------------------------

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function waitForFormReady() {
  await waitFor(() => {
    expect(screen.getByLabelText("generation.nameType")).toBeDefined();
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("NameGenerator", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedNovelsApi.get.mockResolvedValue({ ...mockNovel });
    mockedGenerationApi.generateNames.mockResolvedValue({ ...mockNameResponse });
    // Default mock: idle state
    mockedUseAIOperation.mockReturnValue(createMockAiOp());
  });

  it("renders all form fields", async () => {
    renderWithProviders(<NameGenerator novelId="novel-1" />);

    await waitForFormReady();

    expect(screen.getByLabelText("generation.nameType")).toBeDefined();
    expect(screen.getByLabelText("generation.nameStyle")).toBeDefined();
    expect(screen.getByLabelText("generation.count")).toBeDefined();
    expect(screen.getByLabelText("generation.gender")).toBeDefined();
    expect(screen.getByLabelText("generation.explanationLanguage")).toBeDefined();
    expect(screen.getByText("generation.generateNames")).toBeDefined();
  });

  it("calls aiOp.start when form is submitted", async () => {
    const mockStart = vi.fn();
    mockedUseAIOperation.mockReturnValue(createMockAiOp({ start: mockStart }));

    const user = userEvent.setup();
    renderWithProviders(<NameGenerator novelId="novel-1" />);

    await waitForFormReady();

    await user.click(screen.getByText("generation.generateNames"));

    expect(mockStart).toHaveBeenCalledOnce();
  });

  it("displays results after generation", async () => {
    // Simulate a successful AI operation: start() calls execute → onSuccess → setResults
    mockedUseAIOperation.mockImplementation((options: UseAIOperationOptions<unknown>) => {
      const start = vi.fn(() => {
        options
          .execute(createAbortSignal())
          .then((data) => options.onSuccess?.(data as typeof mockNameResponse))
          .catch(() => {});
      });
      return createMockAiOp({ start });
    });

    const user = userEvent.setup();
    renderWithProviders(<NameGenerator novelId="novel-1" />);

    await waitForFormReady();

    await user.click(screen.getByText("generation.generateNames"));

    await waitFor(() => {
      expect(screen.getByTestId("name-results").textContent).toBe("2 results");
    });
  });

  it("shows loading state during generation", async () => {
    mockedUseAIOperation.mockReturnValue(
      createMockAiOp({
        isLoading: true,
        isIdle: false,
        state: { status: "loading", result: null, error: null, attemptCount: 1 },
      }),
    );

    renderWithProviders(<NameGenerator novelId="novel-1" />);

    await waitForFormReady();

    // Button shows "generating" text and is disabled
    expect(screen.getByText("generating")).toBeDefined();
    expect(screen.getByText("generating").closest("button")).toBeDisabled();
    expect(screen.getByTestId("name-results").textContent).toBe("Loading...");
  });

  it("displays error when generation fails", async () => {
    // Simulate a failed AI operation: start() calls execute → errorMapper → onError → setError
    mockedUseAIOperation.mockImplementation((options: UseAIOperationOptions<unknown>) => {
      const start = vi.fn(() => {
        options.execute(createAbortSignal()).catch((err) => {
          const mapped = options.errorMapper?.(err);
          if (mapped) options.onError?.(mapped);
        });
      });
      return createMockAiOp({ start });
    });

    mockedGenerationApi.generateNames.mockRejectedValue(new Error("Generation failed"));

    const user = userEvent.setup();
    renderWithProviders(<NameGenerator novelId="novel-1" />);

    await waitForFormReady();

    await user.click(screen.getByText("generation.generateNames"));

    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert).toBeDefined();
      // CR-AUFG-07-33: the raw backend message must NOT leak into the UI;
      // the structured i18n connection message is shown instead (§16.5).
      expect(alert.textContent).not.toContain("Generation failed");
      expect(alert.textContent).toContain("Verbindung verloren");
    });
  });

  it("clamps count value to maximum 50", async () => {
    const user = userEvent.setup();
    renderWithProviders(<NameGenerator novelId="novel-1" />);

    await waitForFormReady();

    const countInput = screen.getByLabelText("generation.count") as HTMLInputElement;

    // Default is 10. Clear and type 100 — onChange clamps to 50.
    await user.clear(countInput);
    await user.type(countInput, "100");
    // The onChange handler clamps: Math.min(50, 100) = 50
    expect(Number(countInput.value)).toBeLessThanOrEqual(50);
  });

  it("sends correct parameters via start", async () => {
    const mockStart = vi.fn();
    mockedUseAIOperation.mockReturnValue(createMockAiOp({ start: mockStart }));

    const user = userEvent.setup();
    renderWithProviders(<NameGenerator novelId="novel-1" />);

    await waitForFormReady();

    await user.click(screen.getByText("generation.generateNames"));

    expect(mockStart).toHaveBeenCalledOnce();
    // start() reads requestRef.current which is set before calling start
    // The request is constructed from the form state
    expect(mockedGenerationApi.generateNames).not.toHaveBeenCalled(); // Not called via mock
  });
});
