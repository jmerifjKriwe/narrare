import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { PromptSettings } from "@/components/settings/PromptSettings";
import { createTestWrapper } from "@/lib/test-utils";

describe("PromptSettings", () => {
  it("should render prompt list grouped by category", async () => {
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <PromptSettings />
      </Wrapper>,
    );

    // Wait for prompts to load
    await waitFor(() => {
      expect(screen.getByText("Write / Extend")).toBeInTheDocument();
    });

    expect(screen.getByText("Write / Extend (DE)")).toBeInTheDocument();
    expect(screen.getByText("Analyse / Sentiment")).toBeInTheDocument();
    expect(screen.getByText("KB / Create")).toBeInTheDocument();
    expect(screen.getByText("Generation / Names")).toBeInTheDocument();
  });

  it("should show source indicators for overridden prompts", async () => {
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <PromptSettings />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText("Write / Extend")).toBeInTheDocument();
    });

    // "Analyse / Sentiment" has an override
    const sentimentRow = screen.getByText("Analyse / Sentiment").closest("button");
    expect(sentimentRow).toHaveTextContent("Override");
  });

  it("should show update badge for prompts with available updates", async () => {
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <PromptSettings />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText("Update available")).toBeInTheDocument();
    });
  });

  it("should filter prompts by category", async () => {
    const user = userEvent.setup();
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <PromptSettings />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText("Write / Extend")).toBeInTheDocument();
    });

    // Click on "writing" category filter
    const writingFilter = screen.getByRole("button", { name: "Writing" });
    await user.click(writingFilter);

    await waitFor(() => {
      expect(screen.getByText("Write / Extend")).toBeInTheDocument();
      // Other categories should not appear in the prompt list
      expect(screen.queryByText("KB / Create")).not.toBeInTheDocument();
    });
  });

  it("should navigate to editor when clicking a prompt", async () => {
    const user = userEvent.setup();
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <PromptSettings />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText("Write / Extend")).toBeInTheDocument();
    });

    // Click on a prompt
    await user.click(screen.getByText("Write / Extend"));

    // Should show editor with the prompt content
    await waitFor(() => {
      expect(screen.getByText("Base Content")).toBeInTheDocument();
    });
  });

  it("should show all categories filter button", async () => {
    const Wrapper = createTestWrapper();
    render(
      <Wrapper>
        <PromptSettings />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText("All Categories")).toBeInTheDocument();
    });
  });
});
