import {
  type UseMutationResult,
  type UseQueryResult,
  useMutation,
  useQuery,
} from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { KBTemplateEditor } from "@/components/studio/settings/KBTemplateEditor";

// --- Mock data ---

const mockTemplateDetail = {
  content: "fields:\n  - name: test\n    type: text",
  schema_version: "1.0",
  is_overridden: true,
  based_on_version: "0.9",
};

const defaultTemplateDetail = {
  ...mockTemplateDetail,
  is_overridden: false,
};

const defaultProps = {
  novelId: "novel-1",
  entityType: "character",
  hasUpdate: false,
  onBack: vi.fn(),
};

// --- Mocks ---

vi.mock("@tanstack/react-query", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-query")>()),
  useQuery: vi.fn(() => ({
    data: mockTemplateDetail,
    isLoading: false,
  })),
  useMutation: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => ({ invalidateQueries: vi.fn() })),
}));

// --- Tests ---

describe("KBTemplateEditor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useQuery).mockReturnValue({
      data: mockTemplateDetail,
      isLoading: false,
    } as unknown as UseQueryResult);
    vi.mocked(useMutation).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as UseMutationResult);
  });

  it("renders YAML editor with template content", () => {
    render(<KBTemplateEditor {...defaultProps} />);

    const textarea = screen.getByLabelText("Template content editor");
    expect(textarea).toBeDefined();
    expect((textarea as HTMLTextAreaElement).value).toBe(mockTemplateDetail.content);
  });

  it("save button triggers mutation", async () => {
    const user = userEvent.setup();
    const mockMutate = vi.fn();
    vi.mocked(useMutation).mockReturnValue({
      mutate: mockMutate,
      isPending: false,
    } as unknown as UseMutationResult);

    render(<KBTemplateEditor {...defaultProps} />);

    await user.click(screen.getByText("kb.save"));
    expect(mockMutate).toHaveBeenCalledOnce();
  });

  it("reset button resets to default", async () => {
    const user = userEvent.setup();
    const saveMutate = vi.fn();
    const resetMutate = vi.fn();
    vi.spyOn(window, "confirm").mockReturnValue(true);

    // useMutation is called twice: save (call 1), reset (call 2)
    let callIdx = 0;
    vi.mocked(useMutation).mockImplementation(() => {
      callIdx++;
      const mutate = callIdx === 1 ? saveMutate : resetMutate;
      return {
        mutate,
        isPending: false,
      } as unknown as UseMutationResult;
    });

    render(<KBTemplateEditor {...defaultProps} />);

    await user.click(screen.getByText("kb.resetToDefault"));
    expect(resetMutate).toHaveBeenCalledOnce();

    vi.restoreAllMocks();
  });

  it("shows custom badge when template is overridden", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: mockTemplateDetail,
      isLoading: false,
    } as unknown as UseQueryResult);

    render(<KBTemplateEditor {...defaultProps} />);
    // Badge text is inside a paragraph like "kb.templateVersion · kb.custom"
    const paragraph = screen.getByText(/kb\.custom/);
    expect(paragraph).toBeDefined();
    expect(paragraph.textContent).toContain("kb.custom");
  });

  it("shows default badge when template is not overridden", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: defaultTemplateDetail,
      isLoading: false,
    } as unknown as UseQueryResult);

    render(<KBTemplateEditor {...defaultProps} />);
    // Badge text is inside a paragraph like "kb.templateVersion · kb.defaultLabel"
    const paragraph = screen.getByText(/kb\.defaultLabel/);
    expect(paragraph).toBeDefined();
    expect(paragraph.textContent).toContain("kb.defaultLabel");
  });

  it("shows loading spinner while fetching template", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: undefined,
      isLoading: true,
    } as unknown as UseQueryResult);

    const { container } = render(<KBTemplateEditor {...defaultProps} />);
    const spinner = container.querySelector(".animate-spin");
    expect(spinner).toBeDefined();
  });

  it("shows error alert when query fails", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("Network failure"),
    } as unknown as UseQueryResult);

    render(<KBTemplateEditor {...defaultProps} />);

    expect(screen.getByRole("alert")).toBeDefined();
    expect(screen.getByText("kb.failedToLoadTemplate")).toBeDefined();
  });

  it("shows back button in error state", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("fail"),
    } as unknown as UseQueryResult);

    render(<KBTemplateEditor {...defaultProps} />);
    expect(screen.getByText("kb.back")).toBeDefined();
  });

  it("back button calls onBack", async () => {
    const user = userEvent.setup();
    const onBack = vi.fn();

    render(<KBTemplateEditor {...defaultProps} onBack={onBack} />);

    const backButton = screen.getByLabelText("Back to templates list");
    await user.click(backButton);
    expect(onBack).toHaveBeenCalledOnce();
  });

  it("reset button is disabled when not overridden", () => {
    vi.mocked(useQuery).mockReturnValue({
      data: defaultTemplateDetail,
      isLoading: false,
    } as unknown as UseQueryResult);

    render(<KBTemplateEditor {...defaultProps} />);

    const resetButton = screen.getByText("kb.resetToDefault");
    expect((resetButton as HTMLButtonElement).disabled).toBe(true);
  });
});
