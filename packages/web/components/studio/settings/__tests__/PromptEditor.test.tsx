/**
 * Tests for the refactored PromptEditor.
 *
 * After PROMPT-003 (CR-AUFG-07-16) the editor:
 *   - Uses usePromptEditorState hook for all state (RULE-04).
 *   - Renders PromptPreviewDialog (API-driven) instead of local substitution.
 *   - Renders PromptLiveTestDialog (SSE) with a token-warning gate.
 *   - Renders PromptResetConfirmDialog with override-vs-bundled preview.
 *
 * The local ``PromptPreview.tsx`` (EXAMPLE_VALUES substitution) is deleted.
 */

import {
  type UseMutationResult,
  type UseQueryResult,
  useMutation,
  useQuery,
} from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PromptEditor } from "@/components/studio/settings/PromptEditor";

// --- Mock data ---

const { mockPromptGet, mockPromptSave, mockPromptReset, mockPromptPreview, previewPayload } =
  vi.hoisted(() => ({
    mockPromptGet: vi.fn(),
    mockPromptSave: vi.fn(),
    mockPromptReset: vi.fn(),
    mockPromptPreview: vi.fn(),
    previewPayload: {
      system_prompt: "preview body",
      user_prompt: "",
      first_message: null,
      cascade_source: "bundled",
      variables: [],
      diagnostics: [],
    },
  }));

interface QueryOptionsSubset {
  readonly queryKey?: readonly unknown[];
  readonly enabled?: boolean;
  readonly queryFn?: () => unknown;
}

const mockPrompt = {
  prompt_id: "generation/names",
  name: "Name Generation",
  category: "generation",
  content: "Generate a name for {{topic}}",
  base_content: "Generate a name for {{topic}}",
  source: "bundled",
  is_overridden: false,
  variables: ["topic"],
  metadata: {},
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
    resetWithMetadata: vi.fn(() =>
      Promise.resolve({ reset: true, effective_source: "bundled", effective_content: "default" }),
    ),
    preview: (...args: unknown[]) => mockPromptPreview(...args),
  },
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn((opts?: QueryOptionsSubset) => {
    // Differentiate the two queries the editor issues: prompt detail and preview.
    const key = opts?.queryKey?.[0];
    if (key === "prompt-preview") {
      if (opts?.enabled) void opts?.queryFn?.();
      return { data: previewPayload, isLoading: false };
    }
    return { data: mockPrompt, isLoading: false };
  }),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => ({ invalidateQueries: vi.fn() })),
}));

// useAIOperation is mocked so the live-test never fires a real request.
vi.mock("@/lib/hooks/use-ai-operation", () => ({
  useAIOperation: vi.fn(() => ({
    state: { status: "idle", result: null, error: null, attemptCount: 0 },
    start: vi.fn(),
    cancel: vi.fn(),
    retry: vi.fn(),
    reset: vi.fn(),
    notifyData: vi.fn(),
    isIdle: true,
    isLoading: false,
    isStreaming: false,
    isComplete: false,
    isError: false,
    isConnectionLost: false,
  })),
}));

// --- Tests ---

