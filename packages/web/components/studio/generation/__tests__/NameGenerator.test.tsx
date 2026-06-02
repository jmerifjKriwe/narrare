/**
 * NameGenerator tests — name generation form component.
 *
 * Tests:
 * 1. Renders all form fields
 * 2. Form submission triggers API call
 * 3. Results display after generation
 * 4. Loading state during generation
 * 5. Error handling
 * 6. Count validation (clamped to 1–50)
 * 7. Generates with correct parameters
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { NameGenerator } from "@/components/studio/generation/NameGenerator";

// ---------------------------------------------------------------------------
// Hoisted mock data (needed in vi.mock factory, which is hoisted)
// ---------------------------------------------------------------------------

const { mockNovel, mockNameResponse } = vi.hoisted(() => {
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

  return { mockNovel, mockNameResponse };
});

// ---------------------------------------------------------------------------
// Local type for mock response shape
// ---------------------------------------------------------------------------

type MockNameResponse = typeof mockNameResponse;

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/lib/api/client", () => ({
  novelsApi: {
    get: vi.fn().mockResolvedValue(mockNovel),
  },
  generationApi: {
    generateNames: vi.fn().mockResolvedValue(mockNameResponse),
  },
}));

vi.mock("@/components/studio/generation/NameResults", () => ({
  NameResults: vi.fn(
    ({ results, isLoading }: { results: MockNameResponse | null; isLoading: boolean }) => (
      <div data-testid="name-results">
        {isLoading ? "Loading..." : results ? `${results.count} results` : "No results"}
      </div>
    ),
  ),
}));

vi.mock("@/lib/constants/name-styles", () => ({
  NAME_STYLE_SUGGESTIONS: ["Fantasy", "Sci-Fi", "Nordisch"],
}));

// Static import of the mocked module for typed access in tests
import { generationApi, novelsApi } from "@/lib/api/client";

const mockedGenerationApi = vi.mocked(generationApi);
const mockedNovelsApi = vi.mocked(novelsApi);

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
    // Re-apply default mock return values after clearing
    mockedNovelsApi.get.mockResolvedValue({ ...mockNovel });
    mockedGenerationApi.generateNames.mockResolvedValue({ ...mockNameResponse });
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

  it("form submission triggers API call", async () => {
    const user = userEvent.setup();
    renderWithProviders(<NameGenerator novelId="novel-1" />);

    await waitForFormReady();

    await user.click(screen.getByText("generation.generateNames"));

    await waitFor(() => {
      expect(mockedGenerationApi.generateNames).toHaveBeenCalledOnce();
    });
  });

  it("displays results after generation", async () => {
    const user = userEvent.setup();
    renderWithProviders(<NameGenerator novelId="novel-1" />);

    await waitForFormReady();

    await user.click(screen.getByText("generation.generateNames"));

    await waitFor(() => {
      expect(screen.getByTestId("name-results").textContent).toBe("2 results");
    });
  });

  it("shows loading state during generation", async () => {
    const user = userEvent.setup();

    // Create a controlled promise so the mutation stays pending
    let resolveGeneration: (value: typeof mockNameResponse) => void;
    const pendingPromise = new Promise<typeof mockNameResponse>((resolve) => {
      resolveGeneration = resolve;
    });
    mockedGenerationApi.generateNames.mockReturnValue(pendingPromise);

    renderWithProviders(<NameGenerator novelId="novel-1" />);

    await waitForFormReady();

    await user.click(screen.getByText("generation.generateNames"));

    // During pending: button shows generating text and is disabled
    await waitFor(() => {
      expect(screen.getByText("generating")).toBeDefined();
    });
    expect(screen.getByText("generating").closest("button")).toBeDisabled();
    expect(screen.getByTestId("name-results").textContent).toBe("Loading...");

    // Resolve to clean up pending state
    resolveGeneration!(mockNameResponse);
    await waitFor(() => {
      expect(screen.getByText("generation.generateNames")).toBeDefined();
    });
  });

  it("displays error when generation fails", async () => {
    const user = userEvent.setup();
    mockedGenerationApi.generateNames.mockRejectedValue(new Error("Generation failed"));

    renderWithProviders(<NameGenerator novelId="novel-1" />);

    await waitForFormReady();

    await user.click(screen.getByText("generation.generateNames"));

    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert).toBeDefined();
      expect(alert.textContent).toBe("Generation failed");
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

  it("sends correct parameters to generation API", async () => {
    const user = userEvent.setup();
    renderWithProviders(<NameGenerator novelId="novel-1" />);

    await waitForFormReady();

    await user.click(screen.getByText("generation.generateNames"));

    await waitFor(() => {
      expect(mockedGenerationApi.generateNames).toHaveBeenCalledOnce();
    });

    const calledWith = mockedGenerationApi.generateNames.mock.calls[0][0];
    expect(calledWith).toEqual({
      project_id: "novel-1",
      name_type: "character",
      name_style: "Fantasy",
      count: 10,
      gender: "any",
      explanation_language: "en",
    });
  });
});
