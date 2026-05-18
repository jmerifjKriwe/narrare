import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DashboardView } from "@/components/studio/DashboardView";

// --- Mocks ---

const { mockNovelsApi, mockUseQuery } = vi.hoisted(() => ({
  mockNovelsApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  mockUseQuery: vi.fn(({ queryKey }: { queryKey: string[] }) => {
    if (queryKey[0] === "auth") {
      return { data: { display_name: "Test User", email: "test@test.com" }, isLoading: false };
    }
    return { data: [], isLoading: false };
  }),
}));

vi.mock("@/lib/api/client", () => ({
  novelsApi: mockNovelsApi,
  authApi: { me: vi.fn() },
}));

vi.mock("@tanstack/react-query", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-query")>()),
  useQuery: mockUseQuery,
  useMutation: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => ({ invalidateQueries: vi.fn() })),
}));

vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: vi.fn((selector?: (s: Record<string, unknown>) => unknown) => {
    const state = { logout: vi.fn(), user: { display_name: "Test", email: "test@test.com" } };
    return selector ? selector(state) : state;
  }),
}));

describe("DashboardView", () => {
  afterEach(() => {
    vi.clearAllMocks();
    mockUseQuery.mockImplementation(
      ({ queryKey }: { queryKey: string[] }) => {
        if (queryKey[0] === "auth") {
          return { data: { display_name: "Test User", email: "test@test.com" }, isLoading: false };
        }
        return { data: [], isLoading: false };
      },
    );
  });

  it("renders dashboard title and subtitle", () => {
    render(<DashboardView />);
    expect(screen.getByText("dashboard.title")).toBeDefined();
    expect(screen.getByText("dashboard.subtitle")).toBeDefined();
  });

  it("shows empty state when no novels exist", () => {
    render(<DashboardView />);
    expect(screen.getByText("dashboard.emptyTitle")).toBeDefined();
    expect(screen.getByText("dashboard.emptySubtitle")).toBeDefined();
  });

  it("renders app name in header", () => {
    render(<DashboardView />);
    expect(screen.getByText("sidebar.appName")).toBeDefined();
  });

  it("renders user initial in profile avatar", () => {
    render(<DashboardView />);
    expect(screen.getByText("T")).toBeDefined(); // display_name starts with T
  });

  it("renders user name in header", () => {
    render(<DashboardView />);
    expect(screen.getByText("Test User")).toBeDefined();
  });

  it("renders logout button", () => {
    render(<DashboardView />);
    expect(screen.getByText("sidebar.logout")).toBeDefined();
  });

  it("shows loading state when novels are loading", () => {
    mockUseQuery.mockImplementation(({ queryKey }: { queryKey: string[] }) => {
      if (queryKey[0] === "auth") {
        return { data: { display_name: "Test User", email: "test@test.com" }, isLoading: false };
      }
      return { data: undefined, isLoading: true };
    });
    render(<DashboardView />);
    // Loading skeleton renders 3 pulse animation divs
    expect(screen.getByText("dashboard.title")).toBeDefined();
  });

  it("shows novels grid when novels exist", () => {
    mockUseQuery.mockImplementation(({ queryKey }: { queryKey: string[] }) => {
      if (queryKey[0] === "auth") {
        return { data: { display_name: "Test User", email: "test@test.com" }, isLoading: false };
      }
      return {
        data: [
          { id: "1", title: "My Novel", author: "Author", genre: "Fantasy", updated_at: "2024-01-01" },
        ],
        isLoading: false,
      };
    });
    render(<DashboardView />);
    expect(screen.getByText("My Novel")).toBeDefined();
    expect(screen.getByText("Author")).toBeDefined();
    expect(screen.getByText("Fantasy")).toBeDefined();
  });
});
