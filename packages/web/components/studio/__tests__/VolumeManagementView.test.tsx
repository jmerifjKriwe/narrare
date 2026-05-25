/**
 * VolumeManagementView tests — volume list, create flow, loading & empty states.
 *
 * Tests:
 * 1. Renders volume list after loading
 * 2. Shows loading spinner while fetching
 * 3. Shows empty state when no volumes exist
 * 4. Create button shows the form
 * 5. Create volume flow — fill title, submit, verify API call
 * 6. Cancel create hides the form
 * 7. Renders header with title heading
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { VolumeManagementView } from "@/components/studio/VolumeManagementView";
import type { Volume } from "@/types";

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
// Mock data
// ---------------------------------------------------------------------------

const mockVolumes: Volume[] = [
  {
    id: "vol-1",
    novel_id: "novel-1",
    title: "Volume One",
    subtitle: null,
    description: null,
    word_count_target: 50000,
    position: 0,
    is_default: false,
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "vol-2",
    novel_id: "novel-1",
    title: "Volume Two",
    subtitle: null,
    description: null,
    word_count_target: 40000,
    position: 1,
    is_default: false,
    created_at: "2026-01-01T00:00:00Z",
  },
];

const mockStats = {
  word_count: 45000,
  chapter_count: 12,
  word_count_target: 50000,
  completion_percentage: 90,
};

// ---------------------------------------------------------------------------
// Hoisted mock functions
// ---------------------------------------------------------------------------

const { mockList, mockCreate, mockUpdate, mockDelete, mockReorder, mockGetStats } = vi.hoisted(
  () => ({
    mockList: vi.fn(),
    mockCreate: vi.fn(),
    mockUpdate: vi.fn(),
    mockDelete: vi.fn(),
    mockReorder: vi.fn(),
    mockGetStats: vi.fn(),
  }),
);

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/lib/api/client", () => ({
  volumesApi: {
    list: (...args: unknown[]) => mockList(...args),
    create: (...args: unknown[]) => mockCreate(...args),
    update: (...args: unknown[]) => mockUpdate(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
    reorder: (...args: unknown[]) => mockReorder(...args),
    getStats: (...args: unknown[]) => mockGetStats(...args),
  },
}));

vi.mock("@/components/studio/VolumeCard", () => ({
  VolumeCard: vi.fn(({ volume }: { volume: Volume }) => (
    <div data-testid="volume-card">{volume.title}</div>
  )),
  VolumeFormFields: vi.fn(
    ({
      onTitleChange,
      onSubmit,
      onCancel,
      submitLabel,
    }: {
      onTitleChange: (value: string) => void;
      onSubmit: () => void;
      onCancel: () => void;
      submitLabel: string;
    }) => (
      <div data-testid="volume-form">
        <input data-testid="volume-title-input" onChange={(e) => onTitleChange(e.target.value)} />
        <button type="button" data-testid="volume-submit" onClick={onSubmit}>
          {submitLabel}
        </button>
        <button type="button" data-testid="volume-cancel" onClick={onCancel}>
          Cancel
        </button>
      </div>
    ),
  ),
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("VolumeManagementView", () => {
  beforeEach(() => {
    mockList.mockResolvedValue(mockVolumes);
    mockCreate.mockResolvedValue(mockVolumes[0]);
    mockUpdate.mockResolvedValue(mockVolumes[0]);
    mockDelete.mockResolvedValue(undefined);
    mockReorder.mockResolvedValue(mockVolumes);
    mockGetStats.mockResolvedValue(mockStats);
  });

  it("renders header with title", async () => {
    renderWithProviders(<VolumeManagementView />);

    await waitFor(() => {
      expect(screen.getByText("volumes.title")).toBeDefined();
    });
  });

  it("renders volume list after loading", async () => {
    renderWithProviders(<VolumeManagementView />);

    await waitFor(() => {
      const cards = screen.getAllByTestId("volume-card");
      expect(cards).toHaveLength(2);
    });

    expect(screen.getByText("Volume One")).toBeDefined();
    expect(screen.getByText("Volume Two")).toBeDefined();
  });

  it("shows loading state", () => {
    // Never-resolving promise keeps isLoading true
    mockList.mockReturnValue(new Promise(() => {}));

    renderWithProviders(<VolumeManagementView />);

    // Loader2 spinner renders via animate-spin class
    expect(document.querySelector(".animate-spin")).not.toBeNull();
  });

  it("shows empty state when no volumes", async () => {
    mockList.mockResolvedValue([]);

    renderWithProviders(<VolumeManagementView />);

    await waitFor(() => {
      expect(screen.getByText("volumes.noTarget")).toBeDefined();
    });
  });

  it("shows create form when create button is clicked", async () => {
    const user = userEvent.setup();
    renderWithProviders(<VolumeManagementView />);

    // Wait for volumes to load so the button is visible
    await waitFor(() => {
      expect(screen.getByText("Volume One")).toBeDefined();
    });

    await user.click(screen.getByText("volumes.createVolume"));

    expect(screen.getByTestId("volume-form")).toBeDefined();
  });

  it("creates a volume when form is submitted", async () => {
    const user = userEvent.setup();
    renderWithProviders(<VolumeManagementView />);

    await waitFor(() => {
      expect(screen.getByText("Volume One")).toBeDefined();
    });

    // Open create form
    await user.click(screen.getByText("volumes.createVolume"));

    // Fill in title
    await user.type(screen.getByTestId("volume-title-input"), "New Volume");

    // Submit
    await user.click(screen.getByTestId("volume-submit"));

    expect(mockCreate).toHaveBeenCalledWith("novel-1", {
      title: "New Volume",
      subtitle: null,
      description: null,
      word_count_target: null,
    });
  });

  it("hides create form on cancel", async () => {
    const user = userEvent.setup();
    renderWithProviders(<VolumeManagementView />);

    await waitFor(() => {
      expect(screen.getByText("Volume One")).toBeDefined();
    });

    // Open create form
    await user.click(screen.getByText("volumes.createVolume"));
    expect(screen.getByTestId("volume-form")).toBeDefined();

    // Cancel
    await user.click(screen.getByTestId("volume-cancel"));

    await waitFor(() => {
      expect(screen.queryByTestId("volume-form")).toBeNull();
    });
  });
});
