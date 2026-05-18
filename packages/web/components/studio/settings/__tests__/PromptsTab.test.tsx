import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PromptsTab } from "@/components/studio/settings/PromptsTab";

// --- Hoisted mock data (must be before vi.mock) ---

const { mockPrompts, mockUpdates, mockPromptsList, mockPromptsUpdates } = vi.hoisted(() => ({
  mockPrompts: [
    {
      prompt_id: "generation/names",
      name: "Name Generation",
      category: "generation",
      is_overridden: false,
      content: "Generate names for...",
      variables: [],
    },
    {
      prompt_id: "writing/general",
      name: "Writing",
      category: "writing",
      is_overridden: true,
      content: "Write content...",
      variables: [],
    },
  ],
  mockUpdates: [
    { prompt_id: "generation/names", has_update: true, bundled_content: "new content" },
  ],
  mockPromptsList: vi.fn(),
  mockPromptsUpdates: vi.fn(),
}));

// --- Mocks ---

vi.mock("@/lib/api/client", () => ({
  promptsApi: {
    list: (...args: unknown[]) => mockPromptsList(...args),
    updates: (...args: unknown[]) => mockPromptsUpdates(...args),
  },
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn(({ queryKey }: { queryKey: string[] }) => {
    if (queryKey[0] === "prompts-updates") {
      return { data: mockUpdates, isLoading: false };
    }
    return { data: mockPrompts, isLoading: false };
  }),
  useQueryClient: vi.fn(() => ({ invalidateQueries: vi.fn() })),
  QueryClient: vi.fn(),
  QueryClientProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// --- Tests ---

describe("PromptsTab", () => {
  it("renders prompts tab title", () => {
    render(<PromptsTab />);
    expect(screen.getByText("settings.prompts.title")).toBeDefined();
  });

  it("renders prompt names from API", () => {
    render(<PromptsTab />);
    expect(screen.getByText("Name Generation")).toBeDefined();
  });

  it("renders filter category buttons", () => {
    render(<PromptsTab />);
    expect(screen.getByText("settings.prompts.allCategories")).toBeDefined();
  });

  it("renders prompt categories from data", () => {
    render(<PromptsTab />);
    const genElements = screen.getAllByText("settings.prompts.generation");
    expect(genElements.length).toBeGreaterThanOrEqual(1);
    const writingElements = screen.getAllByText("settings.prompts.writing");
    expect(writingElements.length).toBeGreaterThanOrEqual(1);
  });

  it("shows update badge for prompts with updates", () => {
    render(<PromptsTab />);
    expect(screen.getByText("settings.prompts.updateAvailable")).toBeDefined();
  });

  it("shows source override label for overridden prompts", () => {
    render(<PromptsTab />);
    const overrideLabels = screen.getAllByText("settings.prompts.sourceOverride");
    expect(overrideLabels.length).toBeGreaterThanOrEqual(1);
  });
});
