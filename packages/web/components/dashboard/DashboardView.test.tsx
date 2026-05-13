import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { server } from "@/mocks/server";
import { DashboardView } from "./DashboardView";

// --- Mocks ---

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

    expect(screen.getByText("Loading\u2026")).toBeInTheDocument();
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

  it("should show new novel after creating one", async () => {
    const user = userEvent.setup();

    const newNovel = {
      id: "new-novel-id",
      title: "Untitled Novel",
      author: "",
      genre: "",
      language: "en",
      is_demo: false,
      created_at: "2026-03-01T00:00:00Z",
      updated_at: "2026-03-01T00:00:00Z",
    };

    let created = false;
    server.use(
      http.get("*/api/v1/novels", () => {
        return HttpResponse.json(created ? [newNovel] : []);
      }),
      http.post("*/api/v1/novels", async () => {
        created = true;
        return HttpResponse.json(newNovel, { status: 201 });
      }),
    );

    render(<DashboardView />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/Every story begins with the first sentence/)).toBeInTheDocument();
    });

    const createButton = screen
      .getAllByRole("button")
      .find((btn) => btn.textContent?.includes("New novel"));
    expect(createButton).toBeTruthy();
    await user.click(createButton!);

    await waitFor(() => {
      expect(screen.getByText("Untitled Novel")).toBeInTheDocument();
    });
  });
});
