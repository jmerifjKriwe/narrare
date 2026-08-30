import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SettingsView } from "@/components/studio/SettingsView";

// --- Hoisted mocks ---

const { mockGetUser, mockUpdateUser, navigationMocks } = vi.hoisted(() => ({
  mockGetUser: vi.fn(),
  mockUpdateUser: vi.fn(),
  navigationMocks: {
    pathname: "/novel/novel-1/settings",
    push: vi.fn(),
    replace: vi.fn(),
    searchParams: new URLSearchParams(),
  },
}));

// --- Mocks ---

vi.mock("@/lib/api/client", () => ({
  settingsApi: {
    getUser: (...args: unknown[]) => mockGetUser(...args),
    updateUser: (...args: unknown[]) => mockUpdateUser(...args),
  },
  aiSettingsApi: {
    listProviders: vi.fn(),
    getUserSettings: vi.fn(),
    getProviderModels: vi.fn(),
    updateUserSettings: vi.fn(),
    createProvider: vi.fn(),
    updateProvider: vi.fn(),
    deleteProvider: vi.fn(),
  },
  tokenLimitsApi: {
    getResolved: vi.fn(),
    updateUser: vi.fn(),
    updateProject: vi.fn(),
  },
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(({ queryKey }: { queryKey: string[] }) => {
    if (queryKey[0] === "settings" && queryKey[1] === "user") {
      return { data: { display_name: "Test User", ui_language: "en" }, isLoading: false };
    }
    if (queryKey[0] === "novels") {
      return {
        data: {
          author: "Test Author",
          genre: "Fantasy",
          logline: "A test logline",
          synopsis: "A test synopsis",
          story_structure: "three_act",
          title: "Test Novel",
          tone: "adventurous",
          writing_language: "en",
        },
        isLoading: false,
      };
    }
    if (queryKey[0] === "settings" && queryKey[1] === "ai" && queryKey[2] === "providers") {
      return { data: [], isLoading: false };
    }
    if (queryKey[0] === "settings" && queryKey[1] === "ai") {
      return { data: null, isLoading: false };
    }
    if (queryKey[0] === "settings" && queryKey[1] === "ai" && queryKey[2] === "models") {
      return { data: { models: [] }, isLoading: false };
    }
    return { data: [], isLoading: false };
  }),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => ({ invalidateQueries: vi.fn() })),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => navigationMocks.pathname,
  useRouter: () => ({ push: navigationMocks.push, replace: navigationMocks.replace }),
  useSearchParams: () => navigationMocks.searchParams,
}));

describe("SettingsView", () => {
  beforeEach(() => {
    navigationMocks.push.mockClear();
    navigationMocks.replace.mockClear();
    navigationMocks.searchParams = new URLSearchParams();
  });

  it("renders settings title", () => {
    render(<SettingsView novelId="novel-1" />);
    expect(screen.getAllByText("settings.title").length).toBeGreaterThan(0);
  });

  it("labels the settings view section with its title", () => {
    render(<SettingsView novelId="novel-1" />);

    expect(screen.getByRole("region", { name: "settings.title" })).toBeInTheDocument();
  });

  it("renders all category buttons", () => {
    render(<SettingsView novelId="novel-1" />);
    const categoryKeys = [
      "settings.novelDetails",
      "settings.general",
      "settings.writingGoals",
      "settings.aiSetup",
      "settings.promptsTab",
      "settings.shortcuts",
      "settings.about",
    ];
    for (const key of categoryKeys) {
      expect(screen.getByText(key)).toBeDefined();
    }
  });

  it("defaults to novel-details tab", () => {
    render(<SettingsView novelId="novel-1" />);
    // NovelDetailsTab should render its title
    expect(screen.getByText("settings.novelDetails")).toBeDefined();
  });

  it("switches to shortcuts tab and renders shortcuts", () => {
    render(<SettingsView novelId="novel-1" />);
    fireEvent.click(screen.getByText("settings.shortcuts"));

    // Should render shortcut items
    expect(screen.getByText("settings.shortcutsSection.save")).toBeDefined();
    expect(screen.getByText("settings.shortcutsSection.newChapter")).toBeDefined();
    // Follow-up b3: the global quick-capture shortcut is documented here too.
    expect(screen.getByText("settings.shortcutsSection.quickCapture")).toBeDefined();
  });

  it("switches to about tab and renders about content", () => {
    render(<SettingsView novelId="novel-1" />);
    fireEvent.click(screen.getByText("settings.about"));

    // About section should render
    expect(screen.getByText("settings.about")).toBeDefined();
  });

  it("switches to ai tab when ai button is clicked", () => {
    render(<SettingsView novelId="novel-1" />);
    fireEvent.click(screen.getByText("settings.aiSetup"));

    // AiTab renders provider and model sections
    expect(screen.getByText("settings.ai.title")).toBeDefined();
  });

  it("initializes category from URL state", () => {
    navigationMocks.searchParams = new URLSearchParams("category=ai");

    render(<SettingsView novelId="novel-1" />);

    expect(screen.getByText("settings.ai.title")).toBeDefined();
  });

  it("normalizes invalid category URL state", () => {
    navigationMocks.searchParams = new URLSearchParams("category=missing");

    render(<SettingsView novelId="novel-1" />);

    expect(navigationMocks.replace).toHaveBeenCalledWith("/novel/novel-1/settings", {
      scroll: false,
    });
  });
});
