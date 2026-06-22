/**
 * Tests for PromptLiveTestDialog.
 *
 * The dialog is render-only: it receives ``acknowledged``, ``output``,
 * ``streaming``, ``error`` from the parent (which drives useAIOperation
 * via usePromptEditorState). The dialog itself owns only the local
 * "warning acknowledged" transition and the close affordance.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PromptLiveTestDialog } from "@/components/studio/settings/PromptLiveTestDialog";

describe("PromptLiveTestDialog", () => {
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    promptId: "writing/en/new_chapter",
    acknowledged: false,
    output: "",
    streaming: false,
    error: null as string | null,
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
  };

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("does not render when closed", () => {
    const { container } = render(<PromptLiveTestDialog {...defaultProps} open={false} />);
    expect(container.firstChild).toBeNull();
  });

  it("shows token/privacy warning gate before acknowledgement", () => {
    render(<PromptLiveTestDialog {...defaultProps} acknowledged={false} />);
    expect(
      screen.getByText("settings.prompts.promptCustomization.tokenWarning"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: "settings.prompts.promptCustomization.confirmRun",
      }),
    ).toBeInTheDocument();
  });

  it("calls onConfirm when user acknowledges the warning", () => {
    const onConfirm = vi.fn();
    render(<PromptLiveTestDialog {...defaultProps} acknowledged={false} onConfirm={onConfirm} />);
    fireEvent.click(
      screen.getByRole("button", {
        name: "settings.prompts.promptCustomization.confirmRun",
      }),
    );
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("renders streamed output once acknowledged", () => {
    render(
      <PromptLiveTestDialog
        {...defaultProps}
        acknowledged={true}
        output="Once upon a time"
        streaming={true}
      />,
    );
    expect(screen.getByText(/Once upon a time/)).toBeInTheDocument();
  });

  it("renders empty-state placeholder when acknowledged but no output yet", () => {
    render(
      <PromptLiveTestDialog {...defaultProps} acknowledged={true} output="" streaming={false} />,
    );
    expect(screen.getByText("settings.prompts.promptCustomization.testEmpty")).toBeInTheDocument();
  });

  it("calls onCancel when the stop button is clicked during streaming", () => {
    const onCancel = vi.fn();
    render(
      <PromptLiveTestDialog
        {...defaultProps}
        acknowledged={true}
        output="abc"
        streaming={true}
        onCancel={onCancel}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "aiActions.stop" }));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("renders error message when error is provided", () => {
    render(
      <PromptLiveTestDialog
        {...defaultProps}
        acknowledged={true}
        output=""
        streaming={false}
        error="no_active_provider"
      />,
    );
    // Error message text comes from the i18n key passed via the error prop.
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
