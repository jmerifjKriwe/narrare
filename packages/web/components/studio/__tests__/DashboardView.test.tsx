import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DashboardView } from "@/components/studio/DashboardView";

// --- Mocks ---

const { mockNovelsApi, mockUseQuery } = vi.hoisted(() => ({
  mockNovelsApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  mockUseQuery: vi.fn(
    ({ queryKey }: { queryKey: string[] }): { data: unknown; isLoading: boolean } => {
      if (queryKey[0] === "auth") {
        return { data: { display_name: "Test User", email: "test@test.com" }, isLoading: false };
      }
      return { data: [], isLoading: false };
    },
  ),
}));

vi.mock("@/lib/api/client", () => ({
  novelsApi: mockNovelsApi,
  authApi: { me: vi.fn() },
  setupApi: { listDemos: vi.fn().mockResolvedValue([]) },
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: mockUseQuery,
  useMutation: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => ({ invalidateQueries: vi.fn() })),
  QueryClient: class {
    getQueryData = vi.fn();
    setQueryData = vi.fn();
    invalidateQueries = vi.fn();
  },
  QueryClientProvider: ({ children }: { children: React.ReactNode }) => children,
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
      ({ queryKey }: { queryKey: string[] }): { data: unknown; isLoading: boolean } => {
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
    mockUseQuery.mockImplementation(
      ({ queryKey }: { queryKey: string[] }): { data: unknown; isLoading: boolean } => {
        if (queryKey[0] === "auth") {
          return { data: { display_name: "Test User", email: "test@test.com" }, isLoading: false };
        }
        return { data: undefined, isLoading: true };
      },
    );
    render(<DashboardView />);
    // Loading skeleton renders 3 pulse animation divs
    expect(screen.getByText("dashboard.title")).toBeDefined();
  });

  it("shows novels grid when novels exist", () => {
    mockUseQuery.mockImplementation(
      ({ queryKey }: { queryKey: string[] }): { data: unknown; isLoading: boolean } => {
        if (queryKey[0] === "auth") {
          return { data: { display_name: "Test User", email: "test@test.com" }, isLoading: false };
        }
        if (queryKey[0] === "novels") {
          return {
            data: [
              {
                id: "1",
                title: "My Novel",
                author: "Author",
                genre: "Fantasy",
                updated_at: "2024-01-01",
              },
            ],
            isLoading: false,
          };
        }
        // series / demos / novel-series etc. — must NOT receive novel data
        return { data: [], isLoading: false };
      },
    );
    render(<DashboardView />);
    expect(screen.getByText("My Novel")).toBeDefined();
    expect(screen.getByText("Author")).toBeDefined();
    expect(screen.getByText("Fantasy")).toBeDefined();
  });

  it("renders series cards and standalone novels together (N2 mixed grid)", () => {
    mockUseQuery.mockImplementation(
      ({ queryKey }: { queryKey: string[] }): { data: unknown; isLoading: boolean } => {
        if (queryKey[0] === "auth") {
          return { data: { display_name: "Test User", email: "test@test.com" }, isLoading: false };
        }
        if (queryKey[0] === "series") {
          return {
            data: [
              {
                id: "s1",
                title: "The Expanse",
                subtitle: null,
                status: "active",
                novel_count: 4,
              },
            ],
            isLoading: false,
          };
        }
        if (queryKey[0] === "novels") {
          return {
            data: [
              {
                id: "n1",
                title: "Standalone Book",
                author: "Author",
                genre: "Fantasy",
                updated_at: "2024-01-01",
                series_id: null,
              },
            ],
            isLoading: false,
          };
        }
        // demos / novel-series etc. — must NOT receive novel data
        return { data: [], isLoading: false };
      },
    );
    render(<DashboardView />);
    expect(screen.getByText("The Expanse")).toBeDefined();
    expect(screen.getByText("Standalone Book")).toBeDefined();
  });

  it("does not show novels that belong to a series as standalone cards", () => {
    mockUseQuery.mockImplementation(
      ({ queryKey }: { queryKey: string[] }): { data: unknown; isLoading: boolean } => {
        if (queryKey[0] === "auth") {
          return { data: { display_name: "Test User", email: "test@test.com" }, isLoading: false };
        }
        if (queryKey[0] === "series") {
          return {
            data: [
              {
                id: "s1",
                title: "The Expanse",
                subtitle: null,
                status: "active",
                novel_count: 1,
              },
            ],
            isLoading: false,
          };
        }
        if (queryKey[0] === "novels") {
          return {
            data: [
              {
                id: "n2",
                title: "Member Novel",
                author: "Author",
                genre: "Fantasy",
                updated_at: "2024-01-01",
                series_id: "s1",
              },
            ],
            isLoading: false,
          };
        }
        // demos / novel-series etc. — must NOT receive novel data, otherwise
        // DemoProjectCards would render the member novel as a demo card and
        // defeat the purpose of this assertion.
        return { data: [], isLoading: false };
      },
    );
    render(<DashboardView />);
    // The series still shows; its member novel is NOT duplicated as standalone.
    expect(screen.getByText("The Expanse")).toBeDefined();
    expect(screen.queryByText("Member Novel")).toBeNull();
  });

  it("renders a New Series entry point", () => {
    render(<DashboardView />);
    expect(screen.getByTestId("new-series-btn")).toBeDefined();
  });
});
