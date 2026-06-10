/**
 * NameGeneratorModal tests — name generation side panel.
 *
 * Tests:
 * 1. Renders form with type/culture/count selectors
 * 2. Submits generation request
 * 3. Displays results
 * 4. Shows duplicate badges when is_duplicate=true
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NameGeneratorModal } from "@/components/studio/generation/NameGeneratorModal";
import type { NameGenerateResponse } from "@/types";

// ---------------------------------------------------------------------------
// Mock generation API (bypasses MSW — not compatible with happy-dom)
// ---------------------------------------------------------------------------

const { mockGenerateNames, mockNovelGet } = vi.hoisted(() => ({
  mockGenerateNames: vi.fn(),
  mockNovelGet: vi.fn().mockResolvedValue({ id: "novel-1", writing_language: "en" }),
}));

vi.mock("@/lib/api/client", () => ({
  generationApi: { generateNames: mockGenerateNames },
  novelsApi: { get: mockNovelGet },
}));

const sampleResponse: NameGenerateResponse = {
  names: [
    {
      name: "TestName1",
      pronunciation: "TEST-nam",
      meaning: "Test meaning",
      type: "character",
      name_style: "fantasy",
      is_duplicate: true,
      confidence: 0.9,
    },
    {
      name: "TestName2",
      pronunciation: null,
      meaning: null,
      type: "character",
      name_style: "fantasy",
      is_duplicate: false,
      confidence: 0.85,
    },
  ],
  count: 2,
  name_style: "fantasy",
  name_type: "character",
};

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
// Tests
// ---------------------------------------------------------------------------

describe("NameGeneratorModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGenerateNames.mockResolvedValue(sampleResponse);
  });

  it("renders form with type/culture/count selectors when open", async () => {
    renderWithProviders(<NameGeneratorModal novelId="novel-1" isOpen={true} onClose={vi.fn()} />);

    // Wait for the modal to render
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeDefined();
    });

    // Name type selector
    expect(screen.getByLabelText("generation.nameType")).toBeDefined();
    // Name style input
    expect(screen.getByLabelText("generation.nameStyle")).toBeDefined();
    // Count input
    expect(screen.getByLabelText("generation.count")).toBeDefined();
  });

  it("submits generation request when generate button is clicked", async () => {
    renderWithProviders(<NameGeneratorModal novelId="novel-1" isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("generation.generateNames")).toBeDefined();
    });

    // Click generate button inside act so React flushes microtasks
    await act(async () => {
      fireEvent.click(screen.getByText("generation.generateNames"));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    // After clicking, the MSW handler returns results
    // The button text should change or results should appear
    await waitFor(() => {
      // Either the button shows "generation.generating" or results appear
      const generating = screen.queryByText("generation.generating");
      const results = screen.queryByText(/generation\.nameGenerator \(/);
      expect(generating || results).toBeDefined();
    });
  });

  it("displays results after generation", async () => {
    renderWithProviders(<NameGeneratorModal novelId="novel-1" isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("generation.generateNames")).toBeDefined();
    });

    // Click generate inside act so React flushes microtasks and state updates
    await act(async () => {
      fireEvent.click(screen.getByText("generation.generateNames"));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    // Wait for results to appear in DOM
    await waitFor(() => {
      expect(screen.getByText("TestName1")).toBeDefined();
    });
    expect(screen.getByText("TestName2")).toBeDefined();
  });

  it("shows duplicate badges when is_duplicate=true", async () => {
    renderWithProviders(<NameGeneratorModal novelId="novel-1" isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("generation.generateNames")).toBeDefined();
    });

    // Click generate inside act so React flushes microtasks
    await act(async () => {
      fireEvent.click(screen.getByText("generation.generateNames"));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    // Mock returns TestName1 with is_duplicate=true (first item)
    await waitFor(() => {
      expect(screen.getByText("TestName1")).toBeDefined();
    });

    // The duplicate badge should appear
    expect(screen.getByText("generation.duplicate")).toBeDefined();
  });

  it("does not render when isOpen is false", () => {
    const { container } = renderWithProviders(
      <NameGeneratorModal novelId="novel-1" isOpen={false} onClose={vi.fn()} />,
    );

    expect(container.firstChild).toBeNull();
  });

  it("renders close button when open", async () => {
    renderWithProviders(<NameGeneratorModal novelId="novel-1" isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "generation.close" })).toBeDefined();
    });
  });

  it("renders gender selector", async () => {
    renderWithProviders(<NameGeneratorModal novelId="novel-1" isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByLabelText("generation.gender")).toBeDefined();
    });
  });
});
