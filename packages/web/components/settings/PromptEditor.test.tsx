import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PromptEditor } from "@/components/settings/PromptEditor";
import { createTestWrapper } from "@/lib/test-utils";

describe("PromptEditor", () => {
  const defaultProps = {
    promptId: "write-extend-en",
    hasUpdate: false,
    onBack: vi.fn(),
  };

  it("should display prompt content in read-only mode", async () => {
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <PromptEditor {...defaultProps} />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText("Base Content")).toBeInTheDocument();
    });

    // Should show the prompt content
    const contentArea = screen.getByText("You are a helpful writing assistant. Base content here.");
    expect(contentArea).toBeInTheDocument();
  });

  it("should show edit override button", async () => {
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <PromptEditor {...defaultProps} />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText("Edit as Override")).toBeInTheDocument();
    });
  });

  it("should enter edit mode when clicking edit button", async () => {
    const user = userEvent.setup();
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <PromptEditor {...defaultProps} />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText("Edit as Override")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Edit as Override"));

    // Should show a textarea
    await waitFor(() => {
      expect(screen.getByLabelText("Prompt Content")).toBeInTheDocument();
    });

    // Should show save and cancel buttons
    expect(screen.getByText("Save Override")).toBeInTheDocument();
  });

  it("should show variables sidebar", async () => {
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <PromptEditor {...defaultProps} />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText("Variables")).toBeInTheDocument();
    });

    // Should show variable placeholders
    expect(screen.getByText("{{text}}")).toBeInTheDocument();
    expect(screen.getByText("{{language}}")).toBeInTheDocument();
    expect(screen.getByText("{{context}}")).toBeInTheDocument();
  });

  it("should call save mutation when saving", async () => {
    const user = userEvent.setup();
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <PromptEditor {...defaultProps} />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText("Edit as Override")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Edit as Override"));

    await waitFor(() => {
      expect(screen.getByLabelText("Prompt Content")).toBeInTheDocument();
    });

    // Click save
    await user.click(screen.getByText("Save Override"));

    // Should show success message after save
    await waitFor(() => {
      expect(screen.getByText("Override saved successfully.")).toBeInTheDocument();
    });
  });

  it("should show reset button for overridden prompts", async () => {
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <PromptEditor promptId="analyse-sentiment-en" hasUpdate={false} onBack={vi.fn()} />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText("Reset to Default")).toBeInTheDocument();
    });

    // Reset button should be enabled for overridden prompts
    const resetButton = screen.getByText("Reset to Default").closest("button");
    expect(resetButton).toBeEnabled();
  });

  it("should disable reset button for non-overridden prompts", async () => {
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <PromptEditor {...defaultProps} />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText("Reset to Default")).toBeInTheDocument();
    });

    const resetButton = screen.getByText("Reset to Default").closest("button");
    expect(resetButton).toBeDisabled();
  });

  it("should show update badge when hasUpdate is true", async () => {
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <PromptEditor promptId="analyse-sentiment-en" hasUpdate={true} onBack={vi.fn()} />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText("Update available")).toBeInTheDocument();
    });
  });
});
