/**
 * Tests for PromptHistoryStatus (CR-AUFG-07-19).
 *
 * Presentational loading / error / empty block for the revision list. No data,
 * so no provider is required. The global next-intl mock returns keys verbatim.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PromptHistoryStatus } from "@/components/studio/settings/prompt-history/PromptHistoryStatus";

describe("PromptHistoryStatus", () => {
  it("renders the loading indicator for the loading status", () => {
    render(<PromptHistoryStatus status="loading" />);
    expect(screen.getByText("settings.prompts.promptHistory.loading")).toBeTruthy();
    expect(screen.getByRole("status")).toBeTruthy();
  });

  it("renders the error alert with a retry button that calls onRetry", () => {
    const onRetry = vi.fn();
    render(<PromptHistoryStatus status="error" onRetry={onRetry} />);
    expect(screen.getByRole("alert").textContent).toContain(
      "settings.prompts.promptHistory.loadFailed",
    );
    fireEvent.click(screen.getByRole("button", { name: "settings.prompts.promptHistory.retry" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("renders the empty state copy for the empty status", () => {
    render(<PromptHistoryStatus status="empty" />);
    expect(screen.getByText("settings.prompts.promptHistory.empty")).toBeTruthy();
    expect(screen.getByText("settings.prompts.promptHistory.emptyHint")).toBeTruthy();
  });
});