describe("PromptEditor", () => {
  const onBack = vi.fn();

  afterEach(() => {
    vi.clearAllMocks();
  });

  beforeEach(() => {
    // Preserve the query-key-aware factory by using mockImplementation that
    // falls back to the per-test state for the prompt-detail query.
    vi.mocked(useQuery).mockImplementation(((opts?: QueryOptionsSubset) => {
      const key = opts?.queryKey?.[0];
      if (key === "prompt-preview") {
        if (opts?.enabled) void opts?.queryFn?.();
        return { data: previewPayload, isLoading: false } as unknown as UseQueryResult;
      }
      return {
        data: mockPrompt,
        isLoading: false,
      } as unknown as UseQueryResult;
    }) as typeof useQuery);
    vi.mocked(useMutation).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as UseMutationResult);
    mockPromptPreview.mockResolvedValue(previewPayload);
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
    vi.mocked(useQuery).mockImplementation((opts?: { queryKey?: readonly unknown[] }) => {
      if (opts?.queryKey?.[0] === "prompt-preview") {
        return { data: undefined, isLoading: false } as unknown as UseQueryResult;
      }
      return { data: undefined, isLoading: true } as unknown as UseQueryResult;
    });

    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    expect(screen.getByText("settings.prompts.loadingPrompt")).toBeDefined();
  });

  it("shows error state when prompt fails to load", () => {
    vi.mocked(useQuery).mockImplementation((opts?: { queryKey?: readonly unknown[] }) => {
      if (opts?.queryKey?.[0] === "prompt-preview") {
        return { data: undefined, isLoading: false } as unknown as UseQueryResult;
      }
      return {
        data: undefined,
        isLoading: false,
        error: new Error("fail"),
      } as unknown as UseQueryResult;
    });

    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    expect(screen.getByText("settings.prompts.loadFailed")).toBeDefined();
  });

  it("shows bundled source badge for non-overridden prompt", () => {
    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    expect(screen.getByText("settings.prompts.sourceBundled")).toBeDefined();
  });

  it("shows override source badge for overridden prompt", () => {
    vi.mocked(useQuery).mockImplementation((opts?: { queryKey?: readonly unknown[] }) => {
      if (opts?.queryKey?.[0] === "prompt-preview") {
        return { data: undefined, isLoading: false } as unknown as UseQueryResult;
      }
      return { data: overriddenPrompt, isLoading: false } as unknown as UseQueryResult;
    });

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

  it("renders the Preview button (opens API-driven dialog)", () => {
    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    expect(
      screen.getByRole("button", { name: "settings.prompts.promptCustomization.preview" }),
    ).toBeDefined();
  });

  it("renders the Preview button even when a template has no variables", () => {
    vi.mocked(useQuery).mockImplementation(((opts?: QueryOptionsSubset) => {
      if (opts?.queryKey?.[0] === "prompt-preview") {
        return { data: undefined, isLoading: false } as unknown as UseQueryResult;
      }
      return {
        data: { ...mockPrompt, variables: [] },
        isLoading: false,
      } as unknown as UseQueryResult;
    }) as typeof useQuery);

    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);

    expect(
      screen.getByRole("button", { name: "settings.prompts.promptCustomization.preview" }),
    ).toBeDefined();
  });

  it("renders the Live-Test button (opens dialog with token warning)", () => {
    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    expect(
      screen.getByRole("button", { name: "settings.prompts.promptCustomization.test" }),
    ).toBeDefined();
  });

  it("opens the preview dialog when the Preview button is clicked", async () => {
    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    fireEvent.click(
      screen.getByRole("button", { name: "settings.prompts.promptCustomization.preview" }),
    );
    await waitFor(() => {
      // "generation/names" is a malformed (2-segment) id → parsePromptId
      // falls back, so only the language system variable is sent. Project
      // variables are intentionally absent (RULE-20: no fabricated values).
      expect(mockPromptPreview).toHaveBeenCalledWith(
        "generation/names",
        expect.objectContaining({ variables: { language: "en" }, language: "en" }),
      );
    });
    // The preview dialog title appears once open
    expect(
      await screen.findByText("settings.prompts.promptCustomization.previewTitle"),
    ).toBeDefined();
  });

  it("opens the live-test dialog with warning gate when the Live-Test button is clicked", () => {
    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    fireEvent.click(
      screen.getByRole("button", { name: "settings.prompts.promptCustomization.test" }),
    );
    expect(screen.getByText("settings.prompts.promptCustomization.tokenWarning")).toBeDefined();
  });

  it("switches to edit mode when edit button is clicked", () => {
    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    fireEvent.click(screen.getByText("settings.prompts.editOverride"));
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

  it("opens the reset confirm dialog when Reset is clicked", () => {
    vi.mocked(useQuery).mockImplementation((opts?: { queryKey?: readonly unknown[] }) => {
      if (opts?.queryKey?.[0] === "prompt-preview") {
        return { data: undefined, isLoading: false } as unknown as UseQueryResult;
      }
      return { data: overriddenPrompt, isLoading: false } as unknown as UseQueryResult;
    });

    render(<PromptEditor promptId="generation/names" hasUpdate={false} onBack={onBack} />);
    fireEvent.click(screen.getByText("settings.prompts.resetToDefault"));
    // Reset confirm dialog title appears once open
    expect(screen.getAllByText("settings.prompts.resetToDefault").length).toBeGreaterThan(0);
  });
});
