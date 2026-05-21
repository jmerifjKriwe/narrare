import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { tonesApi } from "@/lib/api/client";
import type { CustomTone } from "@/types";
import { ToneLibrarySection } from "../ToneLibrarySection";

// --- Mocks ---
// Note: next-intl is mocked globally in setupTests.ts

vi.mock("@/lib/api/client", () => ({
  tonesApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

// --- Fixtures ---

const mockTones: CustomTone[] = [
  { id: "tone-1", name: "Epic Fantasy", instructions: "Write in an epic, grandiose style" },
  { id: "tone-2", name: "Noir", instructions: "Dark, cynical, hard-boiled detective style" },
];

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

describe("ToneLibrarySection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(tonesApi.list).mockResolvedValue([...mockTones]);
  });

  it("renders the tone library title and description", async () => {
    renderWithProviders(<ToneLibrarySection />);

    await waitFor(() => {
      expect(screen.getByText("tones.title")).toBeInTheDocument();
    });
    expect(screen.getByText("tones.description")).toBeInTheDocument();
  });

  it("shows loading state while fetching tones", () => {
    vi.mocked(tonesApi.list).mockReturnValue(new Promise(() => {}));
    renderWithProviders(<ToneLibrarySection />);

    // Loading spinner should be present
    expect(document.querySelector(".animate-spin")).toBeInTheDocument();
  });

  it("renders tone list after loading", async () => {
    renderWithProviders(<ToneLibrarySection />);

    await waitFor(() => {
      expect(screen.getByText("Epic Fantasy")).toBeInTheDocument();
    });
    expect(screen.getByText("Noir")).toBeInTheDocument();
  });

  it("shows empty state when no custom tones exist", async () => {
    vi.mocked(tonesApi.list).mockResolvedValue([]);

    renderWithProviders(<ToneLibrarySection />);

    await waitFor(() => {
      expect(screen.getByText("tones.emptyState")).toBeInTheDocument();
    });
  });

  it("opens create dialog when add button is clicked", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ToneLibrarySection />);

    await waitFor(() => {
      expect(screen.getByText("Epic Fantasy")).toBeInTheDocument();
    });

    const addButton = screen.getByText("tones.addTone");
    await user.click(addButton);

    // Dialog should render with form fields
    await waitFor(() => {
      expect(screen.getByLabelText("tones.toneName")).toBeInTheDocument();
    });
    expect(screen.getByLabelText("tones.toneInstructions")).toBeInTheDocument();
  });

  it("calls delete when delete button is clicked", async () => {
    vi.mocked(tonesApi.delete).mockResolvedValue(undefined);

    const user = userEvent.setup();
    renderWithProviders(<ToneLibrarySection />);

    await waitFor(() => {
      expect(screen.getByText("Epic Fantasy")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByLabelText("tones.deleteTone");
    await user.click(deleteButtons[0]);

    await waitFor(() => {
      expect(tonesApi.delete).toHaveBeenCalledWith("tone-1");
    });
  });
});
