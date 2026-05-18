import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { mockPromptsApi, mockUseQuery } = vi.hoisted(() => ({
  mockPromptsApi: { diff: vi.fn(), save: vi.fn(), reset: vi.fn() },
  mockUseQuery: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  promptsApi: mockPromptsApi,
}));

vi.mock("@tanstack/react-query", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-query")>()),
  useQuery: mockUseQuery,
  useMutation: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
  })),
  useQueryClient: vi.fn(() => ({ invalidateQueries: vi.fn() })),
}));

import { PromptDiff } from "@/components/studio/settings/PromptDiff";

describe("PromptDiff", () => {
  const defaultProps = {
    promptId: "prompt-1",
    onBack: vi.fn(),
    onResolved: vi.fn(),
  };

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state", () => {
    mockUseQuery.mockReturnValue({ data: undefined, isLoading: true, error: null });
    render(<PromptDiff {...defaultProps} />);
    expect(screen.getByText("settings.prompts.loadingPrompt")).toBeDefined();
  });

  it("shows error state when data fetch fails", () => {
    mockUseQuery.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("Failed"),
    });
    render(<PromptDiff {...defaultProps} />);
    expect(screen.getByText("settings.prompts.loadFailed")).toBeDefined();
  });

  it("renders diff view with same content", () => {
    mockUseQuery.mockReturnValue({
      data: {
        override_content: "Hello\nWorld",
        bundled_content: "Hello\nWorld",
      },
      isLoading: false,
      error: null,
    });
    render(<PromptDiff {...defaultProps} />);
    expect(screen.getByText("settings.prompts.diffTitle")).toBeDefined();
    expect(screen.getByText("settings.prompts.yourVersion")).toBeDefined();
    expect(screen.getByText("settings.prompts.newDefault")).toBeDefined();
  });

  it("renders diff view with different content", () => {
    mockUseQuery.mockReturnValue({
      data: {
        override_content: "Old content",
        bundled_content: "New content",
      },
      isLoading: false,
      error: null,
    });
    render(<PromptDiff {...defaultProps} />);
    expect(screen.getByText("settings.prompts.diffTitle")).toBeDefined();
    expect(screen.getByText("settings.prompts.keepMyVersion")).toBeDefined();
  });
});
