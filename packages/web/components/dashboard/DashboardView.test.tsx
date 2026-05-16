import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { server } from "@/mocks/server";
import { DashboardView } from "./DashboardView";

// --- Mocks ---

// Mock window.confirm
const mockConfirm = vi.spyOn(window, "confirm").mockReturnValue(true);

vi.mock("next-intl", () => ({
  useTranslations: (ns: string) => {
    const translations: Record<string, Record<string, string>> = {
      dashboard: {
        title: "Your novels",
        newNovel: "New novel",
        noNovels: "No novels yet.",
        noNovelsQuote: "Every story begins with the first sentence.",
        noNovelsHint: "Create your first novel to get started.",
        lastEdited: "Last edited {time}",
        demo: "Demo",
        deleteNovel: "Delete novel",
        confirmDelete: "Are you sure you want to delete this novel? This cannot be undone.",
      },
      common: { loading: "Loading\u2026" },
    };
    return (key: string) => translations[ns]?.[key] ?? `${ns}.${key}`;
  },
}));

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    back: vi.fn(),
  }),
}));

// --- Helpers ---

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = createQueryClient();
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.clearAllMocks();
  mockConfirm.mockReturnValue(true);
});

describe("DashboardView", () => {
  it("should render dashboard title", () => {
    render(<DashboardView />, { wrapper });

    expect(screen.getByText("Your novels")).toBeInTheDocument();
  });

  it("should render novel cards with MSW-mocked data", async () => {
    render(<DashboardView />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText("Test Novel One")).toBeInTheDocument();
      expect(screen.getByText("Test Novel Two")).toBeInTheDocument();
    });
  });

  it("should render author on novel cards when available", async () => {
    render(<DashboardView />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText("Author One")).toBeInTheDocument();
      expect(screen.getByText("Author Two")).toBeInTheDocument();
    });
  });

  it("should render genre on novel cards when available", async () => {
    render(<DashboardView />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText("fantasy")).toBeInTheDocument();
      expect(screen.getByText("scifi")).toBeInTheDocument();
    });
  });

  it("should show demo badge on demo novels", async () => {
    render(<DashboardView />, { wrapper });

    await waitFor(() => {
      const demoBadges = screen.getAllByText("Demo");
      expect(demoBadges.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("should navigate to editor when a novel card is clicked", async () => {
    const user = userEvent.setup();
    render(<DashboardView />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText("Test Novel One")).toBeInTheDocument();
    });

    const novelCard = screen.getByRole("button", { name: "Open Test Novel One" });
    await user.click(novelCard);

    expect(mockPush).toHaveBeenCalledWith("/novel/novel-1/editor");
  });

  it("should show loading state while fetching novels", () => {
    server.use(
      http.get("*/api/v1/novels", async () => {
        await new Promise((resolve) => {
          setTimeout(resolve, 5000);
        });
        return HttpResponse.json([]);
      }),
    );

    render(<DashboardView />, { wrapper });

    expect(screen.getByText(/Loading/)).toBeInTheDocument();
  });

  it("should show empty state when no novels exist", async () => {
    server.use(http.get("*/api/v1/novels", () => HttpResponse.json([])));

    render(<DashboardView />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/Every story begins with the first sentence/)).toBeInTheDocument();
      expect(screen.getByText("Create your first novel to get started.")).toBeInTheDocument();
    });
  });

  it("should render New Novel button in header", async () => {
    render(<DashboardView />, { wrapper });

    // Wait for novels to load, then the "+" card appears in the grid
    await waitFor(() => {
      const newButtons = screen
        .getAllByRole("button")
        .filter((btn) => btn.textContent?.includes("New novel"));
      expect(newButtons.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("should render New Novel button in empty state", async () => {
    server.use(http.get("*/api/v1/novels", () => HttpResponse.json([])));

    render(<DashboardView />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/Every story begins with the first sentence/)).toBeInTheDocument();
    });

    // There should be new novel buttons (header + empty state)
    const newButtons = screen
      .getAllByRole("button")
      .filter((btn) => btn.textContent?.includes("New novel"));
    expect(newButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("should navigate to wizard when New Novel button is clicked in empty state", async () => {
    const user = userEvent.setup();

    server.use(http.get("*/api/v1/novels", () => HttpResponse.json([])));

    render(<DashboardView />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/Every story begins with the first sentence/)).toBeInTheDocument();
    });

    const createButton = screen
      .getAllByRole("button")
      .find((btn) => btn.textContent?.includes("New novel"));
    expect(createButton).toBeTruthy();
    await user.click(createButton!);

    expect(mockPush).toHaveBeenCalledWith("/wizard");
  });

  it("should navigate to wizard when New Novel card is clicked in grid", async () => {
    const user = userEvent.setup();

    render(<DashboardView />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText("Test Novel One")).toBeInTheDocument();
    });

    // Find the dashed "+" new novel card in the grid
    const newNovelCard = screen.getByRole("button", { name: "New novel" });
    await user.click(newNovelCard);

    expect(mockPush).toHaveBeenCalledWith("/wizard");
  });

  // --- Delete functionality ---

  it("should render delete button on novel cards", async () => {
    render(<DashboardView />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText("Test Novel One")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByRole("button", { name: "Delete novel" });
    expect(deleteButtons.length).toBe(2); // one per novel
  });

  it("should call novelsApi.delete and invalidate queries after confirming delete", async () => {
    const user = userEvent.setup();
    const novelsDeleted: string[] = [];

    const novelsData = [
      {
        id: "novel-1",
        title: "Test Novel One",
        author: "Author One",
        genre: "fantasy",
        language: "en",
        is_demo: true,
        created_at: "2026-03-01T00:00:00Z",
        updated_at: "2026-03-10T12:00:00Z",
      },
      {
        id: "novel-2",
        title: "Test Novel Two",
        author: "Author Two",
        genre: "scifi",
        language: "en",
        is_demo: false,
        created_at: "2026-03-01T00:00:00Z",
        updated_at: "2026-03-05T12:00:00Z",
      },
    ];

    server.use(
      http.get("*/api/v1/novels", () => {
        const remaining = novelsData.filter((n) => !novelsDeleted.includes(n.id));
        return HttpResponse.json(remaining);
      }),
      http.delete("*/api/v1/novels/:novelId", ({ params }) => {
        novelsDeleted.push(params.novelId as string);
        return new HttpResponse(null, { status: 204 });
      }),
    );

    render(<DashboardView />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText("Test Novel One")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByRole("button", { name: "Delete novel" });
    await user.click(deleteButtons[0]);

    expect(mockConfirm).toHaveBeenCalledWith(
      "Are you sure you want to delete this novel? This cannot be undone.",
    );
    expect(novelsDeleted).toContain("novel-1");

    await waitFor(() => {
      expect(screen.queryByText("Test Novel One")).not.toBeInTheDocument();
    });
  });

  it("should not delete novel when user cancels confirmation", async () => {
    const user = userEvent.setup();
    mockConfirm.mockReturnValue(false);

    let deleteCalled = false;
    server.use(
      http.delete("*/api/v1/novels/:novelId", () => {
        deleteCalled = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    render(<DashboardView />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText("Test Novel One")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByRole("button", { name: "Delete novel" });
    await user.click(deleteButtons[0]);

    expect(mockConfirm).toHaveBeenCalled();
    expect(deleteCalled).toBe(false);
  });

  it("should not navigate to editor when delete button is clicked", async () => {
    const user = userEvent.setup();

    render(<DashboardView />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText("Test Novel One")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByRole("button", { name: "Delete novel" });
    await user.click(deleteButtons[0]);

    expect(mockPush).not.toHaveBeenCalled();
  });

  it("should use div with role=button for novel cards (no nested buttons)", async () => {
    render(<DashboardView />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText("Test Novel One")).toBeInTheDocument();
    });

    // NovelCard outer element is a div[role="button"], not a <button>
    const novelCard = screen.getByRole("button", { name: "Open Test Novel One" });
    expect(novelCard.tagName).toBe("DIV");
    expect(novelCard).toHaveAttribute("role", "button");
    expect(novelCard).toHaveAttribute("tabindex", "0");

    // Delete button inside is still a real <button>
    const deleteButtons = screen.getAllByRole("button", { name: "Delete novel" });
    expect(deleteButtons[0].tagName).toBe("BUTTON");
  });
});
