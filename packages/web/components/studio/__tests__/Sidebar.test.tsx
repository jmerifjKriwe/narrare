import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Sidebar } from "@/components/studio/Sidebar";

// Mock editorStore selectors
vi.mock("@/lib/stores/editorStore", () => ({
  useEditorStore: vi.fn((selector?: (s: Record<string, unknown>) => unknown) => {
    const state = {
      activeChapterId: "ch-1",
      activeVolumeId: "vol-1",
      setActiveChapterId: vi.fn(),
      setActiveVolumeId: vi.fn(),
    };
    return selector ? selector(state) : state;
  }),
}));

// Mock authStore
vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: vi.fn((selector?: (s: Record<string, unknown>) => unknown) => {
    const state = { logout: vi.fn(), user: null };
    return selector ? selector(state) : state;
  }),
}));

// Mock react-query
vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(({ queryKey }: { queryKey: string[] }) => {
    if (queryKey[0] === "auth") {
      return { data: { display_name: "Test User", email: "test@test.com" }, isLoading: false };
    }
    return { data: [], isLoading: false };
  }),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => ({ invalidateQueries: vi.fn() })),
}));

// Mock API client
vi.mock("@/lib/api/client", () => ({
  volumesApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    reorder: vi.fn(),
  },
  chaptersApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    reorder: vi.fn(),
  },
  authApi: { me: vi.fn() },
}));

describe("Sidebar", () => {
  it("renders sidebar with nav items", () => {
    render(<Sidebar />);
    expect(screen.getByText("sidebar.editor")).toBeDefined();
    expect(screen.getByText("sidebar.volumes")).toBeDefined();
    expect(screen.getByText("sidebar.worldbuilding")).toBeDefined();
    expect(screen.getByText("sidebar.analysis")).toBeDefined();
    expect(screen.getByText("sidebar.settings")).toBeDefined();
  });

  it("exposes the navigation landmark with an accessible name", () => {
    render(<Sidebar />);
    expect(screen.getByRole("navigation", { name: "sidebar.navigation" })).toBeDefined();
  });
});
