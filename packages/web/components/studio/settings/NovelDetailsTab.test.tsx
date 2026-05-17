import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { novelsApi } from "@/lib/api/client";
import type { Novel } from "@/types";
import { NovelDetailsTab } from "./NovelDetailsTab";

// --- Mocks ---
// Note: next-intl is mocked globally in setupTests.ts

vi.mock("@/lib/api/client", () => ({
  novelsApi: {
    get: vi.fn(),
    update: vi.fn(),
  },
}));

// --- Fixtures ---

const mockNovel: Novel = {
  id: "novel-1",
  title: "Test Novel",
  author: "Jane Doe",
  genre: "Fantasy",
  language: "en",
  tone: "dramatic",
  story_structure: "three_act",
  logline: "A hero saves the world",
  synopsis: "An epic tale of adventure",
  is_demo: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

// --- Helpers ---

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = createQueryClient();
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

// --- Tests ---

describe("NovelDetailsTab", () => {
  beforeEach(() => {
    vi.mocked(novelsApi.get).mockResolvedValue({ ...mockNovel });
    vi.mocked(novelsApi.update).mockResolvedValue({ ...mockNovel });
  });

  it("renders loading state while novel data is fetching", () => {
    // Return a never-resolving promise to keep loading state
    vi.mocked(novelsApi.get).mockReturnValueOnce(new Promise(() => {}));

    renderWithProviders(<NovelDetailsTab novelId="novel-1" />);

    expect(document.querySelector(".animate-spin")).toBeInTheDocument();
  });

  it("renders form with pre-populated data after loading", async () => {
    renderWithProviders(<NovelDetailsTab novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByDisplayValue("Test Novel")).toBeInTheDocument();
    });

    expect(screen.getByDisplayValue("Jane Doe")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Fantasy")).toBeInTheDocument();
    expect(screen.getByDisplayValue("A hero saves the world")).toBeInTheDocument();
    expect(screen.getByDisplayValue("An epic tale of adventure")).toBeInTheDocument();
  });

  it("tracks dirty state when a field is edited (Save button appears)", async () => {
    const user = userEvent.setup();
    renderWithProviders(<NovelDetailsTab novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByDisplayValue("Test Novel")).toBeInTheDocument();
    });

    // Save button should not be visible initially
    expect(screen.queryByText("settings.ai.save")).not.toBeInTheDocument();

    // Edit the title field
    const titleInput = screen.getByDisplayValue("Test Novel");
    await user.clear(titleInput);
    await user.type(titleInput, "New Title");

    // Save button should now appear
    expect(screen.getByText("settings.ai.save")).toBeInTheDocument();
  });

  it("calls novelsApi.update() on save with only changed fields", async () => {
    const user = userEvent.setup();
    renderWithProviders(<NovelDetailsTab novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByDisplayValue("Test Novel")).toBeInTheDocument();
    });

    // Edit only the title
    const titleInput = screen.getByDisplayValue("Test Novel");
    await user.clear(titleInput);
    await user.type(titleInput, "New Title");

    // Click save
    const saveButton = screen.getByText("settings.ai.save");
    await user.click(saveButton);

    // Verify update was called with only the changed field
    await waitFor(() => {
      expect(novelsApi.update).toHaveBeenCalledWith("novel-1", {
        title: "New Title",
      });
    });
  });

  it("clears dirty state after successful save", async () => {
    const user = userEvent.setup();
    renderWithProviders(<NovelDetailsTab novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByDisplayValue("Test Novel")).toBeInTheDocument();
    });

    // Edit a field
    const titleInput = screen.getByDisplayValue("Test Novel");
    await user.clear(titleInput);
    await user.type(titleInput, "New Title");

    // Save button visible
    expect(screen.getByText("settings.ai.save")).toBeInTheDocument();

    // Click save
    await user.click(screen.getByText("settings.ai.save"));

    // After successful save, save button should disappear (dirty cleared)
    await waitFor(() => {
      expect(screen.queryByText("settings.ai.save")).not.toBeInTheDocument();
    });
  });

  it("handles save error gracefully", async () => {
    vi.mocked(novelsApi.update).mockRejectedValueOnce(new Error("Network error"));

    const user = userEvent.setup();
    renderWithProviders(<NovelDetailsTab novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByDisplayValue("Test Novel")).toBeInTheDocument();
    });

    // Edit a field
    const titleInput = screen.getByDisplayValue("Test Novel");
    await user.clear(titleInput);
    await user.type(titleInput, "New Title");

    // Click save
    await user.click(screen.getByText("settings.ai.save"));

    // Error message should appear
    await waitFor(() => {
      expect(screen.getByText("settings.novelDetailsSection.saveError")).toBeInTheDocument();
    });

    // Save button should still be visible (dirty state preserved)
    expect(screen.getByText("settings.ai.save")).toBeInTheDocument();
  });
});
