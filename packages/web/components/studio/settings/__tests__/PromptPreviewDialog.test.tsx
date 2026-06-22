import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PromptPreviewDialog } from "@/components/studio/settings/PromptPreviewDialog";
import type { PromptPreview } from "@/types";

const preview: PromptPreview = {
  system_prompt: "Resolved system prompt body",
  user_prompt: "Resolved user message",
  first_message: "Resolved first assistant message",
  cascade_source: "bundled",
  variables: [],
  diagnostics: [
    {
      kind: "missing_variable",
      variable_name: "project_title",
      message: "missing_required_variable:project_title",
    },
  ],
};

describe("PromptPreviewDialog", () => {
  it("does not render when closed", () => {
    const { container } = render(
      <PromptPreviewDialog
        open={false}
        onOpenChange={() => {}}
        promptId="writing/en/new_chapter"
        preview={preview}
        loading={false}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("shows the resolved system prompt and cascade source when open", () => {
    render(
      <PromptPreviewDialog
        open={true}
        onOpenChange={() => {}}
        promptId="writing/en/new_chapter"
        preview={preview}
        loading={false}
      />,
    );
    expect(screen.getByText(/Resolved system prompt body/)).toBeInTheDocument();
    // Cascade source label appears in the header
    expect(screen.getByText("bundled")).toBeInTheDocument();
  });

  it("shows diagnostics when present", () => {
    render(
      <PromptPreviewDialog
        open={true}
        onOpenChange={() => {}}
        promptId="writing/en/new_chapter"
        preview={preview}
        loading={false}
      />,
    );
    // The diagnostic line includes the kind and the variable name
    expect(screen.getByText(/missing_variable/)).toBeInTheDocument();
    expect(screen.getByText(/project_title/)).toBeInTheDocument();
  });

  it("shows the resolved user prompt and first message when present", () => {
    render(
      <PromptPreviewDialog
        open={true}
        onOpenChange={() => {}}
        promptId="writing/en/new_chapter"
        preview={preview}
        loading={false}
      />,
    );

    expect(screen.getByText(/Resolved user message/)).toBeInTheDocument();
    expect(screen.getByText(/Resolved first assistant message/)).toBeInTheDocument();
  });

  it("shows loading state when preview is loading", () => {
    render(
      <PromptPreviewDialog
        open={true}
        onOpenChange={() => {}}
        promptId="writing/en/new_chapter"
        preview={null}
        loading={true}
      />,
    );
    // Loading affordance uses role=status
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.getByText("settings.prompts.promptCustomization.loading")).toBeInTheDocument();
  });

  it("calls onOpenChange(false) when the close button is clicked", () => {
    const onOpenChange = vi.fn();
    render(
      <PromptPreviewDialog
        open={true}
        onOpenChange={onOpenChange}
        promptId="writing/en/new_chapter"
        preview={preview}
        loading={false}
      />,
    );
    screen.getByText("settings.prompts.promptCustomization.close").click();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
