import {
  type UseMutationResult,
  type UseQueryResult,
  useMutation,
  useQuery,
} from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PromptEditor } from "@/components/studio/settings/PromptEditor";

// --- Mock data ---

const { mockPromptGet, mockPromptSave, mockPromptReset } = vi.hoisted(() => ({
  mockPromptGet: vi.fn(),
  mockPromptSave: vi.fn(),
  mockPromptReset: vi.fn(),
}));

const mockPrompt = {
  prompt_id: "generation/names",
  name: "Name Generation",
  category: "generation",
  content: "Generate a name for {{topic}}",
  is_overridden: false,
  variables: ["topic"],
  version: 1,
};

const overriddenPrompt = {
  ...mockPrompt,
  is_overridden: true,
  content: "Custom content for {{topic}}",
};

// --- Mocks ---

vi.mock("@/lib/api/client", () => ({
  promptsApi: {
    get: (...args: unknown[]) => mockPromptGet(...args),
    save: (...args: unknown[]) => mockPromptSave(...args),
    reset: (...args: unknown[]) => mockPromptReset(...args),
  },
}));

vi.mock("@tanstack/react-query", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-query")>()),
  useQuery: vi.fn(() => ({ data: mockPrompt, isLoading: false })),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => ({ invalidateQueries: vi.fn() })),
}));

// --- Tests ---

describe("PromptEditor", () => {
  const onBack = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useQuery).mockReturnValue({
      data: mockPrompt,
      isLoading: false,
    } as unknown as UseQueryResult);
    vi.mocked(useMutation).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as UseMutationResult);
  });

  it("renders prompt ID as title", () => {
    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    expect(screen.getByText("generation/names")).toBeDefined();
  });

  it("renders back button", () => {
    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    expect(screen.getByText("settings.prompts.back")).toBeDefined();
  });

  it("shows loading state when prompt is loading", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: undefined,
      isLoading: true,
    } as unknown as UseQueryResult);

    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    expect(screen.getByText("settings.prompts.loadingPrompt")).toBeDefined();
  });

  it("shows error state when prompt fails to load", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("fail"),
    } as unknown as UseQueryResult);

    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    expect(screen.getByText("settings.prompts.loadFailed")).toBeDefined();
  });

  it("shows error state when prompt is null", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: null,
      isLoading: false,
    } as unknown as UseQueryResult);

    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    expect(screen.getByText("settings.prompts.loadFailed")).toBeDefined();
  });

  it("shows bundled source badge for non-overridden prompt", () => {
    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    expect(screen.getByText("settings.prompts.sourceBundled")).toBeDefined();
  });

  it("shows override source badge for overridden prompt", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: overriddenPrompt,
      isLoading: false,
    } as unknown as UseQueryResult);

    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    expect(screen.getByText("settings.prompts.sourceOverride")).toBeDefined();
  });

  it("shows update available badge when hasUpdate is true", () => {
    render(<PromptEditor promptId="generation/names" hasUpdate={true} onBack={onBack} />);
    expect(screen.getByText("settings.prompts.updateAvailable")).toBeDefined();
  });

  it("renders prompt content in viewer", () => {
    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    expect(screen.getByText("Generate a name for {{topic}}")).toBeDefined();
  });

  it("renders edit button", () => {
    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    expect(screen.getByText("settings.prompts.editOverride")).toBeDefined();
  });

  it("switches to edit mode when edit button is clicked", () => {
    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    fireEvent.click(screen.getByText("settings.prompts.editOverride"));
    // Edit mode shows a textarea with the prompt content
    const textarea = screen.getByLabelText("settings.prompts.promptContent", { exact: false });
    expect(textarea).toBeDefined();
    expect((textarea as HTMLTextAreaElement).value).toBe("Generate a name for {{topic}}");
  });

  it("shows cancel and save buttons in edit mode", () => {
    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    fireEvent.click(screen.getByText("settings.prompts.editOverride"));
    expect(screen.getByText("settings.prompts.cancel")).toBeDefined();
    expect(screen.getByText("settings.prompts.saveOverride")).toBeDefined();
  });

  it("exits edit mode when cancel is clicked", () => {
    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    fireEvent.click(screen.getByText("settings.prompts.editOverride"));
    fireEvent.click(screen.getByText("settings.prompts.cancel"));
    // Should show edit button again
    expect(screen.getByText("settings.prompts.editOverride")).toBeDefined();
  });

  it("calls onBack when back button is clicked", () => {
    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    fireEvent.click(screen.getByText("settings.prompts.back"));
    expect(onBack).toHaveBeenCalledOnce();
  });

  it("shows variables sidebar when prompt has variables", () => {
    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    expect(screen.getByText("settings.prompts.variables")).toBeDefined();
  });

  it("renders variable names in sidebar", () => {
    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    expect(screen.getByText("{{topic}}")).toBeDefined();
  });
});
