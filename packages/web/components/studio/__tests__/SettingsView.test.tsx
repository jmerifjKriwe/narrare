import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SettingsView } from "@/components/studio/SettingsView";

// --- Hoisted mocks ---

const { mockGetUser, mockUpdateUser } = vi.hoisted(() => ({
  mockGetUser: vi.fn(),
  mockUpdateUser: vi.fn(),
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
}));

vi.mock("@tanstack/react-query", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-query")>()),
  useQuery: vi.fn(({ queryKey }: { queryKey: string[] }) => {
    if (queryKey[0] === "settings" && queryKey[1] === "user") {
      return { data: { display_name: "Test User", ui_language: "en" }, isLoading: false };
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
    // Default: empty array for chapters, etc.
    return { data: [], isLoading: false };
  }),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => ({ invalidateQueries: vi.fn() })),
}));

describe("SettingsView", () => {
  it("renders settings title", () => {
    render(<SettingsView novelId="novel-1" />);
    expect(screen.getByText("settings.title")).toBeDefined();
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
});
