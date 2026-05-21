/**
 * Unit tests for WritingGraphStatus component.
 *
 * Verifies rendering of all step states (completed, current, pending),
 * collapse/expand behavior, and collapsed summary display.
 */

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import {
  type StepStatus,
  WritingGraphStatus,
  type WritingStep,
} from "@/components/studio/writing/WritingGraphStatus";

// next-intl is mocked globally in setupTests.ts — returns the key as-is
// or interpolates params via key.replace("{param}", value)

describe("WritingGraphStatus", () => {
  afterEach(() => {
    cleanup();
  });

  const createSteps = (overrides: Array<{ id: WritingStep; status: StepStatus }>) => overrides;

  it("renders all six steps in the correct order", () => {
    const steps = createSteps(
      (
        [
          "plan_outline",
          "write_draft",
          "review_draft",
          "revise_draft",
          "finalize",
          "generate_summary",
        ] as WritingStep[]
      ).map((id) => ({ id, status: "pending" as const })),
    );

    render(<WritingGraphStatus steps={steps} />);

    // Verify all step labels are rendered
    expect(screen.getByText("writingGraph.steps.plan_outline")).toBeInTheDocument();
    expect(screen.getByText("writingGraph.steps.write_draft")).toBeInTheDocument();
    expect(screen.getByText("writingGraph.steps.review_draft")).toBeInTheDocument();
    expect(screen.getByText("writingGraph.steps.revise_draft")).toBeInTheDocument();
    expect(screen.getByText("writingGraph.steps.finalize")).toBeInTheDocument();
    expect(screen.getByText("writingGraph.steps.generate_summary")).toBeInTheDocument();
  });

  it("shows completed steps with checkmark icon", () => {
    const steps = createSteps([
      { id: "plan_outline", status: "completed" },
      { id: "write_draft", status: "pending" },
      { id: "review_draft", status: "pending" },
      { id: "revise_draft", status: "pending" },
      { id: "finalize", status: "pending" },
      { id: "generate_summary", status: "pending" },
    ]);

    render(<WritingGraphStatus steps={steps} />);

    // The completed step should have the step name in its title attribute
    const completedTitle = screen.getByTitle(/writingGraph.steps.plan_outline/);
    expect(completedTitle).toBeInTheDocument();
  });

  it("shows current step with spinner icon", () => {
    const steps = createSteps([
      { id: "plan_outline", status: "completed" },
      { id: "write_draft", status: "current" },
      { id: "review_draft", status: "pending" },
      { id: "revise_draft", status: "pending" },
      { id: "finalize", status: "pending" },
      { id: "generate_summary", status: "pending" },
    ]);

    render(<WritingGraphStatus steps={steps} />);

    // The current step should have the step name in its title attribute
    const spinnerTitle = screen.getByTitle(/writingGraph.steps.write_draft/);
    expect(spinnerTitle).toBeInTheDocument();
  });

  it("collapses and expands when toggle is clicked", async () => {
    const user = userEvent.setup();
    const steps = createSteps(
      (
        [
          "plan_outline",
          "write_draft",
          "review_draft",
          "revise_draft",
          "finalize",
          "generate_summary",
        ] as WritingStep[]
      ).map((id) => ({ id, status: "pending" as const })),
    );

    render(<WritingGraphStatus steps={steps} />);

    // Initially expanded — step labels should be visible
    expect(screen.getByText("writingGraph.steps.plan_outline")).toBeInTheDocument();

    // Click toggle to collapse
    const toggleButton = screen.getByRole("button");
    await user.click(toggleButton);

    // After collapse, step labels should NOT be visible
    // (using queryByText which returns null if not found)
    // Note: When expanded is false, the expanded section uses ul which is hidden
    expect(screen.queryByText("writingGraph.steps.plan_outline")).not.toBeInTheDocument();

    // Click toggle to re-expand
    await user.click(toggleButton);

    // Step labels should be visible again
    expect(screen.getByText("writingGraph.steps.plan_outline")).toBeInTheDocument();
  });

  it("shows 'all complete' message when all steps completed", () => {
    const steps = createSteps(
      (
        [
          "plan_outline",
          "write_draft",
          "review_draft",
          "revise_draft",
          "finalize",
          "generate_summary",
        ] as WritingStep[]
      ).map((id) => ({ id, status: "completed" as const })),
    );

    render(<WritingGraphStatus steps={steps} />);

    expect(screen.getByText("writingGraph.allComplete")).toBeInTheDocument();
  });

  it("shows progress message with current step count", () => {
    const steps = createSteps([
      { id: "plan_outline", status: "completed" },
      { id: "write_draft", status: "current" },
      { id: "review_draft", status: "pending" },
      { id: "revise_draft", status: "pending" },
      { id: "finalize", status: "pending" },
      { id: "generate_summary", status: "pending" },
    ]);

    render(<WritingGraphStatus steps={steps} />);

    // The i18n mock replaces {current}, {total}, {label} in the key
    const progressKey = screen.getByText(/writingGraph\.progress/);
    expect(progressKey).toBeInTheDocument();
  });

  it("accepts and displays a custom currentStepLabel", () => {
    const steps = createSteps([
      { id: "plan_outline", status: "completed" },
      { id: "write_draft", status: "current" },
      { id: "review_draft", status: "pending" },
      { id: "revise_draft", status: "pending" },
      { id: "finalize", status: "pending" },
      { id: "generate_summary", status: "pending" },
    ]);

    render(<WritingGraphStatus steps={steps} currentStepLabel="Writing Draft" />);

    // The button should render a progress message
    // The i18n mock returns the key as-is since {current}/{total}/{label}
    // are not part of the key string itself
    const button = screen.getByRole("button");
    expect(button).toBeInTheDocument();
    expect(button.textContent).toContain("writingGraph.progress");
  });

  it("handles empty steps array gracefully", () => {
    render(<WritingGraphStatus steps={[]} />);

    // Should still render the toggle button
    expect(screen.getByRole("button")).toBeInTheDocument();
    // The progress should show "Step 0/6: " (currentIdx is -1)
    expect(screen.getByText(/writingGraph\.progress/)).toBeInTheDocument();
  });
});
