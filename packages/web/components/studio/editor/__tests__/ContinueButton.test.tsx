/**
 * ContinueButton tests — presentational contract (B08).
 *
 * The button is ops-props driven: the stream owner (EditorView, Task 11)
 * passes `onExtend`/`onStop`/`isStreaming`; the component owns only the
 * length-dropdown state. Hook-level streaming behaviour is covered by
 * `useContinueStream.test.tsx`.
 *
 * @module ContinueButton.test
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ContinueButton } from "@/components/studio/editor/ContinueButton";
import type { ExtendLength } from "@/lib/api/generation";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function renderButton(props: { isStreaming?: boolean } = {}) {
  const onExtend = vi.fn<(length: ExtendLength) => void>();
  const onStop = vi.fn<() => void>();
  render(
    <ContinueButton isStreaming={props.isStreaming ?? false} onExtend={onExtend} onStop={onStop} />,
  );
  return { onExtend, onStop };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ContinueButton", () => {
  it("calls onExtend('medium') on main-button click by default", async () => {
    const user = userEvent.setup();
    const { onExtend } = renderButton();

    await user.click(screen.getByLabelText("annotation.continueWriting"));

    expect(onExtend).toHaveBeenCalledOnce();
    expect(onExtend).toHaveBeenCalledWith("medium");
    expect(onExtend.mock.calls[0][0]).toBe("medium");
  });

  it("does not show the dropdown initially", () => {
    renderButton();

    expect(screen.queryByText("annotation.length.short")).toBeNull();
    expect(screen.queryByText("annotation.length.medium")).toBeNull();
    expect(screen.queryByText("annotation.length.long")).toBeNull();
  });

  it("renders the length dropdown on chevron click", async () => {
    const user = userEvent.setup();
    renderButton();

    await user.click(screen.getByLabelText("annotation.selectLength"));

    expect(screen.getByText("annotation.length.short")).toBeInTheDocument();
    expect(screen.getByText("annotation.length.medium")).toBeInTheDocument();
    expect(screen.getByText("annotation.length.long")).toBeInTheDocument();
  });

  it("uses the length picked from the dropdown for the next extend", async () => {
    const user = userEvent.setup();
    const { onExtend } = renderButton();

    // Open dropdown, pick "short"
    await user.click(screen.getByLabelText("annotation.selectLength"));
    await user.click(screen.getByText("annotation.length.short"));

    // Dropdown closes after selection
    expect(screen.queryByText("annotation.length.short")).toBeNull();

    // Next main-button click extends with the picked length
    await user.click(screen.getByLabelText("annotation.continueWriting"));

    expect(onExtend).toHaveBeenCalledOnce();
    expect(onExtend.mock.calls[0][0]).toBe("short");
  });

  it("closes the dropdown on outside click", async () => {
    const user = userEvent.setup();
    renderButton();

    await user.click(screen.getByLabelText("annotation.selectLength"));
    expect(screen.getByText("annotation.length.short")).toBeInTheDocument();

    await user.click(document.body);

    expect(screen.queryByText("annotation.length.short")).not.toBeInTheDocument();
  });

  it("renders the stop control while streaming and calls onStop on click", async () => {
    const user = userEvent.setup();
    const { onStop } = renderButton({ isStreaming: true });

    expect(screen.getByText("aiActions.stop")).toBeInTheDocument();
    // Chevron dropdown is hidden while streaming
    expect(screen.queryByLabelText("annotation.selectLength")).toBeNull();

    await user.click(screen.getByLabelText("annotation.continueWriting"));

    expect(onStop).toHaveBeenCalledOnce();
  });

  it("does not call onExtend while streaming", async () => {
    const user = userEvent.setup();
    const { onExtend } = renderButton({ isStreaming: true });

    await user.click(screen.getByLabelText("annotation.continueWriting"));

    expect(onExtend).not.toHaveBeenCalled();
  });
});
